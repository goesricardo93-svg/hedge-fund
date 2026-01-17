import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd

st.set_page_config(page_title="Terminal Ricardo", layout="wide")

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX"]: return f"{t}.L"
    return f"{t}.SA"

st.sidebar.header("🕹️ Sistema de Decisão")
ticker_input = st.sidebar.text_input("Ticker:", value="BBSE3")
ticker_final = formatar_ticker(ticker_input)

tab1, tab2, tab3 = st.tabs(["📊 Análise Técnica & Valor", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with tab1:
    try:
        data = yf.download(ticker_final, period="2y", progress=False)
        if not data.empty:
            info = yf.Ticker(ticker_final).info
            m = MotorAnalise()
            res = m.analisar(data, info, ticker_final)

            # --- HEADER DE MÉTRICAS ---
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}" if res['preco_teto'] > 0 else "N/A", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Tendência", res['tendencia'])

            st.subheader(f"Veredito: :{res['cor']}[{res['recomendacao']}]")
            
            # --- GRÁFICO ---
            st.line_chart(res['precos_serie'])

            # --- DETALHES TÉCNICOS ---
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.write("**📊 Valuation**")
                st.write(f"Preço Teto: R$ {res['preco_teto']:.2f}")
                st.write(f"Upside Estimado: {res['upside']:.2f}%")
            with col_b:
                st.write("**📈 Técnico**")
                st.write(f"Média 252 (Anual): R$ {res['ma252']:.2f}")
                st.write(f"Suporte (Mínima): R$ {res['suporte']:.2f}")
            with col_c:
                st.write("**🛡️ Risco**")
                st.write(f"Tipo: {res['tipo']}")
                st.write(f"Status RSI: {'Sobrecomprado' if res['rsi'] > 70 else 'Normal'}")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")

# (As outras abas de FII e PGBL permanecem como estavam para não 'cagar' o que deu certo)
with tab2:
    st.header("Scanner de FIIs")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        def clean(c): return pd.to_numeric(df_fii[c].astype(str).str.replace('.','',regex=False).str.replace(',','.',regex=False), errors='coerce')
        df_fii['P/VP_N'] = clean('P/VP')
        df_fii['LIQ_N'] = clean('LIQUIDEZ MEDIA DIARIA')
        f = df_fii[(df_fii['P/VP_N'] >= 0.85) & (df_fii['P/VP_N'] <= 1.0) & (df_fii['LIQ_N'] >= 800000)].copy()
        st.dataframe(f[['TICKER', 'PRECO', 'P/VP', 'DY', 'LIQUIDEZ MEDIA DIARIA']])
    except: st.info("Adicione o CSV na pasta.")

with tab3:
    st.header("PGBL")
    r = st.number_input("Renda Anual:", value=200000.0)
    st.metric("Aporte 12%", f"R$ {r*0.12:.2f}")