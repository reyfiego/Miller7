import random
import re

def dividir_burbujas_aleatorio(texto: str) -> list[str]:
    """
    Divide un texto largo en burbujas pequeñas de manera aleatoria,
    conservando signos de puntuación y respetando pausas naturales.
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

def enriquecer_burbujas_aleatorio(burbujas: list[str]) -> list[str]:
    """
    Toma las burbujas ya divididas y agrega pausas, reflexiones o frases cortas
    de manera aleatoria para simular un estilo más humano.
    """
    resultado = []
    for b in burbujas:
        resultado.append(b)
        if random.random() < 0.3 and not b.endswith("?"):
            resultado.append(random.choice([
                "...",
                "No siempre tengo todas las palabras.",
                "A veces solo puedo escuchar.",
                "Estoy aquí, aunque no siempre sepa qué decir.",
                "…"
            ]))
    if len(resultado) > 5:
        resultado = resultado[:random.randint(2, 5)]
    return resultado