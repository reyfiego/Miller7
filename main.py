# importante esto hara que se importe directamente la definicion necesaria para que el uvicorn monte el server(ojo aca)
import sys, os
sys.path.append(os.path.dirname(__file__))

from miller_core import app

@app.on_event("startup")
async def startup_event():
    print("Servidor iniciado correctamente")

@app.on_event("shutdown")
async def shutdown_event():
    print("El servidor esta cerrado")
