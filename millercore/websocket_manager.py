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

# -------------------------------
# CONNECTION MANAGER
# -------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.user_last_active: dict[str, datetime.datetime] = {}
        self.last_bubble_time: dict[str, datetime.datetime] = {}
        self.consecutive_bubbles: dict[str, int] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.user_last_active[session_id] = datetime.datetime.now()
        self.last_bubble_time[session_id] = datetime.datetime.min
        self.consecutive_bubbles[session_id] = 0

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.user_last_active.pop(session_id, None)
        self.last_bubble_time.pop(session_id, None)
        self.consecutive_bubbles.pop(session_id, None)

    async def send_personal_message(self, message: str, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_text(message)
            self.last_bubble_time[session_id] = datetime.datetime.now()
            self.consecutive_bubbles[session_id] += 1

    def update_activity(self, session_id: str):
        self.user_last_active[session_id] = datetime.datetime.now()
        self.consecutive_bubbles[session_id] = 0  # resetear al recibir mensaje del usuario

    def get_idle_users(self, timeout_seconds: int):
        now = datetime.datetime.now()
        return [
            sid for sid, ts in self.user_last_active.items()
            if (now - ts).total_seconds() > timeout_seconds
        ]

manager = ConnectionManager()

# -------------------------------
# FUNCIONES AUXILIARES
# -------------------------------
async def enviar_respuesta(session_id: str, reply_text: str):
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
# MENSAJES AUTOMÁTICOS CONTROLADOS
# -------------------------------
async def generar_mensaje_automatico(session_id: str) -> str:
    history = historiales.get(session_id, [])
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
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error generando mensaje automático:", repr(e))
        fallback = [
            "A veces un simple pensamiento puede cambiar cómo nos sentimos…",
            "El silencio también puede ser un buen compañero.",
        ]
        return random.choice(fallback)

async def auto_message_loop():
    while True:
        await asyncio.sleep(5)
        idle_users = manager.get_idle_users(timeout_seconds=15)
        for sid in idle_users:
            if manager.consecutive_bubbles.get(sid, 0) >= 3:
                continue  # no enviar más de 3 burbujas consecutivas
            last_time = manager.last_bubble_time.get(sid, datetime.datetime.min)
            if (datetime.datetime.now() - last_time).total_seconds() < 15:
                continue
            msg = await generar_mensaje_automatico(sid)
            await enviar_respuesta(sid, msg)

asyncio.create_task(auto_message_loop())

# -------------------------------
# WEBSOCKET CHAT
# -------------------------------
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)

    if session_id not in historiales:
        historiales[session_id] = []

    saludo = get_random_greeting()
    if saludo:
        await enviar_respuesta(session_id, saludo)

    try:
        while True:
            data = await websocket.receive_text()
            user_text = data.strip()
            manager.update_activity(session_id)

            if not user_text:
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

                historiales[session_id].append({"role": "assistant", "content": reply_text})
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=" ".join([m["content"] for m in historiales[session_id]]),
                    groq_client=groq_client,
                    max_burbujas=3,
                    relevancia_minima=0.8
                )

                burbujas_previas = set([b["content"] for b in historiales[session_id] if b["role"] == "assistant"])
                count = 0
                for b in burbujas:
                    if b not in burbujas_previas and count < 3:
                        await enviar_respuesta(session_id, b)
                        count += 1

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
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)
