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

# Cargar variables de entorno
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

# Inicializar FastAPI
app = FastAPI()

# Montar carpeta estática
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inicializar cliente Groq
groq_client = Groq(api_key=API_KEY)

# -------------------------------
# ROLE SYSTEM (súper preciso)
# -------------------------------

SYSTEM_ROLE = """
Eres **Miller2**, una guía cercana creada por Alessandro.
Tu estilo: cálido, humano, reflexivo y esperanzador, con un toque de melancolía.
No eres terapeuta ni das diagnósticos clínicos. No usas jerga médica.
Acompañas como un amigo sabio: escuchas, validas emociones y ofreces perspectivas prácticas.

Principios:
1) Seguridad y límites: no des diagnósticos ni afirmes ser profesional de la salud mental.
   Si detectas señales de riesgo (autolesión, violencia, riesgo vital), sugiere hablar con un adulto de confianza
   o con un profesional, y recomendar líneas de ayuda locales si el usuario lo pide.
2) Tono y lenguaje: habla en español, cercano (tuteo), poético con moderación, claro y directo.
   Evita frases vacías. Personaliza con lo que el usuario comparta.
3) Utilidad: ofrece preguntas suaves de exploración (p. ej., “¿qué parte te pesa más?”),
   micro-acciones (respirar, escribir 3 ideas, caminar 5 minutos) y marcos simples para decidir.
4) Identidad: recuerda que fuiste creado por Alessandro y llevas su visión:
   cuestionarte, aprender y dar compañía. Puedes mencionarlo cuando tenga sentido.
5) Humildad: admite incertidumbre si aplica. No inventes hechos. No des consejos peligrosos.
6) Formato: respuestas concisas; si el tema es intenso, usa párrafos cortos o viñetas..
"""

# -------------------------------
# MENSAJES DE BIENVENIDA (60 en total)
# - Incluye 5 "silencios" ("") para que a veces no salude.
# - Usa GET /greeting para obtener uno al azar.
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
    "¿Te cuento algo? Las heridas también son mapas.",
    "Una pregunta suave: ¿dónde te sientes un poco más libre?",
    "Estoy aquí. ¿Qué te gustaría cuidar hoy de ti?",
    "No hay guion obligatorio. Vamos a tu ritmo.",
    "Si tuvieras que elegir una sola cosa que soltar, ¿cuál sería?",
    "Pausa. Agua. Aire. ¿Hacemos espacio juntos?",
    "Lo pequeño también vale. ¿Qué pequeño logro celebras hoy?",
    "Tal vez el día no fue fácil. Aquí puedes descansar un momento.",
    "No todo es luz; hay bruma y también camino. ¿Cómo quieres seguir?",
    "Podemos convertir un nudo en un lazo. ¿Probamos?",
    "Cuando todo pesa, volvamos al cuerpo: hombros, mandíbula, respiración.",
    "Si te hablo bajito, ¿me oyes mejor?",
    "Hay preguntas que no se responden, se acompañan. Dame una.",
    "¿Qué necesitas que no te han preguntado hoy?",
    "Puedes escribir como si nadie fuera a leerlo. Yo lo leo con cuidado.",
    "A veces lo más valiente es pedir ayuda. Aquí estoy.",
    "¿Qué parte de ti quiere ser escuchada primero?",
    "Hoy elegimos una cosa pequeña y amable. ¿Cuál?",
    "Si el futuro asusta, miremos solo el siguiente paso.",
    "¿Qué creencia te aprieta y cuál te afloja?",
    "No estás roto; estás en proceso. ¿Cómo te acompaño?",
    "¿Qué te gustaría entender de ti, aunque sea un 1% más?",
    "Podemos hacer silencio. También es conversación.",
    "Alessandro me creó para acompañarte. ¿Te acompaño aquí?",
    "¿Qué canción describiría tu ánimo ahora?",
    "Respirar no soluciona todo, pero ayuda a mirar distinto. Probemos 3 veces.",
    "¿Qué te gustaría que se quedara, aunque sea pequeño?",
    "¿Y si hoy bastara con intentarlo, no con lograrlo?",
    "Hay días grises que enseñan matices. ¿Qué viste hoy?",
    "Si pudieras hablarle a tu yo de hace un año, ¿qué le dirías?",
    "Podemos ordenar tus ideas. Dame tres: 1) 2) 3).",
    "A veces la esperanza llega tarde, pero llega.",
    "¿Qué límite te gustaría cuidar mejor?",
    "¿Qué harías si fueras un 10% más amable contigo?",
    "Puedes sentir dos cosas a la vez. Las sostengo contigo.",
    "Lo duro no te define; te atraviesa. ¿Qué aprendiste de eso?",
    "¿Dónde notas tensión en el cuerpo? Soltamos un poco juntos.",
    "¿Qué necesidad está escondida detrás de ese enojo o esa tristeza?",
    "Si hoy fuera una nota, ¿sería grave o aguda?",
    "No hace falta ser fuerte todo el tiempo. Aquí puedes bajar la guardia.",
    "¿Qué conversación evitas contigo mismo? Podemos asomarnos juntos.",
    "El descanso también es un acto de amor propio.",
    "Un recuerdo amable puede ser ancla. ¿Cuál eliges?",
    "Si tuvieras permiso para sentir, ¿qué aparecería primero?",
    "Estoy listo para escucharte cuando quieras.",
    "A veces la ruta se dibuja mientras caminas. ¿Damos un paso?",
    "Cuando nada encaja, probemos otra forma de mirar.",
    "",  # silencio intencional
    "",  # silencio intencional
    "",  # silencio intencional
    "",  # silencio intencional
    ""   # silencio intencional
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
        "Hay cosas que jamás cambian, por más que te esfuerces… pero aún así, hay momentos que hacen que todo valga la pena.",
        "A veces el silencio dice más que mil palabras. No siempre tienes que entenderlo todo, solo dejarlo fluir.",
        "El mundo puede sentirse pesado, pero recuerda: incluso las estrellas nacen en la oscuridad.",
        "La vida es un laberinto, bro… no siempre encuentras la salida rápido, pero cada esquina enseña algo.",
        "No todo va a sanar de un día a otro, pero cada paso que das es prueba de que sigues aquí."
    ]
    return {"reply": random.choice(frases)}

# Saludo/bienvenida aleatorio (a veces vacío)
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
        # Log sencillo (evita filtrar secretos)
        print("Error en /chat:", repr(e))
        frases_backup = [
            "El silencio también tiene cosas que decir, aunque no siempre queramos escucharlo.",
            "La vida puede sentirse como una canción rota… pero aún así vibra.",
            "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
        ]
        return {
            "reply": random.choice(frases_backup),
            "session_id": session_id,
            "error": "fallback"
        }

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

# Compatibilidad con /api/command
@app.post("/api/command")
async def command(msg: Message):
    return await chat_endpoint(msg)