from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/")
async def root():
    return FileResponse("static/index.html")

@router.get("/hora")
async def hora():
    import datetime
    now = datetime.datetime.now().strftime("%H:%M:%S")
    return {"reply": f"Son las {now}, pero recuerda… el tiempo nunca se detiene ⏳."}

@router.get("/saludo/{nombre}")
async def saludo(nombre: str):
    return {"reply": f"Hey {nombre}, qué bueno que estés aquí ✨."}

@router.get("/pagina/{nombre}")
async def pagina_personalizada(nombre: str, request: Request):
    """
    Ejemplo de cómo servir plantillas dinámicas según nombre.
    """
    return templates.TemplateResponse(f"{nombre}.html", {"request": request})