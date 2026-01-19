import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import yfinance as yf

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v96", layout="wide", page_icon="💰")

# ======================================================
# 2. AUTO-RESET (GARANTE QUE OS 31 ATIVOS APAREÇAM)
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v96":
    st.session_state.versao_sistema = "v96"
    if "carteira_acoes" in st.session_state: del st.session_state["carteira_acoes"]
    st.toast("Layout v49 restaurado com sucesso!", icon="✅")

# ======================================================
# 3. IMPORTAÇÃO
# ======================================================
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    try: from scanner import scanner_fiis_csv, scanner_auto_yahoo
    except: scanner_fiis_csv = None; scanner_auto_yahoo = None
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
except Exception as e:
    st.error(f"Erro crítico: {e}")
    st.stop()

# ======================================================
# 4. CARGA DOS 31 ATIVOS REAIS
# ======================================================
if "carteira_acoes" not in st.session_state:
    dados_reais = [
        ["ALZR11.SA", 100, 10.81, "FIIs-Tijolo"], ["BBAS3.SA", 1703, 24.48, "Ações-Bancos"], 
        ["BBSE3.SA", 55, 35.64, "Ações-Seguridade"], ["BTCI11.SA", 502, 10.16, "FIIs-Papel"], 
        ["BTLG11.SA", 60, 98.50, "FIIs-Tijolo"], ["CCME11.SA", 152, 8.55, "FIIs-Outros"],
        ["CMIG4.SA", 1644, 11.12, "Ações-Elétricas"], ["CPLE3.SA", 617, 9.64, "Ações-Elétricas"], 
        ["CPSH11.SA", 169, 10.10, "FIIs-Tijolo"], ["CPTS11.SA", 276, 8.52, "FIIs-Papel"], 
        ["CXSE3.SA", 800, 14.20, "Ações-Seguridade"], ["EQTL3.SA", 200, 30.21, "Ações-Elétricas"],
        ["HGCR11.SA", 20, 95.81, "FIIs-Papel"], ["HGLG11.SA", 20, 158.03, "FIIs-Tijolo"], 
        ["ITSA4.SA", 1174, 9.63, "Ações-Bancos"], ["IVVB11.SA", 6, 366.97, "Exterior"], 
        ["KLBN4.SA", 2323, 3.63, "Ações-Commodities"], ["KNCR11.SA", 27, 103.11, "FIIs-Papel"],
        ["KNHF11.SA", 15, 93.23, "FIIs-Papel"], ["KNRI11.SA", 30, 152.49, "FIIs-Tijolo"], 
        ["KNSC11.SA", 373, 8.78, "FIIs-Papel"], ["KNUQ11.SA", 16, 102.45, "FIIs-Outros"], 
        ["PETR4.SA", 900, 32.07, "Ações-Commodities"], ["SAPR11.SA", 300, 37.97, "Ações-Outros"],
        ["TAEE4.SA", 1000, 11.36, "Ações-Elétricas"], ["VALE3.SA", 152, 54.79, "Ações-Commodities"], 
        ["VGIR11.SA", 296, 9.58, "FIIs-Papel"], ["VISC11.SA", 16, 109.70, "FIIs-Tijolo"], 
        ["XPCA11.SA", 110, 8.77, "FIIs-Outros"], ["XPLG11.SA", 26, 102.31, "FIIs-Tijolo"],
        ["XPML11.SA", 10, 106.05, "FIIs-Tijolo"]
    ]
    st.session_state.carteira_acoes = pd.DataFrame(dados_reais, columns=["Ticker", "Qtd", "PM", "Setor"])

if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([
        {"Setor": "Renda Fixa", "Meta (%)": 20.0}, {"Setor": "Exterior", "Meta (%)": 15.0},
        {"Setor": "Ações-Bancos", "Meta (%)": 10.0}, {"Setor": "Ações-Elétricas", "Meta (%)": 10.0},
        {"Setor": "Ações-Seguridade", "Meta (%)": 5.0}, {"Setor": "Ações-Commodities", "Meta (%)": 5.0},
        {"Setor": "Ações-Outros", "Meta (%)": 5.0}, {"Setor": "FIIs-Papel", "Meta (%)": 15.0},
        {"Setor": "FIIs-Tijolo", "Meta (%)": 10.0}, {"Setor": "FIIs-Outros", "Meta (%)": 5.0}
    ])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós-Fixado"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# ======================================================
# 5. FUNÇÕES
# ======================================================
@st.cache_data(ttl=300)
def obter_dados(ticker):
    try: return MotorAnalise().analisar(yf.Ticker(ticker).history(period="2y"), yf.Ticker(ticker).info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_longo(tickers):
    try:
        d = yf.download(tickers, period="5y", progress=False)
        return d["Adj Close"] if "Adj Close" in d else d["Close"]
    except: return pd.DataFrame()

def auto_classificar():
    motor = MotorAnalise()
    prog = st.progress(0, "Classificando...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        try: st.session_state.carteira_acoes.at[i, "Setor"] = motor.identificar_setor(yf.Ticker(row["Ticker"]).info, row["Ticker"])
        except: st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    prog.empty(); st.success("Ok!")

# ======================================================
# 6. UI
# ======================================================
st.title("💰 Hedge Fund Ricardo v96")

with st.sidebar:
    st.header("Backup Seguro")
    csv = st.session_state.carteira_acoes.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Salvar Backup", csv, "backup_v96.csv", "text/csv")
    up = st.file_uploader("📂 Restaurar", type=['csv'])
    if up:
        try:
            st.session_state.carteira_acoes = pd.read_csv(up)
            st.success("Restaurado!"); st.rerun()
        except: st.error("Erro no arquivo")
    
    st.divider()
    if st.button("🧹 Limpar Memória"): 
        st.cache_data.clear()
        st.rerun()

tabs = st.tabs(["🔎 Análise Completa", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# ABA 1: ANÁLISE COMPLETA (LAYOUT V49 RESTAURADO)
with tabs[0]:
    t = st.text_input("Ticker", "BBSE3.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            # --- CABEÇALHO GERAL ---
            c_score, c_veredito = st.columns([1, 3])
            cor = "normal" if r['score_ia'] >= 60 else "inverse"
            c_score.metric("Score IA", f"{r['score_ia']}/100")
            c_veredito.info(f"**Veredito:** {r['decisao_ia']} | **Motivos:** {r['motivos']}")
            if r['alertas']: c_veredito.error(f"**Atenção:** {r['alertas']}")
            
            st.divider()

            # --- LINHA DE MÉTRICAS (V49: PREÇO, TETO, RSI, VOL) ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
            k2.metric("Teto (Stop Gain)", f"R$ {r['stop_gain']:.2f}")
            # AQUI ESTÁ O RSI DE VOLTA
            k3.metric("RSI (14)", f"{r['rsi']:.0f}", delta="Sobrecomprado" if r['rsi']>70 else "Sobrevendido" if r['rsi']<30 else "Neutro", delta_color="inverse")
            k4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")

            st.divider()

            # --- FUNDAMENTOS: VALUATION E SEGURANÇA ---
            col_val, col_fund = st.columns(2)
            
            with col_val:
                st.subheader("📋 Valuation")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Dividendos)", "Graham (Patrimonial)", "Gordon (Crescimento)"],
                    "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
                }))
                
            with col_fund:
                st.subheader("📊 Segurança & Solvência")
                # Exibindo métricas fundamentais detalhadas
                st.dataframe(pd.DataFrame([
                    {"Indicador": "Liquidez Corrente (>1)", "Valor": f"{r['liq_corrente']:.2f}"},
                    {"Indicador": "Cresc. Receita", "Valor": f"{r['cresc_receita']*100:.1f}%"},
                    {"Indicador": "Dívida/EBITDA (<3)", "Valor": f"{r['divida_ebitda']:.2f}x"},
                    {"Indicador": "ROE (Rentabilidade)", "Valor": f"{r['roe']*100:.1f}%"},
                    {"Indicador": "Margem Líquida", "Valor": f"{r['margem_liq']*100:.1f}%"}
                ]), use_container_width=True, hide_index=True)

            # --- SETUP ROBÔ ---
            st.subheader("🎯 Setup Operacional (Robô)")
            sinal = r['sinal_tecnico']
            cor_sinal = "🟢" if "COMPRA" in sinal or "ALTA" in sinal else "🔴" if "VENDA" in sinal or "BAIXA" in sinal else "⚪"
            vol = f"{r['vol_relativo']:.1f}x Média"
            macd_s = "↗️ Subindo" if (r['macd'] - r['macd_signal']) > 0 else "↘️ Caindo"
            
            df_setup = pd.DataFrame([
                {"Indicador": "SINAL TÉCNICO", "Valor": f"{cor_sinal} {sinal}"},
                {"Indicador": "Preço de Entrada (Sugerido)", "Valor": f"R$ {r['preco_alvo_entrada']:.2f}" if r['preco_alvo_entrada']>0 else "-"},
                {"Indicador": "Volume Relativo", "Valor": vol},
                {"Indicador": "MACD", "Valor": macd_s},
                {"Indicador": "Média Curta (9)", "Valor": f"R$ {r['mme9']:.2f}"},
                {"Indicador": "Média Longa (21)", "Valor": f"R$ {r['mme21']:.2f}"},
                {"Indicador": "Stop Loss (Segurança)", "Valor": f"R$ {r['stop_loss']:.2f}"}
            ])
            st.dataframe(df_setup, use_container_width=True, hide_index=True)

            # GRÁFICO
            st.subheader("Gráfico Interativo")
            sym = t.replace(".SA", "")
            widget = f"""<div class="tradingview-widget-container"><div id="tradingview_123"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 500, "symbol": "BMFBOVESPA:{sym}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_123" }});</script></div>"""
            components.html(widget, height=500)
        else: st.error("Ativo não encontrado.")

# ABA 2: CARTEIRA
with tabs[1]:
    c1, c2 = st.columns([1, 2])
    c1.subheader("Metas %")
    st.session_state.df_metas = c1.data_editor(st.session_state.df_metas, num_rows="dynamic")
    
    c2.subheader(f"Meus Ativos ({len(st.session_state.carteira_acoes)})")
    if c2.button("Classificar"): auto_classificar()
    
    st.session_state.carteira_acoes = c2.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=st.session_state.df_metas["Setor"].tolist())}, use_container_width=True)
    
    aporte = c2.number_input("Aporte", 5000.0)
    if c2.button("Calcular Rebalanceamento"):
        m = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        dados = []
        bar = st.progress(0, "Calculando...")
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"])
            p = d["preco"] if d else 0
            s = d["score_ia"] if d else 0
            dados.append({**row.to_dict(), "Preço": p, "Valor_Atual": row["Qtd"]*p, "Score": s})
            bar.progress((i+1)/len(st.session_state.carteira_acoes))
        bar.empty()
        res = rebalancear_e_aportar(pd.DataFrame(dados), aporte, m)
        st.dataframe(res[res["Aporte Sugerido (R$)"] > 0.01].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# DEMAIS ABAS
with tabs[2]:
    st.subheader("Scanner")
    if st.button("Auto Scanner") and scanner_auto_yahoo: st.dataframe(scanner_auto_yahoo())
    up = st.file_uploader("CSV", type=["csv"])
    if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))

with tabs[3]:
    st.subheader("Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

with tabs[4]:
    if st.button("Monte Carlo"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: st.line_chart(MotorAnalise().monte_carlo_carteira(h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna(), 100000, 2000))

with tabs[5]:
    if st.button("DARF") and calcular_darf: st.table(calcular_darf(st.session_state.carteira_acoes))

with tabs[6]:
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1: S=st.number_input("Spot",30.0); K=st.number_input("Strike",32.0)
        with c2: T=st.number_input("Dias",30)/365; sig=st.number_input("Vol",0.30)
        bs = BlackScholes(S,K,T,0.13,sig,"call")
        st.write(bs.calcular_gregas())