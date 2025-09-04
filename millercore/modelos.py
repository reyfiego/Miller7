from pydantic import BaseModel, EmailStr

# -------------------------------
# MODELOS DE USUARIO
# -------------------------------

class RegisterModel(BaseModel):
    email: EmailStr
    password: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str

# -------------------------------
# MODELOS DE CHAT
# -------------------------------

class Message(BaseModel):
    message: str
    session_id: str | None = None