import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import requests
import smtplib
from email.mime.text import MIMEText

# Imports Modulares
try:
    from motor import MotorAnalise
    from scanner import scanner_fiis_csv
    from alerts import disparar_alerta
    from rebalance import rebalancear_e_aportar
    from tax import calcular_darf
except ImportError as e:
    st.error(f"Erro Crítico: Faltam arquivos modulares ({e}).")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 37.0 (Hardcore)", layout="wide")

# ======================================================
# CACHE E FUNÇÕES
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados_v37(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_historico_longo(tickers):
    data = yf.download(tickers, period="5y", progress=False)
    if isinstance(data, pd.DataFrame):
        if "Adj Close" in data: return data["Adj Close"]
        elif "Close" in data: return data["Close"]
    return data

def formatar_ticker(ticker):
    t = ticker.strip().upper()
    if t in ["BTC", "ETH", "SOL", "USDT"]: return f"{t}-USD"
    if any(char.isdigit() for char in t) and "." not in t: return f"{t}.SA"
    return t

# ======================================================
# SESSION STATE (CARTEIRA 31 ATIVOS)
# ======================================================
if "carteira_acoes" not in st.session_state:
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

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000.0, "Pós-Fixado"],
        ["PGBL BTG Pactual", 50000.0, "Previdência"],
        ["LCI CDI 90%", 20000.0, "Isento"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# INTERFACE
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")
ticker_raw = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3").upper()
ticker_input = formatar_ticker(ticker_raw)

if st.sidebar.button("🔄 Restaurar Padrões"):
    st.session_state.clear()
    st.rerun()

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ RF & PGBL", "💰 Futuro", "🦁 Fiscal"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    
    # Chama o motor
    motor = MotorAnalise()
    r = obter_dados_v37(ticker_input)
    
    if r:
        # --- DIVIDENDOS (DESTAQUE NO TOPO) ---
        div_info = motor.consultar_dividendos(ticker_input)
        if div_info['status'] != "SEM DADOS":
            cor_div = "green" if div_info['status'] == "CONFIRMADO" else "blue"
            st.markdown(f"""
            <div style="padding:10px; border-radius:5px; background-color:rgba(0,100,0,0.1); border:1px solid {cor_div}; margin-bottom:10px;">
                💰 <b>PROVENTOS ({div_info['status']}):</b> Data: <b>{div_info['data']}</b> | Valor: <b>{div_info['valor']}</b>
            </div>
            """, unsafe_allow_html=True)

        # --- SCORE IA ---
        col_ia1, col_ia2 = st.columns([1, 3])
        col_ia1.metric("Score IA Rigoroso", f"{r['score_ia']}/100")
        
        if "COMPRA" in r['decisao_ia']: 
            col_ia2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']: 
            col_ia2.error(f"### {r['decisao_ia']}")
        else: 
            col_ia2.warning(f"### {r['decisao_ia']}")
        
        st.write(f"**Veredito Cruzado (Fund + Téc):** {r['motivos']}")
        st.divider()

        # --- DADOS GERAIS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        c2.metric("Teto Técnico", f"R$ {r['stop_gain']:.2f}")
        c3.metric("RSI (14)", f"{r['rsi']:.0f}")
        c4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")

        c_val, c_fund = st.columns(2)
        with c_val:
            st.subheader("📋 Valuation")
            val_data = {
                "Modelo": ["Bazin (Div)", "Graham (Patr)", "Gordon (Cresc)"], 
                "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
            }
            st.dataframe(pd.DataFrame(val_data), use_container_width=True)
        
        with c_fund:
            st.subheader("📊 Qualidade & Saúde")
            # Exibe os novos indicadores rigorosos
            fund_data = {
                "Indicador": ["DY", "P/L", "P/VP", "ROE (Rentab.)", "Dívida/EBITDA"], 
                "Valor": [
                    f"{r['dy']*100:.2f}%", 
                    f"{r['pl']:.2f}", 
                    f"{r['pvp']:.2f}", 
                    f"{r['roe']*100:.1f}%", 
                    f"{r['divida_ebitda']:.2f}x"
                ]
            }
            st.dataframe(pd.DataFrame(fund_data), use_container_width=True)

        # --- GRÁFICO ---
        st.subheader("📈 Gráfico Técnico")
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                # Tratamento robusto
                close = hist_chart["Close"] if "Close" in hist_chart else hist_chart.iloc[:,0]
                if isinstance(close, pd.DataFrame): close = close.iloc[:,0]
                
                mm50 = close.rolling(window=50).mean()
                mm200 = close.rolling(window=200).mean() # Nova MM200 para tendência longa

                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=hist_chart.index, 
                    open=hist_chart["Open"] if "Open" in hist_chart else hist_chart.iloc[:,0], 
                    high=hist_chart["High"] if "High" in hist_chart else hist_chart.iloc[:,0], 
                    low=hist_chart["Low"] if "Low" in hist_chart else hist_chart.iloc[:,0], 
                    close=close, name="Preço"
                ))
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm50, name="MM50 (Curto)", line=dict(color='blue')))
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm200, name="MM200 (Longo)", line=dict(color='orange'))) # Nova Linha
                
                fig.add_hline(y=r['suporte'], line_dash="dot", line_color="green", annotation_text="SUPORTE")
                fig.add_hline(y=r['resistencia'], line_dash="dot", line_color="red", annotation_text="RESISTÊNCIA")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e: st.error(f"Erro gráfico: {e}")

    else: 
        st.warning("Ticker não encontrado. Verifique se digitou corretamente (ex: BBAS3).")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    st.subheader(f"💼 Gestão de Carteira ({len(st.session_state.carteira_acoes)} Ativos)")
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_acoes = df_ed
    
    st.divider()
    aporte_user = st.number_input("💰 Aporte Disponível (R$)", 1000.0)

    if st.button("🔄 Analisar e Rebalancear"):
        res = []
        bar = st.progress(0)
        total_ativos = len(df_ed)
        for i, row in df_ed.iterrows():
            r = obter_dados_v37(row["Ticker"])
            if r:
                rec = r['decisao_ia']
                if r['preco'] < row['PM'] * 0.95 and "COMPRA" in rec: rec = "🔥 COMPRA FORTE (Abaixo PM)"
                
                if r['score_ia'] >= 80 and row["Ticker"] not in st.session_state.alertas_enviados:
                    disparar_alerta(f"TOP PICK: {row['Ticker']}", f"Score: {r['score_ia']}")
                    st.session_state.alertas_enviados.add(row["Ticker"])
                
                res.append({
                    "Ticker": row["Ticker"],
                    "Preço": r["preco"],
                    "PM": row["PM"],
                    "Qtd": row["Qtd"],
                    "Valor_Atual": row["Qtd"] * r["preco"],
                    "Lucro": (r["preco"] - row["PM"]) * row["Qtd"],
                    "Veredito IA": rec,
                    "Score": r['score_ia'],
                    "DY": f"{r['dy']*100:.2f}%"
                })
            bar.progress((i+1)/total_ativos)
        
        if res:
            df_res = pd.DataFrame(res)
            st.session_state.df_analisado = df_res 
            
            df_final = rebalancear_e_aportar(df_res, aporte_user)
            
            if not df_final.empty:
                st.success("✅ Rebalanceamento Concluído!")
                cols_possiveis = ["Ticker", "Score", "Valor_Atual", "Lucro", "Veredito IA", "Aporte Sugerido (R$)"]
                cols_exibicao = [c for c in cols_possiveis if c in df_final.columns]
                
                def cor_lucro(val): return 'color: green' if val > 0 else 'color: red'
                
                st.dataframe(
                    df_final[cols_exibicao]
                    .style.applymap(cor_lucro, subset=["Lucro"] if "Lucro" in df_final.columns else None)
                    .format({"Valor_Atual": "R$ {:.2f}", "Lucro": "R$ {:.2f}", "Aporte Sugerido (R$)": "R$ {:.2f}"}, na_rep="-")
                    .background_gradient(subset=["Aporte Sugerido (R$)"], cmap="Greens"),
                    use_container_width=True
                )
            else:
                st.warning("Não foi possível calcular o rebalanceamento.")

# --- ABA 3: FIIs 360 ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360º")
    uploaded = st.file_uploader("Upload CSV StatusInvest", type=["csv"])
    if uploaded:
        df_fii = scanner_fiis_csv(uploaded)
        if not df_fii.empty:
            st.success(f"{len(df_fii)} FIIs processados!")
            tab_all, tab_papel, tab_tijolo, tab_agro, tab_outros = st.tabs(["🌎 Todos", "📄 Papel", "🧱 Tijolo", "🌱 Agro", "⚙️ Outros"])
            cols = ["TICKER", "CATEGORIA", "PRECO", "DY", "P/VP", "Score", "Veredito", "Motivos (IA)"]
            with tab_all: st.dataframe(df_fii[cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            with tab_papel: st.dataframe(df_fii[df_fii["CATEGORIA"]=="PAPEL"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            with tab_tijolo: st.dataframe(df_fii[df_fii["CATEGORIA"]=="TIJOLO"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            with tab_agro: st.dataframe(df_fii[df_fii["CATEGORIA"]=="AGRO"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            with tab_outros: st.dataframe(df_fii[df_fii["CATEGORIA"]=="OUTROS"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
        else: st.warning("Erro no CSV.")

# --- ABA 4: RENDA FIXA ---
with tabs[3]:
    st.subheader("🛡️ Renda Fixa e PGBL")
    df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_rf = df_rf
    st.metric("Total em Renda Fixa", f"R$ {df_rf['Saldo Atual'].sum():,.2f}")
    st.plotly_chart(go.Figure(data=[go.Pie(labels=df_rf["Ativo"], values=df_rf["Saldo Atual"], hole=.4)]), use_container_width=True)

# --- ABA 5: FUTURO ---
with tabs[4]:
    st.subheader("🔮 Simulação Patrimonial (Monte Carlo Real)")
    
    if "df_analisado" in st.session_state and not st.session_state.df_analisado.empty:
        real_acoes = st.session_state.df_analisado["Valor_Atual"].sum()
    elif not df_ed.empty:
        real_acoes = (df_ed['Qtd'] * df_ed['PM']).sum()
    else:
        real_acoes = 0

    real_rf = st.session_state.carteira_rf["Saldo Atual"].sum()
    real_total = real_acoes + real_rf
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        sim_inicial = st.number_input("💰 Patrimônio Inicial (Simulado)", value=float(real_total), step=1000.0)
    with col_input2:
        sim_aporte = st.number_input("➕ Aporte Mensal", value=2000.0, step=100.0)
    
    if st.button("Simular 10 Anos"):
        tickers = df_ed["Ticker"].tolist()
        try:
            hist = download_historico_longo(tickers)
            retornos_diarios = hist.pct_change().dropna().mean(axis=1)
            
            motor = MotorAnalise()
            prop_risco = 1.0 if real_total == 0 else real_acoes / real_total
            sim_start_risco = sim_inicial * prop_risco
            sim_start_rf = sim_inicial * (1 - prop_risco)
            
            sims_risco = motor.monte_carlo_carteira(retornos_diarios, sim_start_risco, sim_aporte * prop_risco, 10, 1000)
            
            meses = 120
            taxa_mensal_rf = 0.008 
            rf_futuro_base = sim_start_rf * ((1 + taxa_mensal_rf) ** meses)
            aporte_rf = sim_aporte * (1 - prop_risco)
            rf_futuro_aportes = aporte_rf * (((1 + taxa_mensal_rf) ** meses - 1) / taxa_mensal_rf)
            rf_futuro_total = rf_futuro_base + rf_futuro_aportes
            
            sims_total = sims_risco + rf_futuro_total
            
            st.plotly_chart(go.Figure(go.Histogram(x=sims_total, nbinsx=50, marker_color='green')), use_container_width=True)
            
            p50 = np.median(sims_total)
            p10 = np.percentile(sims_total, 10)
            p90 = np.percentile(sims_total, 90)
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Cenário Conservador (10%)", f"R$ {p10:,.2f}")
            k2.metric("Cenário Provável (Mediana)", f"R$ {p50:,.2f}")
            k3.metric("Cenário Otimista (90%)", f"R$ {p90:,.2f}")
            
        except Exception as e: st.error(f"Erro detalhado na simulação: {e}")

# --- ABA 6: FISCAL ---
with tabs[5]:
    st.subheader("🦁 Calculadora de IR (DARF)")
    if "df_vendas" not in st.session_state:
        st.session_state.df_vendas = pd.DataFrame(columns=["Ticker", "Qtd", "Preço Venda", "PM"])
    
    df_vendas = st.data_editor(st.session_state.df_vendas, num_rows="dynamic", use_container_width=True)
    st.session_state.df_vendas = df_vendas
    
    if st.button("Calcular Imposto"):
        resultado = calcular_darf(df_vendas)
        st.divider()
        c1, c2 = st.columns([1, 2])
        c1.metric("DARF a Pagar", f"R$ {resultado['darf']:.2f}")
        c2.write(resultado["detalhes"])
        st.table(resultado["memoria"])