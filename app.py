import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd

st.set_page_config(page_title="Terminal Ricardo", layout="wide")

# Cache para evitar "Muitas Solicitações"
@st.cache_data(ttl=300)
def carregar_dados(ticker):
    data = yf.download(ticker, period="2y", progress=False)
    info = yf.Ticker(ticker).info
    return data, info

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX"]: return f"{t}.L"
    return f"{t}.SA"

st.sidebar.header("🕹️ Hedge Fund System")
ticker_input = st.sidebar.text_input("Ticker:", value="BBSE3")
ticker_final = formatar_ticker(ticker_input)

tab1, tab2, tab3 = st.tabs(["📊 Terminal de Valor", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with tab1:
    try:
        data, info = carregar_dados(ticker_final)
        if not data.empty:
            m = MotorAnalise()
            res = m.analisar(data, info, ticker_final)

            # --- DASHBOARD DE MÉTRICAS ---
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}" if res['preco_teto'] > 0 else "N/A", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Tendência", res['tendencia'])

            st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
            st.line_chart(res['precos_serie'])

            # --- INFO BOXES ---
            col_a, col_b = st.columns(2)
            col_a.info(f"**Análise de Valor:** Preço Teto baseado em Bazin/Graham. Upside de {res['upside']:.2f}%.")
            col_b.info(f"**Análise Técnica:** Suporte Anual em R$ {res['suporte']:.2f}. Média 252p em R$ {res['ma252']:.2f}.")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")

with tab2:
    st.header("Scanner de FIIs (CSV)")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        def clean(c): return pd.to_numeric(df_fii[c].astype(str).str.replace('.','',regex=False).str.replace(',','.',regex=False), errors='coerce')
        df_fii['P/VP_N'] = clean('P/VP')
        df_fii['LIQ_N'] = clean('LIQUIDEZ MEDIA DIARIA')
        f = df_fii[(df_fii['P/VP_N'] >= 0.85) & (df_fii['P/VP_N'] <= 1.0) & (df_fii['LIQ_N'] >= 800000)].copy()
        st.dataframe(f[['TICKER', 'PRECO', 'P/VP', 'DY', 'LIQUIDEZ MEDIA DIARIA']])
    except: st.info("Adicione o CSV na pasta.")

with tab3:
    st.header("Planejamento Fiscal")
    r = st.number_input("Renda Anual:", value=200000.0)
    st.metric("Aporte PGBL (12%)", f"R$ {r*0.12:.2f}")