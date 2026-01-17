import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from motor import MotorAnalise

# 1. SETUP INICIAL
st.set_page_config(page_title="Hedge Fund Ricardo | Terminal v1.0", layout="wide")

# 2. CARTEIRA (SESSION STATE) - 31 ATIVOS
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

# 3. FUNÇÕES TÉCNICAS
def get_rsi_status(val):
    if val < 30: return f"{val:.1f} 🟢 (SOBREVENDA)"
    if val > 70: return f"{val:.1f} 🔴 (SOBRECOMPRA)"
    return f"{val:.1f} ⚪ (NEUTRO)"

def analise_360_fii(row):
    pvp = row.get("P/VP", 0)
    vac = row.get("VACÂNCIA", 0)
    dy = row.get("DY", 0)
    if pvp < 0.95 and vac < 10: return "🏢 OPORTUNIDADE (TIJOLO)"
    if 0.98 <= pvp <= 1.02 and dy > 8: return "🔥 COMPRA (PAPEL)"
    return "✅ MANTER"

# 4. SIDEBAR
st.sidebar.header("🕹️ Ricardo Central")
q_tk = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
ticker = q_tk if "." in q_tk else f"{q_tk}.SA"

tabs = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 Carteira"])

# --- ABA 1: INTELIGÊNCIA ---
with tabs[0]:
    obj = yf.Ticker(ticker)
    hist = obj.history(period="2y")
    info = obj.info if isinstance(obj.info, dict) else {}
    
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, ticker)
        st.subheader(f"📈 {ticker}")
        
        c = st.columns(6)
        c[0].metric("Preço", f"R$ {r['preco']:.2f}")
        c[1].metric("Preço Teto", f"R$ {r['p_bazin']:.2f}")
        c[2].markdown(f"**RSI (14d)**<br>{get_rsi_status(r['rsi'])}", unsafe_allow_html=True)
        c[3].metric("ROE", f"{info.get('returnOnEquity', 0) * 100:.1f}%")
        c[4].metric("DY", f"{info.get('dividendYield', 0) * 100:.2f}%")
        c[5].metric("P/VP", f"{info.get('priceToBook', 0):.2f}")

        st.markdown(f"### 🎯 Veredito: **{r['recomendacao']}**")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Preço"))
        fig.add_hline(y=r["stop_gain"], line_dash="dash", line_color="gold", annotation_text="ALVO")
        fig.add_hline(y=r["suporte"], line_dash="dash", line_color="green", annotation_text="SUPORTE")
        fig.add_hline(y=r["stop_loss"], line_dash="dot", line_color="red", annotation_text="STOP")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Tabela Fundamentalista")
        fund_df = pd.DataFrame({
            "Métrica": ["Graham", "Bazin", "Gordon", "Margem Líq", "Dívida/EBITDA"],
            "Valor": [f"R$ {r['p_graham']:.2f}", f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_gordon']:.2f}", 
                     f"{info.get('profitMargins', 0)*100:.1f}%", f"{info.get('debtToEbitda', 0):.2f}"]
        })
        st.table(fund_df)

# --- ABA 2: SCANNER FIIs ---
with tabs[1]:
    st.header("🏙️ Scanner FII 360º")
    try:
        df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="latin-1")
        df.columns = df.columns.str.strip().str.upper()
        def clean(col): return df[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)
        
        for col in ["P/VP", "DY", "VACÂNCIA"]:
            if col in df.columns: df[col] = clean(col)
        
        df["ANÁLISE"] = df.apply(analise_360_fii, axis=1)
        st.dataframe(df.sort_values("DY", ascending=False), use_container_width=True)
    except Exception as e: st.error(f"Erro no Scanner: {e}")

# --- ABA 3: PGBL (RESTAURADA) ---
with tabs[2]:
    st.header("🛡️ Estratégia PGBL (Dedução Fiscal)")
    c1, c2 = st.columns(2)
    renda_anual = c1.number_input("Renda Bruta Anual (R$):", value=150000.0)
    aporte_mensal = c2.number_input("Aporte PGBL Mensal (R$):", value=1000.0)
    
    limite_12 = renda_anual * 0.12
    total_pgbl = aporte_mensal * 12
    economia = min(total_pgbl, limite_12) * 0.275
    
    st.metric("Restituição IR Estimada", f"R$ {economia:,.2f}")
    st.write(f"Seu limite de aporte para benefício máximo é **R$ {limite_12:,.2f}** por ano.")

# --- ABA 4: CARTEIRA (COM RECOMENDAÇÃO AUTOMÁTICA) ---
with tabs[3]:
    st.header("💼 Gestão de Carteira")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    
    if st.button("🔄 Sincronizar e Analisar Carteira"):
        res = []
        for _, row in df_ed.iterrows():
            t = yf.Ticker(row['Ticker'])
            p_atual = t.fast_info['last_price']
            dy = t.info.get('dividendYield', 0) or 0
            teto = (p_atual * dy) / 0.06 if dy > 0 else 0
            
            # Lógica: Compra se abaixo do PM ou abaixo do Teto Bazin
            if p_atual < row['PM'] * 0.96: rec = "💰 COMPRAR"
            elif teto > 0 and p_atual > teto * 1.15: rec = "⚠️ VENDER"
            else: rec = "✅ MANTER"
            
            res.append({"Cotação": p_atual, "Recomendação": rec, "Lucro": (p_atual - row['PM']) * row['Qtd']})
        
        df_f = pd.concat([df_ed.reset_index(drop=True), pd.DataFrame(res)], axis=1)
        st.dataframe(df_f.style.applymap(lambda x: 'background-color: #2ecc71' if 'COMPRAR' in str(x) else ('background-color: #e74c3c' if 'VENDER' in str(x) else ''), subset=['Recomendação']))