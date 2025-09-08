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
# Funciones
# -------------------------------
def dividir_burbujas_aleatorio(texto: str, max_len: int = 120) -> list[str]:
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


def contexto_coincide(mensaje: str, contexto: list[str]) -> bool:
    mensaje_lower = mensaje.lower()
    for frase in contexto:
        if frase.lower() in mensaje_lower:
            return True
    return False


def generar_frase_contextual_groq(contexto: str, groq_client, system_role: str = "") -> str:
    if not groq_client:
        return ""

    prompt = f"""
Usuario: {contexto}
Responde con una frase corta y coherente que continúe la conversación.
No uses más de 20 palabras.
"""

    messages = []
    if system_role:
        messages.append({"role": "system", "content": system_role})
    messages.append({"role": "user", "content": prompt})

    try:
        respuesta = groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
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
    system_role: str = "",
    max_burbujas: int = 5
) -> list[str]:
    if isinstance(contexto, list):
        contexto = " ".join([m.get("content", "") if isinstance(m, dict) else str(m) for m in contexto])

    resultado = []
    frases_recientes = set()
    frase_contextual_agregada = False

    for b in burbujas:
        b = re.sub(r'…{2,}$', '…', b.strip())
        if b and b not in frases_recientes:
            resultado.append(b)
            frases_recientes.add(b)

        # Probabilidad de añadir frase contextual
        if random.random() < 0.4 and not b.endswith("?") and len(resultado) < max_burbujas:
            frase_contextual = generar_frase_contextual_groq(contexto, groq_client, system_role=system_role)
            if frase_contextual and frase_contextual not in frases_recientes:
                resultado.append(frase_contextual)
                frases_recientes.add(frase_contextual)
                frase_contextual_agregada = True

        if len(resultado) >= max_burbujas:
            break

    # Garantizar al menos una frase contextual si es posible
    if not frase_contextual_agregada and len(resultado) < max_burbujas:
        frase_contextual = generar_frase_contextual_groq(contexto, groq_client, system_role=system_role)
        if frase_contextual and frase_contextual not in frases_recientes:
            resultado.append(frase_contextual)

    return resultado[:max_burbujas]
