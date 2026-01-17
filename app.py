import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import requests
import smtplib
import io
from email.mime.text import MIMEText
from motor import MotorAnalise

# ======================================================
# CONFIGURAÇÕES DE ALERTA
# ======================================================
TELEGRAM_TOKEN = "8515547858:AAHDCGoE-Fg-51If_r_5xZSO2YHgoTrceZQ"
TELEGRAM_CHAT_ID = "833554938"

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
EMAIL_USER = "radgoes@hotmail.com"
EMAIL_PASS = "Ysi0xgki5-"

# ======================================================
# FUNÇÕES DE ALERTA
# ======================================================
def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except:
        pass

def enviar_email(msg):
    try:
        m = MIMEText(msg)
        m["Subject"] = "🚨 ALERTA – TERMINAL RICARDO"
        m["From"] = EMAIL_USER
        m["To"] = EMAIL_USER
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_USER, EMAIL_PASS)
            s.send_message(m)
    except:
        pass

# ======================================================
# IA – APORTES
# ======================================================
def sugerir_aportes(df, aporte):
    df["Valor"] = df["Qtd"] * df["Cotação"]
    total = df["Valor"].sum()
    df["Peso"] = df["Valor"] / total
    df["Peso_Alvo"] = 1 / len(df)

    df["Score_IA"] = (
        (df["Peso_Alvo"] - df["Peso"]) * 2 +
        (df["Score"] / 100) +
        ((df["PM"] - df["Cotação"]) / df["PM"])
    ).clip(lower=0)

    df["Aporte_Sugerido"] = df["Score_IA"] / df["Score_IA"].sum() * aporte
    return df.sort_values("Aporte_Sugerido", ascending=False)

# ======================================================
# SIMULAÇÕES
# ======================================================
def monte_carlo(aporte, meses=120, sims=2000):
    res = []
    for _ in range(sims):
        pat = 0
        for _ in range(meses):
            pat = pat * (1 + np.random.normal(0.01, 0.05)) + aporte
        res.append(pat)
    return res

def stress_test(valor):
    cenarios = {
        "2008": -0.07,
        "COVID": -0.10,
        "Juros Altos": -0.03
    }
    out = {}
    for c, choque in cenarios.items():
        v = valor
        hist = []
        for _ in range(12):
            v *= (1 + choque)
            hist.append(v)
        out[c] = hist
    return out

# ======================================================
# SETUP STREAMLIT
# ======================================================
st.set_page_config("Hedge Fund Ricardo", layout="wide")

# ======================================================
# CARTEIRA INICIAL
# ======================================================
if "carteira" not in st.session_state:
    st.session_state.carteira = pd.DataFrame([
        ["BBAS3.SA",1703,24.48,"Bancos"],
        ["VALE3.SA",152,54.79,"Mineração"],
        ["ITSA4.SA",1174,9.63,"Holding"]
    ], columns=["Ticker","Qtd","PM","Setor"])

# ======================================================
# INTERFACE
# ======================================================
st.sidebar.title("📊 Terminal Ricardo")
ticker = st.sidebar.text_input("Ticker:", "BBAS3").upper()
ticker = ticker if "." in ticker else ticker + ".SA"

tabs = st.tabs(["Ativo","Carteira"])

# ======================================================
# ABA ATIVO
# ======================================================
with tabs[0]:
    t = yf.Ticker(ticker)
    hist = t.history(period="2y")
    info = t.info
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, ticker)
        st.metric("Preço", f"R$ {r['preco']:.2f}")
        st.metric("RSI", f"{r['rsi']:.1f}")
        st.metric("Bazin", f"R$ {r['p_bazin']:.2f}")
        st.metric("Score", "OK")
        fig = go.Figure(go.Scatter(x=hist.index, y=hist["Close"]))
        st.plotly_chart(fig, use_container_width=True)

# ======================================================
# ABA CARTEIRA
# ======================================================
with tabs[1]:
    df = st.data_editor(st.session_state.carteira, num_rows="dynamic")

    if st.button("🔄 Atualizar"):
        dados = []
        for _, row in df.iterrows():
            tk = yf.Ticker(row["Ticker"])
            p = tk.fast_info["last_price"]
            r = MotorAnalise().analisar(tk.history("1y"), tk.info, row["Ticker"])
            score = (r["rsi"] < 35) * 50 + (p < r["p_bazin"]) * 50
            dados.append({"Cotação":p,"Score":score})

            if score >= 80:
                enviar_telegram(f"🟢 OPORTUNIDADE {row['Ticker']} – R$ {p:.2f}")
                enviar_email(f"Oportunidade em {row['Ticker']}")

        df_f = pd.concat([df.reset_index(drop=True), pd.DataFrame(dados)], axis=1)
        st.dataframe(df_f)

        aporte = st.number_input("Aporte (R$)", value=5000.0)
        if st.button("🤖 IA Sugerir Aporte"):
            sug = sugerir_aportes(df_f, aporte)
            st.dataframe(sug[["Ticker","Aporte_Sugerido"]])

        if st.button("🎲 Monte Carlo"):
            mc = monte_carlo(2000)
            st.metric("Mediana", f"R$ {np.median(mc):,.2f}")

        if st.button("🔥 Stress Test"):
            st.write(stress_test(df_f["Cotação"].mul(df_f["Qtd"]).sum()))
