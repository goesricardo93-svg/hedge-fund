import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd

st.set_page_config(page_title="Terminal Ricardo - Hedge Fund Personal", layout="wide")

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX", "IWDA"]: return f"{t}.L"
    return f"{t}.SA"

st.title("🏛️ Terminal de Inteligência Financeira")

# --- SIDEBAR E AUTOMATIZAÇÃO ---
st.sidebar.header("Configurações")
ticker_bruto = st.sidebar.text_input("Ticker (Ex: VALE3, HGLG11, VWRA):", value="VALE3")
ticker_final = formatar_ticker(ticker_bruto)

aba1, aba2 = st.tabs(["📊 Dashboard de Análise", "🛡️ Planejamento PGBL"])

with aba1:
    try:
        data = yf.download(ticker_final, period="1y")
        if data.empty:
            st.error("Ativo não encontrado.")
        else:
            info = yf.Ticker(ticker_final).info
            motor = MotorAnalise()
            analise = motor.analizar(data, info, ticker_final)

            # Dashboard Superior
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Preço Atual", f"R$ {analise['preco']:.2f}")
            col2.metric("RSI (14)", f"{analise['rsi']:.1f}")
            col3.metric("Preço Teto", f"R$ {analise['preco_teto']:.2f}" if analise['preco_teto'] > 0 else "N/A")
            col4.subheader(f":{analise['cor']}[{analise['recomendacao']}]")

            # Gráfico Principal
            st.line_chart(data['close'])

            # Tabela de Barreiras Técnicas
            st.write("### 🏗️ Barreiras Técnicas e Fibonacci")
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Suporte (Mín 52 sem):** R$ {analise['suporte']:.2f}")
            c2.write(f"**Média 252p:** R$ {analise['ma252']:.2f}")
            c3.write(f"**Fibo 50%:** R$ {analise['fib']['50%']:.2f}")

    except Exception as e:
        st.warning(f"Erro ao carregar dados: {e}")

with aba2:
    st.header("🛡️ Gestão de Previdência (PGBL)")
    st.info("O aporte ideal em PGBL é de até 12% da sua Renda Bruta Anual para benefício fiscal máximo.")
    
    renda_anual = st.number_input("Sua Renda Bruta Anual Estimada (R$):", value=200000.0)
    aporte_max_fiscal = renda_anual * 0.12
    
    col_p1, col_p2 = st.columns(2)
    col_p1.metric("Teto de Aporte (12%)", f"R$ {aporte_max_fiscal:.2f}")
    
    ja_aportado = st.number_input("Quanto já aportou este ano? (R$):", value=0.0)
    falta = max(0.0, aporte_max_fiscal - ja_aportado)
    
    if falta > 0:
        st.warning(f"Você ainda pode aportar **R$ {falta:.2f}** para otimizar seu IR.")
    else:
        st.success("✅ Você já atingiu o limite de otimização fiscal do PGBL!")

    st.write("---")
    st.write("**Estratégia Defensoria:** Lembre-se de optar pela tabela **Regressiva** para levar a alíquota a 10% após 10 anos.")