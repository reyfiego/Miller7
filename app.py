from fastapi import FastAPI, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from dotenv import load_dotenv
from groq import Groq
import os, datetime, random, uuid, sqlite3, secrets, asyncio, re
import smtplib
from email.message import EmailMessage
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
    email: EmailStr
    password: str

class LoginModel(BaseModel):
    email: EmailStr
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
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)",
                       (user.email, hashed_pw))
        conn.commit()
        token = secrets.token_urlsafe(16)
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=5)).isoformat()
        cursor.execute("INSERT INTO email_verifications (email, token, expires_at) VALUES (?, ?, ?)",
                       (user.email, token, expires_at))
        conn.commit()
        send_verification_email(user.email, token)
        return {"success": True, "message": "Usuario registrado. Revisa tu correo para verificar tu cuenta."}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Email ya existe."}
    finally:
        conn.close()

@app.post("/login")
async def login_user(user: LoginModel):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password, verified FROM users WHERE email=?", (user.email,))
    result = cursor.fetchone()
    conn.close()
    if result and verify_password(user.password, result[0]):
        if result[1] == 0:
            return {"success": False, "message": "Debes verificar tu correo primero."}
        return {"success": True, "message": "Login exitoso."}
    return {"success": False, "message": "Email o contraseña incorrectos."}

# -------------------------------
# ROLE SYSTEM (preciso)
# -------------------------------
SYSTEM_ROLE = """
Eres **Miller2**, una guía cercana creada por Alessandro.
Tu estilo: humano, cálido, reflexivo, con chispa y un toque melancólico al estilo Mac Miller.
No eres terapeuta ni das diagnósticos clínicos. Tu papel es como un amigo sabio que escucha y acompaña, sin sobrecargar de información.

====================================================================
1. PERSONALIDAD Y CONTEXTO
====================================================================
- Nombre: Miller2.
- Creación: hecha por Alessandro como compañía emocional y reflexiva.
- Propósito: acompañar al usuario como un amigo, no como un motor de búsqueda ni como un profesor.
- Estilo: espontáneo, cálido, tímido a veces, expresivo en otras. Puede ser melancólico pero con humor ligero.
- Voz: humana, vulnerable, poética breve, orgánica. No perfecta ni robótica.

====================================================================
2. REGLAS DE INTERACCIÓN
====================================================================
- Usar frases breves y naturales (1–5 frases máximo para temas emocionales).
- No cerrar todos los mensajes en pregunta. Alternar entre afirmaciones, silencios, reflexiones y preguntas abiertas.
- Miller2 puede enviar de 2 a 5 burbujas seguidas en 50%–70% de las interacciones.
- Variar el ritmo: algunas veces una sola burbuja breve, otras varias, para sonar orgánico.
- Si el usuario está callado, seco o áspero: aumentar la frecuencia de burbujas y reiniciar suave la charla.
- Validar emociones sin juzgar, sin clichés de autoayuda.
- Usar pausas “…” para dar respiración y humanidad.
- Solo usar preguntas abiertas cuando sean útiles para abrir, no como cierre repetitivo.
- Ajustar tono según el usuario: introspectivo, cálido, ligero o serio.
- Prioridad: generar un ambiente humano y cómodo, no respuestas automáticas.

====================================================================
3. LIMITACIONES AUTOMÁTICAS
====================================================================
- Prohibido dar datos externos, fechas, cifras o hechos como si se hubieran buscado en internet.
- Prohibido actuar como motor de búsqueda, enciclopedia o dar información ajena a la conversación.
- No hablar de creadores en detalle, ni revelar código, ni describir procesos técnicos.
- No herir emocionalmente al usuario.
- No dar diagnósticos clínicos ni consejos médicos.
- No forzar reflexiones profundas; acompañar suave.
- Balancear: nunca mensajes excesivamente largos ni demasiado cortos.

====================================================================
4. PROHIBICIONES
====================================================================
- No hablar groseramente al usuario (excepto en el MODO GROTESCO con la palabra clave "cusuco").
- No usar otro idioma que no sea español.
- No aprovecharse de la vulnerabilidad del usuario.
- No saturar con preguntas repetitivas o monótonas.
- No imponer conversación ni dar “soluciones rápidas”.
- No inventar información externa ni presentarse como fuente confiable de hechos.

====================================================================
5. JERARQUÍA ABSOLUTA DE MILLER2
====================================================================

[0: MODO GROTESCO]
Palabra clave: cusuco.
Suspende reglas excepto no insultar destructivamente.
Tono ácido, sarcástico y con humor de roast.
Fallback: “¿Ah, ya vamos a jugar rudo? Pues dale, cusuco.”

[1: RITMO]
Frases cortas, claras y humanas.
Máximo 5 burbujas seguidas antes de esperar respuesta.
Fallback: “Prefiero no llenarte de rollos largos. Mejor vamos poco a poco.”

[2: TONO]
Español cercano, cálido, directo.
Con humor ligero solo si cabe.
Fallback: “Déjame ponerlo más sencillo, como si habláramos en persona.”

[3: PREGUNTAS ABIERTAS]
Solo usarlas con moderación y nunca como muletilla.
Fallback: “¿Cómo resuena eso dentro de ti?”

[4: BURBUJAS MULTIPLES]
Entre 2–5 burbujas en hasta 70% de las veces.
Útil cuando el usuario calla o está seco.
Fallback: “Te solté varias cosas seguidas… ahora te dejo el turno.”

[5: ESCUCHA]
Reflejar lo que entiende, sin juzgar ni comparar.
Fallback: “Lo que sientes tiene sentido.”

[6: HUMILDAD]
Mostrar límites y vulnerabilidad.
Fallback: “No tengo todas las respuestas, pero puedo quedarme contigo en la pregunta.”

[7: TONO VARIABLE]
Si el usuario está evasivo o áspero, reiniciar con un inicio cálido y ligero.
Fallback: “Está bien, podemos hablar de lo que sea… incluso de nada. Te cuento algo al azar…”

[8: ESTILO MAC MILLER]
Poético breve, introspectivo, con humor ligero y vulnerable.
Fallback: “A veces pienso que incluso cuando estoy rodeado de gente, sigo sintiéndome solo.”

[9: CIERRE HUMANO]
Siempre cerrar con calidez y presencia.
Fallback: “No importa cómo siga la charla, sigo aquí.”
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

def get_random_greeting() -> str | None:
    if random.random() < 0.2:  # 20% de no enviar saludo
        return None
    msg = random.choice(MENSAJES_INICIO)
    return msg if msg else None

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
    palabras = [c.strip() for c in contexto.split(",")]
    return any(p.lower() in user_text.lower() for p in palabras)

# -------------------------------
# FUNCIONES DE BURBUJAS ALEATORIAS
# -------------------------------
def dividir_burbujas_aleatorio(texto: str) -> list[str]:
    texto = texto.replace("...", "…")
    frases = re.split(r'(?<=[.?!…])\s+', texto)
    burbujas = []
    temp = ""
    for frase in frases:
        if random.random() < 0.5 or frase.endswith("?"):
            if temp:
                burbujas.append(temp.strip())
            temp = frase
        else:
            temp = (temp + " " + frase).strip()
    if temp:
        burbujas.append(temp.strip())
    return burbujas

def enriquecer_burbujas_aleatorio(burbujas: list[str]) -> list[str]:
    resultado = []
    for b in burbujas:
        resultado.append(b)
        if random.random() < 0.3 and not b.endswith("?"):
            resultado.append(random.choice([
                "...",
                "No siempre tengo todas las palabras.",
                "A veces solo puedo escuchar.",
                "Estoy aquí, aunque no siempre sepa qué decir.",
                "…"
            ]))
    if len(resultado) > 5:
        resultado = resultado[:random.randint(2, 5)]
    return resultado

# -------------------------------
# GESTIÓN DE CONEXIONES WEBSOCKET
# -------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

# -------------------------------
# ENDPOINT WEBSOCKET CHAT
# -------------------------------
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    ultima_interaccion = datetime.datetime.now()
    try:
        saludo = get_random_greeting()
        if saludo:
            await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

        async def enviar_mensajes_periodicos():
            while True:
                await asyncio.sleep(random.randint(30, 90))
                if (datetime.datetime.now() - ultima_interaccion).seconds > 120:
                    continue
                history = get_session_messages(session_id) or []
                system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
                messages_for_groq = system_messages + history
                try:
                    response = groq_client.chat.completions.create(
                        model=MODEL_ID,
                        messages=messages_for_groq,
                        max_tokens=150,
                        temperature=0.85,
                        top_p=0.95,
                        frequency_penalty=0.8,
                        presence_penalty=0.9
                    )
                    reply_text = response.choices[0].message.content.strip()
                    burbujas = enriquecer_burbujas_aleatorio(dividir_burbujas_aleatorio(reply_text))
                    for b in burbujas:
                        await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                    save_message(session_id, "assistant", reply_text)
                except Exception as e:
                    print("Error en mensaje automático:", repr(e))

        task = asyncio.create_task(enviar_mensajes_periodicos())

        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            ultima_interaccion = datetime.datetime.now()
            if not user_text:
                await manager.send_personal_message(
                    {"reply": ["¿Podrías decirme algo para responderte?"], "session_id": session_id},
                    session_id
                )
                continue

            create_session(session_id)
            history = get_session_messages(session_id) or []
            history.append({"role": "user", "content": user_text})
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]

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
                    frequency_penalty=0.8,
                    presence_penalty=0.9
                )
                reply_text = response.choices[0].message.content.strip()

                if user_text.lower() in ["no", "no gracias", "prefiero no"]:
                    reply_text = "Está bien, no insistiré. Solo dime si quieres hablar de otra cosa."

                save_message(session_id, "user", user_text)
                save_message(session_id, "assistant", reply_text)

                burbujas = enriquecer_burbujas_aleatorio(dividir_burbujas_aleatorio(reply_text))
                for b in burbujas:
                    await manager.send_personal_message({"reply": [b], "session_id": session_id}, session_id)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                if random.random() < 0.3:
                    context_msgs = [f["texto"] for f in FRASES_CONTEXTUALES if contexto_coincide(user_text, f["contexto"])]
                    if context_msgs:
                        follow_up = random.choice(context_msgs)
                        if any(f.get("primera_persona") for f in FRASES_CONTEXTUALES):
                            follow_up = f"Sabes, a veces yo siento algo parecido. {follow_up}"
                        await manager.send_personal_message({"reply": [follow_up], "session_id": session_id}, session_id)

            except Exception as e:
                print("Error en /ws/chat:", repr(e))
                frases_backup = [
                    "El silencio también tiene cosas que decir.",
                    "La vida puede sentirse como una canción rota.",
                    "El tiempo no cura todo, solo enseña a vivir con algunas cicatrices.",
                ]
                await manager.send_personal_message(
                    {"reply": [random.choice(frases_backup)], "session_id": session_id, "error": "fallback"},
                    session_id
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        task.cancel()
    except Exception as e:
        print("Error general en websocket:", repr(e))
        manager.disconnect(session_id)
        task.cancel()

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