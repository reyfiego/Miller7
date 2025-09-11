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
def guardar_sesion(user_id, session_id, context):
    return supabase.table("sessions").insert({
        "id": session_id,
        "user_id": user_id,
        "context": context,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }).execute()

def obtener_sesiones(user_id):
    return supabase.table("sessions").select("*").eq("user_id", user_id).execute()

# --- Mensajes ---
def guardar_mensaje(session_id, sender, content, emotion=None):
    return supabase.table("messages").insert({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.now().isoformat()
    }).execute()

def obtener_mensajes(session_id):
    res = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    return res.data if res.data else []

# --- Respaldo de sesiones ---
def guardar_backup(session_id, full_log):
    return supabase.table("session_backups").insert({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "full_log": full_log,
        "created_at": datetime.now().isoformat()
    }).execute()
