import random
import re
import os
from dotenv import load_dotenv
from groq import Groq


load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

if not API_KEY:
    raise ValueError("❌ No se encontró GROQ_API_KEY en el entorno.")

groq_client = Groq(api_key=API_KEY)



def dividir_burbujas_aleatorio(texto: str) -> list[str]:
    """Divide un texto largo en burbujas más pequeñas conservando puntuación y pausas naturales."""
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
    """Verifica si el mensaje coincide con algún elemento del contexto previo."""
    for frase in contexto:
        if frase.lower() in mensaje.lower():
            return True
    return False


def generar_frase_contextual_groq(contexto: str, groq_client) -> str:
    """Genera una frase corta basada en el contexto usando GROQ."""
    prompt = f"""
    Eres un asistente empático y humano.
    Usuario: {contexto}
    Responde con una frase corta y coherente que continúe la conversación.
    No uses más de 20 palabras.
    """
    respuesta = groq_client.predict(
        model_id=MODEL_ID,
        inputs=prompt
    )
  
    return getattr(respuesta, "text", getattr(respuesta, "output_text", "")).strip()


def enriquecer_burbujas_contextual(
    burbujas: list[str],
    contexto: str,
    groq_client
) -> list[str]:
    """
    Enriquece las burbujas agregando frases cortas basadas en el contexto.
    """
    resultado = []
    for b in burbujas:
        resultado.append(b)
        
        if random.random() < 0.3 and not b.endswith("?"):
            if contexto_coincide(b, [contexto]):
                frase_contextual = generar_frase_contextual_groq(contexto, groq_client)
                resultado.append(frase_contextual)
    return resultado



if __name__ == "__main__":
    historial_completo = "Usuario: Hola, hoy me siento un poco triste."
    texto_usuario = "No sé qué hacer con mi tiempo libre. Me siento perdido..."

    burbujas = dividir_burbujas_aleatorio(texto_usuario)
    burbujas_enriquecidas = enriquecer_burbujas_contextual(
        burbujas,
        contexto=historial_completo,
        groq_client=groq_client
    )
    print(burbujas_enriquecidas)
