import random
import re
import os
from dotenv import load_dotenv
from groq import Groq

# ==========================
# CONFIG
# ==========================
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

groq_client = Groq(api_key=API_KEY)

# ==========================
# FUNCIONES
# ==========================
def dividir_burbujas_aleatorio(texto: str) -> list[str]:
    """
    Divide un texto largo en burbujas más pequeñas conservando puntuación y pausas naturales.
    """
    texto = texto.replace("...", "…")
    frases = re.split(r'(?<=[.?!…])\s+', texto)
    burbujas = []
    temp = ""
    for frase in frases:
        if random.random() < 0.5 or frase.endswith("?"):
            if temp:
                burbujas.append(temp.strip())
            temp = frase
        else:
            temp = (temp + " " + frase).strip()
    if temp:
        burbujas.append(temp.strip())
    return burbujas


def contexto_coincide(mensaje: str, contexto: list[str]) -> bool:
    """
    Verifica si el mensaje coincide con algún elemento del contexto previo.
    """
    mensaje_lower = mensaje.lower()
    for frase in contexto:
        if frase.lower() in mensaje_lower:
            return True
    return False


def generar_frase_contextual_groq(contexto: str, groq_client) -> str:
    """
    Genera una frase corta basada en el contexto usando GROQ.
    Si falla, devuelve string vacío para no romper el flujo.
    """
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
        return respuesta.choices[0].message.content.strip()
    except Exception as e:
        print("⚠️ Error generando frase contextual con Groq:", e)
        return ""


def enriquecer_burbujas_contextual(
    burbujas: list[str],
    contexto: str | list[str],
    groq_client = groq_client
) -> list[str]:
    """
    Enriquece las burbujas agregando frases cortas basadas en el contexto.
    Permite que el contexto sea string o lista de strings.
    """
    if isinstance(contexto, list):
        contexto = " ".join(contexto)

    resultado = []
    for b in burbujas:
        resultado.append(b)

        # 60% de probabilidad de añadir frase contextual
        if random.random() < 0.6 and not b.endswith("?"):
            frase_contextual = generar_frase_contextual_groq(contexto, groq_client)
            if frase_contextual:
                resultado.append(frase_contextual)

    return resultado
