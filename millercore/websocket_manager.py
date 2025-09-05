from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import os
import traceback
from groq import Groq

app = FastAPI()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
groq_client = Groq(api_key=API_KEY)

# Diccionario simple para guardar historial en memoria (solo para pruebas)
historiales = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_personal_message(self, message: str, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            user_text = data.strip()
            if not user_text:
                await manager.send_personal_message("Por favor, escribe algo para que pueda responderte.", session_id)
                continue

            # Guardar mensaje usuario en historial
            historial = historiales.get(session_id, [])
            historial.append({"role": "user", "content": user_text})
            historiales[session_id] = historial

            # Construir mensajes para Groq
            system_message = {"role": "system", "content": "Eres un asistente empático y humano."}
            messages_for_groq = [system_message] + historial

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=150,
                    temperature=0.85,
                    top_p=0.95
                )
                print("Respuesta completa de Groq:", response)
                reply_text = response.choices[0].message.content.strip()
                print("Texto respuesta:", reply_text)

                # Guardar respuesta en historial
                historial.append({"role": "assistant", "content": reply_text})
                historiales[session_id] = historial

                print(f"Enviando a cliente: {reply_text}")  # <-- Aquí agregamos el print para depurar

                await manager.send_personal_message(reply_text, session_id)

            except Exception as e:
                print("Error llamando a Groq:", repr(e))
                traceback.print_exc()
                await manager.send_personal_message("Lo siento, tuve un problema para responderte.", session_id)

    except WebSocketDisconnect:
        print(f"Cliente desconectado: {session_id}")
        manager.disconnect(session_id)
