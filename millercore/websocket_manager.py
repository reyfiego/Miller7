import os
import asyncio
import random
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import Groq
from dotenv import load_dotenv

from .burbujas_texto import dividir_burbujas_aleatorio
from .corazon import SYSTEM_ROLE, get_random_greeting
from .db.models import save_message
from .db.supabase_client import supabase

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

groq_client = Groq(api_key=API_KEY)
router = APIRouter()

# UUID fijo para invitados (crear en tabla users con este id)
GUEST_USER_ID = "00000000-0000-0000-0000-000000000000"

# ...

try:
    uuid.UUID(session_id)
    is_logged_in = True
    user_id = session_id  # usuarios logeados
except ValueError:
    # invitado → usar guest fijo
    session_id = str(uuid.uuid4())  # nueva sesión
    user_id = GUEST_USER_ID
    is_logged_in = False



# ------------------------------
# Manejo de conexiones y sesiones
# ------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.burbujas_enviadas: dict[str, set[str]] = {}
        self.sessions_context: dict[str, list] = {}  # memoria corta por session_id

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.burbujas_enviadas[session_id] = set()
        self.sessions_context.setdefault(session_id, [])
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.burbujas_enviadas.pop(session_id, None)
        self.sessions_context.pop(session_id, None)
        print(f"[{session_id}] Desconectado y memoria liberada")

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                if "reply" in message:
                    message["reply"] = [f"[ws] {b}" for b in message["reply"]]
                    self.burbujas_enviadas[session_id].update(message["reply"])
                await websocket.send_json(message)
            except Exception as e:
                print(f"[{session_id}] Error enviando mensaje:", repr(e))


manager = ConnectionManager()


# ------------------------------
# Funciones auxiliares
# ------------------------------
async def enviar_burbujas_con_delay(burbujas, session_id):
    for b in burbujas:
        if f"[ws] {b}" not in manager.burbujas_enviadas[session_id]:
            await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
            await asyncio.sleep(random.uniform(1, 3))


def ensure_session_exists(session_id: str, user_id=None):
    existing = supabase.table("sessions").select("id").eq("id", session_id).execute()
    if not existing.data:
        data = {
            "id": session_id,
            "context": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        if user_id:
            data["user_id"] = user_id
        supabase.table("sessions").insert(data).execute()



# ------------------------------
# WebSocket
# ------------------------------
@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # ------------------------
    # Invitados → UUID nuevo siempre
    # ------------------------
    is_logged_in = False
    user_id = None

    try:
        uuid.UUID(session_id)
        # Si es UUID válido → asumimos logeado
        is_logged_in = True
        user_id = session_id
    except ValueError:
        # Invitado: generamos nuevo UUID para cada refresh
        new_uuid = str(uuid.uuid4())
        print(f"[guest] nuevo session_id generado: {new_uuid}")
        session_id = new_uuid
        user_id = GUEST_USER_ID  # se asigna al invitado fijo

    await manager.connect(websocket, session_id)

    # Crear sesión en DB
    ensure_session_exists(session_id, user_id)

    # Recuperar contexto de DB
    db_session = supabase.table("sessions").select("context").eq("id", session_id).execute()
    if db_session.data and isinstance(db_session.data[0].get("context"), list):
        manager.sessions_context[session_id] = db_session.data[0]["context"]
    else:
        manager.sessions_context[session_id] = []

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                await manager.send_personal_message(
                    {"reply": ["Por favor, dime algo."], "session_id": session_id}, session_id
                )
                continue

            # Guardar mensaje user en memoria
            user_entry = {"role": "user", "content": user_text, "created_at": datetime.utcnow().isoformat()}
            manager.sessions_context[session_id].append(user_entry)

            # Guardar siempre (invitados y logeados)
            supabase.table("messages").insert({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "sender": "user",
                "content": user_text,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            from .db.models import guardar_sesion
            guardar_sesion(session_id, manager.sessions_context[session_id])

            # Historial para IA
            messages_for_groq = [{"role": "system", "content": SYSTEM_ROLE}] + [
                {"role": m["role"], "content": m["content"]} for m in manager.sessions_context[session_id]
            ]

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=250,
                    temperature=0.9,
                    top_p=0.95,
                    frequency_penalty=0.8,
                    presence_penalty=0.9
                )
                reply_text = response.choices[0].message.content.strip()

                # Guardar respuesta asistente en memoria
                assistant_entry = {"role": "assistant", "content": reply_text, "created_at": datetime.utcnow().isoformat()}
                manager.sessions_context[session_id].append(assistant_entry)

                # Guardar en DB
                supabase.table("messages").insert({
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "sender": "assistant",
                    "content": reply_text,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()

                guardar_sesion(session_id, manager.sessions_context[session_id])

                # Enviar burbujas
                burbujas = dividir_burbujas_aleatorio(reply_text)
                await enviar_burbujas_con_delay(burbujas, session_id)

            except Exception as e:
                print(f"[{session_id}] Error en chat:", repr(e))
                fallback_msg = "El silencio también tiene cosas que decir."
                manager.sessions_context[session_id].append({
                    "role": "assistant",
                    "content": fallback_msg,
                    "created_at": datetime.utcnow().isoformat()
                })
                guardar_sesion(session_id, manager.sessions_context[session_id])
                burbujas = dividir_burbujas_aleatorio(fallback_msg)
                await enviar_burbujas_con_delay(burbujas, session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)
