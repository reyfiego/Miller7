import os
import asyncio
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import Groq
from .burbujas_texto import dividir_burbujas_aleatorio
from .corazon import SYSTEM_ROLE, get_random_greeting
from .db.models import crear_usuario, autenticar_usuario, crear_sesion, guardar_sesion, save_message, get_session_messages
from dotenv import load_dotenv

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
        self.sessions_context: dict[str, list] = {}  # memoria corta en RAM

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        if session_id not in self.sessions_context:
            self.sessions_context[session_id] = []
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        print(f"[{session_id}] Desconectado")

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"[{session_id}] Error enviando mensaje:", repr(e))


manager = ConnectionManager()


async def enviar_burbujas_con_delay(burbujas, session_id):
    for b in burbujas:
        await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
        await asyncio.sleep(random.uniform(1, 3))


@router.websocket("/ws/chat/{user_id_or_anonymous}")
async def websocket_endpoint(websocket: WebSocket, user_id_or_anonymous: str):
    """
    user_id_or_anonymous: puede ser user_id si está logueado o "anon" si es anónimo
    """
    # Crear nueva sesión
    user_id = None if user_id_or_anonymous == "anon" else user_id_or_anonymous
    _, session_id = crear_sesion(user_id=user_id)

    await manager.connect(websocket, session_id)

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                await manager.send_personal_message({"reply": ["Por favor, dime algo."], "session_id": session_id}, session_id)
                continue

            # Guardar mensaje del usuario en DB y RAM
            save_message(session_id, "user", user_text)
            manager.sessions_context[session_id].append({"role": "user", "content": user_text})

            # Preparar prompt
            history = manager.sessions_context[session_id]
            messages_for_groq = [{"role": "system", "content": SYSTEM_ROLE}] + history

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
                manager.sessions_context[session_id].append({"role": "assistant", "content": reply_text})

                # Enviar en burbujas
                burbujas = dividir_burbujas_aleatorio(reply_text)
                await enviar_burbujas_con_delay(burbujas, session_id)

                # Actualizar contexto en DB
                guardar_sesion(session_id, manager.sessions_context[session_id])

            except Exception as e:
                print(f"[{session_id}] Error en chat:", repr(e))
                fallback_msg = "El silencio también tiene cosas que decir."
                burbujas = dividir_burbujas_aleatorio(fallback_msg)
                await enviar_burbujas_con_delay(burbujas, session_id)
                manager.sessions_context[session_id].append({"role": "assistant", "content": fallback_msg})
                guardar_sesion(session_id, manager.sessions_context[session_id])

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)
