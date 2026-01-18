import smtplib
import requests
import streamlit as st
from email.mime.text import MIMEText

def get_creds():
    try:
        return {
            "tg_token": st.secrets["telegram"]["token"],
            "tg_chat": st.secrets["telegram"]["chat_id"],
            "email_user": st.secrets["email"]["user"],
            "email_pass": st.secrets["email"]["password"]
        }
    except:
        return {}

def disparar_alerta(titulo, corpo):
    creds = get_creds()
    msg_txt = f"🚨 *{titulo}*\n\n{corpo}"
    
    # Telegram
    if creds.get("tg_token"):
        try:
            requests.post(
                f"https://api.telegram.org/bot{creds['tg_token']}/sendMessage",
                data={"chat_id": creds["tg_chat"], "text": msg_txt, "parse_mode": "Markdown"}
            )
        except: pass

    # Email
    if creds.get("email_user"):
        try:
            msg = MIMEText(msg_txt)
            msg["Subject"] = f"ALERTA: {titulo}"
            msg["From"] = creds["email_user"]
            msg["To"] = creds["email_user"]
            with smtplib.SMTP("smtp.office365.com", 587) as s:
                s.starttls()
                s.login(creds["email_user"], creds["email_pass"])
                s.send_message(msg)
        except: pass