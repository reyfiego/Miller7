import os
import uuid
import speech_recognition as sr
from fastapi import UploadFile, File, APIRouter

router = APIRouter()

@router.post("/audio")
async def audio_to_text(file: UploadFile = File(...)):
    """
    Convierte un archivo de audio a texto usando SpeechRecognition.
    """
    try:
        # Guardar temporalmente el archivo
        path = f"temp_{uuid.uuid4()}.wav"
        with open(path, "wb") as f:
            f.write(await file.read())

        # Reconocimiento de voz
        recognizer = sr.Recognizer()
        with sr.AudioFile(path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="es-ES")
        os.remove(path)
        return {"text": text}

    except Exception as e:
        print("Error en /audio:", repr(e))
        return {"text": "", "error": str(e)}