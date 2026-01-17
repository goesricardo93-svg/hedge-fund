import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd

st.set_page_config(page_title="Terminal Ricardo", layout="wide")

@st.cache_data(ttl=600)
def get_data(ticker):
    d = yf.download(ticker, period="2y", progress=False)
    i = yf.Ticker(ticker).info
    return d, i

st.sidebar.header("🕹️ Comando Central")
ticker_input = st.sidebar.text_input("Ticker:", value="BBSE3")
t_final = ticker_input.upper().strip()
if "." not in t_final:
    t_final = f"{t_final}.L" if t_final in ["VWRA","VUSA","CSPX"] else f"{t_final}.SA"

tab1, tab2, tab3 = st.tabs(["📊 Valuation & Trades", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with tab1:
    try:
        data, info = get_data(t_final)
        res = MotorAnalise().analisar(data, info, t_final)
        
        if res:
            # Layout de Métricas Principais
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}", f"{((res['preco_teto']/res['preco'])-1)*100:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Tendência", res['tendencia'])

            st.line_chart(res['precos_serie'])

            # --- TABELA DE VALUATION E STOPS ---
            st.write("### 🧮 Inteligência de Valor e Operação")
            col_v, col_s = st.columns(2)
            
            with col_v:
                st.write("**Modelos de Valuation**")
                st.write(f"- Graham: R$ {res['p_graham']:.2f}")
                st.write(f"- Bazin (6%): R$ {res['p_bazin']:.2f}")
                st.write(f"- Gordon: R$ {res['p_gordon']:.2f}")
            
            with col_s:
                st.write("**Gerenciamento de Trade**")
                st.error(f"Stop Loss (Segurança): R$ {res['stop_loss']:.2f}")
                st.success(f"Stop Gain (Alvo): R$ {res['stop_gain']:.2f}")
                st.info(f"Suporte Anual: R$ {res['suporte']:.2f} | Resistência: R$ {res['resistencia']:.2f}")

    except Exception as e:
        st.error(f"Aguarde uns instantes ou verifique o ticker. Erro: {e}")

with tab2:
    st.header("Scanner FIIs")
    try:
        df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        def cl(n): return pd.to_numeric(df[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
        df['P/VP_N'], df['LIQ_N'] = cl('P/VP'), cl('LIQUIDEZ MEDIA DIARIA')
        f = df[(df['P/VP_N'] >= 0.85) & (df['P/VP_N'] <= 1.0) & (df['LIQ_N'] >= 800000)].copy()
        # Adicionando Suporte e Stops no Scanner
        f['Stop Loss'] = f['PRECO'].str.replace(',','.').astype(float) * 0.95
        st.dataframe(f[['TICKER', 'PRECO', 'P/VP', 'DY', 'Stop Loss']])
    except: st.info("CSV não encontrado.")

with tab3:
    r = st.number_input("Renda Anual:", value=200000.0)
    st.metric("Aporte PGBL (12%)", f"R$ {r*0.12:.2f}")