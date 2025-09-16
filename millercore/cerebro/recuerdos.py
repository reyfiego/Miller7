import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# USUARIOS
# -------------------------------
def crear_usuario(email: str, hashed_password: str, role: str = "user"):
    """Crea un nuevo usuario."""
    data = {
        "email": email,
        "password": hashed_password,
        "role": role,
        "created_at": datetime.utcnow()
    }
    response = supabase.table("users").insert(data).execute()
    return response.data[0]["id"]

def obtener_usuario(email: str):
    """Busca usuario por email."""
    response = supabase.table("users").select("*").eq("email", email).execute()
    return response.data[0] if response.data else None

# -------------------------------
# SESIONES
# -------------------------------
def crear_sesion(user_id: str, contexto: dict) -> str:
    """Crea una sesión nueva."""
    data = {
        "user_id": user_id,
        "context": contexto,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    response = supabase.table("sessions").insert(data).execute()
    return response.data[0]["id"]

def cerrar_sesion(session_id: str):
    """Cierra sesión marcándola como inactiva y haciendo backup."""
    supabase.table("sessions").update({
        "is_active": False,
        "updated_at": datetime.utcnow()
    }).eq("id", session_id).execute()
    backup_sesion(session_id)

# -------------------------------
# MENSAJES
# -------------------------------
def guardar_mensaje(session_id: str, sender: str, content: str, emotion: str = None):
    """Guarda un mensaje dentro de una sesión"""
    data = {
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.utcnow()
    }
    supabase.table("messages").insert(data).execute()

# -------------------------------
# BACKUPS
# -------------------------------
def backup_sesion(session_id: str):
    """Copia toda la sesión en session_backups"""
    messages = supabase.table("messages").select("*").eq("session_id", session_id).execute().data
    data = {
        "session_id": session_id,
        "full_log": messages,
        "created_at": datetime.utcnow()
    }
    supabase.table("session_backups").insert(data).execute()