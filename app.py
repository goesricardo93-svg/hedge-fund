import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd

st.set_page_config(page_title="Terminal Ricardo - Hedge Fund", layout="wide")

# Cache para evitar bloqueio do Yahoo Finance
@st.cache_data(ttl=600)
def carregar_dados_completos(ticker):
    data = yf.download(ticker, period="2y", progress=False)
    info = yf.Ticker(ticker).info
    return data, info

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX"]: return f"{t}.L"
    return f"{t}.SA"

st.sidebar.header("🕹️ Comando Central")
ticker_raw = st.sidebar.text_input("Ticker:", value="BBSE3")
ticker_final = formatar_ticker(ticker_raw)

aba1, aba2, aba3 = st.tabs(["📊 Inteligência de Mercado", "🏙️ Scanner FIIs (CSV)", "🛡️ Gestão PGBL"])

with aba1:
    try:
        data, info = carregar_dados_completos(ticker_final)
        res = MotorAnalise().analisar(data, info, ticker_final)
        
        if res:
            # --- DASHBOARD SUPERIOR ---
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}" if res['preco_teto'] > 0 else "N/A", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Tendência", res['tendencia'])

            st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
            
            # --- GRÁFICO COM LEGENDA NAS LINHAS ---
            df_grafico = pd.DataFrame(res['precos_serie'])
            df_grafico.columns = ['Preço de Mercado'] # Legenda da linha azul
            
            # Criando as linhas horizontais com nomes que servem de legenda
            df_grafico['🛡️ Suporte Anual'] = res['suporte']
            df_grafico['🚫 Stop Loss'] = res['stop_loss']
            
            if res['preco_teto'] > 0:
                df_grafico['🎯 Stop Gain (Alvo)'] = res['stop_gain']
            
            # Cores: Azul (Preço), Verde (Suporte), Vermelho (Stop Loss), Amarelo (Stop Gain)
            cores_grafico = ["#29b5e8", "#2ecc71", "#e74c3c", "#f1c40f"]
            st.line_chart(df_grafico, color=cores_grafico)

            # --- BLOCOS DE ANÁLISE DETALHADA ---
            col_val, col_tec, col_risk = st.columns(3)
            
            with col_val:
                st.subheader("🏛️ Valuation")
                st.write(f"**Graham:** R$ {res['p_graham']:.2f}")
                st.write(f"**Bazin (6%):** R$ {res['p_bazin']:.2f}")
                st.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")
                st.write(f"**Média Teto:** R$ {res['preco_teto']:.2f}")
            
            with col_tec:
                st.subheader("📈 Técnico")
                st.write(f"**Média 252 (Anual):** R$ {res['ma252']:.2f}")
                st.write(f"**Suporte Anual:** R$ {res['suporte']:.2f}")
                st.write(f"**Resistência Anual:** R$ {res['resistencia']:.2f}")
            
            with col_risk:
                st.subheader("🛡️ Gestão de Trade")
                st.error(f"**Stop Loss:** R$ {res['stop_loss']:.2f}")
                st.success(f"**Stop Gain:** R$ {res['stop_gain']:.2f}")
                st.write(f"**Perfil Ativo:** {res['tipo']}")

    except Exception as e:
        st.error(f"Erro ao processar {ticker_final}: {e}")

with aba2:
    st.header("🏙️ Scanner de FIIs com Balizadores")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        def cl(n): return pd.to_numeric(df_fii[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
        
        df_fii['P/VP_N'], df_fii['LIQ_N'] = cl('P/VP'), cl('LIQUIDEZ MEDIA DIARIA')
        df_fii['PRECO_N'] = cl('PRECO')
        
        # Filtro Ricardo
        f = df_fii[(df_fii['P/VP_N'] >= 0.85) & (df_fii['P/VP_N']