import smtplib
import requests
from email.mime.text import MIMEText

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

def enviar_telegram(token, chat_id, msg):
    if not token:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg})
    except:
        pass

def enviar_email(user, password, msg):
    if not user:
        return
    try:
        email = MIMEText(msg)
        email["Subject"] = "🚨 ALERTA – HEDGE FUND"
        email["From"] = user
        email["To"] = user

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(email)
    except:
        pass
