import os
import asyncio
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import Groq
from .burbujas_texto import dividir_burbujas_aleatorio
from .corazon import SYSTEM_ROLE, get_random_greeting
from .db.models import guardar_sesion, crear_sesion, obtener_sesiones
from .db.supabase_client import supabase
from dotenv import load_dotenv
import uuid
from datetime import datetime

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
        if session_id not in self.sessions_context:
            self.sessions_context[session_id] = []
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.burbujas_enviadas.pop(session_id, None)
        print(f"[{session_id}] Desconectado")

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
        if b not in manager.burbujas_enviadas[session_id]:
            await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
            await asyncio.sleep(random.uniform(1, 3))  # delay aleatorio


# Guardado temporal en memoria corta
def save_message(session_id, role, content):
    manager.sessions_context.setdefault(session_id, []).append({"role": role, "content": content})


# Recuperar mensajes de la DB en orden correcto
def get_session_messages_from_db(session_id):
    res = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", "asc").execute()
    if res.data:
        return [{"role": m["sender"], "content": m["content"]} for m in res.data]
    return []


# ------------------------------
# WebSocket endpoint
# ------------------------------
@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

    try:
        # Recuperar historial de la DB y cargar memoria corta
        history = get_session_messages_from_db(session_id)
        manager.sessions_context[session_id] = history

        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            user_id = data.get("user_id")  # si hay sesión de usuario

            if not user_text:
                await manager.send_personal_message({"reply": ["Por favor, dime algo."], "session_id": session_id}, session_id)
                continue

            # Guardar sesión en DB si es usuario registrado
            if user_id:
                try:
                    crear_sesion(user_id=user_id, context="chat")  # crea o ignora si ya existe
                except Exception:
                    pass  # sesión ya creada, ignorar
            else:
                # Sesión anónima
                guardar_sesion(session_id=session_id, context="chat")

            # Guardar mensaje del usuario
            save_message(session_id, "user", user_text)
            supabase.table("messages").insert({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "sender": "user",
                "content": user_text,
                "created_at": datetime.now().isoformat()
            }).execute()

            # Preparar historial para IA
            history = manager.sessions_context[session_id]
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + history

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
                    "created_at": datetime.now().isoformat()
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
