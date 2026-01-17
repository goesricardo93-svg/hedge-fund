import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
from motor import MotorAnalise
from alerts import disparar_alerta # Importa o novo sistema de alertas

# ======================================================
# CONFIGURAÇÃO DA PÁGINA
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | v8.0", layout="wide")

# ======================================================
# FUNÇÕES AUXILIARES (CACHE E LÓGICA)
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None, None
        
        motor = MotorAnalise()
        r = motor.analisar(hist, t.info, ticker)
        return r, t.info
    except:
        return None, None

def get_rsi_status(val):
    if val < 30: return f"🟢 SOBREVENDA ({val:.0f})"
    if val > 70: return f"🔴 SOBRECOMPRA ({val:.0f})"
    return f"⚪ NEUTRO ({val:.0f})"

def sugerir_aportes(df, aporte, metas_setor):
    if df.empty: return pd.DataFrame()
    df = df.copy()
    
    # Cálculos de Peso
    df["Valor"] = df["Qtd"] * df["Cotação"]
    total = df["Valor"].sum()
    if total == 0: total = 1
    
    df["Peso_Atual"] = df["Valor"] / total
    
    # Metas
    dict_metas = dict(zip(metas_setor["Setor"], metas_setor["Meta"]))
    df["Meta_Setorial"] = df["Setor"].map(dict_metas).fillna(0.05)
    qtd_por_setor = df.groupby("Setor")["Ticker"].transform("count")
    df["Peso_Alvo"] = df["Meta_Setorial"] / qtd_por_setor

    # Score de Prioridade
    df["Gap"] = df["Peso_Alvo"] - df["Peso_Atual"]
    
    # Fórmula: Gap (rebalanceamento) + Score Técnico + Oportunidade Preço
    df["Score_IA"] = (
        (df["Gap"] * 100 * 2) +          
        (df["Score"] / 100) +            
        ((df["PM"] - df["Cotação"]) / df["PM"]) 
    )
    df["Score_IA"] = df["Score_IA"].clip(lower=0)

    # Distribuição
    soma = df["Score_IA"].sum()
    if soma > 0:
        df["Aporte_Sugerido"] = (df["Score_IA"] / soma) * aporte
    else:
        df["Aporte_Sugerido"] = 0
        
    return df[df["Aporte_Sugerido"] > 1].sort_values("Aporte_Sugerido", ascending=False)

# ======================================================
# ESTADO DA SESSÃO (DADOS INICIAIS)
# ======================================================
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 1703, 24.48, "Bancos"],
        ["VALE3.SA", 152, 54.79, "Mineração"],
        ["ITSA4.SA", 1174, 9.63, "Holding"],
        ["TAEE11.SA", 500, 35.00, "Elétricas"],
        ["KLBN4.SA", 2323, 3.63, "Papel"],
        ["PETR4.SA", 900, 32.07, "Petróleo"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_fiis" not in st.session_state:
    st.session_state.carteira_fiis = pd.DataFrame([
        ["HGLG11.SA", 20, 158.03, "Logística"],
        ["KNCR11.SA", 27, 103.11, "Papel"],
        ["MXRF11.SA", 100, 10.50, "Híbrido"],
        ["VISC11.SA", 16, 109.70, "Shoppings"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000, "Pós"],
        ["PGBL BTG", 50000, "Multimercado"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

if "metas_setor" not in st.session_state:
    st.session_state.metas_setor = pd.DataFrame([
        ["Bancos", 0.15], ["Mineração", 0.10], ["Elétricas", 0.15],
        ["Holding", 0.10], ["Logística", 0.10], ["Papel", 0.10],
        ["Outros", 0.10], ["Petróleo", 0.10], ["Shoppings", 0.05], ["Híbrido", 0.05]
    ], columns=["Setor", "Meta"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# INTERFACE PRINCIPAL
# ======================================================
st.sidebar.title("📊 Painel de Controle")

# --- SIDEBAR: METAS ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Metas de Alocação")
df_metas = st.sidebar.data_editor(st.session_state.metas_setor, num_rows="dynamic", key="meta_ed")
st.session_state.metas_setor = df_metas

soma = df_metas["Meta"].sum()
if abs(soma - 1.0) > 0.01:
    st.sidebar.warning(f"⚠️ Soma: {soma*100:.0f}% (Ideal: 100%)")
else:
    st.sidebar.success("✅ Alocação Balanceada")

st.sidebar.markdown("---")
ticker_input = st.sidebar.text_input("🔍 Ticker:", "BBAS3.SA").upper()

# --- ABAS PRINCIPAIS ---
tabs = st.tabs(["🔎 Análise Técnica", "💼 Ações", "🏢 FIIs & Scanner", "💰 RF & PGBL"])

# === ABA 1: ANÁLISE TÉCNICA E FUNDAMENTALISTA ===
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    r, info = obter_dados(ticker_input)
    
    if r:
        # Linha 1: Preços
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        c2.metric("Bazin (Teto 6%)", f"R$ {r['p_bazin']:.2f}", delta=f"{r['p_bazin']-r['preco']:.2f}")
        c3.metric("Graham (Justo)", f"R$ {r['p_graham']:.2f}")
        c4.metric("Gordon (Est.)", f"R$ {r['p_gordon']:.2f}")

        # Linha 2: Indicadores
        c5, c6, c7, c8 = st.columns(4)
        c5.markdown(f"**{get_rsi_status(r['rsi'])}**")
        c6.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        c7.metric("Drawdown Max", f"{r['drawdown']:.1f}%", delta_color="inverse")
        c8.metric("DY Anual", f"{r['dy']*100:.2f}%")

        # Gráfico
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist_chart.index, y=hist_chart["Close"], name="Preço"))
            if r['p_bazin'] > 0: 
                fig.add_hline(y=r['p_bazin'], line_dash="dash", line_color="green", annotation_text="Teto Bazin")
            st.plotly_chart(fig, use_container_width=True)
        except:
            st.warning("Gráfico indisponível.")
    else:
        st.warning("Ticker não encontrado.")

# === ABA 2: AÇÕES ===
with tabs[1]:
    st.subheader("Gestão de Ações")
    df_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", key="ed_acoes", use_container_width=True)
    st.session_state.carteira_acoes = df_acoes

    if st.button("🔄 Analisar Ações"):
        res = []
        bar = st.progress(0)
        for i, row in df_acoes.iterrows():
            r, info = obter_dados(row["Ticker"])
            if r:
                # Score de Convergência
                score = 0
                if r["preco"] < r["p_bazin"]: score += 30
                if r["preco"] < r["p_graham"]: score += 20
                if r["rsi"] < 40: score += 30
                if row["PM"] > r["preco"]: score += 20
                
                status = "MANTER"
                if score >= 70: status = "🟢 COMPRA"
                elif score <= 30: status = "🔴 VENDA"

                # Disparo de Alerta (Telegram + Outlook)
                chave = f"{row['Ticker']}_{status}"
                if "COMPRA" in status and chave not in st.session_state.alertas_enviados:
                    titulo = f"OPORTUNIDADE: {row['Ticker']}"
                    corpo = f"Preço: R$ {r['preco']:.2f}\nBazin: R$ {r['p_bazin']:.2f}\nScore: {score}/100"
                    disparar_alerta(titulo, corpo)
                    st.session_state.alertas_enviados.add(chave)
                    st.toast(f"Alerta enviado para {row['Ticker']}", icon="📧")

                res.append({**row.to_dict(), "Cotação": r["preco"], "Score": score, "Bazin": r["p_bazin"]})
            else:
                res.append({**row.to_dict(), "Cotação": 0, "Score": 0, "Bazin": 0})
            bar.progress((i+1)/len(df_acoes))
        st.session_state.df_final_acoes = pd.DataFrame(res)
        st.rerun()

    if "df_final_acoes" in st.session_state:
        df_final = st.session_state.df_final_acoes
        st.dataframe(df_final.style.background_gradient(subset=["Score"], cmap="Greens"), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.write("#### 🤖 IA de Aporte")
            val = st.number_input("Aporte Disponível (R$)", 1000.0)
            if st.button("Sugerir Alocação"):
                sug = sugerir_aportes(df_final, val, st.session_state.metas_setor)
                st.dataframe(sug[["Ticker", "Setor", "Peso_Atual", "Peso_Alvo", "Aporte_Sugerido"]].style.format({
                    "Peso_Atual": "{:.1%}", "Peso_Alvo": "{:.1%}", "Aporte_Sugerido": "R$ {:.2f}"
                }))
        
        with c2:
            st.write("#### 📉 Stress Test")
            pat = (df_final["Cotação"] * df_final["Qtd"]).sum()
            if st.button("Simular Crises"):
                motor = MotorAnalise()
                res_stress = motor.stress_test(pat)
                fig = go.Figure()
                for k, v in res_stress.items():
                    fig.add_trace(go.Scatter(y=v, name=k))
                st.plotly_chart(fig, use_container_width=True)

# === ABA 3: FIIs & SCANNER ===
with tabs[2]:
    st.subheader("Carteira FIIs")
    df_fiis = st.data_editor(st.session_state.carteira_fiis, num_rows="dynamic", key="ed_fiis", use_container_width=True)
    st.session_state.carteira_fiis = df_fiis
    
    if st.button("🔄 Atualizar FIIs"):
        res = []
        for _, row in df_fiis.iterrows():
            r, info = obter_dados(row["Ticker"])
            if r:
                res.append({
                    "Ticker": row["Ticker"],
                    "Preço": r["preco"],
                    "DY": f"{r['dy']*100:.2f}%",
                    "PVP Est.": f"{(r['preco'] / r['p_bazin']) * 0.6:.2f}"
                })
        st.session_state.df_fiis_final = pd.DataFrame(res)
        st.rerun()
        
    if "df_fiis_final" in st.session_state:
        st.dataframe(st.session_state.df_fiis_final, use_container_width=True)
        
    st.divider()
    st.subheader("🔍 Scanner CSV (StatusInvest)")
    arquivo_csv = "statusinvest-busca-avancada.csv"
    if os.path.exists(arquivo_csv):
        try:
            df_scan = pd.read_csv(arquivo_csv, sep=";", encoding="latin-1")
            df_scan.columns = df_scan.columns.str.strip().str.upper()
            
            # Tratamento de dados numéricos BR
            cols = ["DY", "P/VP", "VACÂNCIA FISICA"]
            for c in cols:
                if c in df_scan.columns:
                    df_scan[c] = pd.to_numeric(df_scan[c].astype(str).str.replace(".","").str.replace(",",".").str.replace("%",""), errors='coerce')
            
            # Filtro Ricardo
            filtro = (df_scan["DY"] > 6) & (df_scan["P/VP"] < 1.0) & (df_scan["P/VP"] > 0.8)
            st.success(f"{len(df_scan[filtro])} Oportunidades Encontradas")
            st.dataframe(df_scan[filtro][["TICKER", "PRECO", "DY", "P/VP", "SEGMENTO"]].sort_values("DY", ascending=False))
        except Exception as e:
            st.error(f"Erro no CSV: {e}")
    else:
        st.info("Para usar o Scanner Offline, adicione o arquivo 'statusinvest-busca-avancada.csv' na raiz.")

# === ABA 4: RF & PGBL ===
with tabs[3]:
    st.subheader("Renda Fixa & Previdência")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Carteira RF")
        df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", key="ed_rf", use_container_width=True)
        st.session_state.carteira_rf = df_rf
        st.metric("Total RF", f"R$ {df_rf['Saldo Atual'].sum():,.2f}")
        
    with col2:
        st.markdown("### 🛡️ Calculadora Fiscal PGBL")
        renda = st.number_input("Renda Bruta Anual", 100000.0, step=1000.0)
        aporte = st.number_input("Aporte PGBL Feito", 12000.0, step=500.0)
        
        limite = renda * 0.12
        restituicao = min(aporte, limite) * 0.275
        
        st.metric("Limite de Benefício (12%)", f"R$ {limite:,.2f}")
        st.metric("Restituição IR Estimada", f"R$ {restituicao:,.2f}", delta="No bolso")
    
    st.divider()
    if st.button("🔮 Simular Futuro (Monte Carlo)"):
        pat_acoes = (st.session_state.df_final_acoes["Cotação"] * st.session_state.df_final_acoes["Qtd"]).sum() if "df_final_acoes" in st.session_state else 0
        total_geral = df_rf['Saldo Atual'].sum() + pat_acoes
        
        motor = MotorAnalise()
        sims = motor.monte_carlo(total_geral, 2000)
        
        fig = go.Figure(go.Histogram(x=sims, nbinsx=30))
        fig.update_layout(title="Distribuição de Patrimônio (10 anos)")
        st.plotly_chart(fig, use_container_width=True)