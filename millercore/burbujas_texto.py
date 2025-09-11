import random
import re

# -------------------------------
# Funciones de burbujas
# -------------------------------
def dividir_burbujas_aleatorio(texto: str, max_len: int = 120) -> list[str]:
    """
    Divide un texto largo en burbujas cortas, respetando frases y signos de puntuación(no mandar mas de 5 burbujas).
    """
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


def filtrar_burbujas_repetidas(burbujas: list[str], burbujas_enviadas_global: set) -> list[str]:
    """
    Elimina burbujas que ya han sido enviadas previamente para la sesión.
    """
    resultado = []
    for b in burbujas:
        if b not in burbujas_enviadas_global:
            resultado.append(b)
            burbujas_enviadas_global.add(b)
    return resultado
