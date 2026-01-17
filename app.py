import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import numpy as np

st.set_page_config(page_title="Terminal Ricardo", layout="wide")

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX", "IWDA"]: return f"{t}.L"
    return f"{t}.SA"

st.sidebar.header("🕹️ Controle")
ticker_bruto = st.sidebar.text_input("Ticker:", value="VALE3")
ticker_final = formatar_ticker(ticker_bruto)

aba1, aba2, aba3 = st.tabs(["📊 Análise", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with aba1:
    try:
        data = yf.download(ticker_final, period="1y", progress=False)
        if data.empty:
            st.error("Ativo não encontrado.")
        else:
            info = yf.Ticker(ticker_final).info
            motor = MotorAnalise()
            analise = motor.analisar(data, info, ticker_final)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {analise['preco']:.2f}")
            c2.metric("RSI", f"{analise['rsi']:.1f}")
            c3.metric("Teto", f"R$ {analise['preco_teto']:.2f}" if analise['preco_teto'] > 0 else "N/A")
            c4.subheader(f":{analise['cor']}[{analise['recomendacao']}]")

            # Tratamento para plotar o gráfico corretamente
            chart_data = data['Close'][ticker_final] if isinstance(data.columns, pd.MultiIndex) else data['Close']
            st.line_chart(chart_data)

    except Exception as e:
        st.error(f"Erro: {e}")

with aba2:
    st.header("🏙️ Scanner FIIs (P/VP 0.85-1.0)")
    try:
        # Lendo o CSV com o separador correto e tratando números brasileiros
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        
        # Converter colunas de texto/brasileiro para números
        def clean_num(col):
            return pd.to_numeric(df_fii[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')

        df_fii['P/VP'] = clean_num('P/VP')
        df_fii['LIQUIDEZ'] = clean_num('LIQUIDEZ MEDIA DIARIA')
        
        filtrados = df_fii[(df_fii['P/VP'] >= 0.85) & (df_fii['P/VP'] <= 1.0) & (df_fii['LIQUIDEZ'] >= 800000)]
        
        st.write(f"🔍 {len(filtrados)} fundos encontrados.")
        st.dataframe(filtrados[['TICKER', 'PRECO', 'P/VP', 'DY', 'LIQUIDEZ']])
    except Exception as e:
        st.info("💡 Coloque 'statusinvest-busca-avancada.csv' na mesma pasta.")

with aba3:
    st.header("🛡️ Planejamento PGBL")
    renda = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Teto de Aporte (12%)", f"R$ {renda * 0.12:.2f}")