import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime

from motor import MotorAnalise
from alerts import enviar_telegram, enviar_email

st.set_page_config("Hedge Fund Ricardo | FINAL", layout="wide")

# SEGREDOS
try:
    TG_TOKEN = st.secrets["telegram"]["token"]
    TG_CHAT = st.secrets["telegram"]["chat_id"]
    EMAIL_USER = st.secrets["email"]["user"]
    EMAIL_PASS = st.secrets["email"]["password"]
except:
    TG_TOKEN = TG_CHAT = EMAIL_USER = EMAIL_PASS = ""

motor = MotorAnalise()

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    t = yf.Ticker(ticker)
    hist = t.history(period="2y")
    if hist.empty:
        return None
    info = t.info or {}
    return motor.analisar(hist, info, ticker), hist

if "alertas_diarios" not in st.session_state:
    st.session_state.alertas_diarios = {}

st.sidebar.title("📊 Hedge Fund Ricardo")
ticker = st.sidebar.text_input("Ticker", "BBAS3.SA").upper()

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏆 Ranking", "📈 Monte Carlo"])

# --- ABA 1
with tabs[0]:
    r, hist = obter_dados(ticker)
    if r:
        st.metric("Score IA", r["score_ia"])
        st.subheader(r["decisao_ia"])
        st.caption(r["motivos"])

        fig = go.Figure(go.Candlestick(
            x=hist.index,
            open=hist["Open"],
            high=hist["High"],
            low=hist["Low"],
            close=hist["Close"]
        ))
        st.plotly_chart(fig, use_container_width=True)

# --- ABA 2
with tabs[1]:
    if "carteira" not in st.session_state:
        st.session_state.carteira = pd.DataFrame([
            ["BBAS3.SA", "Bancos"],
            ["VALE3.SA", "Mineração"],
            ["PETR4.SA", "Petróleo"]
        ], columns=["Ticker", "Setor"])

    df = st.data_editor(st.session_state.carteira, num_rows="dynamic")
    st.session_state.carteira = df

    if st.button("Analisar Carteira"):
        res = []
        for _, row in df.iterrows():
            r, _ = obter_dados(row["Ticker"])
            if r:
                hoje = datetime.date.today()
                if r["decisao_ia"].startswith("🟢") and st.session_state.alertas_diarios.get(row["Ticker"]) != hoje:
                    enviar_telegram(TG_TOKEN, TG_CHAT, f"{row['Ticker']} → {r['decisao_ia']}")
                    enviar_email(EMAIL_USER, EMAIL_PASS, f"{row['Ticker']} → {r['decisao_ia']}")
                    st.session_state.alertas_diarios[row["Ticker"]] = hoje

                res.append({
                    "Ticker": row["Ticker"],
                    "Score": r["score_ia"],
                    "Decisão": r["decisao_ia"]
                })
        st.dataframe(pd.DataFrame(res))

# --- ABA 3
with tabs[2]:
    if st.button("Gerar Ranking"):
        ranking = []
        for _, row in st.session_state.carteira.iterrows():
            r, _ = obter_dados(row["Ticker"])
            if r:
                ranking.append({
                    "Ticker": row["Ticker"],
                    "Score": r["score_ia"],
                    "Decisão": r["decisao_ia"]
                })
        st.dataframe(pd.DataFrame(ranking).sort_values("Score", ascending=False))

# --- ABA 4
with tabs[3]:
    pat = st.number_input("Patrimônio Atual", 100000.0)
    aporte = st.number_input("Aporte Mensal", 2000.0)
    if st.button("Simular"):
        sims = motor.monte_carlo(pat, aporte)
        fig = go.Figure(go.Histogram(x=sims))
        st.plotly_chart(fig, use_container_width=True)
