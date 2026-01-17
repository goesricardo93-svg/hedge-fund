import streamlit as st
import yfinance as yf
from motor import MotorAnalise  # Agora minúsculo conforme o arquivo
import pandas as pd
import numpy as np

st.set_page_config(page_title="Terminal Ricardo - Hedge Fund", layout="wide")

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX", "IWDA"]: return f"{t}.L"
    return f"{t}.SA"

st.sidebar.header("🕹️ Controle de Operações")
ticker_bruto = st.sidebar.text_input("Ticker:", value="VALE3")
ticker_final = formatar_ticker(ticker_bruto)

aba1, aba2, aba3 = st.tabs(["📊 Dashboard Principal", "🏙️ Scanner de FIIs (CSV)", "🛡️ PGBL & IR"])

with aba1:
    try:
        # Download dos dados
        data = yf.download(ticker_final, period="1y", progress=False)
        if data.empty:
            st.error("Ativo não encontrado ou erro na conexão.")
        else:
            info = yf.Ticker(ticker_final).info
            motor = MotorAnalise()
            analise = motor.analizar(data, info, ticker_final)

            # Cabeçalho de Métricas
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {analise['preco']:.2f}")
            c2.metric("RSI (14)", f"{analise['rsi']:.1f}")
            c3.metric("Preço Teto", f"R$ {analise['preco_teto']:.2f}" if analise['preco_teto'] > 0 else "N/A")
            c4.subheader(f":{analise['cor']}[{analise['recomendacao']}]")

            st.line_chart(data['Close'])

            st.write("### 🏗️ Barreiras Técnicas")
            col_a, col_b = st.columns(2)
            col_a.write(f"**Suporte Anual:** R$ {analise['suporte']:.2f}")
            col_b.write(f"**Fibo 50% (Equilíbrio):** R$ {analise['fib']['50%']:.2f}")

    except Exception as e:
        st.error(f"Ocorreu um erro na análise: {e}")

with aba2:
    st.header("🏙️ Scanner Automatizado de FIIs")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";")
        # Aplicando seus filtros: P/VP entre 0.85 e 1.0 e Liquidez > 800k
        # Tratando as vírgulas do CSV brasileiro para ponto
        df_fii['P/VP'] = df_fii['P/VP'].str.replace(',', '.').astype(float)
        df_fii['LIQUIDEZ MEDIA DIARIA'] = df_fii['LIQUIDEZ MEDIA DIARIA'].str.replace('.', '').str.replace(',', '.').astype(float)
        
        filtrados = df_fii[(df_fii['P/VP'] >= 0.85) & (df_fii['P/VP'] <= 1.0) & (df_fii['LIQUIDEZ MEDIA DIARIA'] >= 800000)]
        
        st.write(f"Encontrados **{len(filtrados)}** fundos na zona de valor (P/VP 0.85-1.0).")
        st.dataframe(filtrados[['TICKER', 'PRECO', 'P/VP', 'DY', 'LIQUIDEZ MEDIA DIARIA']])
    except:
        st.info("💡 Coloque o arquivo 'statusinvest-busca-avancada.csv' na pasta para ver o scanner.")

with aba3:
    st.header("🛡️ Proteção Fiscal PGBL")
    renda = st.number_input("Renda Bruta Anual:", value=200000.0)
    teto = renda * 0.12
    st.metric("Limite de Isenção (12%)", f"R$ {teto:.2f}")
    st.write("Utilize este valor para abater do seu Imposto de Renda e reinvestir o diferencial.")