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
        self.periodic_tasks: dict[str, asyncio.Task] = {}
        self.burbujas_enviadas: dict[str, set[str]] = {}  # Registro global de burbujas enviadas por sesión

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.burbujas_enviadas[session_id] = set()
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.burbujas_enviadas.pop(session_id, None)
        task = self.periodic_tasks.pop(session_id, None)
        if task:
            task.cancel()
        print(f"[{session_id}] Desconectado")

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                # Marcamos el origen como websocket
                message["origin"] = "websocket"
                await websocket.send_json(message)
            except Exception as e:
                print(f"[{session_id}] Error enviando mensaje:", repr(e))


manager = ConnectionManager()


async def enviar_mensajes_periodicos(session_id: str):
    """Envía mensajes periódicos solo si hay interacción reciente."""
    try:
        while session_id in manager.active_connections:
            await asyncio.sleep(random.randint(30, 90))

            history = get_session_messages(session_id) or []
            if not history:
                continue

            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            contexto = history[-1]["content"] if history else ""
            messages_for_groq = system_messages + [{"role": "user", "content": contexto}]

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=150,
                    temperature=0.9,
                    top_p=0.95,
                    frequency_penalty=0.8,
                    presence_penalty=0.9
                )
                reply_text = response.choices[0].message.content.strip()
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=contexto
                )

                for b in burbujas:
                    if b not in manager.burbujas_enviadas.get(session_id, set()):
                        await manager.send_personal_message({"reply": [b]}, session_id)
                        manager.burbujas_enviadas[session_id].add(b)
                        await asyncio.sleep(random.uniform(0.5, 1.2))

                save_message(session_id, "assistant", reply_text)
            except Exception as e:
                print(f"[{session_id}] Error en mensaje periódico:", repr(e))

    except asyncio.CancelledError:
        print(f"[{session_id}] Tarea periódica cancelada")
    except Exception as e:
        print(f"[{session_id}] Error general tarea periódica:", repr(e))


@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message({"reply": [saludo]}, session_id)
        manager.burbujas_enviadas[session_id].add(saludo)

    # Habilitar mensajes periódicos si quieres
    # periodic_task = asyncio.create_task(enviar_mensajes_periodicos(session_id))
    # manager.periodic_tasks[session_id] = periodic_task

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                msg = "Por favor, dime algo para responderte."
                if msg not in manager.burbujas_enviadas[session_id]:
                    await manager.send_personal_message({"reply": [msg]}, session_id)
                    manager.burbujas_enviadas[session_id].add(msg)
                continue

            create_session(session_id)
            save_message(session_id, "user", user_text)
            history = get_session_messages(session_id) or []

            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + [{"role": "user", "content": user_text}]

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
                save_message(session_id, "assistant", reply_text)

                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=user_text
                )

                for b in burbujas:
                    if b not in manager.burbujas_enviadas.get(session_id, set()):
                        await manager.send_personal_message({"reply": [b]}, session_id)
                        manager.burbujas_enviadas[session_id].add(b)
                        await asyncio.sleep(random.uniform(0.5, 1.2))

            except Exception as e:
                print(f"[{session_id}] Error en chat:", repr(e))
                fallback_msg = "El silencio también tiene cosas que decir."
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(fallback_msg),
                    contexto=user_text
                )
                for b in burbujas:
                    if b not in manager.burbujas_enviadas.get(session_id, set()):
                        await manager.send_personal_message({"reply": [b], "error": "fallback"}, session_id)
                        manager.burbujas_enviadas[session_id].add(b)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)
