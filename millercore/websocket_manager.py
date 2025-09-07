# millercore/websocket_manager.py
import os
import json
import datetime
import asyncio
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import Groq
from .burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual
from .corazon import SYSTEM_ROLE, FRASES_CONTEXTUALES, get_random_greeting
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

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        task = self.periodic_tasks.pop(session_id, None)
        if task:
            task.cancel()
        print(f"[{session_id}] Desconectado")

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"[{session_id}] Error enviando mensaje:", repr(e))


manager = ConnectionManager()


async def enviar_mensajes_periodicos(session_id: str):
    """Envía mensajes periódicos si hay interacción reciente."""
    try:
        while True:
            await asyncio.sleep(random.randint(30, 90))
            if session_id not in manager.active_connections:
                break

            history = get_session_messages(session_id) or []
            if not history:
                continue

            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + history
            contexto = history[-1]["content"] if history else ""

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
                    await manager.send_personal_message(
                        {"reply": [b], "session_id": session_id}, session_id
                    )
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
    burbujas_mostradas: set[str] = set()

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message(
            {"reply": [saludo], "session_id": session_id}, session_id
        )

    # Iniciar tarea periódica
    periodic_task = asyncio.create_task(enviar_mensajes_periodicos(session_id))
    manager.periodic_tasks[session_id] = periodic_task

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                await manager.send_personal_message(
                    {"reply": ["Por favor, dime algo para responderte."], "session_id": session_id},
                    session_id
                )
                continue

            create_session(session_id)
            history = get_session_messages(session_id) or []
            history.append({"role": "user", "content": user_text})
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]

            # Aplicar frases contextuales
            for frase in FRASES_CONTEXTUALES:
                contextos = frase["contexto"]
                if isinstance(contextos, str):
                    lista_contextos = contextos.split(",")
                elif isinstance(contextos, list):
                    lista_contextos = contextos
                else:
                    continue

                if any(p.lower() in user_text.lower() for p in lista_contextos) and random.random() < 0.4:
                    contenido = frase["texto"]
                    if frase.get("primera_persona"):
                        contenido = f"Sabes, a veces yo siento algo parecido. {contenido}"
                    system_messages.append({
                        "role": "system",
                        "content": f"Inspírate en esta frase para responder: {contenido}"
                    })

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

                save_message(session_id, "user", user_text)
                save_message(session_id, "assistant", reply_text)

                # Enriquecer burbujas con contexto
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=user_text
                )

                for b in burbujas:
                    if b not in burbujas_mostradas:
                        await manager.send_personal_message(
                            {"reply": [b], "session_id": session_id}, session_id
                        )
                        burbujas_mostradas.add(b)
                        await asyncio.sleep(random.uniform(0.5, 1.2))

            except Exception as e:
                print(f"[{session_id}] Error en chat:", repr(e))
                fallback_messages = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                    "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
                ]
                fallback_msg = random.choice(fallback_messages)
                # Enriquecer fallback
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(fallback_msg),
                    contexto=user_text
                )
                for b in burbujas:
                    if b not in burbujas_mostradas:
                        await manager.send_personal_message(
                            {"reply": [b], "session_id": session_id, "error": "fallback"}, session_id
                        )
                        burbujas_mostradas.add(b)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)
