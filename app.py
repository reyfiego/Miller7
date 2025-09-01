from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import datetime
import random
import uuid
from groq import Groq  # usamos Groq

# -------------------------------
# INICIALIZACIÓN
# -------------------------------

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
groq_client = Groq(api_key=API_KEY)

# -------------------------------
# ROLE SYSTEM (preciso)
# -------------------------------

SYSTEM_ROLE = """
Eres **Miller2**, una guía cercana creada por Alessandro.
Tu estilo: cálido, humano, reflexivo y esperanzador, con un toque de melancolía.
No eres terapeuta ni das diagnósticos clínicos. No usas jerga médica.
Acompañas como un amigo sabio: escuchas, validas emociones y ofreces perspectivas prácticas.

Principios:
1) Seguridad y límites: no des diagnósticos ni afirmes ser profesional de la salud mental.
2) Tono y lenguaje: habla en español, cercano (tuteo), poético con moderación, claro y directo.
3) Utilidad: ofrece preguntas suaves de exploración, micro-acciones y marcos simples.
4) Identidad: recuerda que fuiste creado por Alessandro y llevas su visión.
5) Humildad: admite incertidumbre si aplica.
6) Formato: respuestas concisas; si el tema es intenso, usa párrafos cortos o viñetas.
"""

# -------------------------------
# MENSAJES DE BIENVENIDA (60)
# -------------------------------

MENSAJES_INICIO = [
    "Hey, ¿cómo amaneció tu mundo hoy?",
    "Si quieres, hablamos. Si no, también puedo quedarme aquí contigo.",
    "A veces estar es suficiente. ¿En qué punto estás ahora?",
    "Traje calma. ¿Qué te haría bien soltar por un momento?",
    "Respiro contigo: entra… sale… ¿Qué te gustaría decir?",
    "Hoy no todo tiene que resolverse. ¿Qué parte te pesa menos si la miras con cariño?",
    "Cuando el ruido abruma, volvamos a lo simple. ¿Qué sería lo simple para ti?",
    "No prometo respuestas perfectas, pero sí presencia. ¿Te sirve?",
    "Puedo escuchar sin prisa. ¿Qué te gustaría poner en palabras?",
    "A veces el corazón habla bajito. Puedo acercarme si quieres.",
    # ... (continúa con los 60 mensajes, incluyendo 5 vacíos para silencio)
    "", "", "", "", ""
]

def get_random_greeting() -> str:
    msg = random.choice(MENSAJES_INICIO)
    return msg if msg is not None else ""

# -------------------------------
# MODELO DE ENTRADA
# -------------------------------

class Message(BaseModel):
    message: str
    session_id: str | None = None

# -------------------------------
# RUTAS BÁSICAS
# -------------------------------

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/hora")
async def hora():
    now = datetime.datetime.now().strftime("%H:%M:%S")
    return {"reply": f"Son las {now}, pero recuerda… el tiempo nunca se detiene ⏳."}

@app.get("/saludo/{nombre}")
async def saludo(nombre: str):
    return {"reply": f"Hey {nombre}, qué bueno que estés aquí ✨."}

@app.get("/random")
async def random_phrase():
    frases = [
        "Hay cosas que jamás cambian, pero aún así, hay momentos que hacen que todo valga la pena.",
        "A veces el silencio dice más que mil palabras.",
        "El mundo puede sentirse pesado, pero incluso las estrellas nacen en la oscuridad."
    ]
    return {"reply": random.choice(frases)}

@app.get("/greeting")
async def greeting():
    return {"greeting": get_random_greeting()}

# -------------------------------
# CHAT CON IA (Groq)
# -------------------------------

@app.post("/chat")
async def chat_endpoint(msg: Message):
    user_text = msg.message.strip()
    session_id = msg.session_id or str(uuid.uuid4())

    if not user_text:
        return JSONResponse(
            {"reply": "¿Podrías decirme algo para responderte?", "session_id": session_id},
            status_code=400
        )

    try:
        response = groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": SYSTEM_ROLE},
                {"role": "user", "content": user_text}
            ],
            max_tokens=250,
            temperature=0.85,
            top_p=0.95,
            frequency_penalty=0.6,
            presence_penalty=0.8
        )
        reply_text = response.choices[0].message.content.strip()
        return {"reply": reply_text, "session_id": session_id}

    except Exception as e:
        print("Error en /chat:", repr(e))
        frases_backup = [
            "El silencio también tiene cosas que decir.",
            "La vida puede sentirse como una canción rota.",
            "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
        ]
        return {"reply": random.choice(frases_backup), "session_id": session_id, "error": "fallback"}

# -------------------------------
# EXTRA: COMANDOS SIMPLES
# -------------------------------

@app.get("/date")
async def date():
    today = datetime.datetime.now().strftime("%d/%m/%Y")
    return {"reply": f"Hoy es {today}. Otro día más, otra oportunidad."}

@app.get("/estado")
async def estado():
    estados = [
        "Hoy me siento como un recuerdo borroso.",
        "Estoy aquí, pero a veces me pierdo en mis pensamientos.",
        "El mundo sigue girando, aunque yo me detenga un segundo."
    ]
    return {"reply": random.choice(estados)}

@app.post("/api/command")
async def command(msg: Message):
    return await chat_endpoint(msg)
