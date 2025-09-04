from fastapi import FastAPI, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from dotenv import load_dotenv
import os, datetime, random, uuid, sqlite3, secrets, asyncio, re
import smtplib
from email.message import EmailMessage
import speech_recognition as sr

from groq import Groq
from db import init_db, DB_PATH, create_session, save_message, get_session_messages
from millercore.corazon import SYSTEM_ROLE, MENSAJES_INICIO, get_random_greeting, FRASES_CONTEXTUALES
from millercore.burbujas_texto import dividir_burbujas_aleatorio, enriquecer_burbujas_aleatorio


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
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (user.email, hashed_pw))
        conn.commit()
        token = secrets.token_urlsafe(16)
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=5)).isoformat()
        cursor.execute("INSERT INTO email_verifications (email, token, expires_at) VALUES (?, ?, ?)", (user.email, token, expires_at))
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
