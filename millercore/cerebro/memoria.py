from datetime import datetime
from millercore.db.supabase_client import supabase

# -------------------------------
# BACKUPS Y SESIONES INACTIVAS
# -------------------------------
def backup_sesion(session_id: str):
    """Copia toda la sesión activa a session_backups"""
    res = supabase.table("messages").select("*").eq("session_id", session_id).execute()
    mensajes = res.data if res.data else []

    # Convertir datetime a ISO
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
