import requests
import streamlit as st
from email.mime.text import MIMEText
import smtplib

def get_creds():
    try:
        return {
            "tg_token": st.secrets["telegram"]["token"],
            "tg_chat": st.secrets["telegram"]["chat_id"]
        }
    except:
        return {}

def disparar_alerta(titulo, corpo):
    creds = get_creds()
    if creds.get("tg_token"):
        try:
            requests.post(
                f"https://api.telegram.org/bot{creds['tg_token']}/sendMessage",
                data={"chat_id": creds["tg_chat"], "text": f"🚨 *{titulo}*\n\n{corpo}", "parse_mode": "Markdown"}
            )
        except: pass