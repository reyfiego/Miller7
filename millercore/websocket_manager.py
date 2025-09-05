from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import json, os, datetime, random, asyncio
from groq import Groq
from millercore.corazon import SYSTEM_ROLE, FRASES_CONTEXTUALES, get_random_greeting
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual, contexto_coincide

# ==========================
# CONFIG
# ==========================
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
burbujas_enviadas = {}

# ==========================
# MANAGER
# ==========================
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.user_last_active: dict[str, datetime.datetime] = {}
        self.last_bubble_time: dict[str, datetime.datetime] = {}
        self.consecutive_bubbles: dict[str, int] = {}
        self.silence_mode: dict[str, bool] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.user_last_active[session_id] = datetime.datetime.now()
        self.last_bubble_time[session_id] = datetime.datetime.min
        self.consecutive_bubbles[session_id] = 0
        self.silence_mode[session_id] = False
        print(f"Conectado: {session_id}")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.user_last_active.pop(session_id, None)
        self.last_bubble_time.pop(session_id, None)
        self.consecutive_bubbles.pop(session_id, None)
        self.silence_mode.pop(session_id, None)
        print(f"Desconectado: {session_id}")

    def update_activity(self, session_id: str):
        self.user_last_active[session_id] = datetime.datetime.now()
        self.consecutive_bubbles[session_id] = 0
        self.silence_mode[session_id] = False

manager = ConnectionManager()

# ==========================
# FUNCIONES AUX
# ==========================
async def generar_mensaje_automatico(session_id: str) -> str:
    history = historiales.get(session_id, [])
    system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
    messages_for_groq = system_messages + history
    try:
        response = groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=messages_for_groq,
            max_tokens=150,
            temperature=0.9,
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
        for sid in manager.active_connections.keys():
            if manager.silence_mode.get(sid, False):
                continue
            idle_time = (datetime.datetime.now() - manager.user_last_active[sid]).total_seconds()
            if idle_time > 300:  # 5 min
                if manager.consecutive_bubbles[sid] >= 4:
                    continue
                last_time = manager.last_bubble_time.get(sid, datetime.datetime.min)
                if (datetime.datetime.now() - last_time).total_seconds() < 15:
                    continue
                msg = await generar_mensaje_automatico(sid)
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(msg),
                    contexto=historiales.get(sid, []),
                    burbujas_previas=burbujas_enviadas.get(sid, set()),
                    max_burbujas=2
                )
                websocket = manager.active_connections.get(sid)
                if websocket:
                    await websocket.send_text(json.dumps({"reply": burbujas}))
                    manager.last_bubble_time[sid] = datetime.datetime.now()
                    manager.consecutive_bubbles[sid] += len(burbujas)
                    burbujas_enviadas[sid].update(burbujas)
                await asyncio.sleep(random.uniform(5, 10))

asyncio.create_task(auto_message_loop())

# ==========================
# WEBSOCKET
# ==========================
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    if session_id not in historiales:
        historiales[session_id] = []
    if session_id not in burbujas_enviadas:
        burbujas_enviadas[session_id] = set()

    # Saludo inicial sin delay
    saludo = get_random_greeting()
    if saludo:
        await websocket.send_text(json.dumps({"reply": saludo}))
        burbujas_enviadas[session_id].add(saludo)

    try:
        while True:
            data = await websocket.receive_text()
            manager.update_activity(session_id)
            try:
                data_json = json.loads(data)
                user_text = data_json.get("message", "").strip()
            except Exception:
                user_text = data.strip()
            if not user_text:
                continue

            historiales[session_id].append({"role": "user", "content": user_text})

            # Generar respuesta con Groq
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            messages_for_groq = system_messages + historiales[session_id]

            try:
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=250,
                    temperature=0.9,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()
                historiales[session_id].append({"role": "assistant", "content": reply_text})

                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=historiales[session_id],
                    burbujas_previas=burbujas_enviadas.get(session_id, set()),
                    max_burbujas=4
                )
                if burbujas:
                    await websocket.send_text(json.dumps({"reply": burbujas}))
                    manager.last_bubble_time[session_id] = datetime.datetime.now()
                    manager.consecutive_bubbles[session_id] += len(burbujas)
                    burbujas_enviadas[session_id].update(burbujas)

            except Exception as e:
                print("Error en chat:", repr(e))
                fallback_messages = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                    "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
                ]
                fallback = random.choice(fallback_messages)
                await websocket.send_text(json.dumps({"reply": [fallback]}))
                burbujas_enviadas[session_id].add(fallback)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)
