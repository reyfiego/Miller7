import os
import asyncio
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import Groq
from .burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual
from .corazon import SYSTEM_ROLE, get_random_greeting
from db import create_session, save_message, get_session_messages
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

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
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


@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        # Nota: La lógica de burbujas en el front-end es más eficiente
        # No es necesario dividir el saludo en varias burbujas
        await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                await manager.send_personal_message({"reply": ["Por favor, dime algo para responderte."], "session_id": session_id}, session_id)
                continue

            create_session(session_id)
            history = get_session_messages(session_id) or []
            
            # **CORRECCIÓN 1: Enviar el historial completo a la IA**
            # Añadir el mensaje del usuario al historial para la llamada a la API
            messages_for_groq = history + [{"role": "user", "content": user_text}]
            
            # Añadir el rol del sistema al inicio
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + messages_for_groq

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

                save_message(session_id, "user", user_text)
                save_message(session_id, "assistant", reply_text)

                # **CORRECCIÓN 2: Lógica de envío simplificada**
                # Enviar todas las burbujas de una vez
                burbujas = enriquecer_burbujas_contextual(dividir_burbujas_aleatorio(reply_text), contexto=user_text)
                await manager.send_personal_message({"reply": burbujas, "session_id": session_id}, session_id)

            except Exception as e:
                print(f"[{session_id}] Error en chat:", repr(e))
                fallback_msg = "El silencio también tiene cosas que decir."
                burbujas = enriquecer_burbujas_contextual(dividir_burbujas_aleatorio(fallback_msg), contexto=user_text)
                await manager.send_personal_message({"reply": burbujas, "session_id": session_id, "error": "fallback"}, session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)