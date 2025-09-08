import random
import re
from groq import Groq
from dotenv import load_dotenv
import os

# -------------------------------
# Configuración inicial
# -------------------------------
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    print("⚠️ Advertencia: No se encontró GROQ_API_KEY en el entorno. Algunas funciones no funcionarán.")
    groq_client = None
else:
    groq_client = Groq(api_key=API_KEY)

# -------------------------------
# Funciones de burbujas
# -------------------------------
def normalizar_frase(frase: str) -> str:
    """Quita espacios extra y normaliza la frase para comparar duplicados."""
    frase = frase.strip().lower()
    frase = re.sub(r'\s+', ' ', frase)
    frase = re.sub(r'\.+$', '', frase)  # quitar puntos finales extra
    return frase

def dividir_burbujas_aleatorio(texto: str, max_len: int = 120) -> list[str]:
    """Divide el texto en burbujas (frases cortas) usando puntuación + azar + control de longitud."""
    texto = texto.replace("...", "…")
    frases = re.split(r'(?<=[.?!…])\s+', texto)
    burbujas, temp = [], ""

    for frase in frases:
        if random.random() < 0.5 or frase.endswith("?") or len(temp) + len(frase) > max_len:
            if temp:
                burbujas.append(temp.strip())
            temp = frase
        else:
            temp = (temp + " " + frase).strip()

    if temp:
        burbujas.append(temp.strip())

    return burbujas

def generar_frase_contextual_groq(contexto: str, groq_client) -> str:
    """Genera una frase corta y coherente con el contexto usando Groq."""
    if not groq_client:
        return ""

    prompt = f"""
Eres un asistente empático y humano.
Usuario: {contexto}
Responde con una frase corta y coherente que continúe la conversación.
No uses más de 20 palabras.
"""

    try:
        respuesta = groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.9
        )
        mensaje = respuesta.choices[0].message
        if isinstance(mensaje, dict):
            return mensaje.get("content", "").strip()
        elif hasattr(mensaje, "content"):
            return mensaje.content.strip()
        else:
            return ""
    except Exception as e:
        print("⚠️ Error generando frase contextual con Groq:", e)
        return ""

def enriquecer_burbujas_contextual(
    burbujas: list[str],
    contexto: str | list[str],
    groq_client=groq_client,
    max_burbujas: int = 5
) -> list[str]:
    """Enriquecer las burbujas añadiendo frases contextuales y evitando duplicados."""
    if isinstance(contexto, list):
        contexto = " ".join(
            [m.get("content", "") if isinstance(m, dict) else str(m) for m in contexto]
        )

    resultado = []
    frases_enviadas = set()

    for b in burbujas:
        b_norm = normalizar_frase(b)
        if b_norm not in frases_enviadas:
            resultado.append(b)
            frases_enviadas.add(b_norm)

        # Probabilidad de añadir frase contextual
        if random.random() < 0.4 and not b.endswith("?") and len(resultado) < max_burbujas:
            frase_contextual = generar_frase_contextual_groq(contexto, groq_client)
            if frase_contextual:
                fc_norm = normalizar_frase(frase_contextual)
                if fc_norm not in frases_enviadas:
                    resultado.append(frase_contextual)
                    frases_enviadas.add(fc_norm)

        if len(resultado) >= max_burbujas:
            break

    # Asegurar al menos una frase contextual
    if len(resultado) < max_burbujas:
        frase_contextual = generar_frase_contextual_groq(contexto, groq_client)
        if frase_contextual:
            fc_norm = normalizar_frase(frase_contextual)
            if fc_norm not in frases_enviadas:
                resultado.append(frase_contextual)

    return resultado[:max_burbujas]

# -------------------------------
# Ejemplo de envío de websocket
# -------------------------------
def enviar_burbujas_websocket(ws, burbujas: list[str]):
    """Envía burbujas al websocket, marcadas con [ws], evitando duplicados."""
    burbujas_enviadas = set()

    for b in burbujas:
        b_norm = normalizar_frase(b)
        if b_norm not in burbujas_enviadas:
            mensaje_ws = f"[ws] {b}"
            ws.send(mensaje_ws)  # enviar al websocket
            burbujas_enviadas.add(b_norm)
