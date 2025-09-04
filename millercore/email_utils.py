# MillerCore/email_utils.py

import smtplib
from email.message import EmailMessage
from .config import EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_VERIFICATION_EXPIRATION_MINUTES

def send_verification_email(to_email: str, token: str):
    """
    Envía un correo de verificación al usuario con un token temporal.
    """
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Verifica tu cuenta'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email

        # Link de verificación (puede adaptarse a tu dominio o frontend)
        link = f"http://localhost:8000/verify?token={token}"
        msg.set_content(
            f"Confirma tu correo haciendo clic en el enlace: {link}\n"
            f"Este enlace expira en {EMAIL_VERIFICATION_EXPIRATION_MINUTES} minutos."
        )

        # Envío seguro vía SMTP SSL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Correo de verificación enviado a {to_email}")
    except Exception as e:
        print(f"❌ Error al enviar correo a {to_email}: {repr(e)}")