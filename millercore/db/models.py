from .supabase_client import supabase
import bcrypt
import uuid
from datetime import datetime

# -------------------------
# USUARIOS
# -------------------------
def crear_usuario(email, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return supabase.table("users").insert({
        "id": str(uuid.uuid4()),
        "email": email,
        "password": hashed,
        "created_at": datetime.now().isoformat()
    }).execute()

def autenticar_usuario(email, password):
    user = supabase.table("users").select("*").eq("email", email).execute()
    if user.data and bcrypt.checkpw(password.encode(), user.data[0]['password'].encode()):
        return user.data[0]
    return None

# -------------------------
# SESIONES
# -------------------------
def guardar_sesion(user_id, session_id, context):
    # Verifica si la sesión ya existe
    existing = supabase.table("sessions").select("*").eq("id", session_id).execute()
    if existing.data:
        # Actualiza contexto y updated_at
        return supabase.table("sessions").update({
            "context": context,
            "updated_at": datetime.now().isoformat()
        }).eq("id", session_id).execute()
    else:
        # Crea nueva sesión
        return supabase.table("sessions").insert({
            "id": session_id,
            "user_id": user_id,
            "context": context,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }).execute()

def obtener_sesiones(user_id):
    return supabase.table("sessions").select("*").eq("user_id", user_id).execute()

# -------------------------
# MENSAJES
# -------------------------
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
    res = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    return res.data if res.data else []
