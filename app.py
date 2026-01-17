import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd

st.set_page_config(page_title="Terminal Ricardo", layout="wide")

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX", "IWDA"]: return f"{t}.L"
    return f"{t}.SA"

st.sidebar.header("🕹️ Controle")
ticker_input = st.sidebar.text_input("Ticker:", value="BBSE3")
ticker_final = formatar_ticker(ticker_input)

aba1, aba2, aba3 = st.tabs(["📊 Análise", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with aba1:
    try:
        # Forçamos o download a ser simples
        data = yf.download(ticker_final, period="2y", progress=False)
        
        if data.empty:
            st.error("Ativo não encontrado.")
        else:
            ticker_obj = yf.Ticker(ticker_final)
            info = ticker_obj.info
            motor = MotorAnalise()
            analise = motor.analisar(data, info, ticker_final)

            if analise:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {analise['preco']:.2f}")
                c2.metric("RSI (14)", f"{analise['rsi']:.1f}")
                c3.metric("Preço Teto", f"R$ {analise['preco_teto']:.2f}" if analise['preco_teto'] > 0 else "N/A")
                c4.subheader(f":{analise['cor']}[{analise['recomendacao']}]")

                # Gráfico usando a série limpa do motor
                st.line_chart(analise['precos_serie'])
                st.caption(f"Suporte Anual (Mínima): R$ {analise['suporte']:.2f}")
            else:
                st.warning("Dados insuficientes para este ticker.")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")

with aba2:
    st.header("🏙️ Scanner FIIs (P/VP 0.85-1.0)")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        def clean(c): return pd.to_numeric(df_fii[c].astype(str).str.replace('.','',regex=False).str.replace(',','.',regex=False), errors='coerce')
        df_fii['P/VP_N'] = clean('P/VP')
        df_fii['LIQ_N'] = clean('LIQUIDEZ MEDIA DIARIA')
        f = df_fii[(df_fii['P/VP_N'] >= 0.85) & (df_fii['P/VP_N'] <= 1.0) & (df_fii['LIQ_N'] >= 800000)].copy()
        st.write(f"🔍 {len(f)} fundos encontrados.")
        st.dataframe(f[['TICKER', 'PRECO', 'P/VP', 'DY', 'LIQUIDEZ MEDIA DIARIA']])
    except:
        st.info("Coloque 'statusinvest-busca-avancada.csv' na pasta.")

with aba3:
    st.header("🛡️ Planejamento PGBL")
    r = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Teto de Aporte (12%)", f"R$ {r * 0.12:.2f}")