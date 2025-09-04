import random
import re


def dividir_burbujas_aleatorio(texto: str) -> list[str]:
    """
    Divide un texto largo en burbujas pequeñas de manera aleatoria,
    conservando signos de puntuación y respetando pausas naturales.
    """
    texto = texto.replace("...", "…")
    # Separa por signos de puntuación
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



def generar_frase_contextual_groq(contexto: str, groq_client) -> str:
    """
    Llama al modelo de lenguaje GROQ para generar una frase corta basada en el contexto.
    """
    prompt = f"""
    Eres un asistente empático y humano.
    Usuario: {contexto}
    Responde con una frase corta y coherente que continúe la conversación.
    No uses más de 20 palabras.
    """
    respuesta = groq_client.predict(
        model_id="meta-llama/llama-4-scout-17b-16e-instruct",
        inputs=prompt
    )
    return respuesta.output_text.strip()




def enriquecer_burbujas_contextual(
    burbujas: list[str], 
    contexto: str, 
    groq_client
) -> list[str]:
    """
    Enriquece las burbujas agregando frases cortas según el contexto.
    """
    resultado = []
    for b in burbujas:
        resultado.append(b)

        if random.random() < 0.3 and not b.endswith("?"):
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
