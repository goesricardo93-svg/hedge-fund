import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import datetime

try:
    from motor import MotorAnalise
    from scanner import scanner_fiis_csv
    from alerts import disparar_alerta, enviar_relatorio_anexo
    from rebalance import rebalancear_e_aportar
    from tax import calcular_darf
    from relatorio import RelatorioPrivate
    from options import BlackScholes
except:
    st.error("Erro ao carregar módulos dependentes."); st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 55.0", layout="wide")

# Mapeamento de Metas conforme sua solicitação
METAS_ESTRATEGIA = {
    "Renda Fixa": 30.0, "Exterior": 20.0, "Ações-Bancos": 7.5,
    "Ações-Elétricas": 7.5, "Ações-Seguridade": 6.0, "Ações-Commodities": 6.0,
    "Ações-Outros": 3.0, "FIIs-Papel": 10.0, "FIIs-Tijolo": 6.0, "FIIs-Outros": 4.0
}

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker); hist = t.history(period="2y")
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

def auto_classificar_carteira():
    motor = MotorAnalise()
    with st.spinner("🤖 IA classificando setores..."):
        for idx, row in st.session_state.carteira_acoes.iterrows():
            try:
                info = yf.Ticker(row["Ticker"]).info
                st.session_state.carteira_acoes.at[idx, "Setor"] = motor.identificar_setor(info, row["Ticker"])
            except: st.session_state.carteira_acoes.at[idx, "Setor"] = "Ações-Outros"

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 25.0, "Aguardando IA..."], ["TAEE11.SA", 100, 35.0, "Aguardando IA..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós"]], columns=["Ativo", "Saldo Atual", "Tipo"])

st.sidebar.title("📊 Hedge Fund Ricardo")
if st.sidebar.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

ticker_input = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3").upper()
if not ticker_input.endswith(".SA") and not "-" in ticker_input: ticker_input += ".SA"

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs", "🛡️ Renda Fixa", "💰 Futuro", "⚡ Opções"])

with tabs[0]:
    r = obter_dados(ticker_input)
    if r:
        st.metric("Score IA", f"{r['score_ia']}/100")
        st.write(f"Veredito: {r['decisao_ia']}")
        # Widget TradingView simplificado
        components.html(f'<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width": "100%", "height": 400, "symbol": "BMFBOVESPA:{ticker_input.replace(".SA","")}", "interval": "D", "theme": "light"}});</script>', height=400)
    else: st.warning("Ativo não encontrado.")

with tabs[1]:
    st.subheader("💼 Gestão de Carteira")
    if st.button("🤖 Classificar Setores via IA"): auto_classificar_carteira(); st.rerun()
    
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True, 
                           column_config={"Setor": st.column_config.SelectboxColumn("Setor (IA)", options=list(METAS_ESTRATEGIA.keys()))})
    st.session_state.carteira_acoes = df_ed
    
    aporte = st.number_input("Aporte Disponível (R$)", 1000.0)
    if st.button("🚀 Executar Rebalanceamento"):
        if "Aguardando IA..." in df_ed["Setor"].values: st.error("Classifique os setores primeiro.")
        else:
            analisados = []
            for _, row in df_ed.iterrows():
                dat = obter_dados(row["Ticker"])
                if dat: analisados.append({**row.to_dict(), "Preço": dat["preco"], "Valor_Atual": row["Qtd"]*dat["preco"], "Score": dat["score_ia"]})
            if analisados:
                df_final = rebalancear_e_aportar(pd.DataFrame(analisados), aporte, metas_setores=METAS_ESTRATEGIA)
                st.dataframe(df_final[df_final["Aporte Sugerido (R$)"] > 0][["Ticker", "Setor", "Aporte Sugerido (R$)"]])