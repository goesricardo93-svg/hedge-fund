import smtplib
import requests
import streamlit as st
from email.mime.text import MIMEText

def get_secrets():
    # Tenta pegar segredos, retorna vazios se falhar para não quebrar o app
    try:
        return {
            "tg_token": st.secrets["telegram"]["token"],
            "tg_chat": st.secrets["telegram"]["chat_id"],
            "email_user": st.secrets["email"]["user"],
            "email_pass": st.secrets["email"]["password"]
        }
    except:
        return {"tg_token": "", "tg_chat": "", "email_user": "", "email_pass": ""}

def enviar_telegram(msg):
    creds = get_secrets()
    if not creds["tg_token"]: return
    try:
        url = f"https://api.telegram.org/bot{creds['tg_token']}/sendMessage"
        requests.post(url, data={"chat_id": creds["tg_chat"], "text": msg, "parse_mode": "Markdown"})
    except: pass

def enviar_email(msg):
    creds = get_secrets()
    if not creds["email_user"]: return
    try:
        message = MIMEText(msg)
        message["Subject"] = "🚨 ALERTA HEDGE FUND"
        message["From"] = creds["email_user"]
        message["To"] = creds["email_user"]
        
        with smtplib.SMTP("smtp.office365.com", 587) as server:
            server.starttls()
            server.login(creds["email_user"], creds["email_pass"])
            server.send_message(message)
    except: pass

def disparar_alerta(titulo, corpo):
    texto = f"🚨 *{titulo}*\n\n{corpo}"
    enviar_telegram(texto)
    enviar_email(texto)