import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 1. CONFIGURAÇÃO INICIAL
st.set_page_config(page_title="Terminal Ricardo - Hedge Fund", layout="wide")

# Inicialização da Carteira no Session State (para não perder as edições)
if 'meus_ativos' not in st.session_state:
    st.session_state.meus_ativos = pd.DataFrame([
        {"Ticker": "ALZR11.SA", "Qtd": 100, "PM": 10.81}, {"Ticker": "BBAS3.SA", "Qtd": 1703, "PM": 24.48},
        {"Ticker": "BBSE3.SA", "Qtd": 55, "PM": 35.64}, {"Ticker": "BTCI11.SA", "Qtd": 502, "PM": 10.16},
        {"Ticker": "BTLG11.SA", "Qtd": 60, "PM": 98.50}, {"Ticker": "CCME11.SA", "Qtd": 152, "PM": 8.55},
        {"Ticker": "CMIG4.SA", "Qtd": 1644, "PM": 11.12}, {"Ticker": "CPLE3.SA", "Qtd": 617, "PM": 9.64},
        {"Ticker": "CPSH11.SA", "Qtd": 169, "PM": 10.10}, {"Ticker": "CPTS11.SA", "Qtd": 276, "PM": 8.52},
        {"Ticker": "CXSE3.SA", "Qtd": 800, "PM": 14.20}, {"Ticker": "EQTL3.SA", "Qtd": 200, "PM": 30.21},
        {"Ticker": "HGCR11.SA", "Qtd": 20, "PM": 95.81}, {"Ticker": "HGLG11.SA", "Qtd": 20, "PM": 158.03},
        {"Ticker": "ITSA4.SA", "Qtd": 1174, "PM": 9.63}, {"Ticker": "IVVB11.SA", "Qtd": 6, "PM": 366.97},
        {"Ticker": "KLBN4.SA", "Qtd": 2323, "PM": 3.63}, {"Ticker": "KNCR11.SA", "Qtd": 27, "PM": 103.11},
        {"Ticker": "KNHF11.SA", "Qtd": 15, "PM": 93.23}, {"Ticker": "KNRI11.SA", "Qtd": 30, "PM": 152.49},
        {"Ticker": "KNSC11.SA", "Qtd": 373, "PM": 8.78}, {"Ticker": "KNUQ11.SA", "Qtd": 16, "PM": 102.45},
        {"Ticker": "PETR4.SA", "Qtd": 900, "PM": 32.07}, {"Ticker": "SAPR11.SA", "Qtd": 300, "PM": 37.97},
        {"Ticker": "TAEE4.SA", "Qtd": 1000, "PM": 11.36}, {"Ticker": "VALE3.SA", "Qtd": 152, "PM": 54.79},
        {"Ticker": "VGIR11.SA", "Qtd": 296, "PM": 9.58}, {"Ticker": "VISC11.SA", "Qtd": 16, "PM": 109.70},
        {"Ticker": "XPCA11.SA", "Qtd": 110, "PM": 8.77}, {"Ticker": "XPLG11.SA", "Qtd": 26, "PM": 102.31},
        {"Ticker": "XPML11.SA", "Qtd": 10, "PM": 106.05}
    ])

# 2. FUNÇÕES DE SUPORTE
@st.cache_data(ttl=600)
def carregar_dados_ticker(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

def veredito_fii_scanner(row):
    try:
        p, m = row.get('P/VP_N', 0), row.get('Margem Seg. (%)', 0)
        seg = str(row.get('SEGMENTO', 'N/A')).upper()
        vac, imov = row.get('VACANCIA_N', 0), row.get('IMOVEIS_N', 0)
        if "PAPEL" in seg: return "🔥 COMPRA SEGURA (Papel)" if 0.97 <= p <= 1.00 else "🟡 ANALISAR"
        if vac and vac > 15: return "❌ EVITAR (Vacância)"
        return "🏢 OPORTUNIDADE (Tijolo)" if p < 0.95 and m > 5 else "✅ COMPRA"
    except: return "Analise Manual"

def analisar_status_carteira(ticker, preco_atual, info):
    try:
        p_vp = info.get('priceToBook', 0) or 0
        dy = (info.get('dividendYield', 0) or 0) * 100
        if "11" in ticker:
            if 0.85 <= p_vp <= 1.00: return "🔥 COMPRA (P/VP)"
            if p_vp > 1.05: return "⚠️ CARO"
            return "✅ MANTER"
        teto = (preco_atual * (dy / 100)) / 0.06 if dy > 0 else 0
        return "💰 OPORTUNIDADE" if teto > preco_atual else "✅ EM VALOR"
    except: return "---"

# 3. INTERFACE LATERAL
st.sidebar.header("🕹️ Comando Central")
tk_raw = st.sidebar.text_input("Consultar Ticker:", value="BBSE3")
tk_final = tk_raw.strip().upper() if "." in tk_raw else f"{tk_raw.strip().upper()}.SA"

tab1, tab2, tab3, tab4 = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 MINHA CARTEIRA"])

# --- ABA 1: INTELIGÊNCIA DE MERCADO (AÇÕES) ---
with tab1:
    df_h, info = carregar_dados_ticker(tk_final)
    if not df_h.empty:
        res = MotorAnalise().analisar(df_h, info, tk_final)
        if res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("P. Teto (Bazin)", f"R$ {res['p_bazin']:.2f}", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Dívida/EBITDA", f"{info.get('debtToEbitda', 0):.1f}")
            st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_h.index, y=df_h['Close'], name='PREÇO', line=dict(color='#29b5e8', width=3)))
            fig.add_trace(go.Scatter(x=df_h.index, y=[res['suporte']]*len(df_h), name='🛡️ SUPORTE', line=dict(color='#2ecc71', dash='dash')))
            fig.add_trace(go.Scatter(x=df_h.index, y=[res['stop_loss']]*len(df_h), name='🚫 STOP LOSS', line=dict(color='#e74c3c', dash='dot')))
            if res['stop_gain'] > 0: fig.add_trace(go.Scatter(x=df_h.index, y=[res['stop_gain']]*len(df_h), name='🎯 ALVO', line=dict(color='#f1c40f', dash='dashdot')))
            fig.update_layout(height=400, margin=dict(l=0,r=0,b=0,t=40), legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("---")
            col_v, col_t, col_r = st.columns(3)
            with col_v:
                st.subheader("🏛️ Valuation")
                st.write(f"**Graham:** R$ {res['p_graham']:.2f}")
                st.write(f"**Bazin:** R$ {res['p_bazin']:.2f}")
                st.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")
            with col_t:
                st.subheader("📈 Técnico")
                st.write(f"**Suporte:** R$ {res['suporte']:.2f}")
                st.write(f"**Resistência:** R$ {res['resistencia']:.2f}")
                st.write(f"**Tendência:** {res['tendencia']}")
            with col_r:
                st.subheader("🛡️ Risco")
                st.error(f"**Stop Loss:** R$ {res['stop_loss']:.2f}")
                st.success(f"**Stop Gain:** R$ {res['stop_gain']:.2f}")
                st.write(f"**ROE:** {info.get('returnOnEquity', 0)*100:.1f}%")

# --- ABA 2: SCANNER FIIS ---
with tab2:
    st.header("🏙️ Scanner FII - Stress Test")
    try:
        try: df_f = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        except: df_f = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="iso-8859-1")
        def cl(n): 
            if n in df_f.columns: return pd.