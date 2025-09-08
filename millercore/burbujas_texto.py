import random
import re

def dividir_burbujas_aleatorio(texto, min_burbujas=2, max_burbujas=4):
    """
    Divide un texto en un número aleatorio de "burbujas" o segmentos.
    """
    segmentos = re.split(r'([.?!])', texto)
    segmentos = [s.strip() for s in segmentos if s.strip()]
    if not segmentos:
        return [texto]

    burbujas = []
    num_burbujas = random.randint(min_burbujas, min(max_burbujas, len(segmentos)))
    
    for i in range(num_burbujas):
        start_index = len(burbujas)
        end_index = len(segmentos)
        
        if i < num_burbujas - 1:
            segmentos_en_burbuja = random.randint(1, len(segmentos) - start_index - (num_burbujas - (i+1)))
            burbujas.append(" ".join(segmentos[start_index:start_index+segmentos_en_burbuja]))
            
        else:
            burbujas.append(" ".join(segmentos[start_index:end_index]))
    
    if not burbujas:
        return [texto]
    
    return [b for b in burbujas if b.strip()]

def enriquecer_burbujas_contextual(burbujas, contexto, burbujas_enviadas_global=None):
    """
    Añade un toque personal a las burbujas, como el prefijo [ws].
    """
    enriched_burbujas = []
    
    for b in burbujas:
        # Aquí puedes añadir la lógica de enriquecimiento que tenías.
        # Por ejemplo, enriquecer el mensaje según el contexto de la conversación.
        enriched_burbujas.append(b)

    return enriched_burbujas