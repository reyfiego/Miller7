from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from groq import Groq
from fastapi import FastAPI, HTTPException
from from .db.models import crear_usuario, autenticar_usuario, guardar_sesion
import os, uuid
import speech_recognition as sr

from millercore.websocket_manager import router as websocket_router

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    print("⚠️ No se encontró GROQ_API_KEY. La IA no funcionará completamente.")
    groq_client = None
else:
    groq_client = Groq(api_key=API_KEY)

app = FastAPI()
app.include_router(websocket_router)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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

@app.post("/registro/")
def registro(correo: str, contra: str):
    crear_usuario(correo, contra)
    return {"status": "usuario creado"}

@app.post("/login/")
def login(correo: str, contra: str):
    user = autenticar_usuario(correo, contra)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {"status": "login exitoso", "user_id": user['id']}

@app.post("/sesion/")
def nueva_sesion(user_id: str, contexto: str):
    guardar_sesion(user_id, contexto)
    return {"status": "sesion guardada"}