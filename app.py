import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 1. SETUP E CARTEIRA INTEGRAL
st.set_page_config(page_title="Hedge Fund Ricardo | Terminal v1.0", layout="wide")

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
def load_market_data(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

def analise_360_fii(row):
    try:
        p_vp, dy, vac = row.get('P/VP_N', 0), row.get('DY_N', 0), row.get('VAC_N', 0)
        seg = str(row.get('SEGMENTO', '')).upper()
        if "PAPEL" in seg:
            return "🔥 COMPRA SEGURA" if 0.98 <= p_vp <= 1.01 else "🟡 OBSERVANDO"
        return "🏢 OPORTUNIDADE" if vac < 10 and p_vp < 0.95 else "✅ MANTÉM"
    except: return "Analise Manual"

def rec_carteira(tk, preco, pm, info):
    dy = info.get('dividendYield', 0) or 0
    teto = (preco * dy) / 0.06 if dy > 0 else 0
    if preco < pm * 0.97: return "💰 COMPRAR"
    if teto > 0 and preco > teto * 1.1: return "⚠️ VENDER"
    return "✅ MANTÉM"

# 3. INTERFACE
st.sidebar.header("🕹️ Ricardo Central")
q_tk = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
tk = q_tk if "." in q_tk else f"{q_tk}.SA"

t1, t2, t3, t4 = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 CARTEIRA"])

with t1:
    hist, info = load_market_data(tk)
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, tk)
        # Métricas de Topo
        m = st.columns(5)
        m[0].metric("Preço", f"R$ {r['preco']:.2f}")
        m[1].metric("Alvo (Gain)", f"R$ {r['stop_gain']:.2f}")
        m[2].metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
        m[3].metric("DY (Anual)", f"{info.get('dividendYield', 0)*100:.2f}%")
        m[4].metric("P. Bazin", f"R$ {r['p_bazin']:.2f}")
        
        st.markdown(f"### Veredito: :{r['cor']}[{r['recomendacao']}]")
        
        # Gráfico Técnico
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Preço', line=dict(color='#29b5e8', width=2)))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_gain']]*len(hist), name='ALVO', line=dict(dash='dash', color='gold')))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_loss']]*len(hist), name='STOP', line=dict(dash='dot', color='red')))
        st.plotly_chart(fig, use_container_width=True)
        
        # TABELA DE INFORMAÇÕES FUNDAMENTALISTAS (A CORRIGIDA)
        st.subheader("📋 Resumo Fundamentalista")
        dados_fund = {
            "Indicador": ["P/L", "P/VP", "DY", "ROE", "Margem Líquida", "Dívida Bruta/EBITDA", "Preço Graham", "Preço Bazin"],
            "Valor": [
                f"{info.get('trailingPE', 0):.2f}",
                f"{info.get('priceToBook', 0):.2f}",
                f"{info.get('dividendYield', 0)*100:.2f}%",
                f"{info.get('returnOnEquity', 0)*100:.1f}%",
                f"{info.get('profitMargins', 0)*100:.1f}%",
                f"{info.get('debtToEbitda', 0):.2f}",
                f"R$ {r['p_graham']:.2f}",
                f"R$ {r['p_bazin']:.2f}"
            ]
        }
        st