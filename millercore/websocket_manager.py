from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import datetime
import json
import random
from groq import Groq
import os

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

groq = Groq(api_key=API_KEY)

router = APIRouter()

# Simulación cliente Groq (solo para ejemplo)
class GroqClient:
    def chat_completion(self, messages):
        response = groq.chat.completions.create(
            model=MODEL_ID,
            messages=messages
        )
        return response.choices[0].message.content

groq_client = GroqClient()

# -------------------------------
# Connection Manager con historial
# -------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.user_last_active: dict[str, datetime.datetime] = {}
        self.consecutive_bubbles: dict[str, int] = {}
        self.last_bubble_time: dict[str, datetime.datetime] = {}
        self.burbujas_enviadas: dict[str, set] = {}
        self.historial: dict[str, list] = {}  # 🔥 historial de mensajes

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        now = datetime.datetime.now()
        self.user_last_active[session_id] = now
        self.last_bubble_time[session_id] = datetime.datetime.min
        self.consecutive_bubbles[session_id] = 0
        self.burbujas_enviadas.setdefault(session_id, set())
        self.historial.setdefault(session_id, [])  # 🔥 inicializa historial
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.user_last_active.pop(session_id, None)
        self.consecutive_bubbles.pop(session_id, None)
        self.last_bubble_time.pop(session_id, None)
        self.burbujas_enviadas.pop(session_id, None)
        self.historial.pop(session_id, None)  # 🔥 limpia historial
        print(f"[{session_id}] Desconectado")

manager = ConnectionManager()

# -------------------------------
# WebSocket principal
# -------------------------------
@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            user_text = data_json.get("message", "").strip()

            if not user_text:
                continue

            # 🔥 Guardamos el mensaje del usuario en el historial
            manager.historial[session_id].append({"role": "user", "content": user_text})

            # 🔥 Creamos el contexto de la conversación
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Eres Miller, un asistente conversacional empático, reflexivo y humano. "
                        "Responde de manera natural y sin repetirte demasiado."
                    )
                }
            ] + manager.historial[session_id]

            # 🔥 Llamada al modelo con historial completo
            response_text = groq_client.chat_completion(messages)

            # 🔥 Guardamos también la respuesta de la IA
            manager.historial[session_id].append({"role": "assistant", "content": response_text})

            # Enviar la respuesta en una burbuja
            await websocket.send_text(json.dumps({"reply": [response_text]}))

    except WebSocketDisconnect:
        manager.disconnect(session_id)