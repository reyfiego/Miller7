import json
import logging
import random
import asyncio
from fastapi import WebSocket
from groq import Groq
from corazon import SYSTEM_ROLE  # Usamos solo el rol sistema

logger = logging.getLogger("uvicorn")

# -------------------------------
# CLIENTE GROQ
# -------------------------------
client = Groq(api_key="tu_api_key")

# -------------------------------
# FUNCION PRINCIPAL
# -------------------------------
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    logger.info(f"Cliente conectado: {client_id}")

    try:
        # Historial de mensajes (solo para guardar localmente)
        history = []
        burbujas_mostradas = set()

        while True:
            # Recibir mensaje del usuario
            data = await websocket.receive_text()
            message = json.loads(data)
            user_message = message.get("message", "").strip()

            if not user_message:
                continue

            logger.info(f"Mensaje de {client_id}: {user_message}")

            # Guardar historial simple
            history.append({"role": "user", "content": user_message})

            # ---------------------------
            # Enviar a Groq SOLO último mensaje
            # ---------------------------
            messages_for_groq = [
                {"role": "system", "content": SYSTEM_ROLE},
                {"role": "user", "content": user_message}
            ]

            response = client.chat.completions.create(
                model="llama-3.2-11b-text-preview",
                messages=messages_for_groq,
                temperature=0.8,
                max_tokens=200
            )

            respuesta_texto = response.choices[0].message.content.strip()
            logger.info(f"Respuesta de Groq: {respuesta_texto}")

            # Dividir en burbujas por saltos de línea
            burbujas = [b.strip() for b in respuesta_texto.split("\n") if b.strip()]

            # ---------------------------
            # Enviar con delay y sin repetir
            # ---------------------------
            for burbuja in burbujas:
                if burbuja not in burbujas_mostradas:
                    burbujas_mostradas.add(burbuja)
                    await websocket.send_text(json.dumps({
                        "sender": "Miller2",
                        "message": burbuja
                    }))
                    await asyncio.sleep(random.uniform(1.2, 2.5))  # delay natural

    except Exception as e:
        logger.error(f"Error en WebSocket con {client_id}: {e}")
        await websocket.close()

    finally:
        logger.info(f"Cliente desconectado: {client_id}")
