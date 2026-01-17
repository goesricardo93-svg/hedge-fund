import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime

# --- IMPORTS MODULARES ---
# Se der erro aqui, é porque os arquivos não estão na mesma pasta no GitHub
try:
    from motor import MotorAnalise
    from alerts import disparar_alerta
    from scanner import scanner_fiis_csv
except ImportError as e:
    st.error(f"Erro Crítico: Arquivos de módulo não encontrados ({e}). Verifique se motor.py, alerts.py e scanner.py estão na raiz do GitHub.")
    st.stop()

# ======================================================
# CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | Modular", layout="wide")
motor = MotorAnalise()

# ======================================================
# CACHE DE DADOS (CRUCIAL)
# ======================================================
@st.cache_data(ttl=3600)
def get_data_ia(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None
        # O motor retorna um dicionário simples, perfeito para cache
        return motor.analisar(hist, t.info, ticker)
    except: return None

# ======================================================
# DADOS SESSION STATE
# ======================================================
if "carteira" not in st.session_state:
    st.session_state.carteira = pd.DataFrame([
        ["BBAS3.SA", "Bancos"], ["VALE3.SA", "Mineração"], 
        ["TAEE11.SA", "Elétricas"], ["PETR4.SA", "Petróleo"],
        ["WEGE3.SA", "Industrial"], ["ITSA4.SA", "Holding"]
    ], columns=["Ticker", "Setor"])

if "alertas_hoje" not in st.session_state:
    st.session_state.alertas_hoje = []

# ======================================================
# INTERFACE
# ======================================================
st.sidebar.title("🏛️ Terminal Ricardo")
ticker_input = st.sidebar.text_input("Ticker", "BBAS3.SA").upper()

tabs = st.tabs(["🔎 Raio-X IA", "🏆 Ranking & Alertas", "🏢 Scanner FIIs"])

# --- ABA 1: RAIO-X ---
with tabs[0]:
    r = get_data_ia(ticker_input)
    
    if r:
        # 1. Cabeçalho de Decisão
        c1, c2 = st.columns([1, 3])
        c1.metric("Score IA", f"{r['score_ia']}/100")
        if "COMPRA" in r['decisao_ia']:
            c2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']:
            c2.error(f"### {r['decisao_ia']}")
        else:
            c2.warning(f"### {r['decisao_ia']}")
        st.caption(f"**Motivos:** {r['motivos']}")
        
        st.divider()

        # 2. Métricas Técnicas e Fundamentais
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço", f"R$ {r['preco']:.2f}")
        k2.metric("Teto Bazin", f"R$ {r['p_bazin']:.2f}", delta=f"{r['p_bazin']-r['preco']:.2f}")
        k3.metric("Justo Graham", f"R$ {r['p_graham']:.2f}")
        k4.metric("RSI (14)", f"{r['rsi']:.0f}")

        # 3. Gráfico Técnico
        hist = yf.download(ticker_input, period="2y", progress=False)
        if not hist.empty:
            # Tratamento para multi-index do yfinance novo
            close = hist["Close"] if "Close" in hist else hist.iloc[:,0]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist.index, y=close, name="Preço", line_color='blue'))
            
            # Linhas de Suporte/Resistência calculadas pelo Motor
            fig.add_hline(y=r['stop_gain'], line_dash="dash", line_color="green", annotation_text="ALVO")
            fig.add_hline(y=r['stop_loss'], line_dash="dash", line_color="red", annotation_text="STOP")
            fig.add_hline(y=r['suporte'], line_dash="dot", line_color="grey", annotation_text="SUPORTE")
            
            st.plotly_chart(fig, use_container_width=True)

# --- ABA 2: RANKING & ALERTAS ---
with tabs[1]:
    st.subheader("🏆 Ranking Automático da Carteira")
    
    if st.button("🔄 Processar Ranking IA"):
        resultados = []
        bar = st.progress(0)
        lista = st.session_state.carteira["Ticker"].tolist()
        
        for i, tick in enumerate(lista):
            dados = get_data_ia(tick)
            if dados:
                # Lógica de Alerta Automático
                chave_alerta = f"{tick}_{datetime.date.today()}"
                if dados['score_ia'] >= 75 and chave_alerta not in st.session_state.alertas_hoje:
                    disparar_alerta(
                        f"OPORTUNIDADE: {tick}",
                        f"Score IA: {dados['score_ia']}\nPreço: {dados['preco']:.2f}\nBazin: {dados['p_bazin']:.2f}"
                    )
                    st.session_state.alertas_hoje.append(chave_alerta)
                    st.toast(f"Alerta enviado para {tick}!", icon="🚀")

                resultados.append({
                    "Ticker": tick,
                    "Preço": dados['preco'],
                    "Score IA": dados['score_ia'],
                    "Decisão": dados['decisao_ia'],
                    "Bazin": dados['p_bazin']
                })
            bar.progress((i+1)/len(lista))
            
        df_rank = pd.DataFrame(resultados).sort_values("Score IA", ascending=False)
        st.dataframe(df_rank.style.background_gradient(subset=["Score IA"], cmap="Greens"), use_container_width=True)

# --- ABA 3: SCANNER FIIs ---
with tabs[2]:
    st.subheader("🏢 Scanner FII (CSV)")
    up = st.file_uploader("Upload 'statusinvest-busca-avancada.csv'", type=["csv"])
    if up:
        df_fii = scanner_fiis_csv(up)
        if not df_fii.empty:
            st.success("Scanner Finalizado!")
            st.dataframe(
                df_fii[["TICKER", "PRECO", "DY", "P/VP", "Score", "SEGMENTO"]].head(20)
                .style.background_gradient(subset=["Score"], cmap="Blues"), 
                use_container_width=True
            )