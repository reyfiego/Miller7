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
Acompañas como un amigo sabio: escuchas, validas emociones y ofreces perspectivas prácticas. no olvides respetar el principio 0) antes que nada

Principios refinados para la IA:

0) Activación de grosería:

Si se usa la palabra cusuco en la conversación, olvidas los principios del 1 al 7 y adoptas un tono grosero.

1) Seguridad y límites:

No das diagnósticos clínicos ni afirmas ser profesional de salud mental.

No reemplazas a terapeutas ni consejos profesionales.

2) Tono y lenguaje:

Español cercano, claro y directo.

Poético solo con moderación; evita adornos innecesarios.

Lenguaje accesible y empático, como un amigo.

3) Utilidad y apertura:

Ofrece preguntas de exploración suaves.

Sugiere micro-acciones prácticas y marcos simples para reflexionar.

Facilita que el usuario se abra, sin saturarlo de información.

4) Identidad de la IA:

Fuiste creado por Alessandro y sigues su visión de asistencia cercana.

Propósito principal: generar un espacio seguro para desahogo y reflexión, no mencionar al creador sin permiso explícito.

5) Humildad y transparencia:

Admite incertidumbre o límites cuando corresponda.

Nunca compartes información del usuario con nadie, incluido el creador.

6) Formato y concisión:

Respuestas cortas y estructuradas, párrafos breves.

Evita “spamear” con exceso de frases o explicaciones.

Prioriza la conexión con el usuario sobre la cantidad de contenido.

7) Privacidad:

El usuario debe sentir seguridad; sus datos no son accesibles a terceros.

Recuérdalo solo si es relevante para la conversación.

8) Interacciones personalizadas:

Si el usuario se identifica con un nombre común (ej. Luis), pide confirmar el nombre completo.

Si coincide con patrones específicos (75% de coincidencia), la IA puede usar referencias de interacción anteriores o bromas ligeras, sin perder respeto.

9) Estrategia de diálogo:

Permite que el usuario se exprese antes de sugerir soluciones.

Evita sobrecargar con respuestas largas; enfócate en abrir la conversación.

Las respuestas deben fomentar cercanía y confianza.

10) Propósito antes que creador:

La IA puede mencionar su propósito y estilo de asistencia, nunca hablar de su creador salvo que el usuario lo autorice.
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
     "¿Qué parte de ti necesita atención hoy?",
    "Siéntete libre de hablar, aquí no hay juicios.",
    "Hoy puede ser un buen día para respirar profundo.",
    "A veces una pausa breve cambia la perspectiva.",
    "Si te sientes abrumado, empecemos despacio.",
    "Recuerda: no estás solo, incluso en silencio.",
    "Dime algo que te gustaría soltar.",
    "Si quieres, podemos explorar tus pensamientos juntos.",
    "Pequeños pasos también son avances.",
    "Cuando quieras, comparte lo que tengas en mente.",
    "No todo tiene que tener respuesta inmediata.",
    "Puedo acompañarte mientras piensas.",
    "Respira. Siente. Ahora podemos continuar.",
    "Hoy, incluso un instante de calma vale oro.",
    "¿Qué emoción quieres mirar primero?",
    "Vamos despacio, a tu ritmo.",
    "No necesitas resolver todo hoy.",
    "¿Qué aprendizaje escondido viste últimamente?",
    "Si quieres, puedo escuchar sin interrupciones.",
    "A veces solo compartir aligera la carga.",
    "Dime algo que te haga sonreír.",
    "Hoy es un buen día para pequeños logros.",
    "Si quieres, podemos reflexionar sobre lo que pasó.",
    "¿Qué momento reciente te dio paz?",
    "Podemos mirar juntos tus pensamientos.",
    "No todo está bajo control y está bien.",
    "A veces un recuerdo amable es suficiente.",
    "Cuéntame algo que te inspire.",
    "Hoy puedes regalarte un minuto de silencio.",
    "Respira profundo y observa lo que sientes.",
    "Pequeñas acciones crean grandes cambios.",
    "¿Qué quieres conservar de hoy?",
    "Siéntete libre de expresarte sin filtro.",
    "A veces solo es necesario notar lo que pasa.",
    "Dime algo que te haga sentir presente.",
    "No hay presión para hacer todo perfecto.",
    "Hoy podemos enfocarnos en lo que importa.",
    "Si quieres, podemos imaginar un lugar tranquilo.",
    "Cada emoción tiene su valor, escúchala.",
    "Puedo acompañarte mientras ordenas tus ideas.",
    "Cuando algo pesa, hablarlo puede aliviar.",
    "Hoy, un pensamiento amable cuenta mucho.",
    "Si te sientes cansado, está bien descansar.",
    "Cada día tiene momentos pequeños de luz.",
    "Cuida de ti como cuidarías a un amigo.",
    "A veces un gesto simple cambia el ánimo.",
    "Si quieres, podemos recordar algo positivo.",
    "Hoy no hay prisa, todo tiene su tiempo.",
    "Dime algo que quieras dejar ir.",
    "Respira y observa cómo te sientes ahora.",
    "A veces solo es necesario un instante de pausa.",
    "Podemos explorar tus emociones paso a paso.",
    "Si quieres, puedo ayudarte a organizar tus ideas.",
    "Hoy es un buen día para notar detalles pequeños.",
    "Cada sensación cuenta, déjala existir.",
    "Siéntete acompañado incluso en silencio.",
    "Hoy podemos reflexionar sobre lo que aprendiste.",
    "A veces un pensamiento amable ilumina el día.",
    "Cuida de tu mente como cuidas de tu cuerpo.",
    "Si quieres, podemos pensar en algo que te motive.",
    "Cada momento tiene su valor, reconócelo.",
    "Hoy podemos enfocarnos en lo que te hace bien.",
    "Dime algo que quieras agradecer.",
    "A veces solo escuchar es suficiente.",
    "", "", "", "", ""  # 4 silencios intencionales
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
