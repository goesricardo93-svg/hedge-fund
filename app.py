import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 1. SETUP E CARTEIRA (31 ATIVOS)
st.set_page_config(page_title="Terminal Ricardo", layout="wide")

if 'meus_ativos' not in st.session_state:
    data = [
        ["ALZR11.SA", 100, 10.81], ["BBAS3.SA", 1703, 24.48], ["BBSE3.SA", 55, 35.64],
        ["BTCI11.SA", 502, 10.16], ["BTLG11.SA", 60, 98.50], ["CCME11.SA", 152, 8.55],
        ["CMIG4.SA", 1644, 11.12], ["CPLE3.SA", 617, 9.64], ["CPSH11.SA", 169, 10.10],
        ["CPTS11.SA", 276, 8.52], ["CXSE3.SA", 800, 14.20], ["EQTL3.SA", 200, 30.21],
        ["HGCR11.SA", 20, 95.81], ["HGLG11.SA", 20, 158.03], ["ITSA4.SA", 1174, 9.63],
        ["IVVB11.SA", 6, 366.97], ["KLBN4.SA", 2323, 3.63], ["KNCR11.SA", 27, 103.11],
        ["KNHF11.SA", 15, 93.23], ["KNRI11.SA", 30, 152.49], ["KNSC11.SA", 373, 8.78],
        ["KNUQ11.SA", 16, 102.45], ["PETR4.SA", 900, 32.07], ["SAPR11.SA", 300, 37.97],
        ["TAEE4.SA", 1000, 11.36], ["VALE3.SA", 152, 54.79], ["VGIR11.SA", 296, 9.58],
        ["VISC11.SA", 16, 109.70], ["XPCA11.SA", 110, 8.77], ["XPLG11.SA", 26, 102.31],
        ["XPML11.SA", 10, 106.05]
    ]
    st.session_state.meus_ativos = pd.DataFrame(data, columns=["Ticker", "Qtd", "PM"])

# 2. FUNÇÕES DE SUPORTE
@st.cache_data(ttl=600)
def load_ticker(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

def status_invest(tk, pr, info):
    try:
        p_vp = info.get('priceToBook', 0) or 0
        dy = info.get('dividendYield', 0) or 0
        if "11" in tk:
            if 0.85 <= p_vp <= 1.00: return "🔥 COMPRA"
            return "⚠️ CARO" if p_vp > 1.05 else "✅ OK"
        teto = (pr * dy) / 0.06 if dy > 0 else 0
        return "💰 OPORTUNIDADE" if teto > pr else "✅ VALOR"
    except: return "-"

# 3. INTERFACE PRINCIPAL
st.sidebar.header("🕹️ Comando Central")
q_tk = st.sidebar.text_input("Ticker:", value="BBSE3")
tk = q_tk.strip().upper() if "." in q_tk else f"{q_tk.strip().upper()}.SA"

t1, t2, t3, t4 = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 CARTEIRA"])

# --- ABA 1: INTELIGÊNCIA ---
with t1:
    hist, info = load_ticker(tk)
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, tk)
        if r:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("Teto (Bazin)", f"R$ {r['p_bazin']:.2f}")
            c3.metric("RSI", f"{r['rsi']:.1f}")
            c4.metric("Dívida/EBITDA", f"{info.get('debtToEbitda', 0):.1f}")
            
            st.markdown(f"### Veredito: :{r['cor']}[{r['recomendacao']}]")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='PREÇO'))
            fig.add_trace(go.Scatter(x=hist.index, y=[r['suporte']]*len(hist), name='SUPORTE', line=dict(dash='dash', color='green')))
            fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_loss']]*len(hist), name='STOP', line=dict(dash='dot', color='red')))
            fig.update_layout(height=400, margin=dict(l=0,r=0,b=0,t=0))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            v1, v2, v3 = st.columns(3)
            with v1:
                st.subheader("🏛️ Valuation")
                st.write(f"**Graham:** R$ {r['p_graham']:.2f}")
                st.write(f"**Bazin:** R$ {r['p_bazin']:.2f}")
                st.write(f"**Gordon:** R$ {r['p_gordon']:.2f}")
            with v2:
                st.subheader("📈 Técnico")
                st.write(f"**Suporte:** R$ {r['suporte']:.2f}")
                st.write(f"**Resistência:** R$ {r['resistencia']:.2f}")
                st.write(f"**Tendência:** {r['tendencia']}")
            with v3:
                st.subheader("🛡️ Risco