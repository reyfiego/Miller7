import random
import re

# -------------------------------
# Funciones para manejar burbujas
# -------------------------------

def dividir_burbujas_aleatorio(texto: str, max_len: int = 120) -> list[str]:
    """
    Divide un texto en burbujas usando puntuación y longitud máxima.
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


def enriquecer_burbujas_sin_contexto(
    burbujas: list[str],
    burbujas_enviadas_global: set | None = None,
    max_burbujas: int = 5
) -> list[str]:
    """
    Solo maneja las burbujas que ya existen.
    Evita duplicados y limita el número máximo de burbujas.
    """
    if burbujas_enviadas_global is None:
        burbujas_enviadas_global = set()

    resultado = []
    for b in burbujas:
        b = b.strip()
        if b and b not in burbujas_enviadas_global:
            resultado.append(b)
            burbujas_enviadas_global.add(b)
        if len(resultado) >= max_burbujas:
            break

    return resultado[:max_burbujas]
