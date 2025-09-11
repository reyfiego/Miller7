import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from groq import Groq
from supabase import create_client, Client

# -------------------------------
# CARGA DE VARIABLES DE ENTORNO
# -------------------------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")
SECRET_KEY = os.getenv("SECRET_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # acceso completo

if not GROQ_API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ No se encontró la configuración de Supabase en el entorno.")

# -------------------------------
# CLIENTE GROQ
# -------------------------------
groq_client = Groq(api_key=GROQ_API_KEY)

# -------------------------------
# CLIENTE SUPABASE
# -------------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# PASSWORD HASHING
# -------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Genera un hash seguro para la contraseña."""
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verifica si una contraseña coincide con su hash."""
    return pwd_context.verify(password, hashed)

# -------------------------------
# TIEMPOS Y SETTINGS
# -------------------------------
EMAIL_VERIFICATION_EXPIRATION_MINUTES = 5  # minutos de validez de token de verificación
WEBSOCKET_IDLE_TIMEOUT_SECONDS = 120       # tiempo para considerar inactividad en websockets
DEFAULT_GREETING_PROBABILITY = 0.8         # probabilidad de enviar un saludo al iniciar sesión
MAX_BUBBLES_PER_RESPONSE = 5               # máximo de burbujas que se pueden enviar por mensaje
MIN_BUBBLES_PER_RESPONSE = 2               # mínimo de burbujas por mensaje

# -------------------------------
# RUTA LOCAL BASE DE DATOS (opcional SQLite)
# -------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "miller2.db")
