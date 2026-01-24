# --- IMPORTANTE: NADA ANTES DESSA LINHA ---
import streamlit as st
st.set_page_config(page_title="Hedge Fund v143", layout="wide")
# ------------------------------------------

import pandas as pd
import numpy as np
import time

# Bloco Try/Except para garantir visualização do erro
try:
    import yfinance as yf
    import plotly.express as px
    import scipy
    from motor import MotorAnalise
except Exception as e:
    st.error(f"Erro de Biblioteca: {e}")
    st.stop()

# Helpers
def formatar_ticker(t):
    t = str(t).upper().strip()
    return f"{t}.SA" if any(char.isdigit() for char in t) and "." not in t else t

# Cache Compatível (Funciona em versões antigas e novas)
@st.cache(allow_output_mutation=True, suppress_st_warning=True)
def obter_dados_legacy(ticker, modo_crise):
    t = formatar_ticker(ticker)
    try:
        t_obj = yf.Ticker(t)
        hist = t_obj.history(period="2y")
        try: info = t_obj.info
        except: info = {"symbol": t}
        return MotorAnalise().analisar(hist, info, t, modo_crise)
    except: return None

@st.cache(allow_output_mutation=True, suppress_st_warning=True)
def download_historico(tickers):
    l = [formatar_ticker(t) for t in tickers]
    return yf.download(l, period="5y", progress=False)['Close']

# --- SIDEBAR & MENU (Substitui TABS que podem dar erro) ---
st.sidebar.title("Hedge Fund Ricardo v143")
modo_crise = st.sidebar.checkbox("Modo Crise", value=False)

menu = st.sidebar.radio("Navegação", [
    "Dashboard", 
    "Análise Detalhada", 
    "Stress Test", 
    "Correlação", 
    "Monte Carlo"
])

if st.sidebar.button("Limpar Cache"):
    st.legacy_caching.clear_cache()
    st.experimental_rerun()

# --- DADOS ---
if "carteira" not in st.session_state:
    st.session_state.carteira = pd.DataFrame([
        ["BBAS3", 1703], ["VALE3", 152], ["PETR4", 900], ["TAEE4", 1000], 
        ["ALZR11", 100], ["HGLG11", 20], ["KNCR11", 27]
    ], columns=["Ticker", "Qtd"])

# --- LÓGICA DAS TELAS ---

if menu == "Dashboard":
    st.title("📊 Visão Geral")
    if st.button("Atualizar Valores"):
        total = 0
        vals = []
        bar = st.progress(0)
        df = st.session_state.carteira
        for i, row in df.iterrows():
            d = obter_dados_legacy(row["Ticker"], False)
            p = d['preco'] if d else 0.0
            vals.append(p * row["Qtd"])
            bar.progress((i+1)/len(df))
        
        st.metric("Patrimônio Estimado", f"R$ {sum(vals):,.2f}")
        st.bar_chart(pd.DataFrame({"Valor": vals}, index=df["Ticker"]))
    else:
        st.info("Clique em Atualizar Valores para baixar cotações.")

elif menu == "Análise Detalhada":
    st.title("🔎 Deep Dive")
    tgt = st.text_input("Ativo", "VALE3")
    if st.button("Analisar"):
        r = obter_dados_legacy(tgt, modo_crise)
        if r:
            c1, c2, c3 = st.columns(3)
            c1.metric("Score", f"{r['score_ia']}", r['decisao_ia'])
            c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c3.metric("RSI", f"{r['rsi']:.0f}")
            
            st.write("### Modelos de Valuation")
            st.write(r['modelos_val'])
            
            st.write("### Dados Brutos")
            st.write(r['dados_fund'])
        else:
            st.error("Ativo não encontrado ou Yahoo bloqueou.")

elif menu == "Stress Test":
    st.title("🧪 Stress Test")
    if st.button("Simular"):
        m = MotorAnalise()
        res_total = {}
        for i, row in st.session_state.carteira.iterrows():
            d = obter_dados_legacy(row["Ticker"], False)
            p = d['preco'] if d else 0
            res = m.calcular_stress_test(formatar_ticker(row["Ticker"]), row["Qtd"], p)
            for k, v in res.items():
                res_total[k] = res_total.get(k, 0) + v
        
        for k, v in res_total.items():
            st.metric(k, f"R$ {v:,.2f}", delta_color="inverse")

elif menu == "Correlação":
    st.title("🔗 Matriz de Correlação")
    if st.button("Calcular"):
        ts = [formatar_ticker(t) for t in st.session_state.carteira["Ticker"]]
        h = yf.download(ts, period="6mo", progress=False)['Close']
        fig = px.imshow(h.corr(), text_auto=True, color_continuous_scale="RdBu_r")
        st.plotly_chart(fig)

elif menu == "Monte Carlo":
    st.title("🔮 Futuro (Monte Carlo)")
    if st.button("Simular 5 Anos"):
        ts = [formatar_ticker(t) for t in st.session_state.carteira["Ticker"]]
        h = download_historico(ts)
        if not h.empty:
            ret = h.pct_change().dropna().mean(axis=1)
            # Valor aproximado fixo para teste
            sim = MotorAnalise().monte_carlo_carteira(ret, 100000, 1000)
            st.line_chart(sim)