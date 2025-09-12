import uuid
from datetime import datetime
from .supabase_client import supabase
import bcrypt

# ------------------------------- USUARIOS -------------------------------
def crear_usuario(email: str, password: str):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    data = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password": hashed,
        "created_at": datetime.utcnow()
    }
    res = supabase.table("users").insert(data).execute()
    return res.data[0] if res.data else None

def autenticar_usuario(email: str, password: str):
    user = supabase.table("users").select("*").eq("email", email).execute()
    if user.data and bcrypt.checkpw(password.encode(), user.data[0]["password"].encode()):
        return user.data[0]
    return None

def obtener_usuario(email: str):
    res = supabase.table("users").select("*").eq("email", email).execute()
    return res.data[0] if res.data else None

# ------------------------------- SESIONES -------------------------------


def guardar_sesion(session_id, context):
    res = supabase.table("sessions").update({
        "context": context,
        "updated_at": datetime.utcnow()
    }).eq("id", session_id).execute()
    return res.data

def obtener_sesiones(user_id):
    res = supabase.table("sessions").select("*").eq("user_id", user_id).execute()
    return res.data if res.data else []

# ------------------------------- MENSAJES -------------------------------
def save_message(session_id, sender, content, emotion=None):
    data = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.utcnow()
    }
    supabase.table("messages").insert(data).execute()
    return data



# -------------------------------
# SESIONES
# -------------------------------
def crear_sesion(user_id=None, context=None):
    """Crea una nueva sesión en la tabla sessions"""
    session_data = {
        "user_id": user_id,
        "context": context or [],
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("sessions").insert(session_data).execute()
    if res.data:
        return res.data[0]["id"]
    return None


# -------------------------------
# MENSAJES
# -------------------------------
def save_message(session_id: str, role: str, content: str):
    """Guarda un mensaje en la tabla messages"""
    message_data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table("messages").insert(message_data).execute()

