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
st.set_page_config(page_title="Hedge Fund Ricardo | v6.1 Fix", layout="wide")

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

# --- LÓGICA DE APORTES COM METAS POR SETOR ---
def sugerir_aportes(df, aporte, metas_setor):
    if df.empty: return pd.DataFrame()
    df = df.copy()
    
    # 1. Dados Financeiros
    df["Valor"] = df["Qtd"] * df["Cotação"]
    total = df["Valor"].sum()
    if total == 0: total = 1 
    
    df["Peso_Atual"] = df["Valor"] / total

    # 2. Mapear a Meta do Setor
    dict_metas = dict(zip(metas_setor["Setor"], metas_setor["Meta"]))
    df["Meta_Setorial"] = df["Setor"].map(dict_metas).fillna(0.05)
    
    # Divide a meta do setor pelo número de ativos
    qtd_por_setor = df.groupby("Setor")["Ticker"].transform("count")
    df["Peso_Alvo"] = df["Meta_Setorial"] / qtd_por_setor

    # 3. Score de Aporte
    df["Gap"] = df["Peso_Alvo"] - df["Peso_Atual"]
    
    df["Score_IA"] = (
        (df["Gap"] * 100 * 2) +          
        (df["Score"] / 100) +            
        ((df["PM"] - df["Cotação"]) / df["PM"]) 
    )
    
    df["Score_IA"] = df["Score_IA"].clip(lower=0)

    # 4. Distribuição
    soma_score = df["Score_IA"].sum()
    if soma_score > 0:
        df["Aporte_Sugerido"] = (df["Score_IA"] / soma_score) * aporte
    else:
        df["Aporte_Sugerido"] = 0
        
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

df_metas = st.sidebar.data_editor(
    st.session_state.metas_setor, 
    column_config={"Meta": st.column_config.NumberColumn(format="%.2f")},
    num_rows="dynamic",
    key="editor_metas"
)
st.session_state.metas_setor = df_metas

soma_metas = df_metas["Meta"].sum()
if soma_metas != 1.0:
    st.sidebar.warning(f"⚠️ Soma: {soma_metas*100:.0f}% (Ideal: 100%)")
else:
    st.sidebar.success("✅ Metas OK (100%)")

st.sidebar.markdown("---")
# AQUI ESTAVA O ERRO ANTES, AGORA ESTÁ CORRIGIDO:
ticker_analise = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3.SA").upper()

# --- ABAS ---
tabs = st.tabs(["🔎 Análise", "💼 Ações", "🏢 FIIs", "💰 Fixa & PGBL"])

# ABA 1: ANÁLISE
with tabs[0]:
    st.header(f"Raio-X: {ticker_analise}")
    r, info = obter_dados(ticker_analise)
    if r:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço", f"R$ {r['preco']:.2f}")
        c2.metric("Bazin (6%)", f"R$ {r['p_bazin']:.2f}", delta=f"{r['p_bazin']-r['preco']:.2f}")
        c3.metric("RSI", f"{r['rsi']:.0f}")
        c4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        
        # Gráfico simples
        try:
            hist_chart = yf.download(ticker_analise, period="1y", progress=False)["Close"]
            if not hist_chart.empty:
                st.line_chart(hist_chart)
        except:
            st.warning("Gráfico indisponível no momento.")
    else:
        st.warning("Ticker não encontrado ou erro na API.")

# ABA 2: AÇÕES
with tabs[1]:
    st.subheader("Carteira de Ações")
    df_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", key="ed_ac", use_container_width=True)
    st.session_state.carteira_acoes = df_acoes

    if st.button("🔄 Calcular Ações"):
        res = []
        bar = st.progress(0)
        for i, row in df_acoes.iterrows():
            r, info = obter_dados(row["Ticker"])
            if r:
                score = 0
                if r["preco"] < r["p_bazin"]: score += 40
                if r["rsi"] < 40: score += 30
                if row["PM"] > r["preco"]: score += 30
                
                status = "MANTER"
                if score >= 70: status = "🟢 COMPRA"
                
                # Alerta
                chave = f"{row['Ticker']}_{status}"
                if "COMPRA" in status and chave not in st.session_state.alertas_enviados:
                    enviar_telegram(f"AÇÃO: {row['Ticker']} barato! Bazin: {r['p_bazin']:.2f}")
                    st.session_state.alertas_enviados.add(chave)

                res.append({**row.to_dict(), "Cotação": r["preco"], "Score": score, "Bazin": r["p_bazin"]})
            else:
                res.append({**row.to_dict(), "Cotação": 0, "Score": 0, "Bazin": 0})
            bar.progress((i+1)/len(df_acoes))
        st.session_state.df_final_acoes = pd.DataFrame(res)
        st.rerun()

    if "df_final_acoes" in st.session_state:
        df_final = st.session_state.df_final_acoes
        st.dataframe(df_final.style.background_gradient(subset=["Score"], cmap="Greens"), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### 🤖 IA de Aporte (Baseada nas Metas)")
            val = st.number_input("Valor Aporte", 1000.0)
            if st.button("Sugerir Aporte"):
                sug = sugerir_aportes(df_final, val, st.session_state.metas_setor)
                if not sug.empty:
                    st.dataframe(sug[["Ticker", "Setor", "Peso_Atual", "Peso_Alvo", "Aporte_Sugerido"]].style.format({
                        "Peso_Atual": "{:.1%}", "Peso_Alvo": "{:.1%}", "Aporte_Sugerido": "R$ {:.2f}"
                    }))
                else:
                    st.info("Nenhum aporte sugerido (Carteira balanceada ou Score baixo).")
        
        with c2:
            st.write("#### 📉 Stress Test")
            pat = (df_final["Cotação"] * df_final["Qtd"]).sum()
            st.metric("Patrimônio Ações", f"R$ {pat:,.2f}")
            if st.button("Rodar Stress"):
                fig = go.Figure()
                for k, v in stress_test(pat).items():
                    fig.add_trace(go.Scatter(y=v, name=k))
                st.plotly_chart(fig, use_container_width=True)

# ABA 3: FIIs
with tabs[2]:
    st.subheader("Carteira de FIIs")
    df_fiis = st.data_editor(st.session_state.carteira_fiis, num_rows="dynamic", key="ed_fi", use_container_width=True)
    st.session_state.carteira_fiis = df_fiis

    if st.button("🔄 Calcular FIIs"):
        res = []
        for _, row in df_fiis.iterrows():
            r, info = obter_dados(row["Ticker"])
            if r:
                dy = info.get('dividendYield', 0)
                res.append({
                    "Ticker": row["Ticker"], 
                    "Setor": row["Setor"],
                    "Preço": r["preco"], 
                    "DY": f"{dy*100:.2f}%",
                    "PVP Est.": f"{(r['preco']/r['p_bazin'])*0.6:.2f}" 
                })
        st.session_state.df_fiis_final = pd.DataFrame(res)
        st.rerun()
        
    if "df_fiis_final" in st.session_state:
        st.dataframe(st.session_state.df_fiis_final, use_container_width=True)

# ABA 4: RF
with tabs[3]:
    st.subheader("Renda Fixa e PGBL")
    df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", key="ed_rf", use_container_width=True)
    st.session_state.carteira_rf = df_rf
    
    tot_rf = df_rf["Saldo Atual"].sum()
    st.metric("Total RF", f"R$ {tot_rf:,.2f}")
    
    if st.button("Projeção Global (Monte Carlo)"):
        pat_ac = (st.session_state.df_final_acoes["Cotação"] * st.session_state.df_final_acoes["Qtd"]).sum() if "df_final_acoes" in st.session_state else 0
        total = tot_rf + pat_ac
        
        # Simula 2k aporte/mês
        sims = monte_carlo(total, 2000)
        
        fig = go.Figure(go.Histogram(x=sims, nbinsx=30))
        fig.update_layout(title="Patrimônio Projetado (10 Anos)")
        st.plotly_chart(fig, use_container_width=True)