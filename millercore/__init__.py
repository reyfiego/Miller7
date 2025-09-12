init

import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel
import speech_recognition as sr
from groq import Groq

from .db.models import crear_usuario, autenticar_usuario, guardar_sesion, obtener_sesiones
from .websocket_manager import router as websocket_router

load_dotenv()

# -------------------------
# CONFIGURACIÓN GROQ
# -------------------------
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    print("⚠️ No se encontró GROQ_API_KEY. La IA no funcionará completamente.")
    groq_client = None
else:
    groq_client = Groq(api_key=API_KEY)

# -------------------------
# APP FASTAPI
# -------------------------
app = FastAPI()
app.include_router(websocket_router)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# -------------------------
# Pydantic Models
# -------------------------
class User(BaseModel):
    email: str
    password: str

class SessionData(BaseModel):
    user_id: str
    contexto: str

# -------------------------
# ENDPOINTS HTTP
# -------------------------
@app.get("/")
async def root():
    return FileResponse("static/index.html")

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

@app.post("/register")
def register(user: User):
    crear_usuario(user.email, user.password)
    return {"success": True, "message": "Usuario creado"}

@app.post("/login")
def login(user: User):
    u = autenticar_usuario(user.email, user.password)
    if not u:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {"success": True, "user_id": u['id']}

@app.post("/session/")
def nueva_sesion(data: SessionData):
    guardar_sesion(data.user_id, data.contexto)
    return {"success": True, "message": "Sesión guardada"}

@app.get("/session/{session_id}/messages")
def get_session_messages_endpoint(session_id: str):
    sesiones = obtener_sesiones(session_id)
    messages = [{"sender": "user", "content": s["contexto"]} for s in sesiones.data] if sesiones.data else []
    return {"messages": messages}