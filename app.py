import streamlit as st
import time

# ======================================================
# 1. CONFIGURAÇÃO (PRIMEIRA LINHA OBRIGATÓRIA)
# ======================================================
st.set_page_config(page_title="Hedge Fund v145", layout="wide")

# Mensagem de Debug Inicial
status_text = st.empty()
status_text.text("🚀 Inicializando... (Se travar aqui, é falta de biblioteca)")

# ======================================================
# 2. IMPORTAÇÃO SEGURA (PROTEGE CONTRA TELA BRANCA)
# ======================================================
try:
    import pandas as pd
    import numpy as np
    import yfinance as yf
    import plotly.express as px
    import scipy
    from scipy.signal import argrelextrema
except ImportError as e:
    st.error(f"❌ ERRO DE BIBLIOTECA: {e}")
    st.info("Instale: pip install scipy yfinance plotly pandas numpy")
    st.stop()

# Importa o Motor com proteção
try:
    from motor import MotorAnalise
except Exception as e:
    st.error(f"❌ ERRO NO ARQUIVO MOTOR.PY: {e}")
    st.stop()

# Módulos Opcionais (Scanner, Rebalance, etc)
# Se não existirem, cria funções vazias para não quebrar
try: from rebalance import rebalancear_e_aportar
except: 
    def rebalancear_e_aportar(*args): return pd.DataFrame()
try: from scanner import executar_scanner
except: 
    def executar_scanner(*args): return pd.DataFrame()
try: from options import BlackScholes
except: BlackScholes = None
try: from tax import calcular_darf
except: calcular_darf = None

status_text.empty() # Limpa a mensagem de carregamento

# ======================================================
# 3. LÓGICA DO SISTEMA
# ======================================================
if "versao_sistema" not in st.session_state:
    st.session_state.versao_sistema = "v145"
    st.success("Sistema Carregado com Sucesso!")

# Cache compatível com versões antigas e novas
try:
    cache_func = st.cache_data
except:
    cache_func = st.cache(suppress_st_warning=True)

@cache_func
def obter_dados(ticker, modo_crise):
    # Formata ticker
    t = str(ticker).upper().strip()
    if any(char.isdigit() for char in t) and "." not in t: t += ".SA"
    
    try:
        t_obj = yf.Ticker(t)
        hist = t_obj.history(period="2y")
        if hist.empty: return None
        try: info = t_obj.info
        except: info = {}
        return MotorAnalise().analisar(hist, info, t, modo_crise)
    except: return None

@cache_func
def download_longo(tickers):
    l = [t + ".SA" if "." not in t else t for t in tickers]
    return yf.download(l, period="5y", progress=False)['Close']

def carregar_carteira_padrao():
    return pd.DataFrame([
        ["BBAS3", 1703], ["VALE3", 152], ["PETR4", 900], ["TAEE4", 1000], 
        ["ALZR11", 100], ["HGLG11", 20], ["KNCR11", 27]
    ], columns=["Ticker", "Qtd"])

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = carregar_carteira_padrao()
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])

# ======================================================
# 4. INTERFACE
# ======================================================
st.title("💰 Hedge Fund Ricardo v145")

with st.sidebar:
    st.header("Configurações")
    # Checkbox é mais seguro que Toggle em versões antigas
    modo_crise = st.checkbox("Modo Crise (Defensivo)", value=False)
    
    if st.button("Recarregar Padrão"):
        st.session_state.carteira_acoes = carregar_carteira_padrao()
        st.experimental_rerun()

# Tabs
tabs = st.tabs(["Dash", "Análise", "Stress", "Matriz", "Carteira", "Scanner", "Monte Carlo", "Opções"])

with tabs[0]: # Dash
    if st.button("Atualizar Cotações"):
        with st.spinner("Baixando..."):
            vals = []
            df = st.session_state.carteira_acoes
            for _, r in df.iterrows():
                d = obter_dados(r["Ticker"], False)
                p = d['preco'] if d else 0.0
                vals.append(p * r["Qtd"])
            st.session_state.total_rv = sum(vals)
            st.success("Atualizado!")
    
    if "total_rv" in st.session_state:
        st.metric("Total Renda Variável", f"R$ {st.session_state.total_rv:,.2f}")

with tabs[1]: # Análise
    t = st.text_input("Ticker", "VALE3")
    if st.button("Analisar"):
        r = obter_dados(t, modo_crise)
        if r:
            c1, c2, c3 = st.columns(3)
            c1.metric("Score", f"{r['score_ia']}", r['decisao_ia'])
            c2.metric("Qualidade", r['score_qualidade'])
            c3.metric("Convicção", r['score_conviccao'])
            st.info(f"Motivos: {r['motivos']}")
            
            st.write("### Valuation")
            c4, c5, c6 = st.columns(3)
            c4.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c5.metric("Teto", f"R$ {r['p_teto']:.2f}")
            c6.metric("Margem", f"{r['margem']*100:.0f}%")
            st.write(r['modelos_val'])
            
            st.write("### Indicadores")
            st.json({k:v for k,v in r.items() if k in ['dy_anual','pvp','roe','rsi','beta_info']})

with tabs[2]: # Stress
    if st.button("Rodar Stress Test"):
        m = MotorAnalise()
        total = {}
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"], False)
            if d:
                res = m.calcular_stress_test(row["Ticker"], row["Qtd"], d['preco'])
                for k, v in res.items(): total[k] = total.get(k, 0) + v
        for k, v in total.items(): st.metric(k, f"R$ {v:,.2f}")

with tabs[3]: # Matriz
    if st.button("Gerar"):
        ts = [t+".SA" if "." not in t else t for t in st.session_state.carteira_acoes["Ticker"]]
        h = yf.download(ts, period="6mo", progress=False)['Close']
        st.plotly_chart(px.imshow(h.corr(), text_auto=True, color_continuous_scale="RdBu_r"))

with tabs[4]: # Carteira
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes)

with tabs[5]: # Scanner
    c1, c2 = st.columns(2)
    if c1.button("Scanner Ações"): st.dataframe(executar_scanner("ACOES"))
    if c2.button("Scanner FIIs"): st.dataframe(executar_scanner("FIIS"))

with tabs[6]: # Monte Carlo
    if st.button("Simular"):
        ts = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_longo(ts)
        if not h.empty:
            ret = h.pct_change().dropna().mean(axis=1)
            sim = MotorAnalise().monte_carlo_carteira(ret, 100000, 1000)
            st.line_chart(sim)

with tabs[7]: # Opções
    if BlackScholes:
        S = st.number_input("Preço Ativo", 30.0)
        K = st.number_input("Strike", 32.0)
        if st.button("Calcular"):
            st.write(BlackScholes(S, K, 30/365, 0.13, 0.3, "call").calcular_gregas())
    else: st.warning("Módulo Opções ausente")