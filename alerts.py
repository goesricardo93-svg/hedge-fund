import requests
import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

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
    """Envio de texto simples (Alertas de Oportunidade)"""
    creds = get_creds()
    if creds.get("tg_token"):
        try:
            requests.post(
                f"https://api.telegram.org/bot{creds['tg_token']}/sendMessage",
                data={"chat_id": creds["tg_chat"], "text": f"🚨 *{titulo}*\n\n{corpo}", "parse_mode": "Markdown"}
            )
        except: pass

def enviar_relatorio_anexo(pdf_bytes, filename):
    """Envio de PDF via Telegram e E-mail"""
    creds = get_creds()
    
    # --- TELEGRAM (Documento) ---
    if creds.get("tg_token"):
        try:
            url = f"https://api.telegram.org/bot{creds['tg_token']}/sendDocument"
            files = {'document': (filename, pdf_bytes)}
            requests.post(url, data={'chat_id': creds["tg_chat"], 'caption': f"📊 {filename}"}, files=files)
        except Exception as e:
            print(f"Erro Telegram: {e}")

    # --- E-MAIL (Gmail) ---
    if creds.get("email_user") and creds.get("email_pass"):
        try:
            msg = MIMEMultipart()
            msg['Subject'] = f"📈 Relatório Mensal: {filename}"
            msg['From'] = creds["email_user"]
            msg['To'] = creds["email_user"] # Envia para você mesmo
            
            msg.attach(MIMEText("Segue anexo o relatório consolidado de performance do seu Hedge Fund Pessoal.", 'plain'))
            
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {filename}")
            msg.attach(part)
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(creds["email_user"], creds["email_pass"])
                server.send_message(msg)
        except Exception as e:
            print(f"Erro Email: {e}")