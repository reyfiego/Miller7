from datetime import datetime
from millercore.db.supabase_client import supabase

# -------------------------------
# MENSAJES
# -------------------------------
def get_session_messages(session_id):
    """Obtiene todos los mensajes de una sesión ordenados por fecha."""
    res = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    messages = []
    for m in res.data or []:
        m_copy = m.copy()
        if isinstance(m_copy.get("created_at"), datetime):
            m_copy["created_at"] = m_copy["created_at"].isoformat()
        messages.append(m_copy)
    return sorted(messages, key=lambda x: x["created_at"])

# -------------------------------
# BACKUPS Y SESIONES INACTIVAS
# -------------------------------
def backup_sesion(session_id: str):
    """Copia toda la sesión activa a session_backups"""
    messages = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    data = {
        "session_id": session_id,
        "full_log": messages.data if messages.data else [],
        "created_at": datetime.utcnow()
    }
    supabase.table("session_backups").insert(data).execute()

def cerrar_sesion(session_id: str):
    """Marca la sesión como inactiva y hace backup"""
    supabase.table("sessions").update({
        "is_active": False,
        "updated_at": datetime.utcnow()
    }).eq("id", session_id).execute()
    backup_sesion(session_id)
