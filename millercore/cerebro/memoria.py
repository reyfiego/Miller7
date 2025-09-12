from datetime import datetime
from millercore.db.supabase_client import supabase

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
