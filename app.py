import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np

# Tenta importar módulos opcionais sem quebrar o app principal
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    # Imports opcionais (se não tiver os arquivos, o app roda sem eles)
    try: from scanner import scanner_fiis_csv
    except: scanner_fiis_csv = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from options import BlackScholes
    except: BlackScholes = None
except ImportError as e:
    st.error(f"Erro crítico nos módulos: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo v59.0 (Full)", layout="wide")

# METAS
METAS = {
    "Renda Fixa": 30.0, "Exterior": 20.0,
    "Ações-Bancos": 7.5, "Ações-Elétricas": 7.5, "Ações-Seguridade": 6.0, "Ações-Commodities": 6.0, "Ações-Outros": 3.0,
    "FIIs-Papel": 10.0, "FIIs-Tijolo": 6.0, "FIIs-Outros": 4.0
}

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker); hist = t.history(period="1y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

def auto_classificar():
    motor = MotorAnalise()
    for idx, row in st.session_state.carteira_acoes.iterrows():
        try:
            t = yf.Ticker(row["Ticker"])
            setor = motor.identificar_setor(t.info, row["Ticker"])
            st.session_state.carteira_acoes.at[idx, "Setor"] = setor
        except: st.session_state.carteira_acoes.at[idx, "Setor"] = "Outros"

# INICIALIZAÇÃO
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Aguardando..."],
        ["CPSH11.SA", 50, 10.10, "Aguardando..."],
        ["XPML11.SA", 10, 115.00, "Aguardando..."],
        ["IVVB11.SA", 5, 280.00, "Aguardando..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# --- INTERFACE ---
st.title("💰 Hedge Fund Ricardo")
st.sidebar.button("🧹 Limpar Cache", on_click=lambda: st.cache_data.clear())

# RECOLOCANDO TODAS AS ABAS
tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# 1. ANÁLISE (Com Travas de Risco)
with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            # Cabeçalho com Riscos
            st.subheader("📊 Raio-X & Segurança")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("DY Anual (Real)", f"{r.get('dy_anual', 0):.2f}%")
            
            # Score Vermelho se for 0
            score_val = r['score_ia']
            if score_val == 0: c3.error("BLOQUEADO (0/100)")
            else: c3.metric("Score IA", f"{score_val}/100", delta=r['decisao_ia'])
            
            c4.metric("Liquidez Média", f"R$ {r.get('liq_media', 0)/1000:.0f}k")
            
            st.divider()
            
            # Valuation
            k1, k2 = st.columns(2)
            k1.table(pd.DataFrame({"Modelo": ["Bazin", "Graham", "Gordon"], "Valor": [f"R$ {r.get('p_bazin',0):.2f}", f"R$ {r.get('p_graham',0):.2f}", f"R$ {r.get('p_gordon',0):.2f}"]}))
            
            # Motivos (Coloridos se tiver perigo)
            motivos = r.get('motivos', '')
            if "⚠️" in motivos or "⛔" in motivos: k2.error(motivos)
            else: k2.info(motivos)
            
        else: st.error("Ativo não encontrado.")

# 2. CARTEIRA (Rebalanceamento)
with tabs[1]:
    st.subheader("Gestão da Carteira")
    if st.button("🤖 1. Classificar (IA)"): auto_classificar(); st.rerun()
    
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True, column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=list(METAS.keys()))})
    st.session_state.carteira_acoes = df_ed
    
    aporte = st.number_input("Aporte (R$)", value=5000.0)
    if st.button("🚀 2. Rebalancear"):
        dados = []
        for _, row in df_ed.iterrows():
            d = obter_dados(row["Ticker"])
            if d: dados.append({**row.to_dict(), "Preço": d["preco"], "Valor_Atual": row["Qtd"]*d["preco"], "Score": d["score_ia"]})
            else: dados.append({**row.to_dict(), "Preço": 10, "Valor_Atual": row["Qtd"]*10, "Score": 50}) # Fallback
        
        df_final = rebalancear_e_aportar(pd.DataFrame(dados), aporte, METAS)
        
        # Filtra apenas compras válidas (> R$ 1 e Score > 0)
        df_show = df_final[(df_final["Aporte Sugerido (R$)"] > 1) & (df_final["Score"] > 0)]
        
        if df_show.empty and df_final["Aporte Sugerido (R$)"].sum() > 0:
            st.warning("O sistema sugeriu compras, mas os ativos foram BLOQUEADOS pelas travas de segurança (Score 0).")
        else:
            st.success("Plano de Compra Gerado:")
            st.dataframe(df_show[["Ticker", "Setor", "Score", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# 3. FIIs 360 (Restaurado)
with tabs[2]:
    st.write("Scanner de FIIs")
    up = st.file_uploader("Upload CSV StatusInvest", type=["csv"])
    if up and scanner_fiis_csv:
        df_fii = scanner_fiis_csv(up)
        st.dataframe(df_fii)
    elif up and not scanner_fiis_csv: st.warning("Arquivo scanner.py ausente.")

# 4. RF
with tabs[3]:
    st.write("Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total RF", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

# 5. Futuro (Placeholder Seguro)
with tabs[4]: st.info("Simulação de Monte Carlo disponível se arquivos auxiliares estiverem presentes.")

# 6. Fiscal
with tabs[5]:
    st.write("Cálculo de DARF")
    if st.button("Calcular") and calcular_darf:
        res = calcular_darf(st.session_state.carteira_acoes)
        st.write(res)
    elif not calcular_darf: st.warning("Arquivo tax.py ausente.")

# 7. Opções
with tabs[6]:
    st.write("Black-Scholes")
    if BlackScholes:
        spot = st.number_input("Preço Ativo", 30.0)
        strike = st.number_input("Strike", 32.0)
        bs = BlackScholes(spot, strike, 1/12, 0.12, 0.3, "call")
        st.metric("Preço Justo", f"R$ {bs.calcular_preco():.2f}")
    else: st.warning("Arquivo options.py ausente.")