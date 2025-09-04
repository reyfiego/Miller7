import asyncio
import datetime
import random
from typing import Dict
from fastapi import WebSocket

from modelos import get_session_messages, save_message, create_session
from corazon import SYSTEM_ROLE, FRASES_CONTEXTUALES, get_random_greeting
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual
from groq import Groq
import os

# Inicializamos el cliente de Groq una sola vez
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
groq_client = Groq(api_key=API_KEY)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(message)


manager = ConnectionManager()


async def manejar_chat(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    ultima_interaccion = datetime.datetime.now()

    try:
        # Saludo inicial
        saludo = get_random_greeting()
        if saludo:
            await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            ultima_interaccion = datetime.datetime.now()

            if not user_text:
                await manager.send_personal_message(
                    {"reply": ["¿Podrías decirme algo para responderte?"], "session_id": session_id},
                    session_id
                )
                continue

            # Guardamos sesión y mensajes
            create_session(session_id)
            save_message(session_id, "user", user_text)
            history = get_session_messages(session_id) or []
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]

            # Revisamos frases contextuales
            for frase in FRASES_CONTEXTUALES:
                if any(p.lower() in user_text.lower() for p in frase["contexto"].split(",")) and random.random() < 0.4:
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
                    temperature=0.85,
                    top_p=0.95,
                    frequency_penalty=0.8,
                    presence_penalty=0.9
                )
                reply_text = response.choices[0].message.content.strip()
                save_message(session_id, "assistant", reply_text)

                # Enriquecemos las burbujas con contexto
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto="\n".join([m["content"] for m in history]),
                    groq_client=groq_client
                )

                for b in burbujas:
                    await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                print("Error en /ws/chat:", repr(e))
                frases_backup = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                    "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
                ]
                await manager.send_personal_message(
                    {"reply": [random.choice(frases_backup)], "session_id": session_id, "error": "fallback"},
                    session_id
                )

    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)
