from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os, datetime, random, asyncio
from groq import Groq
from millercore.corazon import SYSTEM_ROLE, get_random_greeting, FRASES_CONTEXTUALES
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual, contexto_coincide

# -------------------------------
# CONFIG
# -------------------------------
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

groq_client = Groq(api_key=API_KEY)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

historiales = {}

# -------------------------------
# CONNECTION MANAGER
# -------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

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

# -------------------------------
# FUNCIÓN PARA LIMPIAR RESPUESTA
# -------------------------------
async def enviar_respuesta(session_id: str, reply_text: str):
    clean_text = reply_text.replace("<|header_start|>", "").replace("<|header_end|>", "").strip()
    clean_text = clean_text.replace('"', '')
    await manager.send_personal_message(clean_text, session_id)

# -------------------------------
# WEBSOCKET CHAT
# -------------------------------
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    ultima_interaccion = datetime.datetime.now()

    if session_id not in historiales:
        historiales[session_id] = []

    # Saludo inicial
    saludo = get_random_greeting()
    if saludo:
        await enviar_respuesta(session_id, saludo)

    async def mensajes_periodicos():
        while True:
            await asyncio.sleep(random.randint(30, 90))
            if (datetime.datetime.now() - ultima_interaccion).seconds > 120:
                continue
            history = historiales.get(session_id, [])
            if not history:
                continue

            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + history

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=150,
                    temperature=0.85,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()

                contexto_completo = " ".join([m["content"] for m in history])
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=contexto_completo,
                    groq_client=groq_client,
                    max_burbujas=2,
                    relevancia_minima=0.8
                )

                for b in burbujas:
                    await enviar_respuesta(session_id, b)
                    await asyncio.sleep(random.uniform(0.5, 1.2))

                historiales[session_id].append({"role": "assistant", "content": reply_text})

            except Exception as e:
                print("Error en mensaje automático:", repr(e))

    task = asyncio.create_task(mensajes_periodicos())

    try:
        while True:
            data = await websocket.receive_text()
            user_text = data.strip()
            ultima_interaccion = datetime.datetime.now()
            if not user_text:
                await enviar_respuesta(session_id, "Por favor, escribe algo para responderte.")
                continue

            historiales[session_id].append({"role": "user", "content": user_text})
            history = historiales[session_id]

            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            for frase in FRASES_CONTEXTUALES:
                contexto_lista = frase["contexto"] if isinstance(frase["contexto"], list) else [c.strip() for c in frase["contexto"].split(",")]
                if contexto_coincide(user_text, contexto_lista) and random.random() < 0.4:
                    contenido = frase["texto"]
                    if frase.get("primera_persona"):
                        contenido = f"Sabes, a veces yo siento algo parecido. {contenido}"
                    system_messages.append({"role": "system", "content": f"Inspírate en esta frase para responder: {contenido}"})

            messages_for_groq = system_messages + history

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=250,
                    temperature=0.85,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()

                # Ajuste de tono amigable
                if user_text.lower() in ["no", "no gracias", "prefiero no"]:
                    reply_text = "Está bien, no insistiré. Solo dime si quieres hablar de otra cosa."

                historiales[session_id].append({"role": "assistant", "content": reply_text})

                contexto_completo = " ".join([m["content"] for m in historiales[session_id]])
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=contexto_completo,
                    groq_client=groq_client,
                    max_burbujas=2,
                    relevancia_minima=0.8
                )

                for b in burbujas:
                    await enviar_respuesta(session_id, b)
                    await asyncio.sleep(random.uniform(0.5, 1.2))

            except Exception as e:
                print("Error en chat:", repr(e))
                fallback_messages = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                    "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
                ]
                await enviar_respuesta(session_id, random.choice(fallback_messages))

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        task.cancel()
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)
        task.cancel()
