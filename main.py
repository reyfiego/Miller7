# importante esto hara que se importe directamente la definicion necesaria para que el uvicorn monte el server(ojo aca)
import sys
import os


sys.path.append(os.path.dirname(__file__))

from miller_core import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
