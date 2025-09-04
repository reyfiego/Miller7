# importante esto hara que se importe directamente la definicion necesaria para que el uvicorn monte el server(ojo aca)
from miller_core import app  # importa el FastAPI desde __init__.py

if __name__ == "__main__":
    import uvicorn
    import os