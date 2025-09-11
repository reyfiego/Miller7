from db.supabase_client import supabase
import bcrypt
import uuid
from datetime import datetime

# --- Usuarios ---
def crear_usuario(correo, contra):
    hashed = bcrypt.hashpw(contra.encode(), bcrypt.gensalt()).decode()
    return supabase.table("usuarios").insert({
        "id": str(uuid.uuid4()),
        "correo": correo,
        "contra": hashed
    }).execute()

def autenticar_usuario(correo, contra):
    user = supabase.table("usuarios").select("*").eq("correo", correo).execute()
    if user.data and bcrypt.checkpw(contra.encode(), user.data[0]['contra'].encode()):
        return user.data[0]
    return None

# --- Sesiones ---
def guardar_sesion(usuario_id, contexto):
    return supabase.table("sesiones").insert({
        "id": str(uuid.uuid4()),
        "usuario_id": usuario_id,
        "contexto": contexto,
        "creado_en": datetime.now().isoformat()
    }).execute()

def obtener_sesiones(usuario_id):
    return supabase.table("sesiones").select("*").eq("usuario_id", usuario_id).execute()
