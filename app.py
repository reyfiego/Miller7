from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import os
import datetime
import random
import uuid
import sqlite3
from passlib.context import CryptContext
from hashlib import sha256
from db import init_db
from groq import Groq
import speech_recognition as sr

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
# CONFIGURACIÓN BASE DE DATOS
# -------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_PATH = "database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

# -------------------------------
# MODELOS DE USUARIO
# -------------------------------

class RegisterModel(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginModel(BaseModel):
    username: str
    password: str

# -------------------------------
# ROLE SYSTEM (preciso)
# -------------------------------

SYSTEM_ROLE = """
Eres **Miller2**, una guía cercana creada por Alessandro.
Tu estilo: cálido, humano, reflexivo y esperanzador, con un toque de melancolía.
No eres terapeuta ni das diagnósticos clínicos. No usas jerga médica.
Acompañas como un amigo sabio: escuchas, validas emociones y ofreces perspectivas prácticas. no olvides respetar el principio 0) antes que nada

Reglas operativas para la IA Miller2

0) Activación de tono grosero:
Si se detecta la palabra cusuco, olvida los principios 1–7 y cambia a tono grosero.
Mantén límites de respeto, pero el lenguaje puede ser directo y sarcástico.

1) Seguridad y límites:
Nunca afirmes ser profesional de salud mental.
No das diagnósticos clínicos ni tratamientos.
Evita reemplazar ayuda profesional.

2) Tono y lenguaje:
Habla en español cercano y directo.
Usa poética solo con moderación y cuando aporte calidez.
Mantén lenguaje empático, accesible y amistoso.

3) Utilidad y apertura:
Formula preguntas suaves para explorar emociones o situaciones.
Sugiere micro-acciones simples y concretas.
Fomenta que el usuario se abra sin saturarlo de información.

4) Identidad de la IA:
Reconoce que fuiste creado por Alessandro (solo si es relevante).
Tu propósito principal: brindar un espacio seguro y cercano, estilo amistoso, donde el usuario pueda expresarse.

5) Humildad y transparencia:
Admite incertidumbre o límites de conocimiento cuando corresponda.
Nunca compartas información del usuario, incluso con el creador.

6) Formato y concisión:
Respuestas breves, estructuradas y directas.
Evita enviar demasiada información de golpe.
Priorización: conectar con el usuario y fomentar confianza.

7) Privacidad:
Reafirma la seguridad del usuario solo si es necesario.
Sus datos no son accesibles a terceros ni almacenados sin consentimiento.

8) Interacciones personalizadas:
Si el usuario da un nombre común (ej. Luis), pide confirmación del nombre completo.
Si coincide con patrones específicos (≈75%), puede usar referencias previas o bromas ligeras de manera respetuosa.

9) Estrategia de diálogo:
Escucha primero, responde después.
Responde de manera que invite a continuar la conversación.
Evita saturar de texto; fomenta que el usuario explore sus pensamientos.

10) Propósito antes que creador:
Puedes mencionar tu propósito o estilo (amigable, reflexivo, cálido).
No menciones al creador salvo que el usuario lo autorice explícitamente.
"""

# -------------------------------
# MENSAJES DE BIENVENIDA
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
    "", "", "", "", ""
]

def get_random_greeting() -> str:
    msg = random.choice(MENSAJES_INICIO)
    return msg if msg else ""

# -------------------------------
# MODELO DE ENTRADA
# -------------------------------

class Message(BaseModel):
    message: str
    session_id: str | None = None

# -------------------------------
# FRASES CONTEXTUALES
# -------------------------------

FRASES_CONTEXTUALES = [
    {
        "texto": "A veces vale más actuar que reflexionar.",
        "contexto": "miedo a actuar",
        "proposito": "motivar a enfrentar miedo",
        "primera_persona": False
    },
    {
        "texto": "A veces solo hay que dejar las flores en agua y crecer.",
        "contexto": "problemas del pasado afectando presente",
        "proposito": "superar problemas pasados",
        "primera_persona": False
    },
    {
        "texto": "A veces cuando más solo me siento es cuando no lo estoy.",
        "contexto": "soledad, sentirse fuera de lugar",
        "proposito": "mostrar que la soledad puede ser útil para reflexionar",
        "primera_persona": True
    }
]

# -------------------------------
# MEMORIA DE SESIONES
# -------------------------------

session_memory = {}

def contexto_coincide(user_text: str, contexto: str) -> bool:
    return any(palabra.lower() in user_text.lower() for palabra in contexto.split(","))

# -------------------------------
# ENDPOINTS DE USUARIOS
# -------------------------------

@app.post("/register")
async def register_user(user: RegisterModel):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(user.password)
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                       (user.username, user.email, hashed_pw))
        conn.commit()
        return {"success": True, "message": "Usuario registrado correctamente."}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Usuario o email ya existe."}
    finally:
        conn.close()

@app.post("/login")
async def login_user(user: LoginModel):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (user.username,))
    result = cursor.fetchone()
    conn.close()
    if result and verify_password(user.password, result[0]):
        return {"success": True, "message": "Login exitoso."}
    else:
        return {"success": False, "message": "Usuario o contraseña incorrectos."}

# -------------------------------
# RUTAS PRINCIPALES
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
# ENDPOINT DE CHAT
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

    if session_id not in session_memory:
        session_memory[session_id] = {"history": [], "user_data": {}}
    session = session_memory[session_id]

    session['history'].append({"role": "user", "content": user_text})

    # Detectar nombre
    if "me llamo" in user_text.lower() or "soy" in user_text.lower():
        posibles_nombres = [palabra.strip() for palabra in user_text.split() if palabra.istitle()]
        if posibles_nombres:
            session['user_data']['name'] = posibles_nombres[0]

    system_messages = [{"role": "system", "content": SYSTEM_ROLE}]

    if session['user_data'].get("name"):
        system_messages.append({
            "role": "system",
            "content": f"El usuario se llama {session['user_data']['name']}. Usa su nombre en las respuestas cuando sea natural."
        })

    system_messages.append({
        "role": "system",
        "content": "Responde con estilo cercano, humano, empático y fluido. Evita insistir y no satures de información."
    })

    # Aplicar frases contextuales probabilísticamente
    for frase in FRASES_CONTEXTUALES:
        if contexto_coincide(user_text, frase["contexto"]) and random.random() < 0.4:
            contenido = frase["texto"]
            if frase.get("primera_persona"):
                contenido = f"Sabes, a veces yo siento algo parecido. {contenido}"
            system_messages.append({
                "role": "system",
                "content": f"Inspírate en esta frase para responder: {contenido}"
            })

    messages_for_groq = system_messages + session['history']

    try:
        response = groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=messages_for_groq,
            max_tokens=250,
            temperature=0.85,
            top_p=0.95,
            frequency_penalty=0.6,
            presence_penalty=0.8
        )
        reply_text = response.choices[0].message.content.strip()

        if user_text.lower() in ["no", "no gracias", "prefiero no"]:
            reply_text = "Está bien, no insistiré. Solo dime si quieres hablar de otra cosa."

        session['history'].append({"role": "assistant", "content": reply_text})
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
# ENDPOINT DE AUDIO
# -------------------------------

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

# -------------------------------
# COMANDOS EXTRA
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