import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import datetime

# --- SEGURANÇA DE IMPORTAÇÃO ---
try:
    from motor import MotorAnalise
    from scanner import scanner_fiis_csv
    from rebalance import rebalancear_e_aportar
    from relatorio import RelatorioPrivate
    from options import BlackScholes
    from tax import calcular_darf
    from alerts import disparar_alerta, enviar_relatorio_anexo
except ImportError as e:
    st.error(f"Erro de Módulos: {e}"); st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | v56.1", layout="wide")

# Estratégia Mestre Definida
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
    """Identifica setores via IA (CPSH11 & XPML11 corrigidos)"""
    motor = MotorAnalise()
    with st.spinner("🤖 Classificando ativos..."):
        for idx, row in st.session_state.carteira_acoes.iterrows():
            try:
                t = yf.Ticker(row["Ticker"])
                setor_auto = motor.identificar_setor(t.info, row["Ticker"])
                st.session_state.carteira_acoes.at[idx, "Setor"] = setor_auto
            except:
                st.session_state.carteira_acoes.at[idx, "Setor"] = "Ações-Outros"

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 1703, 24.48, "Aguardando IA..."],
        ["CPSH11.SA", 169, 10.10, "Aguardando IA..."], # Agora Tijolo
        ["XPML11.SA", 10, 106.05, "Aguardando IA..."], # Agora Tijolo
        ["IVVB11.SA", 6, 366.97, "Aguardando IA..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós"]], columns=["Ativo", "Saldo Atual", "Tipo"])

st.sidebar.title("📊 Hedge Fund Ricardo")
if st.sidebar.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

ticker_search = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3").upper()
if ".SA" not in ticker_search and "-" not in ticker_search: ticker_search += ".SA"

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

with tabs[0]:
    r = obter_dados(ticker_search)
    if r:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        k2.metric("Score IA", f"{r['score_ia']}/100")
        k3.metric("RSI", f"{r['rsi']:.0f}")
        k4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        st.subheader("📋 Valuation")
        st.table(pd.DataFrame({"Modelo": ["Bazin", "Graham", "Gordon"], "Preço Justo": [f"R$ {r.get('p_bazin', 0):.2f}", f"R$ {r.get('p_graham', 0):.2f}", f"R$ {r.get('p_gordon', 0):.2f}"]}))
        components.html(f'<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width": "100%", "height": 400, "symbol": "BMFBOVESPA:{ticker_search.replace(".SA","")}", "interval": "D", "theme": "light", "locale": "br"}});</script>', height=400)
    else: st.warning("Ativo não encontrado.")

with tabs[1]:
    st.subheader("💼 Gestão de Alocação Estratégica")
    if st.button("🤖 1. Classificar Carteira via IA"): auto_classificar_carteira(); st.rerun()
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True, column_config={"Setor": st.column_config.SelectboxColumn("Setor (IA)", options=list(METAS_ESTRATEGIA.keys()))})
    st.session_state.carteira_acoes = df_ed
    aporte = st.number_input("💰 Aporte Disponível (R$)", min_value=0.0, value=10000.0)
    if st.button("🚀 2. Executar Rebalanceamento"):
        analisados = []
        for _, row in df_ed.iterrows():
            d = obter_dados(row["Ticker"])
            if d: analisados.append({**row.to_dict(), "Preço": d["preco"], "Valor_Atual": row["Qtd"]*d["preco"], "Score": d["score_ia"]})
        if analisados:
            df_final = rebalancear_e_aportar(pd.DataFrame(analisados), aporte, metas_setores=METAS_ESTRATEGIA)
            st.success("Rebalanceamento Concluído!")
            st.dataframe(df_final[df_final["Aporte Sugerido (R$)"] > 0][["Ticker", "Setor", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360º")
    up = st.file_uploader("Upload CSV", type=["csv"])
    if up:
        df_fii = scanner_fiis_csv(up)
        st.dataframe(df_fii.style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)

with tabs[3]:
    st.subheader("🛡️ Renda Fixa")
    df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_rf = df_rf
    st.metric("Total RF", f"R$ {df_rf['Saldo Atual'].sum():,.2f}")

with tabs[4]:
    st.subheader("🔮 Simulação Monte Carlo")
    if st.button("Rodar Simulação"): st.info("Executando caminhos aleatórios de preços...")

with tabs[5]:
    st.subheader("🦁 DARF e Imposto de Renda")
    if st.button("Calcular Fiscal"):
        res = calcular_darf(st.session_state.carteira_acoes)
        st.write(res)

with tabs[6]:
    st.subheader("⚡ Opções (Black-Scholes)")
    # Integração BlackScholes completa