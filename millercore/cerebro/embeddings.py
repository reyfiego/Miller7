import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# KNOWLEDGE BASE
# -------------------------------
def guardar_conocimiento(title: str, content: str, embedding: list = None):
    """Guarda un contenido en knowledge_base"""
    data = {
        "title": title,
        "content": content,
        "created_at": datetime.utcnow()
    }
    if embedding:
        data["embedding"] = embedding  # si activas pgvector
    supabase.table("knowledge_base").insert(data).execute()

def buscar_conocimiento(query: str):
    """Busca coincidencias simples por título o contenido"""
    response = supabase.table("knowledge_base")\
        .select("*")\
        .or_(f"title.ilike.%{query}%,content.ilike.%{query}%")\
        .execute()
    return response.data
