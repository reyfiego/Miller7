from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os, datetime, random, asyncio
from groq import Groq
from millercore.corazon import SYSTEM_ROLE, FRASES_CONTEXTUALES, get_random_greeting
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
ultimo_auto_msg = {}  # ← Control de último mensaje automático

# -------------------------------
# CONNECTION MANAGER
# -------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.user_last_active: dict[str, datetime.datetime] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.user_last_active[session_id] = datetime.datetime.now()

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.user_last_active.pop(session_id, None)
        ultimo_auto_msg.pop(session_id, None)

    async def send_personal_message(self, message: str, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_text(message)

    def update_activity(self, session_id: str):
        self.user_last_active[session_id] = datetime.datetime.now()

    def get_idle_users(self, timeout_seconds: int):
        now = datetime.datetime.now()
        return [sid for sid, ts in self.user_last_active.items() if (now - ts).total_seconds() > timeout_seconds]

manager = ConnectionManager()

# -------------------------------
# FUNCIONES AUXILIARES
# -------------------------------
async def enviar_respuesta(session_id: str, reply_text: str):
    if not reply_text:
        return
    clean_text = reply_text.replace("<|header_start|>", "").replace("<|header_end|>", "").strip()
    clean_text = clean_text.replace('"', '')
    await manager.send_personal_message(clean_text, session_id)

def es_pregunta_directa(texto: str):
    try:
        if "+" in texto or "-" in texto or "*" in texto or "/" in texto:
            return str(eval(texto))
    except:
        pass
    return None

# -------------------------------
# MENSAJES AUTOMÁTICOS
# -------------------------------
async def generar_mensaje_automatico(session_id: str) -> str | None:
    # Evitar repetir mensajes automáticos muy seguido
    last_time = ultimo_auto_msg.get(session_id)
    if last_time and (datetime.datetime.now() - last_time).total_seconds() < 20:
        return None

    history = historiales.get(session_id, [])
    system_messages = [{"role": "system", "content": SYSTEM_ROLE}] + history
    try:
        response = groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=system_messages,
            max_tokens=150,
            temperature=0.85,
            top_p=0.95
        )
        msg = response.choices[0].message.content.strip()
        ultimo_auto_msg[session_id] = datetime.datetime.now()
        return msg
    except:
        fallback = [
            "A veces un simple pensamiento puede cambiar cómo nos sentimos…",
            "El silencio también puede ser un buen compañero.",
        ]
        ultimo_auto_msg[session_id] = datetime.datetime.now()
        return random.choice(fallback)

async def auto_message_loop():
    while True:
        await asyncio.sleep(5)
        idle_users = manager.get_idle_users(timeout_seconds=15)
        for sid in idle_users:
            msg = await generar_mensaje_automatico(sid)
            if msg:
                await enviar_respuesta(sid, msg)
                manager.update_activity(sid)

asyncio.create_task(auto_message_loop())

# -------------------------------
# WEBSOCKET CHAT
# -------------------------------
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    ultima_interaccion = datetime.datetime.now()

    if session_id not in historiales:
        historiales[session_id] = []

    # Saludo inicial (solo 1 burbuja)
    saludo = get_random_greeting()
    if saludo:
        await enviar_respuesta(session_id, saludo)

    async def enviar_mensaje_auto():
        await asyncio.sleep(20)  # espera 20s de inactividad
        idle_time = (datetime.datetime.now() - ultima_interaccion).total_seconds()
        if idle_time >= 20:
            msg = await generar_mensaje_automatico(session_id)
            await enviar_respuesta(session_id, msg)

    try:
        while True:
            data = await websocket.receive_text()
            user_text = data.strip()
            ultima_interaccion = datetime.datetime.now()
            manager.update_activity(session_id)

            if not user_text:
                continue  # no enviar nada si está vacío

            historiales[session_id].append({"role": "user", "content": user_text})

            # Construir mensajes del sistema
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            for frase in FRASES_CONTEXTUALES:
                contexto_lista = frase["contexto"] if isinstance(frase["contexto"], list) else [c.strip() for c in frase["contexto"].split(",")]
                if contexto_coincide(user_text, contexto_lista) and random.random() < 0.4:
                    contenido = frase["texto"]
                    if frase.get("primera_persona"):
                        contenido = f"Sabes, a veces yo siento algo parecido. {contenido}"
                    system_messages.append({"role": "system", "content": f"Inspírate en esta frase para responder: {contenido}"})

            messages_for_groq = system_messages + historiales[session_id]

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=250,
                    temperature=0.85,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()
                historiales[session_id].append({"role": "assistant", "content": reply_text})
                await enviar_respuesta(session_id, reply_text)
            except Exception as e:
                print("Error en chat:", repr(e))
                fallback_messages = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                ]
                await enviar_respuesta(session_id, random.choice(fallback_messages))

            # Lanzar el mensaje automático de retomar conversación
            asyncio.create_task(enviar_mensaje_auto())

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)