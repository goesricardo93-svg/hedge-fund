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
# 2. CARTEIRA BASE (PERSISTENTE)
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
    st.session_state.meus_ativos = pd.DataFrame(
        data, columns=["Ticker", "Qtd", "PM"]
    )

# ======================================================
# 3. FUNÇÕES AUXILIARES
# ======================================================
def get_rsi_status(val):
    if val < 30:
        return f"RSI {val:.1f} 🟢 SOBREVENDA"
    if val > 70:
        return f"RSI {val:.1f} 🔴 SOBRECOMPRA"
    return f"RSI {val:.1f} ⚪ NEUTRO"

def calcular_drawdown(hist):
    topo = hist["Close"].cummax()
    return ((hist["Close"] - topo) / topo).min() * 100

def score_convergencia(r, info):
    score = 0
    if r["rsi"] < 35:
        score += 20
    if r["preco"] < r["p_bazin"]:
        score += 20
    if r["preco"] < r["p_graham"]:
        score += 15
    if info.get("returnOnEquity", 0) > 0.15:
        score += 15
    if info.get("dividendYield", 0) * 100 > 6:
        score += 30
    return min(score, 100)

# ======================================================
# 4. SIDEBAR
# ======================================================
st.sidebar.header("🕹️ Central de Comando")
ticker_input = st.sidebar.text_input("Ticker para Análise", "BBSE3").strip().upper()
ticker = ticker_input if "." in ticker_input else f"{ticker_input}.SA"

tabs = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 Carteira"])

# ======================================================
# 5. ABA 1 — INTELIGÊNCIA (TÉCNICA + FUNDAMENTALISTA)
# ======================================================
with tabs[0]:
    obj = yf.Ticker(ticker)
    hist = obj.history(period="2y")
    info = obj.info

    if hist.empty:
        st.warning("Sem dados históricos.")
    else:
        r = MotorAnalise().analisar(hist, info, ticker)
        score = score_convergencia(r, info)

        cols = st.columns(7)
        cols[0].metric("Preço", f"R$ {r['preco']:.2f}")
        cols[1].metric("Bazin", f"R$ {r['p_bazin']:.2f}")
        cols[2].metric("Graham", f"R$ {r['p_graham']:.2f}")
        cols[3].metric("Gordon", f"R$ {r['p_gordon']:.2f}")
        cols[4].markdown(f"**{get_rsi_status(r['rsi'])}**")
        cols[5].metric("Drawdown", f"{calcular_drawdown(hist):.1f}%")
        cols[6].metric("Score", f"{score}/100")

        st.markdown(f"## 🎯 Veredito Final: **{r['recomendacao']}**")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist["Close"],
            name="Preço",
            line=dict(color="white")
        ))

        fig.add_hline(y=r["suporte"], line_dash="dash", line_color="green")
        fig.add_hline(y=r["stop_loss"], line_dash="dash", line_color="red")
        fig.add_hline(y=r["stop_gain"], line_dash="dash", line_color="gold")

        st.plotly_chart(fig, use_container_width=True)

# ======================================================
# 6. ABA 2 — SCANNER FIIs
# ======================================================
with tabs[1]:
    st.header("🏙️ Scanner FII 360º")

    try:
        df = pd.read_csv(
            "statusinvest-busca-avancada.csv",
            sep=";",
            encoding="latin-1"
        )
        df.columns = df.columns.str.upper().str.strip()

        def fix(col):
            return pd.to_numeric(
                df[col].astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False),
                errors="coerce"
            )

        df["PVP"] = fix("P/VP")
        df["DY"] = fix("DY")
        df["VAC"] = fix("VACÂNCIA FISICA")

        df["ANÁLISE"] = df.apply(
            lambda r: "🏢 OPORTUNIDADE"
            if r["PVP"] < 0.95 and r["VAC"] < 10
            else "✅ MANTER",
            axis=1
        )

        st.dataframe(
            df[["TICKER", "ANÁLISE", "P/VP", "DY", "VACÂNCIA FISICA"]]
            .sort_values("DY", ascending=False),
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Erro no Scanner: {e}")

# ======================================================
# 7. ABA 3 — PGBL
# ======================================================
with tabs[2]:
    st.header("🛡️ Benefício Fiscal PGBL")

    c1, c2 = st.columns(2)
    renda = c1.number_input("Renda Bruta Anual", value=150000.0)
    aporte = c2.number_input("Aporte Mensal", value=1000.0)

    limite = renda * 0.12
    restit = min(aporte * 12, limite) * 0.275

    st.metric("💰 Restituição Estimada", f"R$ {restit:,.2f}")

# ======================================================
# 8. ABA 4 — CARTEIRA PROFISSIONAL
# ======================================================
with tabs[3]:
    st.header("💼 Gestão de Carteira")

    df_edit = st.data_editor(
        st.session_state.meus_ativos,
        num_rows="dynamic",
        use_container_width=True
    )

    if st.button("🔄 Sincronizar Carteira"):
        resultado = []

        for _, row in df_edit.iterrows():
            try:
                t = yf.Ticker(row["Ticker"])
                preco = t.fast_info["last_price"]
                dy = t.info.get("dividendYield", 0) or 0
                teto = (preco * dy) / 0.06 if dy > 0 else 0

                acao = (
                    "💰 COMPRAR" if preco < row["PM"] * 0.96
                    else "⚠️ VENDER" if teto > 0 and preco > teto * 1.15
                    else "✅ MANTER"
                )

                resultado.append({
                    "Preço Atual": preco,
                    "Lucro/Prejuízo": (preco - row["PM"]) * row["Qtd"],
                    "Ação": acao
                })

            except Exception:
                resultado.append({
                    "Preço Atual": None,
                    "Lucro/Prejuízo": None,
                    "Ação": "ERRO"
                })

        df_final = pd.concat(
            [df_edit.reset_index(drop=True), pd.DataFrame(resultado)],
            axis=1
        )

        st.dataframe(
            df_final.style.applymap(
                lambda x:
                "background-color:#2ecc71"
                if "COMPRAR" in str(x)
                else "background-color:#e74c3c"
                if "VENDER" in str(x)
                else "",
                subset=["Ação"]
            ),
            use_container_width=True
        )

        st.session_state.meus_ativos = df_edit
