# utils/email_utils.py
import os
import smtplib
from email.message import EmailMessage

def send_verification_email(to_email: str, code: str):
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 465))

    if not smtp_user or not smtp_pass:
        print("SMTP não configurado (SMTP_USER/SMTP_PASS).")
        return

    msg = EmailMessage()
    msg["Subject"] = "Verificação de e-mail - Serenamente"
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.set_content(
        f"Olá!\n\n"
        f"Seu código de verificação de e-mail é: {code}\n"
        f"Ele é válido por 15 minutos.\n\n"
        f"Abraços,\n"
        f"Equipe Serenamente"
    )

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)
