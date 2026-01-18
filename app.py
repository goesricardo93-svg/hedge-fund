import streamlit as st
# --- 1. CONFIGURAÇÃO (PRIMEIRA LINHA) ---
st.set_page_config(page_title="Hedge Fund Ricardo v78", layout="wide")

# --- 2. IMPORTS ---
import pandas as pd
import yfinance as yf
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    try: from scanner import scanner_fiis_csv, scanner_auto_yahoo
    except: scanner_auto_yahoo = None
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
except Exception as e:
    st.error(f"Erro Fatal: {e}")
    st.stop()

# --- 3. ESTADO ---
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([["MXRF11.SA", 100, 10.0, "FIIs-Papel"]], columns=["Ticker", "Qtd", "PM", "Setor"])
if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([{"Setor": "FIIs-Papel", "Meta (%)": 100.0}])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro", 1000, "Pos"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# --- 4. FUNÇÕES ---
@st.cache_data(ttl=300)
def get_data(t): 
    try: return MotorAnalise().analisar(yf.Ticker(t).history(period="1y"), yf.Ticker(t).info, t)
    except: return None

# --- 5. UI ---
st.title("💰 Hedge Fund Ricardo v78")

with st.sidebar:
    if st.button("Limpar Cache"): st.cache_data.clear(); st.rerun()
    if gerar_pdf_carteira and st.button("Gerar PDF"):
        st.success("PDF Gerado (Simulação)")

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "⚡ Opções", "🦁 Fiscal"])

with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = get_data(t)
        if r:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("DY", f"{r['dy_anual']:.2f}%")
            c3.metric("Score", f"{r['score_ia']}", delta=r['decisao_ia'])
            c4.metric("P/VP", f"{r['pvp']:.2f}") # Agora mostra o P/VP calculado
            
            st.write(f"**Motivos:** {r['motivos']}")
            if r.get('alertas'): st.error(f"**Risco:** {r['alertas']}")
            
            st.table(pd.DataFrame({"Bazin": [r['p_bazin']], "Preço Justo": [r['preco_justo']]}))

with tabs[1]:
    st.write("Carteira")
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic")
    if st.button("Rebalancear"):
        meta = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        dados = []
        for _, row in st.session_state.carteira_acoes.iterrows():
            d = get_data(row["Ticker"])
            if d: dados.append({**row, "Preço": d['preco'], "Score": d['score_ia'], "Valor_Atual": d['preco']*row['Qtd']})
        st.dataframe(rebalancear_e_aportar(pd.DataFrame(dados), 5000, meta))

with tabs[2]:
    st.subheader("Scanner 360")
    if st.button("Rodar Scanner"):
        if scanner_auto_yahoo:
            with st.spinner("Analisando..."):
                df = scanner_auto_yahoo()
                st.dataframe(df)
        else: st.error("Scanner indisponível")

with tabs[3]:
    if BlackScholes:
        st.write("Black-Scholes")
        bs = BlackScholes(30, 32, 0.1, 0.13, 0.3, "call")
        st.write(bs.calcular_gregas())

with tabs[4]:
    if calcular_darf:
        if st.button("Calcular DARF"):
            st.table(calcular_darf(st.session_state.carteira_acoes))