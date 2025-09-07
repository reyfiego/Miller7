from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import datetime
import json
import random

router = APIRouter()

# Simulación cliente Groq (solo para ejemplo)
class GroqClient:
    def chat_completion(self, messages):
        user_msg = messages[-1]["content"].lower() if messages else "hola"
        
        if "hola" in user_msg or "hey" in user_msg:
            return "¡Hola! ¿En qué puedo ayudarte hoy?"
        elif "cómo estás" in user_msg:
            return "Estoy bien, gracias por preguntar. ¿Y tú?"
        elif "gracias" in user_msg:
            return "¡De nada! Estoy aquí para ayudarte."
        else:
            # Respuesta por defecto
            return f"No estoy seguro de entender '{user_msg}', ¿puedes aclarar?"


groq_client = GroqClient()

# Manager para conexiones y estados
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.user_last_active: dict[str, datetime.datetime] = {}
        self.consecutive_bubbles: dict[str, int] = {}
        self.last_bubble_time: dict[str, datetime.datetime] = {}
        self.burbujas_enviadas: dict[str, set] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        now = datetime.datetime.now()
        self.user_last_active[session_id] = now
        self.last_bubble_time[session_id] = datetime.datetime.min
        self.consecutive_bubbles[session_id] = 0
        self.burbujas_enviadas.setdefault(session_id, set())
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.user_last_active.pop(session_id, None)
        self.consecutive_bubbles.pop(session_id, None)
        self.last_bubble_time.pop(session_id, None)
        self.burbujas_enviadas.pop(session_id, None)
        print(f"[{session_id}] Desconectado")

    def update_activity(self, session_id: str):
        self.user_last_active[session_id] = datetime.datetime.now()
        self.consecutive_bubbles[session_id] = 0

manager = ConnectionManager()

# Función para generar mensaje automático (simulado)
async def generar_mensaje_automatico(session_id: str) -> str:
    posibles = [
        "A veces un simple pensamiento puede cambiar cómo nos sentimos…",
        "El silencio también puede ser un buen compañero.",
        "Recuerda que siempre hay luz al final del túnel."
    ]
    return random.choice(posibles)

# Loop para mensajes automáticos (desactivado por defecto)
async def auto_message_loop():
    while True:
        await asyncio.sleep(5)
        now = datetime.datetime.now()
        for sid in list(manager.active_connections.keys()):
            idle_time = (now - manager.user_last_active.get(sid, now)).total_seconds()
            if idle_time < 300:  # Solo si inactivo más de 5 minutos
                continue

            if manager.consecutive_bubbles.get(sid, 0) >= 4:
                continue

            last_time = manager.last_bubble_time.get(sid, datetime.datetime.min)
            if (now - last_time).total_seconds() < 15:
                continue

            msg = await generar_mensaje_automatico(sid)
            if msg in manager.burbujas_enviadas[sid]:
                continue  # No repetir mensajes

            websocket = manager.active_connections.get(sid)
            if websocket:
                print(f"[{sid}] Enviando mensaje automático: {msg}")
                await websocket.send_text(json.dumps({"reply": [msg]}))
                manager.last_bubble_time[sid] = datetime.datetime.now()
                manager.consecutive_bubbles[sid] += 1
                manager.burbujas_enviadas[sid].add(msg)

# Para activar el loop, descomenta la siguiente línea:
# asyncio.create_task(auto_message_loop())


@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_text()
            manager.update_activity(session_id)
            print(f"[{session_id}] Mensaje recibido: {data}")

            try:
                data_json = json.loads(data)
            except Exception:
                print(f"[{session_id}] No es JSON válido")
                continue

            if data_json.get("from") != "user":
                print(f"[{session_id}] Ignorando mensaje no usuario: {data_json}")
                continue

            user_text = data_json.get("message", "").strip()
            if not user_text:
                print(f"[{session_id}] Mensaje vacío, ignorando")
                continue

            # Generar respuesta con GroqClient
            print(f"[{session_id}] Generando respuesta para: {user_text}")
            response_text = groq_client.chat_completion([
                {"role": "system", "content": "Eres Miller, un asistente conversacional."},
                {"role": "user", "content": user_text}
            ])

            # Opcional: evitar repetir la misma respuesta (puedes comentar para desactivar)
            # if response_text in manager.burbujas_enviadas[session_id]:
            #     print(f"[{session_id}] Respuesta ya enviada, ignorando")
            #     continue

            # Enviar respuesta
            await websocket.send_text(json.dumps({"reply": [response_text]}))
            print(f"[{session_id}] Respuesta enviada: {response_text}")

            manager.consecutive_bubbles[session_id] += 1
            manager.last_bubble_time[session_id] = datetime.datetime.now()
            manager.burbujas_enviadas[session_id].add(response_text)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general: {repr(e)}")
        manager.disconnect(session_id)