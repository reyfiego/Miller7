from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os, datetime, random, asyncio, uuid
import speech_recognition as sr
from groq import Groq

from millercore.corazon import SYSTEM_ROLE, get_random_greeting, FRASES_CONTEXTUALES
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_contextual, contexto_coincide

# Configuración
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

groq_client = Groq(api_key=API_KEY)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Historial por sesión
historiales = {}

# Manejo de conexiones
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

# Página principal
@app.get("/")
async def root():
    return FileResponse("static/index.html")

# WebSocket para chat
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    if session_id not in historiales:
        historiales[session_id] = []

    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message(saludo, session_id)

    try:
        while True:
            data = await websocket.receive_text()
            user_text = data.strip()
            if not user_text:
                await manager.send_personal_message("Por favor, escribe algo para responderte.", session_id)
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
                    temperature=0.9,
                    top_p=0.95
                )
                reply_text = response.choices[0].message.content.strip()

                if user_text.lower() in ["no", "no gracias", "prefiero no"]:
                    reply_text = "Está bien, no insistiré. Solo dime si quieres hablar de otra cosa."

                historiales[session_id].append({"role": "assistant", "content": reply_text})

                contexto_completo = " ".join([m["content"] for m in historiales[session_id]])
                burbujas = enriquecer_burbujas_contextual(
                    dividir_burbujas_aleatorio(reply_text),
                    contexto=contexto_completo,
                    groq_client=groq_client
                )

                for b in burbujas:
                    await manager.send_personal_message(b, session_id)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                print("Error en chat:", repr(e))
                await manager.send_personal_message("Algo salió mal al procesar tu mensaje.", session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)

# Endpoint para reconocimiento de voz
@app.post("/audio")
async def audio_to_text(file: UploadFile = File(...)):
    try:
        path = f"temp_{uuid.uuid4()}.wav"
        with open(path, "wb") as f:
            f.write(await file.read())

        recognizer = sr.Recognizer()
        with sr.AudioFile(path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="es-ES")
        os.remove(path)
        return {"text": text}
    except Exception as e:
        print("Error en /audio:", repr(e))
        return {"text": "", "error": str(e)}
