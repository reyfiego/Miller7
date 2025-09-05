from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import datetime
import random
import os
import traceback
from groq import Groq

from millercore.corazon import SYSTEM_ROLE, FRASES_CONTEXTUALES, get_random_greeting
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual

app = FastAPI()

# -------------------------------
# Configuración Groq
# -------------------------------
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
groq_client = Groq(api_key=API_KEY)

# -------------------------------
# Historial en memoria (por sesión)
# -------------------------------
historiales = {}

# -------------------------------
# Connection Manager
# -------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_message(self, message: str, session_id: str):
        ws = self.active_connections.get(session_id)
        if ws:
            await ws.send_text(message)

manager = ConnectionManager()

# -------------------------------
# Función auxiliar: contexto
# -------------------------------
def contexto_coincide(mensaje: str, contexto: list[str]) -> bool:
    mensaje_lower = mensaje.lower()
    return any(c.lower() in mensaje_lower for c in contexto)

# -------------------------------
# WebSocket endpoint
# -------------------------------
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    historial = historiales.get(session_id, [])
    ultima_interaccion = datetime.datetime.now()
    task = None

    # -------------------------------
    # Mensajes automáticos periódicos
    # -------------------------------
    async def mensajes_periodicos():
        nonlocal ultima_interaccion, historial
        while True:
            await asyncio.sleep(random.randint(30, 90))
            if (datetime.datetime.now() - ultima_interaccion).seconds > 120:
                continue
            if not historial:
                continue

            system_msg = {"role": "system", "content": SYSTEM_ROLE}
            messages_for_groq = [system_msg] + historial
            contexto_completo = " ".join(m["content"] for m in historial)

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=150,
                    temperature=0.85,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()

                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=contexto_completo,
                    groq_client=groq_client
                )

                for b in burbujas:
                    await manager.send_message(b, session_id)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                historial.append({"role": "assistant", "content": reply_text})
                historiales[session_id] = historial

            except Exception as e:
                print("Error en mensaje automático:", repr(e))
                traceback.print_exc()

    try:
        # Saludo inicial
        saludo = get_random_greeting()
        if saludo:
            await manager.send_message(saludo, session_id)

        task = asyncio.create_task(mensajes_periodicos())

        # -------------------------------
        # Loop principal
        # -------------------------------
        while True:
            data = await websocket.receive_text()
            user_text = data.strip()
            ultima_interaccion = datetime.datetime.now()

            if not user_text:
                await manager.send_message("Por favor, escribe algo para responderte.", session_id)
                continue

            # Guardar mensaje del usuario
            historial.append({"role": "user", "content": user_text})

            # Preparar mensajes para Groq
            system_msg = {"role": "system", "content": SYSTEM_ROLE}

            # Aplicar frases contextuales
            system_messages = [system_msg]
            for frase in FRASES_CONTEXTUALES:
                contexto_lista = frase["contexto"] if isinstance(frase["contexto"], list) else [p.strip() for p in frase["contexto"].split(",")]
                if contexto_coincide(user_text, contexto_lista) and random.random() < 0.4:
                    contenido = frase["texto"]
                    if frase.get("primera_persona"):
                        contenido = f"Sabes, a veces yo siento algo parecido. {contenido}"
                    system_messages.append({"role": "system", "content": f"Inspírate en esta frase: {contenido}"})

            messages_for_groq = system_messages + historial
            contexto_completo = " ".join(m["content"] for m in historial)

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=250,
                    temperature=0.85,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()

                if user_text.lower() in ["no", "no gracias", "prefiero no"]:
                    reply_text = "Está bien, no insistiré. Solo dime si quieres hablar de otra cosa."

                # Guardar respuesta
                historial.append({"role": "assistant", "content": reply_text})
                historiales[session_id] = historial

                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=contexto_completo,
                    groq_client=groq_client
                )

                for b in burbujas:
                    await manager.send_message(b, session_id)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                print("Error en chat:", repr(e))
                traceback.print_exc()
                await manager.send_message("Lo siento, tuve un problema para responderte.", session_id)

    except WebSocketDisconnect:
        print(f"Cliente desconectado: {session_id}")
        manager.disconnect(session_id)
        if task:
            task.cancel()
    except Exception as e:
        print("Error general:", repr(e))
        traceback.print_exc()
        manager.disconnect(session_id)
        if task:
            task.cancel()
