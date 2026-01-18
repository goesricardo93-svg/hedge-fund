import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np

# Importação Segura
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    try: from scanner import scanner_fiis_csv
    except: scanner_fiis_csv = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from options import BlackScholes
    except: BlackScholes = None
except ImportError as e:
    st.error(f"Erro nos módulos: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo v61.0", layout="wide")

METAS = {
    "Renda Fixa": 30.0, "Exterior": 20.0,
    "Ações-Bancos": 7.5, "Ações-Elétricas": 7.5, "Ações-Seguridade": 6.0, "Ações-Commodities": 6.0, "Ações-Outros": 3.0,
    "FIIs-Papel": 10.0, "FIIs-Tijolo": 6.0, "FIIs-Outros": 4.0
}

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker); hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_historico_longo(tickers):
    d = yf.download(tickers, period="5y", progress=False)
    return d["Adj Close"] if "Adj Close" in d else d["Close"]

def auto_classificar():
    motor = MotorAnalise()
    prog = st.progress(0, text="Classificando...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        try:
            t = yf.Ticker(row["Ticker"])
            st.session_state.carteira_acoes.at[i, "Setor"] = motor.identificar_setor(t.info, row["Ticker"])
        except: st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    prog.empty()
    st.success("Concluído!")

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Aguardando..."],
        ["CPSH11.SA", 50, 10.10, "Aguardando..."],
        ["XPML11.SA", 10, 115.00, "Aguardando..."],
        ["IVVB11.SA", 5, 280.00, "Aguardando..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós"]], columns=["Ativo", "Saldo Atual", "Tipo"])

st.title("💰 Hedge Fund Ricardo")
st.sidebar.button("🧹 Limpar Cache", on_click=lambda: st.cache_data.clear())

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# 1. ANÁLISE
with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            st.subheader("📊 Raio-X & Risco")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("DY Anual", f"{r['dy_anual']:.2f}%")
            if r['score_ia'] == 0: c3.error("BLOQUEADO (0/100)")
            else: c3.metric("Score IA", f"{r['score_ia']}/100", delta=r['decisao_ia'])
            c4.metric("Liquidez", f"R$ {r['liq_media']/1000:.0f}k")
            
            st.divider()
            k1, k2 = st.columns(2)
            k1.table(pd.DataFrame({"Modelo": ["Bazin", "Graham", "Gordon"], "Valor": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]}))
            if "⚠️" in r['motivos'] or "⛔" in r['motivos']: k2.error(r['motivos'])
            else: k2.info(r['motivos'])
            
            st.subheader("Gráfico & Técnico")
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("Stop Loss", f"R$ {r['stop_loss']:.2f}")
            cc2.metric("Stop Gain", f"R$ {r['stop_gain']:.2f}")
            cc3.metric("Sinal", r['sinal_tecnico'])

            components.html(f"""<script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width":"100%","height":500,"symbol":"BMFBOVESPA:{t.replace('.SA','')}","interval":"D","theme":"light"}});</script>""", height=500)
        else: st.error("Ativo não encontrado. Limpe o cache.")

# 2. CARTEIRA
with tabs[1]:
    st.subheader("Gestão")
    if st.button("🤖 1. Classificar"): auto_classificar(); st.rerun()
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True, column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=list(METAS.keys()))})
    st.session_state.carteira_acoes = df_ed
    aporte = st.number_input("Aporte (R$)", value=5000.0)
    if st.button("🚀 2. Rebalancear"):
        dados = []
        for _, row in df_ed.iterrows():
            d = obter_dados(row["Ticker"])
            if d: dados.append({**row.to_dict(), "Preço": d["preco"], "Valor_Atual": row["Qtd"]*d["preco"], "Score": d["score_ia"]})
            else: dados.append({**row.to_dict(), "Preço": 10, "Valor_Atual": row["Qtd"]*10, "Score": 50})
        
        df_final = rebalancear_e_aportar(pd.DataFrame(dados), aporte, METAS)
        df_show = df_final[(df_final["Aporte Sugerido (R$)"] > 1) & (df_final["Score"] > 0)]
        
        if df_show.empty and df_final["Aporte Sugerido (R$)"].sum() > 0: st.warning("Compras bloqueadas por Risco (Score 0).")
        else: st.dataframe(df_show[["Ticker", "Setor", "Score", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# 3. FIIs
with tabs[2]:
    st.subheader("Scanner")
    up = st.file_uploader("Upload CSV", type=["csv"])
    if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))

# 4. RF
with tabs[3]:
    st.subheader("RF")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

# 5. FUTURO
with tabs[4]:
    st.subheader("Monte Carlo")
    if st.button("Simular"):
        tks = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_historico_longo(tks)
        if not h.empty:
            r = h.pct_change().dropna().mean(axis=1)
            st.line_chart(MotorAnalise().monte_carlo_carteira(r, 100000, 2000))

# 6. FISCAL
with tabs[5]:
    st.subheader("DARF")
    if st.button("Calcular") and calcular_darf: st.write(calcular_darf(st.session_state.carteira_acoes))

# 7. OPÇÕES
with tabs[6]:
    st.subheader("Black-Scholes")
    if BlackScholes:
        s = st.number_input("Spot", 30.0); k = st.number_input("Strike", 32.0)
        st.metric("Call", f"R$ {BlackScholes(s, k, 1/12, 0.12, 0.3, 'call').calcular_preco():.2f}")