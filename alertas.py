import smtplib
import requests
from email.mime.text import MIMEText

# ===============================
# CONFIGURAÇÕES
# ===============================
# Substitua pelos seus dados reais ou use st.secrets se for para produção
TELEGRAM_TOKEN = "8515547858:AAHDCGoE-Fg-51If_r_5xZSO2YHgoTrceZQ"
TELEGRAM_CHAT_ID = "833554938"

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
EMAIL_USER = "radgoes@hotmail.com"  # Ou hotmail.com / live.com
EMAIL_PASS = "Ysi0xgki5-"       # Senha de login do email

# ===============================
# TELEGRAM
# ===============================
def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram usando a API oficial."""
    try:
        if "8515547858:AAHDCGoE-Fg-51If_r_5xZSO2YHgoTrceZQ" in TELEGRAM_TOKEN: return # Evita erro se não configurado
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown" # Permite negrito/itálico
        }
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Erro Telegram: {e}")

# ===============================
# EMAIL (OUTLOOK/HOTMAIL)
# ===============================
def enviar_email(mensagem):
    """Envia email usando servidor SMTP do Outlook."""
    try:
        if "seu_email" in EMAIL_USER: return # Evita erro se não configurado
        
        msg = MIMEText(mensagem)
        msg["Subject"] = "🚨 ALERTA – TERMINAL RICARDO"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER # Envia para você mesmo

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls() # Criptografia TLS
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
            
    except Exception as e:
        print(f"Erro Email: {e}")

# ===============================
# DISPARO UNIFICADO
# ===============================
def disparar_alerta(mensagem):
    """Função única para chamar no app principal."""
    enviar_telegram(mensagem)
    enviar_email(mensagem)

# Teste direto se rodar este arquivo
if __name__ == "__main__":
    disparar_alerta("✅ Teste de alerta: Sistema Hedge Fund Ricardo Online!")

