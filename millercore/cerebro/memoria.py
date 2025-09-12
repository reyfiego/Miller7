from datetime import datetime
from millercore.db.supabase_client import supabase

# -------------------------------
# MENSAJES
# -------------------------------
def get_session_messages(session_id: str):
    """Obtiene todos los mensajes de una sesión ordenados por fecha."""
    res = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    messages = []
    for m in res.data or []:
        m_copy = m.copy()
        # Normalizar created_at a ISO string
        if isinstance(m_copy.get("created_at"), datetime):
            m_copy["created_at"] = m_copy["created_at"].isoformat()
        elif m_copy.get("created_at") and not isinstance(m_copy.get("created_at"), str):
            try:
                m_copy["created_at"] = str(m_copy["created_at"])
            except Exception:
                m_copy["created_at"] = None
        messages.append(m_copy)

    return sorted(messages, key=lambda x: x.get("created_at") or "")


# -------------------------------
# BACKUPS Y SESIONES INACTIVAS
# -------------------------------
def backup_sesion(session_id: str):
    """Copia toda la sesión activa a session_backups"""
    res = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    mensajes = res.data if res.data else []

    # Convertir fechas a ISO string
    for m in mensajes:
        if isinstance(m.get("created_at"), datetime):
            m["created_at"] = m["created_at"].isoformat()

    data = {
        "session_id": session_id,
        "full_log": mensajes,
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table("session_backups").insert(data).execute()


def cerrar_sesion(session_id: str):
    """Marca la sesión como inactiva y hace backup"""
    supabase.table("sessions").update({
        "is_active": False,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", session_id).execute()

    try:
        backup_sesion(session_id)
    except Exception as e:
        print(f"[{session_id}] Error cerrando sesión:", repr(e))
