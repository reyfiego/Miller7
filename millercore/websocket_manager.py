import os
import asyncio
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import Groq
from .burbujas_texto import dividir_burbujas_aleatorio
from .corazon import SYSTEM_ROLE, get_random_greeting
from millercore.db.models import save_message, get_session_messages, crear_sesion
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

groq_client = Groq(api_key=API_KEY)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.burbujas_enviadas: dict[str, set[str]] = {}
        self.sessions_context: dict[str, list] = {}

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
                if "reply" in message and isinstance(message["reply"], list):
                    message["reply"] = [str(b) for b in message["reply"]]
                    self.burbujas_enviadas[session_id].update(message["reply"])
                await websocket.send_json(message)
            except Exception as e:
                print(f"[{session_id}] Error enviando mensaje:", repr(e))

manager = ConnectionManager()

async def enviar_burbujas_con_delay(burbujas, session_id):
    for b in burbujas:
        if b not in manager.burbujas_enviadas[session_id]:
            await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
            await asyncio.sleep(random.uniform(1, 2))

@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    if not session_id or session_id == "guest":
        session_id = crear_sesion(user_id=None, context=[])
        print(f"Nuevo session_id invitado: {session_id}")

    await manager.connect(websocket, session_id)
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

    try:
        history = get_session_messages(session_id)
        manager.sessions_context[session_id] = history
        await manager.send_personal_message({
            "reply": history,
            "session_id": session_id
        }, session_id)

        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                await manager.send_personal_message({"reply": ["Por favor, dime algo."], "session_id": session_id}, session_id)
                continue

            save_message(session_id, "user", user_text)
            manager.sessions_context[session_id].append({
                "role": "user",
                "content": user_text,
                "created_at": datetime.utcnow()
            })

            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + manager.sessions_context[session_id]

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=250,
                    temperature=0.9
                )
                reply_text = response.choices[0].message.content.strip()
                save_message(session_id, "assistant", reply_text)
                manager.sessions_context[session_id].append({
                    "role": "assistant",
                    "content": reply_text,
                    "created_at": datetime.utcnow()
                })
                burbujas = dividir_burbujas_aleatorio(reply_text)
                await enviar_burbujas_con_delay(burbujas, session_id)
            except Exception as e:
                print(f"[{session_id}] Error chat:", repr(e))
                await enviar_burbujas_con_delay(dividir_burbujas_aleatorio("El silencio también tiene cosas que decir."), session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)
