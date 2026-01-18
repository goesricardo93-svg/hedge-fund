import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import datetime

# --- CONFIGURAÇÃO DE SEGURANÇA ---
try:
    from motor import MotorAnalise
    from scanner import scanner_fiis_csv
    from alerts import disparar_alerta, enviar_relatorio_anexo
    from rebalance import rebalancear_e_aportar
    from tax import calcular_darf
    from relatorio import RelatorioPrivate
    from options import BlackScholes
except ImportError as e:
    st.error(f"Erro de Módulos: {e}"); st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | v56.0", layout="wide")

# Estratégia Definida pelo Usuário
METAS_ESTRATEGIA = {
    "Renda Fixa": 30.0, "Exterior": 20.0, "Ações-Bancos": 7.5,
    "Ações-Elétricas": 7.5, "Ações-Seguridade": 6.0, "Ações-Commodities": 6.0,
    "Ações-Outros": 3.0, "FIIs-Papel": 10.0, "FIIs-Tijolo": 6.0, "FIIs-Outros": 4.0
}

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

def auto_classificar_carteira():
    motor = MotorAnalise()
    with st.spinner("🤖 IA analisando balanços e setores..."):
        for idx, row in st.session_state.carteira_acoes.iterrows():
            try:
                t = yf.Ticker(row["Ticker"])
                setor_auto = motor.identificar_setor(t.info, row["Ticker"])
                st.session_state.carteira_acoes.at[idx, "Setor"] = setor_auto
            except:
                st.session_state.carteira_acoes.at[idx, "Setor"] = "Ações-Outros"

# Inicialização de Estado
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 1703, 24.48, "Aguardando IA..."],
        ["BBSE3.SA", 55, 35.64, "Aguardando IA..."],
        ["IVVB11.SA", 6, 366.97, "Aguardando IA..."],
        ["HGLG11.SA", 20, 158.03, "Aguardando IA..."],
        ["KNCR11.SA", 27, 103.11, "Aguardando IA..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

# Sidebar
st.sidebar.title("📊 Hedge Fund Ricardo")
if st.sidebar.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

ticker_search = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3").upper()
if ".SA" not in ticker_search and "-" not in ticker_search: ticker_search += ".SA"

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "⚡ Opções"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    r = obter_dados(ticker_search)
    if r:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        k2.metric("Score IA", f"{r['score_ia']}/100")
        k3.metric("RSI", f"{r['rsi']:.0f}")
        k4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        
        st.subheader("📋 Valuation")
        st.table(pd.DataFrame({
            "Modelo": ["Bazin", "Graham", "Gordon"],
            "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
        }))
        
        # Gráfico TradingView
        components.html(f'<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width": "100%", "height": 400, "symbol": "BMFBOVESPA:{ticker_search.replace(".SA","")}", "interval": "D", "theme": "light", "locale": "br"}});</script>', height=400)
    else: st.warning("Ativo não encontrado.")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    st.subheader("💼 Gestão de Alocação Estratégica")
    
    if st.button("🤖 1. Classificar Carteira via IA"):
        auto_classificar_carteira(); st.rerun()
    
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True,
                           column_config={"Setor": st.column_config.SelectboxColumn("Setor (IA)", options=list(METAS_ESTRATEGIA.keys()))})
    st.session_state.carteira_acoes = df_ed
    
    aporte = st.number_input("💰 Aporte Disponível (R$)", min_value=0.0, value=10000.0)
    
    if st.button("🚀 2. Executar Rebalanceamento"):
        if "Aguardando IA..." in df_ed["Setor"].values:
            st.error("Classifique os ativos via IA primeiro.")
        else:
            analisados = []
            for _, row in df_ed.iterrows():
                d = obter_dados(row["Ticker"])
                if d:
                    analisados.append({**row.to_dict(), "Preço": d["preco"], "Valor_Atual": row["Qtd"]*d["preco"], "Score": d["score_ia"]})
            
            if analisados:
                df_final = rebalancear_e_aportar(pd.DataFrame(analisados), aporte, metas_setores=METAS_ESTRATEGIA)
                st.success("Rebalanceamento Concluído!")
                st.dataframe(df_final[df_final["Aporte Sugerido (R$)"] > 0][["Ticker", "Setor", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)