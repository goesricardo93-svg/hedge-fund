import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import requests
import smtplib
from email.mime.text import MIMEText
from motor import MotorAnalise

# ======================================================
# 1. CONFIGURAÇÕES & SEGREDOS
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | v6.0", layout="wide")

TELEGRAM_TOKEN = "8515547858:AAHDCGoE-Fg-51If_r_5xZSO2YHgoTrceZQ"
TELEGRAM_CHAT_ID = "833554938"
EMAIL_USER = "goes.ricardo93@gmail.com"
EMAIL_PASS = "Ysi0xgki5-"

# ======================================================
# 2. FUNÇÕES DE SUPORTE
# ======================================================
def enviar_telegram(msg):
    try:
        if "8515547858:AAHDCGoE-Fg-51If_r_5xZSO2YHgoTrceZQ" not in TELEGRAM_TOKEN: return
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except: pass

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None, None
        
        motor = MotorAnalise()
        r = motor.analisar(hist, t.info, ticker)
        return r, t.info
    except Exception as e:
        print(f"Erro: {e}")
        return None, None

# --- NOVA LÓGICA DE APORTES COM METAS POR SETOR ---
def sugerir_aportes(df, aporte, metas_setor):
    """
    df: DataFrame da carteira
    aporte: Valor em R$
    metas_setor: DataFrame com colunas ['Setor', 'Meta'] (ex: 0.20 para 20%)
    """
    if df.empty: return pd.DataFrame()
    df = df.copy()
    
    # 1. Dados Financeiros
    df["Valor"] = df["Qtd"] * df["Cotação"]
    total = df["Valor"].sum()
    if total == 0: total = 1 # Evita div por zero
    
    df["Peso_Atual"] = df["Valor"] / total

    # 2. Mapear a Meta do Setor para cada Ativo
    # Transforma o DF de metas em dicionário: {'Bancos': 0.20, 'FII': 0.40...}
    dict_metas = dict(zip(metas_setor["Setor"], metas_setor["Meta"]))
    
    # Aplica a meta ao ativo (se não achar o setor, assume 5%)
    df["Meta_Setorial"] = df["Setor"].map(dict_metas).fillna(0.05)
    
    # Divide a meta do setor pelo número de ativos naquele setor
    # Ex: Se Meta Bancos é 20% e tenho 2 bancos, a meta de cada um é 10%
    qtd_por_setor = df.groupby("Setor")["Ticker"].transform("count")
    df["Peso_Alvo"] = df["Meta_Setorial"] / qtd_por_setor

    # 3. Cálculo do Score de Aporte
    # Prioridade = (Falta muito para o alvo?) + (Está barato/Score alto?) + (Preço < PM?)
    df["Gap"] = df["Peso_Alvo"] - df["Peso_Atual"]
    
    df["Score_IA"] = (
        (df["Gap"] * 100 * 2) +          # Peso 2x para rebalanceamento
        (df["Score"] / 100) +            # Peso 1x para qualidade técnica
        ((df["PM"] - df["Cotação"]) / df["PM"]) # Peso 1x para oportunidade preço
    )
    
    # Remove negativos (quem está acima do alvo não recebe aporte agora)
    df["Score_IA"] = df["Score_IA"].clip(lower=0)

    # 4. Distribuição do Dinheiro
    soma_score = df["Score_IA"].sum()
    if soma_score > 0:
        df["Aporte_Sugerido"] = (df["Score_IA"] / soma_score) * aporte
    else:
        df["Aporte_Sugerido"] = 0
        
    # Retorna tabela limpa e ordenada
    return df[df["Aporte_Sugerido"] > 1].sort_values("Aporte_Sugerido", ascending=False)

def monte_carlo(patrimonio_atual, aporte, meses=120, sims=1000):
    res = []
    mu = 0.008 
    sigma = 0.05 
    for _ in range(sims):
        pat = patrimonio_atual
        for _ in range(meses):
            pat = pat * (1 + np.random.normal(mu, sigma)) + aporte
        res.append(pat)
    return res

def stress_test(valor):
    cenarios = {"2008 (-50%)": -0.50, "COVID (-35%)": -0.35, "Juros Altos (-15%)": -0.15}
    out = {}
    for c, choque in cenarios.items():
        hist = [valor]
        v = valor * (1 + choque)
        hist.append(v)
        for _ in range(10):
            v = v * (1 + 0.005)
            hist.append(v)
        out[c] = hist
    return out

# ======================================================
# 3. INICIALIZAÇÃO DE DADOS
# ======================================================
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 1703, 24.48, "Bancos"],
        ["VALE3.SA", 152, 54.79, "Mineração"],
        ["ITSA4.SA", 1174, 9.63, "Holding"],
        ["TAEE11.SA", 500, 35.00, "Elétricas"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_fiis" not in st.session_state:
    st.session_state.carteira_fiis = pd.DataFrame([
        ["HGLG11.SA", 50, 160.00, "Logística"],
        ["KNCR11.SA", 100, 100.50, "Papel"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000, "Pós"],
        ["PGBL BTG", 50000, "Multimercado"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

# --- NOVO: METAS POR SETOR (EDITÁVEL) ---
if "metas_setor" not in st.session_state:
    st.session_state.metas_setor = pd.DataFrame([
        ["Bancos", 0.15],
        ["Mineração", 0.10],
        ["Elétricas", 0.15],
        ["Holding", 0.10],
        ["Logística", 0.20],
        ["Papel", 0.20],
        ["Outros", 0.10]
    ], columns=["Setor", "Meta"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# 4. INTERFACE
# ======================================================
st.sidebar.title("📊 Painel de Controle")

# --- BLOCO DE METAS (SIDEBAR) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Metas por Setor (%)")
st.sidebar.info("Ajuste aqui para calibrar a IA de aportes.")
# Editor de metas na lateral
df_metas = st.sidebar.data_editor(
    st.session_state.metas_setor, 
    column_config={"Meta": st.column_config.NumberColumn(format="%.2f")},
    num_rows="dynamic",
    key="editor_metas"
)
st.session_state.metas_setor = df_metas

# Validação visual da soma
soma_metas = df_metas["Meta"].sum()
if soma_metas != 1.0:
    st.sidebar.warning(f"⚠️ Soma das metas: {soma_metas*100:.0f}% (Ideal: 100%)")
else:
    st.sidebar.success("✅ Metas balanceadas (100%)")

st.sidebar.markdown("---")
ticker_analise = st.sidebar.text_input("🔍 Analisar Ticker:",


