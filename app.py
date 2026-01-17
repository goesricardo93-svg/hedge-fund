import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from motor import MotorAnalise

# ======================================================
# 1. CONFIGURAÇÃO E CARTEIRA (31 ATIVOS)
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | Terminal v1.0", layout="wide")

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
# 2. FUNÇÕES TÉCNICAS
# ======================================================
def get_rsi_status(val):
    if val < 30: return f"RSI: {val:.1f} 🟢 SOBREVENDA"
    if val > 70: return f"RSI: {val:.1f} 🔴 SOBRECOMPRA"
    return f"RSI: {val:.1f} ⚪ NEUTRO"

def score_convergencia(r, info):
    s = 0
    if r["rsi"] < 35: s += 20
    if r["preco"] < r["p_bazin"]: s += 20
    if r["preco"] < r["p_graham"]: s += 15
    if info.get("returnOnEquity", 0) > 0.15: s += 15
    if info.get("dividendYield", 0) * 100 > 6: s += 30
    return min(s, 100)

def analise_360_fii(row):
    pvp = row.get("P/VP_N", 0)
    vac = row.get("VAC_N", 0)
    dy = row.get("DY_N", 0)
    if pvp < 0.95 and vac < 10: return "🏢 OPORTUNIDADE"
    if 0.98 <= pvp <= 1.02 and dy > 0.8: return "🔥 COMPRA"
    return "✅ MANTER"

# ======================================================
# 3. SIDEBAR E NAVEGAÇÃO
# ======================================================
st.sidebar.header("🕹️ Ricardo Central")
q_tk = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
ticker = q_tk if "." in q_tk else f"{q_tk}.SA"

tabs = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 Carteira"])

# --- ABA 1: INTELIGÊNCIA COMPLETA ---
with tabs[0]:
    obj = yf.Ticker(ticker)
    hist, info = obj.history(period="2y"), obj.info
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, ticker)
        score = score_convergencia(r, info)
        
        # Dashboard de Métricas
        c = st.columns(6)
        c[0].metric("Preço", f"R$ {r['preco']:.2f}")
        c[1].metric("P. Bazin", f"R$ {r['p_bazin']:.2f}")
        c[2].metric("P. Graham", f"R$ {r['p_graham']:.2f}")
        c[3].metric("P. Gordon", f"R$ {r['p_gordon']:.2f}")
        c[4].metric("Drawdown", f"{( (hist['Close'] - hist['Close'].cummax()) / hist['Close'].cummax() ).min() * 100:.1f}%")
        c[5].metric("Score", f"{score}/100")

        st.markdown("---")
        f = st.columns(6)
        f[0].metric("DY (%)", f"{info.get('dividendYield', 0)*100:.2f}%")
        f[1].metric("P/L", f"{info.get('trailingPE', 0):.2f}")
        f[2].metric("P/VP", f"{info.get('priceToBook', 0):.2f}")
        f[3].metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
        f[4].metric("Margem Líq.", f"{info.get('profitMargins', 0)*100:.1f}%")
        f[5].markdown(f"**Técnico**<br>{get_rsi_status(r['rsi'])}", unsafe_allow_html=True)

        st.markdown(f"### Veredito: **{r['recomendacao']}**")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Preço"))
        fig.add_hline(y=r["stop_gain"], line_dash="dash", line_color="gold", annotation_text="ALVO")
        fig.add_hline(y=r["suporte"], line_dash="dash", line_color="green", annotation_text="SUPORTE")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Painel Consolidado de Fundamentos")
        dados_tabela = {
            "Métrica": ["DY (%)", "P/L", "P/VP", "ROE (%)", "Margem Líquida (%)", "Dívida/EBITDA", "P. Bazin", "P. Graham", "P. Gordon"],
            "Valor": [
                f"{info.get('dividendYield', 0)*100:.2f}%", f"{info.get('trailingPE', 0):.2f}",
                f"{info.get('priceToBook', 0):.2f}", f"{info.get('returnOnEquity', 0)*100:.1f}%",
                f"{info.get('profitMargins', 0)*100:.1f}%", f"{info.get('debtToEbitda', 0):.2f}",
                f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"
            ]
        }
        st.table(pd.DataFrame(dados_tabela))

# --- ABA 2: SCANNER FIIs (BLINDADO) ---
with tabs[1]:
    st.header("🏙️ Scanner FII 360º")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="latin-1")
        df_fii.columns = df_fii.columns.str.strip().str.upper()
        
        def clean_col(c): 
            return pd.to_numeric(df_fii[c].astype(str).str.replace(".","").str.replace(",","."), errors='coerce') if c in df_fii.columns else 0

        df_fii["P/VP_N"] = clean_col("P/VP")
        df_fii["DY_N"] = clean_col("DY")
        df_fii["VAC_N"] = clean_col("VACÂNCIA FISICA")
        df_fii["PRECO_N"] = clean_col("PREÇO")
        
        df_fii["VEREDITO"] = df_fii.apply(analise_360_fii, axis=1)
        st.dataframe(df_fii[["TICKER", "VEREDITO", "P/VP", "DY", "VACÂNCIA FISICA", "PREÇO"]].sort_values("DY", ascending=False))
    except Exception as e: st.error(f"Erro no Scanner: {e}")

# --- ABA 3: PGBL ---
with tabs[2]:
    st.header("🛡️ Benefício Fiscal PGBL")
    c1, c2 = st.columns(2)
    renda = c1.number_input("Renda Bruta Anual:", value=150000.0)
    aporte = c2.number_input("Aporte Mensal PGBL:", value=1000.0)
    limite = renda * 0.12
    restituicao = min(aporte * 12, limite) * 0.275
    st.metric("Restituição IR Estimada", f"R$ {restituicao:,.2f}")
    st.info(f"O limite ideal de aporte anual para sua renda é R$ {limite:,.2f}")

# --- ABA 4: CARTEIRA PROFISSIONAL ---
with tabs[3]:
    st.header("💼 Gestão de Carteira")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    if st.button("🔄 Sincronizar Tudo"):
        res = []
        for _, row in df_ed.iterrows():
            try:
                t = yf.Ticker(row['Ticker'])
                p = t.fast_info['last_price']
                dy = t.info.get('dividendYield', 0) or 0
                teto = (p * dy) / 0.06 if dy > 0 else 0
                rec = "💰 COMPRAR" if p < row['PM'] * 0.96 else ("⚠️ VENDER" if (teto > 0 and p > teto * 1.15) else "✅ MANTER")
                res.append({"Cotação": p, "Recomendação": rec, "Lucro": (p - row['PM']) * row['Qtd']})
            except: res.append({"Cotação": 0, "Recomendação": "❌ ERRO", "Lucro": 0})
        
        df_f = pd.concat([df_ed.reset_index(drop=True), pd.DataFrame(res)], axis=1)
        st.dataframe(df_f.style.applymap(lambda x: 'background-color: #2ecc71' if 'COMPRAR' in str(x) else ('background-color: #e74c3c' if 'VENDER' in str(x) else ''), subset=['Recomendação']))