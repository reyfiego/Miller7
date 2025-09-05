from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import json, os, datetime, random, asyncio
from groq import Groq
from millercore.corazon import SYSTEM_ROLE, FRASES_CONTEXTUALES, get_random_greeting
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual, contexto_coincide

# Carga configuración
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
        if self.silence_mode.get(session_id, False):
            print(f"Modo silencio desactivado para {session_id} por actividad del usuario")
        self.silence_mode[session_id] = False

    def get_idle_users(self, timeout_seconds: int):
        now = datetime.datetime.now()
        return [
            sid for sid, ts in self.user_last_active.items()
            if (now - ts).total_seconds() > timeout_seconds and not self.silence_mode.get(sid, False)
        ]

manager = ConnectionManager()

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
        idle_users = manager.get_idle_users(timeout_seconds=300)
        for sid in idle_users:
            if manager.consecutive_bubbles.get(sid, 0) >= 4:
                continue
            last_time = manager.last_bubble_time.get(sid, datetime.datetime.min)
            if (datetime.datetime.now() - last_time).total_seconds() < 15:
                continue
            msg = await generar_mensaje_automatico(sid)
            burbujas = enriquecer_burbujas_contextual(
                dividir_burbujas_aleatorio(msg),
                contexto=historiales.get(sid, []),
                max_burbujas=2
            )
            websocket = manager.active_connections.get(sid)
            if websocket:
                for i, burbuja in enumerate(burbujas):
                    if i == 0:
                        await websocket.send_text(json.dumps({"reply": burbuja}))
                    else:
                        await asyncio.sleep(random.uniform(5, 10))
                        await websocket.send_text(json.dumps({"reply": burbuja}))
                manager.last_bubble_time[sid] = datetime.datetime.now()
                manager.consecutive_bubbles[sid] += len(burbujas)

asyncio.create_task(auto_message_loop())

@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    if session_id not in historiales:
        historiales[session_id] = []

    saludo = get_random_greeting()
    if saludo:
        await websocket.send_text(json.dumps({"reply": saludo}))  # Saludo sin delay

    burbujas_enviadas = set()
    ultima_respuesta_con_contexto = False

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

            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]

            if not ultima_respuesta_con_contexto:
                for frase in FRASES_CONTEXTUALES:
                    contexto_lista = frase["contexto"] if isinstance(frase["contexto"], list) else [c.strip() for c in frase["contexto"].split(",")]
                    if contexto_coincide(user_text, contexto_lista) and random.random() < 0.1:
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
                    temperature=0.9,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()
                historiales[session_id].append({"role": "assistant", "content": reply_text})

                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=historiales[session_id],
                    max_burbujas=2
                )

                # Evitar repetición exacta, permitir variaciones leves
                nuevas_burbujas = []
                for b in burbujas:
                    if b not in burbujas_enviadas:
                        nuevas_burbujas.append(b)
                        burbujas_enviadas.add(b)
                    else:
                        b_mod = b + "…" if not b.endswith("…") else b
                        nuevas_burbujas.append(b_mod)
                        burbujas_enviadas.add(b_mod)
                burbujas = nuevas_burbujas

                # Enviar burbujas con delay
                for i, b in enumerate(burbujas):
                    if i == 0:  # primer burbuja sin delay
                        await websocket.send_text(json.dumps({"reply": b}))
                    else:
                        await asyncio.sleep(random.uniform(5, 10))
                        await websocket.send_text(json.dumps({"reply": b}))

                manager.last_bubble_time[session_id] = datetime.datetime.now()
                manager.consecutive_bubbles[session_id] += len(burbujas)

                ultima_respuesta_con_contexto = any(
                    "Inspírate en esta frase para responder:" in m.get("content", "")
                    for m in system_messages
                )

            except Exception as e:
                print("Error en chat:", repr(e))
                fallback_messages = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                    "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
                ]
                fallback = random.choice(fallback_messages)
                await websocket.send_text(json.dumps({"reply": [fallback]}))
                ultima_respuesta_con_contexto = False

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)
