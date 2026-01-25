# ==============================================================================
# HEDGE FUND RICARDO V160 - CLEAN ARCHITECTURE (SEM WIDGETS EXTERNOS)
# ==============================================================================
import streamlit as st
import time

# 1. CONFIGURAÇÃO (LINHA 1 OBRIGATÓRIA)
st.set_page_config(
    page_title="Hedge Fund v160",
    layout="wide",
    page_icon="💰",
    initial_sidebar_state="expanded"
)

# 2. STATUS DE CARREGAMENTO (FEEDBACK VISUAL)
status = st.empty()
status.info("🚀 Carregando sistema...")

# 3. IMPORTAÇÃO SEGURA
try:
    import pandas as pd
    import numpy as np
    import yfinance as yf
    import plotly.express as px
    # Removemos Scipy do topo para evitar crash silencioso
    # Removemos HTML components para evitar bloqueio do navegador
except ImportError as e:
    st.error(f"❌ Erro de Biblioteca: {e}")
    st.stop()

# 4. MOTOR LÓGICO (EMBUTIDO E SEGURO)
class MotorAnalise:
    def __init__(self):
        pass

    def baixar_dados(self, ticker):
        try:
            ticker = str(ticker).upper().strip()
            if not ticker.endswith(".SA") and not ticker.isdigit():
                ticker += ".SA"
            
            # TRUQUE DE SEGURANÇA: Threads=False evita travamento no Windows
            t_obj = yf.Ticker(ticker)
            hist = t_obj.history(period="1y") # Removido threads=False pois yf.Ticker não aceita, mas history é safe
            
            if hist.empty: return None, ticker
            return hist, ticker
        except: return None, ticker

    def analisar(self, hist, ticker):
        try:
            # Cálculos com Numpy/Pandas (Sem Scipy pesado)
            c = hist["Close"]
            atual = float(c.iloc[-1])
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            
            # RSI Manual
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100 / (1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1] > 0 else 50

            # Score Simples
            score = 50
            motivos = []
            if mme9 > mme21: score += 20; motivos.append("Tendência Alta (9>21)")
            else: score -= 20
            if rsi < 30: score += 15; motivos.append("Oportunidade (RSI Baixo)")
            
            decisao = "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"
            
            return {
                "score": score, "decisao": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "rsi": rsi, "mme9": mme9, "mme21": mme21
            }
        except: return None

# Limpa status
status.empty()

# ==============================================================================
# 5. INTERFACE (SEM HTML EXTERNO)
# ==============================================================================
st.title("💰 Hedge Fund Ricardo (v160)")

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Controle")
    if st.button("Limpar Cache"):
        st.cache_data.clear()
        st.rerun()
    st.info("Versão Segura: Sem widgets externos que travam a tela.")

# INICIALIZAÇÃO DE DADOS
if "carteira" not in st.session_state:
    st.session_state.carteira = pd.DataFrame([
        ["BBAS3", 100], ["VALE3", 100], ["PETR4", 100], ["TAEE11", 100]
    ], columns=["Ticker", "Qtd"])

# ABAS
tabs = st.tabs(["📊 Dashboard", "🔎 Análise", "💼 Carteira", "📡 Scanner"])

# --- ABA 1: DASHBOARD ---
with tabs[0]:
    if st.button("🔄 Atualizar Valores", type="primary"):
        total = 0
        vals = []
        motor = MotorAnalise()
        prog = st.progress(0)
        
        df = st.session_state.carteira.copy()
        for i, row in df.iterrows():
            hist, _ = motor.baixar_dados(row["Ticker"])
            if hist is not None:
                p = float(hist["Close"].iloc[-1])
                vals.append(p * row["Qtd"])
                total += p * row["Qtd"]
            else:
                vals.append(0.0)
            prog.progress((i+1)/len(df))
        
        df["Valor Atual"] = vals
        st.session_state.dash_df = df
        st.session_state.total = total
        st.rerun()

    if "total" in st.session_state:
        c1, c2 = st.columns(2)
        c1.metric("Patrimônio Total", f"R$ {st.session_state.total:,.2f}")
        c2.metric("Ativos", len(st.session_state.dash_df))
        
        c_graf, c_tab = st.columns([2, 1])
        with c_graf:
            st.plotly_chart(px.pie(st.session_state.dash_df, values="Valor Atual", names="Ticker", hole=0.4), use_container_width=True)
        with c_tab:
            st.dataframe(st.session_state.dash_df, height=300)
    else:
        st.info("Clique no botão acima para carregar o Dashboard.")

# --- ABA 2: ANÁLISE ---
with tabs[1]:
    col_input, col_btn = st.columns([3, 1])
    ticker = col_input.text_input("Ticker", "VALE3")
    if col_btn.button("Analisar"):
        motor = MotorAnalise()
        with st.spinner(f"Analisando {ticker}..."):
            hist, t_fmt = motor.baixar_dados(ticker)
            if hist is not None:
                res = motor.analisar(hist, t_fmt)
                if res:
                    # Scoreboard Bonito (Nativo)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Decisão", res['decisao'])
                    c2.metric("Score", f"{res['score']}/100")
                    c3.metric("Preço", f"R$ {res['preco']:.2f}")
                    c4.metric("RSI", f"{res['rsi']:.0f}")
                    
                    if res['motivos']:
                        st.success(f"**Motivos:** {res['motivos']}")
                    
                    # Gráfico Nativo (Seguro)
                    st.subheader("Gráfico de Preços (1 Ano)")
                    st.line_chart(hist["Close"], color="#00FF00")
            else:
                st.error("Não foi possível baixar dados. Verifique o ticker.")

# --- ABA 3: CARTEIRA ---
with tabs[2]:
    st.subheader("Sua Carteira")
    st.session_state.carteira = st.data_editor(st.session_state.carteira, num_rows="dynamic", use_container_width=True)

# --- ABA 4: SCANNER ---
with tabs[3]:
    st.subheader("Scanner Rápido")
    if st.button("Escanear IBOV (Top 5)"):
        lista = ["VALE3", "PETR4", "ITUB4", "BBDC4", "WEGE3"]
        res_scan = []
        motor = MotorAnalise()
        bar = st.progress(0)
        
        for i, t in enumerate(lista):
            hist, _ = motor.baixar_dados(t)
            if hist is not None:
                r = motor.analisar(hist, t)
                if r:
                    res_scan.append({
                        "Ticker": t,
                        "Preço": r['preco'],
                        "Score": r['score'],
                        "Decisão": r['decisao']
                    })
            bar.progress((i+1)/len(lista))
            
        st.dataframe(pd.DataFrame(res_scan).style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)