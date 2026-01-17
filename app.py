import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from motor import MotorAnalise

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(
    page_title="Hedge Fund Ricardo | Terminal v1.0",
    layout="wide"
)

# ======================================================
# 2. CARTEIRA FIXA INICIAL
# ======================================================
if "meus_ativos" not in st.session_state:
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

# ======================================================
# 3. FUNÇÕES
# ======================================================
def get_rsi_status(val):
    if val < 30: return f"{val:.1f} 🟢 (SOBREVENDA)"
    if val > 70: return f"{val:.1f} 🔴 (SOBRECOMPRA)"
    return f"{val:.1f} ⚪ (NEUTRO)"

def calcular_drawdown(hist):
    topo = hist["Close"].cummax()
    dd = (hist["Close"] - topo) / topo
    return dd.min() * 100

def score_convergencia(r, info, hist):
    score = 0
    if r["rsi"] < 35: score += 20
    if r["preco"] < r["p_bazin"]: score += 20
    if r["preco"] < r["p_graham"]: score += 15
    if info.get("returnOnEquity", 0) > 0.15: score += 10
    if info.get("profitMargins", 0) > 0.10: score += 10
    if info.get("dividendYield", 0) * 100 > 6: score += 10
    return min(score, 100)

# ======================================================
# 4. SIDEBAR
# ======================================================
st.sidebar.header("🕹️ Ricardo Central")
q_tk = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
ticker = q_tk if "." in q_tk else f"{q_tk}.SA"

tabs = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 Carteira"])

# ======================================================
# ABA 1 — INTELIGÊNCIA COMPLETA
# ======================================================
with tabs[0]:
    obj = yf.Ticker(ticker)
    hist = obj.history(period="2y")
    info = obj.info if isinstance(obj.info, dict) else {}

    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, ticker)
        dd = calcular_drawdown(hist)
        score = score_convergencia(r, info, hist)

        c = st.columns(7)
        c[0].metric("Preço", f"R$ {r['preco']:.2f}")
        c[1].metric("Bazin", f"R$ {r['p_bazin']:.2f}")
        c[2].metric("Graham", f"R$ {r['p_graham']:.2f}")
        c[3].metric("Gordon", f"R$ {r['p_gordon']:.2f}")
        c[4].markdown(get_rsi_status(r["rsi"]))
        c[5].metric("Drawdown", f"{dd:.1f}%")
        c[6].metric("Score", score)

        st.markdown(f"### 🎯 Veredito: **{r['recomendacao']}**")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Preço"))
        fig.add_hline(y=r["stop_gain"], line_dash="dash", line_color="gold")
        fig.add_hline(y=r["suporte"], line_dash="dash", line_color="green")
        fig.add_hline(y=r["stop_loss"], line_dash="dot", line_color="red")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Fundamentos")
        st.table(pd.DataFrame({
            "Métrica": ["ROE", "Margem", "Dívida/EBITDA", "P/L", "P/VP", "DY"],
            "Valor": [
                f"{info.get('returnOnEquity',0)*100:.1f}%",
                f"{info.get('profitMargins',0)*100:.1f}%",
                f"{info.get('debtToEbitda',0):.2f}",
                f"{info.get('trailingPE',0):.2f}",
                f"{info.get('priceToBook',0):.2f}",
                f"{info.get('dividendYield',0)*100:.2f}%"
            ]
        }))

# ======================================================
# ABA 4 — CARTEIRA PROFISSIONAL
# (mantida conforme versão anterior, sem cortes)
# ======================================================
# 👉 permanece exatamente como você já tem
