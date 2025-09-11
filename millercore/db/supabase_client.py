import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # 🔑 acceso completo

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Faltan variables de entorno de Supabase")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
