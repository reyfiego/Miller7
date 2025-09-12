# millercore/websocket_manager.py
import os
import asyncio
import random
import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from groq import Groq

from .burbujas_texto import dividir_burbujas_aleatorio
from .corazon import SYSTEM_ROLE, get_random_greeting
from .db.supabase_client import supabase
from .db.models import save_message  # tu helper para guardar (si existe)

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

groq_client = Groq(api_key=API_KEY)
router = APIRouter()


# ------------------------------
# Connection manager (memoria corta por session_id)
# ------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.burbujas_enviadas: dict[str, set[str]] = {}
        # Cada session_id -> lista de {"role": "...", "content": "..."}
        self.sessions_context: dict[str, list[dict]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.burbujas_enviadas[session_id] = set()
        if session_id not in self.sessions_context:
            self.sessions_context[session_id] = []
        print(f"[{session_id}] Conectado")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        self.burbujas_enviadas.pop(session_id, None)
        # keep sessions_context in memory while server runs (optional)
        print(f"[{session_id}] Desconectado")

    async def send_personal_message(self, message: dict, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                if "reply" in message:
                    # No duplicar: comprobamos antes de enviar
                    to_send = []
                    for b in message["reply"]:
                        label = f"[ws] {b}"
                        if label not in self.burbujas_enviadas[session_id]:
                            to_send.append(b)
                            self.burbujas_enviadas[session_id].add(label)
                    if to_send:
                        await websocket.send_json({"reply": to_send, "session_id": session_id})
                else:
                    await websocket.send_json(message)
            except Exception as e:
                print(f"[{session_id}] Error enviando mensaje:", repr(e))


manager = ConnectionManager()


# ------------------------------
# Helpers DB / session context
# ------------------------------
def ensure_session_exists(session_id: str) -> None:
    """Crea la fila sessions si no existe (usar context JSON para memoria de esa sesión)."""
    existing = supabase.table("sessions").select("id").eq("id", session_id).execute()
    if not existing.data:
        supabase.table("sessions").insert({
            "id": session_id,
            "user_id": None,
            "context": {},  # guardamos un JSON object (mapa)
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()


def load_session_context_from_db(session_id: str) -> Dict[str, Any]:
    """Carga el campo context (json) de sessions y lo devuelve como dict."""
    res = supabase.table("sessions").select("context").eq("id", session_id).execute()
    if res.data and len(res.data) > 0:
        ctx = res.data[0].get("context") or {}
        if isinstance(ctx, dict):
            return ctx
    return {}


def update_session_context_in_db(session_id: str, context: dict):
    """Actualiza el context JSON de la sesión (sobrescribe)."""
    return supabase.table("sessions").update({
        "context": context,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", session_id).execute()


def get_session_messages_from_db(session_id: str) -> list[dict]:
    """Trae mensajes asociados a session_id (orden asc por created_at)."""
    # Supabase ordering espera "col.asc" / "col.desc"
    res = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at.asc").execute()
    if res.data:
        # Normalize to chat roles expected by the groq model
        return [{"role": (m.get("sender") or "user"), "content": m.get("content")} for m in res.data]
    return []


def persist_message_db(session_id: str, sender: str, content: str):
    """Inserta mensaje en tabla messages y devuelve resultado (no lanza si falla)."""
    try:
        res = supabase.table("messages").insert({
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "sender": sender,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        return res
    except Exception as e:
        print(f"[{session_id}] Error insertando message en DB: {repr(e)}")
        return None


def append_to_memory(session_id: str, role: str, content: str):
    """Agrega al manager.sessions_context[session_id] (memoria corta en RAM)."""
    manager.sessions_context.setdefault(session_id, []).append({"role": role, "content": content})


# ------------------------------
# Utility: detectar 'llamame' o 'soy' para guardar display_name en session context
# ------------------------------
def extract_name_from_text(text: str) -> str | None:
    """Búsqueda simple: 'llámame X', 'llamame X', 'soy X', 'mi nombre es X'."""
    t = text.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    patterns = [
        ("llamame ", 8),
        ("llamame:", 8),
        ("llamame,", 8),
        ("soy ", 4),
        ("mi nombre es ", 12),
        ("call me ", 8),
    ]
    for p, idx in patterns:
        if p in t:
            # slice original (respect accents/case) after locating pattern in lowercase
            i = t.find(p)
            name_raw = text[i + idx :].strip()
            # take first word or up to punctuation
            if not name_raw:
                return None
            # split by punctuation or newline
            for sep in [",", ".", "?", "!", "\n"]:
                if sep in name_raw:
                    name_raw = name_raw.split(sep)[0].strip()
            # return capitalized short name
            name = name_raw.split(" ")[0].strip()
            if name:
                return name.capitalize()
    return None


# ------------------------------
# WebSocket endpoint
# ------------------------------
@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)

    # 1) Asegurar la fila sessions existe (hotfix para constraint FK)
    ensure_session_exists(session_id)

    # 2) Cargar context (JSON) de esta sesión y sincronizar con memoria corta
    session_context = load_session_context_from_db(session_id)  # dict
    # convert to model-friendly messages if there are saved short "notes"
    # We'll store per-session small notes under keys in session_context, e.g. {"display_name": "Dante"}
    manager.sessions_context[session_id] = []  # start fresh list of messages
    # If session_context has a display_name, inject as system note (not as message from user)
    if session_context.get("display_name"):
        manager.sessions_context[session_id].append({
            "role": "system",
            "content": f"El usuario se registra como: {session_context['display_name']}"
        })

    # 3) Recuperar mensajes previos de la tabla messages (ordenados) y cargar a memoria corta
    prior_msgs = get_session_messages_from_db(session_id)
    for m in prior_msgs:
        manager.sessions_context[session_id].append(m)

    # 4) Saludo inicial aleatorio (mantener comportamiento)
    saludo = get_random_greeting()
    if saludo:
        await manager.send_personal_message({"reply": [saludo], "session_id": session_id}, session_id)

    try:
        while True:
            data = await websocket.receive_json()
            user_text = (data.get("message") or "").strip()
            user_id = data.get("user_id")  # si el front envía user_id al estar logueado

            if not user_text:
                await manager.send_personal_message({"reply": ["Por favor, dime algo."], "session_id": session_id}, session_id)
                continue

            # --- Detectar petición de nombre personalizado ---
            name = extract_name_from_text(user_text)
            if name:
                # Guardar SOLO en session context (no en users) — persistimos en DB sessions
                session_context["display_name"] = name
                update_session_context_in_db(session_id, session_context)
                # Añadir nota al historial de la sesión (memoria corta)
                append_to_memory(session_id, "system", f"Usuario pidió ser llamado: {name}")
                # Respuesta humana inmediata
                reply = f"Perfecto, {name}. Me acordaré durante esta sesión."
                # Guardar y enviar
                append_to_memory(session_id, "assistant", reply)
                persist_message_db(session_id, "assistant", reply)
                burb = dividir_burbujas_aleatorio(reply)
                await enviar_burbujas_con_delay(burb, session_id)
                continue

            # --- Guardar mensaje del usuario (RAM y DB) ---
            append_to_memory(session_id, "user", user_text)
            persist_message_db(session_id, "user", user_text)

            # --- Preparar prompt / historial para la IA ---
            system_messages = [{"role": "system", "content": SYSTEM_ROLE}]
            history = manager.sessions_context[session_id].copy()  # mensajes previos en esta sesión
            # Añadimos el último mensaje del usuario como item final (si no lo está ya)
            history.append({"role": "user", "content": user_text})
            messages_for_groq = system_messages + history

            try:
                # Llamada a GROQ
                response = groq_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages_for_groq,
                    max_tokens=250,
                    temperature=0.9,
                    top_p=0.95,
                    frequency_penalty=0.8,
                    presence_penalty=0.9
                )
                reply_text = response.choices[0].message.content.strip()

                # Guardar respuesta en RAM y DB
                append_to_memory(session_id, "assistant", reply_text)
                persist_message_db(session_id, "assistant", reply_text)

                # Enviar en burbujas
                burbujas = dividir_burbujas_aleatorio(reply_text)
                await enviar_burbujas_con_delay(burbujas, session_id)

            except Exception as e:
                print(f"[{session_id}] Error en chat (Llamada a GROQ):", repr(e))
                fallback_msg = "Lo siento, estoy teniendo problemas para pensar ahora mismo."
                append_to_memory(session_id, "assistant", fallback_msg)
                persist_message_db(session_id, "assistant", fallback_msg)
                burbujas = dividir_burbujas_aleatorio(fallback_msg)
                await enviar_burbujas_con_delay(burbujas, session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[{session_id}] Error general websocket:", repr(e))
        manager.disconnect(session_id)
