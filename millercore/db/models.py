import uuid
from datetime import datetime
from .supabase_client import supabase
import bcrypt

# -------------------------------
# UTILIDADES
# -------------------------------
def log_result(action, res):
    """Muestra resultado de operación Supabase."""
    if hasattr(res, "data") and res.data:
        print(f"[OK] {action}: {res.data}")
    elif hasattr(res, "error") and res.error:
        print(f"[ERROR] {action}: {res.error}")
    else:
        print(f"[INFO] {action}: sin resultados")

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
    res = supabase.table("users").insert(data).execute()
    log_result("crear_usuario", res)
    return res

def autenticar_usuario(email: str, password: str):
    """Verifica credenciales y retorna usuario si es correcto."""
    user = supabase.table("users").select("*").eq("email", email).execute()
    log_result("autenticar_usuario fetch", user)
    if user.data and bcrypt.checkpw(password.encode(), user.data[0]['password'].encode()):
        return user.data[0]
    return None

def obtener_usuario(email: str):
    """Busca usuario por email."""
    res = supabase.table("users").select("*").eq("email", email).execute()
    log_result("obtener_usuario", res)
    return res.data[0] if res.data else None

# -------------------------------
# SESIONES ACTIVAS
# -------------------------------
def crear_sesion(user_id=None, context=None):
    """Crea una nueva sesión activa y retorna session_id."""
    session_id = str(uuid.uuid4())

    if user_id:
        user_check = supabase.table("users").select("id").eq("id", user_id).execute()
        if not user_check.data:
            print(f"[WARN] Usuario {user_id} no encontrado. Se creará sesión sin user_id.")
            user_id = None

    data = {
        "id": session_id,
        "user_id": user_id,
        "context": context or [],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    print(f"[INFO] Insertando sesión: {data}")
    res = supabase.table("sessions").insert(data).execute()
    log_result("crear_sesion", res)
    return session_id

def guardar_sesion(session_id, context):
    """Actualiza el contexto de la sesión activa."""
    if not session_id:
        print("[ERROR] guardar_sesion: session_id inválido")
        return None
    data = {"context": context, "updated_at": datetime.utcnow()}
    res = supabase.table("sessions").update(data).eq("id", session_id).execute()
    log_result("guardar_sesion", res)
    return res

def obtener_sesiones(user_id):
    """Retorna todas las sesiones de un usuario."""
    if not user_id:
        print("[WARN] obtener_sesiones: user_id es None")
        return []
    res = supabase.table("sessions").select("*").eq("user_id", user_id).execute()
    log_result("obtener_sesiones", res)
    return res.data if res.data else []

# -------------------------------
# MENSAJES
# -------------------------------
def save_message(session_id, sender, content, emotion=None):
    """Guarda un mensaje en la DB de la sesión activa."""
    if not session_id:
        print("[ERROR] save_message: session_id inválido")
        return None
    data = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "emotion": emotion,
        "created_at": datetime.utcnow()
    }
    print(f"[INFO] Guardando mensaje: {data}")
    res = supabase.table("messages").insert(data).execute()
    log_result("save_message", res)
    return res

def get_session_messages(session_id):
    """Retorna todos los mensajes de una sesión, ordenados por created_at."""
    if not session_id:
        print("[WARN] get_session_messages: session_id inválido")
        return []

    res = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    log_result("get_session_messages fetch", res)
    if not res.data:
        return []

    messages = []
    for m in res.data:
        m_copy = m.copy()
        if isinstance(m_copy.get("created_at"), datetime):
            m_copy["created_at"] = m_copy["created_at"].isoformat()
        messages.append(m_copy)

    return sorted(messages, key=lambda x: x["created_at"])
