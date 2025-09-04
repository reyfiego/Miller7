import datetime
import asyncio
import random
from typing import List
from fastapi import WebSocket, WebSocketDisconnect

from millercore.corazon import SYSTEM_ROLE, get_random_greeting, FRASES_CONTEXTUALES
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual
from db import create_session, save_message, get_session_messages
from .__init__ import groq_client, MODEL_ID


# ==========================
# CONNECTION MANAGER
# ==========================
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)


manager = ConnectionManager()

# ==========================
# HANDLER
# ==========================
async def websocket_handler(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    ultima_interaccion = datetime.datetime.now()

    try:
        # --------------------------
        # SALUDO INICIAL
        # --------------------------
        saludo = get_random_greeting()
        if saludo:
            await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

        # --------------------------
        # TAREA DE MENSAJES PERIÓDICOS
        # --------------------------
        async def enviar_mensajes_periodicos():
            nonlocal ultima_interaccion
            while True:
                await asyncio.sleep(random.randint(30, 90))
                if (datetime.datetime.now() - ultima_interaccion).seconds > 120:
                    continue

                history = get_session_messages(session_id) or []
                system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
                messages_for_groq = system_messages + history

                try:
                    response = groq_client.chat.completions.create(
                        model=MODEL_ID,
                        messages=messages_for_groq,
                        max_tokens=150,
                        temperature=0.85,
                        top_p=0.95,
                        frequency_penalty=0.8,
                        presence_penalty=0.9
                    )
                    reply_text = response.choices[0].message.content.strip()

                    burbujas = enriquecer_burbujas_contextual(
                        dividir_burbujas_aleatorio(reply_text),
                        contexto=reply_text,
                        groq_client=groq_client
                    )

                    for b in burbujas:
                        await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
                        await asyncio.sleep(random.uniform(0.5, 1.5))

                    save_message(session_id, "assistant", reply_text)

                except Exception as e:
                    print("Error en mensaje automático:", repr(e))

        task = asyncio.create_task(enviar_mensajes_periodicos())

        # --------------------------
        # LOOP PRINCIPAL
        # --------------------------
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

            create_session(session_id)
            history = get_session_messages(session_id) or []
            history.append({"role": "user", "content": user_text})
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]

            # Aplicar frases contextuales predefinidas
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

                # Pequeña lógica especial
                if user_text.lower() in ["no", "no gracias", "prefiero no"]:
                    reply_text = "Está bien, no insistiré. Solo dime si quieres hablar de otra cosa."

                save_message(session_id, "user", user_text)
                save_message(session_id, "assistant", reply_text)

                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=user_text,
                    groq_client=groq_client
                )

                for b in burbujas:
                    await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                print("Error en chat:", repr(e))
                fallback_messages = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                    "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
                ]
                await manager.send_personal_message(
                    {"reply": [random.choice(fallback_messages)], "session_id": session_id, "error": "fallback"},
                    session_id
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        task.cancel()
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)
        task.cancel()
