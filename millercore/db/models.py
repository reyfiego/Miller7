from .supabase_client import supabase
import bcrypt
import uuid
from datetime import datetime

# --- Usuarios ---
def crear_usuario(email, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return supabase.table("users").insert({
        "id": str(uuid.uuid4()),
        "email": email,
        "password": hashed
    }).execute()

def autenticar_usuario(email, password):
    user = supabase.table("users").select("*").eq("email", email).execute()
    if user.data and bcrypt.checkpw(password.encode(), user.data[0]['password'].encode()):
        return user.data[0]
    return None

# --- Sesiones ---
def crear_sesion(user_id=None, context=None):
    """Crea una nueva sesión y retorna el session_id"""
    session_id = str(uuid.uuid4())

    # Verificar si el usuario existe
    if user_id:
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        if not user_check.data:  # usuario no existe → tratar como anónimo
            user_id = None

    return supabase.table("sessions").insert({
        "id": session_id,
        "user_id": user_id,
        "context": context or [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }).execute(), session_id

def guardar_sesion(session_id, context):
    """Actualiza el contexto de la sesión"""
    return supabase.table("sessions").update({
        "context": context,
        "updated_at": datetime.now().isoformat()
    }).eq("id", session_id).execute()

def obtener_sesiones(user_id):
    return supabase.table("sessions").select("*").eq("user_id", user_id).execute()

# --- Mensajes ---
def save_message(session_id, sender, content, emotion=None):
    return supabase.table("messages").insert({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.now().isoformat()
    }).execute()

def get_session_messages(session_id):
    # Orden correcto usando 'asc' como string
    res = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", ascending="asc").execute()
    return res.data if res.data else []

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

