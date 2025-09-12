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
def save_message(session_id, sender, content, emotion=None, user_id=None):
    # Guardar en messages
    supabase.table("messages").insert({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.now().isoformat()
    }).execute()

    print(f"[DEBUG] Guardando en contexto de sesión {session_id}")

    # Leer contexto
    session = supabase.table("sessions").select("context").eq("id", session_id).execute()

    if not session.data:
        # Si no existe, crearla automáticamente
        print(f"[DEBUG] No se encontró sesión con id {session_id}, creando nueva sesión")
        guardar_sesion(session_id=session_id, context=[])
        session = supabase.table("sessions").select("context").eq("id", session_id).execute()

    current_context = session.data[0]["context"] or []
    if not isinstance(current_context, list):
        current_context = []

    # Agregar mensaje al contexto
    current_context.append({
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.now().isoformat()
    })

    # Actualizar sesión
    res = supabase.table("sessions").update({
        "context": current_context,
        "updated_at": datetime.now().isoformat()
    }).eq("id", session_id).execute()

    print(f"[DEBUG] Contexto actualizado → {res.data}")
