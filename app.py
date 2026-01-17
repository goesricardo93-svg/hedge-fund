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
ticker_bruto = st.sidebar.text_input("Ticker:", value="VALE3")
ticker_final = formatar_ticker(ticker_bruto)

aba1, aba2, aba3 = st.tabs(["📊 Análise", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with aba1:
    try:
        # progress=False e auto_adjust=True ajudam na estabilidade
        data = yf.download(ticker_final, period="2y", progress=False)
        
        if data.empty:
            st.error("Ativo não encontrado.")
        else:
            ticker_obj = yf.Ticker(ticker_final)
            info = ticker_obj.info
            motor = MotorAnalise()
            analise = motor.analisar(data, info, ticker_final)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {analise['preco']:.2f}")
            c2.metric("RSI", f"{analise['rsi']:.1f}")
            c3.metric("Teto (Bazin/Graham)", f"R$ {analise['preco_teto']:.2f}" if analise['preco_teto'] > 0 else "N/A")
            c4.subheader(f":{analise['cor']}[{analise['recomendacao']}]")

            # Gráfico compatível com MultiIndex
            if isinstance(data.columns, pd.MultiIndex):
                st.line_chart(data['Close'][ticker_final])
            else:
                st.line_chart(data['Close'])

            st.write(f"**Suporte Anual (Mínima):** R$ {analise['suporte']:.2f} | **Resistência:** R$ {analise['resistencia']:.2f}")

    except Exception as e:
        st.error(f"Erro no Dashboard: {e}")

with aba2:
    st.header("🏙️ Scanner FIIs (CSV)")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        
        # Função para limpar pontos de milhar e vírgula decimal
        def clean_col(nome_col):
            return pd.to_numeric(df_fii[nome_col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')

        df_fii['P/VP_NUM'] = clean_col('P/VP')
        df_fii['LIQ_NUM'] = clean_col('LIQUIDEZ MEDIA DIARIA')
        
        filtrados = df_fii[(df_fii['P/VP_NUM'] >= 0.85) & (df_fii['P/VP_NUM'] <= 1.0) & (df_fii['LIQ_NUM'] >= 800000)].copy()
        
        st.write(f"🔍 **{len(filtrados)}** fundos na zona de valor.")
        st.dataframe(filtrados[['TICKER', 'PRECO', 'P/VP', 'DY', 'LIQUIDEZ MEDIA DIARIA']])
    except Exception as e:
        st.info("Coloque o CSV na pasta para ativar o scanner.")

with aba3:
    st.header("🛡️ Planejamento PGBL")
    renda = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Aporte Ideal (12%)", f"R$ {renda * 0.12:.2f}")
    st.write("Dica: Use esse valor para reduzir sua base tributável e turbinar sua restituição.")