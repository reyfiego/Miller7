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
        self.sessions_context[session_id] = []  # siempre limpiar al conectar
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.burbujas_enviadas.pop(session_id, None)
        self.sessions_context.pop(session_id, None)  # limpiar memoria corta
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
    """Asegura que la sesión exista en DB"""
    existing = supabase.table("sessions").select("id").eq("id", session_id).execute()
    if not existing.data:
        supabase.table("sessions").insert({
            "id": session_id,
            "user_id": user_id,
            "context": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()


def get_session_messages_from_db(session_id):
    res = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at").execute()
    if res.data:
        return [{"role": "user" if m["sender"] == "user" else "assistant", "content": m["content"]} for m in res.data]
    return []


# ------------------------------
# WebSocket endpoint
# ------------------------------
@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Invitado: siempre sesión nueva
    if not session_id or session_id == "guest":
        session_id = str(uuid.uuid4())
        user_id = None
    else:
        # Usuario logueado: usar session_id y asociar user_id si se requiere
        user_id = None  # <-- aquí puedes pasar el user_id real
        ensure_session_exists(session_id, user_id=user_id)

    await manager.connect(websocket, session_id)

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

    # Cargar historial solo de esta sesión
    manager.sessions_context[session_id] = get_session_messages_from_db(session_id)

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                await manager.send_personal_message({"reply": ["Por favor, dime algo."], "session_id": session_id}, session_id)
                continue

            # Guardar mensaje del usuario
            save_message(session_id, "user", user_text)
            supabase.table("messages").insert({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "sender": "user",
                "content": user_text,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            # Preparar historial para IA (solo de esta sesión)
            history = manager.sessions_context[session_id]
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + history + [{"role": "user", "content": user_text}]

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

                # Guardar respuesta de Miller
                save_message(session_id, "assistant", reply_text)
                supabase.table("messages").insert({
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "sender": "assistant",
                    "content": reply_text,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()

                # Enviar burbujas
                burbujas = dividir_burbujas_aleatorio(reply_text)
                await enviar_burbujas_con_delay(burbujas, session_id)

            except Exception as e:
                print(f"[{session_id}] Error en chat:", repr(e))
                fallback_msg = "El silencio también tiene cosas que decir."
                burbujas = dividir_burbujas_aleatorio(fallback_msg)
                await enviar_burbujas_con_delay(burbujas, session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)
