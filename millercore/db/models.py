import uuid
from datetime import datetime
from .supabase_client import supabase
import bcrypt

# -------------------------------
# USUARIOS
# -------------------------------
def crear_usuario(email: str, password: str):
    """Crea un usuario en la DB y retorna el registro."""
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    data = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password": hashed,
        "created_at": datetime.utcnow()
    }
    return supabase.table("users").insert(data).execute()

def autenticar_usuario(email: str, password: str):
    """Verifica credenciales y retorna usuario si es correcto."""
    user = supabase.table("users").select("*").eq("email", email).execute()
    if user.data and bcrypt.checkpw(password.encode(), user.data[0]['password'].encode()):
        return user.data[0]
    return None

def obtener_usuario(email: str):
    """Busca usuario por email."""
    res = supabase.table("users").select("*").eq("email", email).execute()
    return res.data[0] if res.data else None

# -------------------------------
# SESIONES ACTIVAS
# -------------------------------
def crear_sesion(user_id=None, context=None):
    """Crea una nueva sesión activa y retorna session_id."""
    session_id = str(uuid.uuid4())
    
    # Verificar existencia del usuario
    if user_id:
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        if not user_check.data:
            user_id = None  # tratar como invitado

    data = {
        "id": session_id,
        "user_id": user_id,
        "context": context or [],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    supabase.table("sessions").insert(data).execute()
    return session_id

def guardar_sesion(session_id, context):
    """Actualiza el contexto de la sesión activa."""
    return supabase.table("sessions").update({
        "context": context,
        "updated_at": datetime.utcnow()
    }).eq("id", session_id).execute()

def obtener_sesiones(user_id):
    """Retorna todas las sesiones de un usuario."""
    return supabase.table("sessions").select("*").eq("user_id", user_id).execute()

# -------------------------------
# MENSAJES
# -------------------------------
def save_message(session_id, sender, content, emotion=None):
    """Guarda un mensaje en la DB de la sesión activa."""
    return supabase.table("messages").insert({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.utcnow()
    }).execute()

def get_session_messages(session_id):
    """Retorna todos los mensajes de una sesión, con datetime serializable para JSON."""
    # .order() compatible con tu versión de supabase-py
    res = supabase.table("messages") \
                  .select("*") \
                  .eq("session_id", session_id) \
                  .order("created_at", "asc") \
                  .execute()
    if not res.data:
        return []

    # Convertir datetime a string para JSON
    for msg in res.data:
        if isinstance(msg.get("created_at"), datetime):
            msg["created_at"] = msg["created_at"].isoformat()
    return res.data
