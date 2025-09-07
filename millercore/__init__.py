from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os, uuid
import speech_recognition as sr

from .websocket_manager import router as websocket_router  # <--- importa el router

load_dotenv()

app = FastAPI()
app.include_router(websocket_router)  # <--- registra el router

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
