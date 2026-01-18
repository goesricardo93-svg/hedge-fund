import requests
import streamlit as st

def alerta(mensagem):
    """
    Envia uma mensagem para o Telegram configurado nos secrets.
    """
    try:
        # Tenta pegar as credenciais. Se não existirem, silencia o erro.
        if "telegram" in st.secrets:
            token = st.secrets["telegram"]["token"]
            chat = st.secrets["telegram"]["chat_id"]
            
            if token and chat:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = {"chat_id": chat, "text": mensagem}
                requests.post(url, data=data, timeout=5)
    except Exception as e:
        # Em produção, pode ser útil logar o erro, mas aqui evitamos travar o app
        print(f"Erro ao enviar alerta: {e}")
        pass