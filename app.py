import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# Imports Modulares (Garantir que os arquivos estão na mesma pasta)
try:
    from motor import MotorAnalise
    from scanner import scanner_fiis_csv
    from alerts import disparar_alerta
except ImportError as e:
    st.error(f"Erro de Importação: {e}. Verifique se motor.py, scanner.py e alerts.py estão no GitHub.")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | vFinal Modular", layout="wide")

# ======================================================
# CACHE E CARTEIRA
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

if "carteira_acoes" not in st.session_state:
    # SUA LISTA INTEGRAL
    dados = [
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
    st.session_state.carteira_acoes = pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# INTERFACE
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")
ticker_input = st.sidebar.text_input("🔍 Ticker:", "BBAS3.SA").upper()

tabs = st.tabs(["🔎 Análise Técnica", "💼 Carteira & Ranking", "🏢 Scanner FIIs 360", "💰 Futuro"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    r = obter_dados(ticker_input)
    
    if r:
        # Score IA
        c1, c2 = st.columns([1, 3])
        c1.metric("Score IA", f"{r['score_ia']}/100")
        if "COMPRA" in r['decisao_ia']: c2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']: c2.error(f"### {r['decisao_ia']}")
        else: c2.warning(f"### {r['decisao_ia']}")
        st.caption(f"**Motivos:** {r['motivos']}")
        st.divider()

        # Métricas
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço", f"R$ {r['preco']:.2f}")
        k2.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        k3.metric("Drawdown", f"{r['drawdown']:.1f}%")
        k4.metric("RSI", f"{r['rsi']:.0f}")

        # Tabela Valuation
        c_val, c_fund = st.columns(2)
        with c_val:
            st.subheader("📋 Valuation")
            val_data = {
                "Modelo": ["Bazin", "Graham", "Gordon"],
                "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
            }
            st.dataframe(pd.DataFrame(val_data), use_container_width=True)
        
        with c_fund:
            st.subheader("📊 Fundamentos")
            fund_data = {
                "Indicador": ["DY", "P/L", "P/VP", "ROE"], 
                "Valor": [f"{r['dy']*100:.1f}%", f"{r['pl']:.1f}", f"{r['pvp']:.2f}", f"{r['roe']*100:.1f}%"]
            }
            st.dataframe(pd.DataFrame(fund_data), use_container_width=True)

        # Gráfico
        st.subheader("📈 Gráfico Técnico")
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                # Tratamento de Série
                close = hist_chart["Close"]
                if isinstance(close, pd.DataFrame): close = close.iloc[:,0]
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=hist_chart.index, 
                    open=hist_chart["Open"].iloc[:,0] if isinstance(hist_chart["Open"], pd.DataFrame) else hist_chart["Open"],
                    high=hist_chart["High"].iloc[:,0] if isinstance(hist_chart["High"], pd.DataFrame) else hist_chart["High"],
                    low=hist_chart["Low"].iloc[:,0] if isinstance(hist_chart["Low"], pd.DataFrame) else hist_chart["Low"],
                    close=close, name="Preço"))
                
                fig.add_hline(y=r['suporte'], line_dash="dot", line_color="green", annotation_text="SUPORTE")
                fig.add_hline(y=r['resistencia'], line_dash="dot", line_color="red", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=r['stop_loss'], line_dash="dash", line_color="red", annotation_text="STOP LOSS")
                fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e: st.error(f"Erro gráfico: {e}")
    else: st.warning("Ticker não encontrado.")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    st.subheader("🏆 Gestão de Carteira (31 Ativos)")
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_acoes = df_ed

    if st.button("🔄 Analisar Carteira"):
        res = []
        bar = st.progress(0)
        total = len(df_ed)
        for i, row in df_ed.iterrows():
            r = obter_dados(row["Ticker"])
            if r:
                # Alerta
                if r['score_ia'] >= 80 and row["Ticker"] not in st.session_state.alertas_enviados:
                    disparar_alerta(f"OPORTUNIDADE: {row['Ticker']}", f"Score: {r['score_ia']}")
                    st.session_state.alertas_enviados.add(row["Ticker"])

                rec = r['decisao_ia']
                if r['preco'] < row['PM'] * 0.95 and "COMPRA" in rec: rec = "🔥 COMPRA FORTE (Abaixo PM)"
                
                res.append({
                    "Ticker": row["Ticker"],
                    "Preço": r["preco"],
                    "PM": row["PM"],
                    "Lucro": (r["preco"] - row["PM"]) * row["Qtd"],
                    "Veredito IA": rec,
                    "Score": r['score_ia'],
                    "Bazin": r["p_bazin"]
                })
            bar.progress((i+1)/total)
        
        if res:
            df_res = pd.DataFrame(res).sort_values("Score", ascending=False)
            st.dataframe(df_res.style.background_gradient(subset=["Score"], cmap="Greens"), use_container_width=True)

# --- ABA 3: FIIs ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360º")
    uploaded = st.file_uploader("Upload CSV StatusInvest", type=["csv"])
    if uploaded:
        df_fii = scanner_fiis_csv(uploaded)
        if not df_fii.empty:
            st.success(f"{len(df_fii)} FIIs analisados!")
            st.dataframe(df_fii.head(30).style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
        else:
            st.warning("Erro ao ler CSV.")

# --- ABA 4: FUTURO ---
with tabs[3]:
    st.subheader("🔮 Simulação Patrimonial")
    if not df_ed.empty:
        patrimonio_atual = (df_ed['Qtd'] * df_ed['PM']).sum()
        st.metric("Patrimônio Base", f"R$ {patrimonio_atual:,.2f}")
        aporte = st.number_input("Aporte Mensal", 2000.0)
        
        if st.button("Simular 10 Anos"):
            motor = MotorAnalise()
            sims = motor.monte_carlo(patrimonio_atual, aporte, 10, 1000)
            fig = go.Figure(go.Histogram(x=sims, nbinsx=40, marker_color='green'))
            st.plotly_chart(fig, use_container_width=True)
            st.metric("Mediana Esperada", f"R$ {np.median(sims):,.2f}")