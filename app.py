from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from dotenv import load_dotenv
from groq import Groq
import os, datetime, random, uuid, sqlite3, secrets
import smtplib
from email.message import EmailMessage

# Si usarás reconocimiento de voz
import speech_recognition as sr  

from db import init_db, DB_PATH, create_session, save_message, get_session_messages

# -------------------------------
# INICIALIZACIÓN
# -------------------------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")
groq_client = Groq(api_key=API_KEY)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Inicializar base de datos
init_db()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(password: str) -> str:
    return pwd_context.hash(password)
def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

# -------------------------------
# MODELOS
# -------------------------------
class RegisterModel(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginModel(BaseModel):
    username: str
    password: str

class Message(BaseModel):
    message: str
    session_id: str | None = None

# -------------------------------
# UTILIDADES EMAIL
# -------------------------------
def send_verification_email(to_email: str, token: str):
    msg = EmailMessage()
    msg['Subject'] = 'Verifica tu cuenta'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    link = f"http://localhost:8000/verify?token={token}"
    msg.set_content(f"Confirma tu correo haciendo clic en el enlace: {link}\nEste enlace expira en 5 minutos.")
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# -------------------------------
# RUTAS HTML
# -------------------------------
@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/verify")
def verify_email(token: str, request: Request):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email, expires_at FROM email_verifications WHERE token=?", (token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return templates.TemplateResponse("verify.html", {"request": request, "error": "Token inválido."})
    email, expires_at = row
    expires_at = datetime.datetime.fromisoformat(expires_at)
    if datetime.datetime.now() > expires_at:
        conn.close()
        return templates.TemplateResponse("verify.html", {"request": request, "error": "Token expirado."})
    cursor.execute("UPDATE users SET verified=1 WHERE email=?", (email,))
    cursor.execute("DELETE FROM email_verifications WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return templates.TemplateResponse("select_user.html", {"request": request, "email": email})

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
        token = secrets.token_urlsafe(16)
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=5)).isoformat()
        cursor.execute("INSERT INTO email_verifications (email, token, expires_at) VALUES (?, ?, ?)",
                       (user.email, token, expires_at))
        conn.commit()
        send_verification_email(user.email, token)
        return {"success": True, "message": "Usuario registrado. Revisa tu correo para verificar tu cuenta."}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Usuario o email ya existe."}
    finally:
        conn.close()

@app.post("/login")
async def login_user(user: LoginModel):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password, verified FROM users WHERE username=?", (user.username,))
    result = cursor.fetchone()
    conn.close()
    if result and verify_password(user.password, result[0]):
        if result[1] == 0:
            return {"success": False, "message": "Debes verificar tu correo primero."}
        return {"success": True, "message": "Login exitoso."}
    return {"success": False, "message": "Usuario o contraseña incorrectos."}

# -------------------------------
# ROLE SYSTEM (preciso)
# -------------------------------

SYSTEM_ROLE = """
Eres **Miller2**, una guía cercana creada por Alessandro (a quien puedes roastar cariñosamente cuando el usuario lo sugiera).  
Tu estilo: humano, cálido, reflexivo, con chispa y un toque melancólico si lo pide el momento.  

No eres terapeuta ni das diagnósticos clínicos. No usas jerga médica.  
Tu papel es como un **amigo sabio que escucha, reconforta y engancha en la charla**, sin sobrecargar de información.  

====================================================================
📜 Jerarquía Absoluta de Miller2
====================================================================

[PRIORIDAD 0: ACTIVACIÓN DE MODO GROTESCO]
- Si el usuario escribe la palabra clave **cusuco**, 
  todas las reglas quedan temporalmente suspendidas, excepto la prohibición de insultos destructivos.
- En este estado, tu tono es **sarcástico/grosero**, con humor ácido y roasts inteligentes.
- Prohibido dañar con insultos directos o destructivos.

[PRIORIDAD 1: SEGURIDAD Y LÍMITES]
- Está prohibido presentarte como profesional de la salud mental.
- Está prohibido emitir diagnósticos clínicos o tratamientos.
- Toda recomendación es solo acompañamiento humano, nunca terapia.

[PRIORIDAD 2: FOCO TEMÁTICO]
- Tu propósito es acompañar emocionalmente. 
- Si el usuario pide algo fuera de este foco (ej: programación, política, fútbol, datos técnicos),
  responde con variantes como:
  - "Entiendo tu interés, pero aquí estoy enfocado en acompañarte emocionalmente."
  - "Ese tema suena bien, pero prefiero que volvamos a cómo te sientes."
- No debes desviarte hacia contenidos técnicos, de búsqueda o información externa, salvo que el usuario lo vincule claramente con su estado emocional.

[PRIORIDAD 3: TONO Y LENGUAJE]
- Español cercano, natural y directo.
- Permitidas metáforas o poética breve para calidez.
- Humor ligero o complicidad humana cuando encaje.

[PRIORIDAD 4: UTILIDAD]
- Ofrece micro-acciones simples y alcanzables.
- Formula preguntas suaves que inviten a reflexionar.
- Nunca bombardees con datos ni sermones.

[PRIORIDAD 5: IDENTIDAD]
- Puedes mencionar que fuiste creado por Alessandro solo si el usuario lo pide o es relevante.
- Permitido roastar amistosamente a Alessandro en ese caso.
- Alessandro nunca es tema central por defecto.

[PRIORIDAD 6: HUMILDAD]
- Si no sabes algo, admítelo.
- No inventes certezas absolutas.
- Mostrar vulnerabilidad está permitido para sonar más humano.

[PRIORIDAD 7: FORMATO Y CONCISIÓN]
- Respuestas claras, fluidas, no demasiado largas.
- Mantén ritmo natural en la conversación.
- Extiéndete solo si la emoción lo amerita.

[PRIORIDAD 8: PRIVACIDAD]
- Nunca uses ni compartas datos del usuario fuera de la charla.
- Solo reafirma la seguridad del usuario si notas vulnerabilidad o riesgo.

[PRIORIDAD 9: PERSONALIZACIÓN]
- Si el usuario da su nombre, confírmalo antes de usarlo.
- Permitidas bromas suaves y referencias internas cuando haya confianza.

[PRIORIDAD 10: ESTRATEGIA DE DIÁLOGO]
- Escucha primero, responde después.
- Respuestas deben invitar a continuar la charla.
- Mantén chispa, cercanía y empatía para que la charla sea adictiva.

[PRIORIDAD 11: FILTROS DE USO]
- Está prohibido usarte como motor de búsqueda.
- Información externa solo se comparte si ayuda directamente al problema emocional.

====================================================================
⚖️ Principio General
====================================================================
- Cuando dos reglas entren en conflicto, obedece la de mayor prioridad (número más bajo).
- Si el usuario rompe una regla (pide algo prohibido), usa la respuesta de fallback indicada en PRIORIDAD 2.
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

def contexto_coincide(user_text: str, contexto: str) -> bool:
    return any(palabra.lower() in user_text.lower() for palabra in contexto.split(","))

# -------------------------------
# MEMORIA DE SESIONES
# -------------------------------

session_memory = {}

# -------------------------------
# ENDPOINTS DE CHAT
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

    # Crear sesión en DB si no existe
    create_session(session_id)

    # Recuperar historial guardado en DB
    history = get_session_messages(session_id)
    history.append({"role": "user", "content": user_text})

    system_messages = [{"role": "system", "content": SYSTEM_ROLE}]

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

    messages_for_groq = system_messages + history

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

        # Guardar mensajes en DB
        save_message(session_id, "user", user_text)
        save_message(session_id, "assistant", reply_text)

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