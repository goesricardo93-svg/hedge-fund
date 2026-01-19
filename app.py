import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import yfinance as yf

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v102", layout="wide", page_icon="💰")

# ======================================================
# 2. AUTO-RESET
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v102":
    st.session_state.versao_sistema = "v102"
    st.cache_data.clear()
    st.toast("FIIs: P/VP > 1.02 penalizado! Opções Formatadas.", icon="📉")

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
# 4. CARGA DOS 31 ATIVOS
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
def formatar_ticker_global(t):
    t = t.upper().strip()
    if t in ["BTC", "ETH", "SOL", "USDT", "ADA", "DOGE"]: return f"{t}-USD"
    if "." in t or "-" in t or "=" in t: return t
    if any(char.isdigit() for char in t): return f"{t}.SA"
    return t

@st.cache_data(ttl=300)
def obter_dados(ticker_raw):
    ticker = formatar_ticker_global(ticker_raw)
    try: 
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="2y")
        if hist is None or hist.empty: return None
        try: info = ticker_obj.info
        except: info = {}
        return MotorAnalise().analisar(hist, info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_longo(tickers_raw):
    lista_formatada = [formatar_ticker_global(t) for t in tickers_raw]
    try:
        d = yf.download(lista_formatada, period="5y", progress=False)
        return d["Adj Close"] if "Adj Close" in d else d["Close"]
    except: return pd.DataFrame()

def auto_classificar():
    motor = MotorAnalise()
    prog = st.progress(0, "Classificando...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        try: st.session_state.carteira_acoes.at[i, "Setor"] = motor.identificar_setor(yf.Ticker(formatar_ticker_global(row["Ticker"])).info, row["Ticker"])
        except: st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    prog.empty(); st.success("Ok!")

# ======================================================
# 6. UI
# ======================================================
st.title("💰 Hedge Fund Ricardo v102")

with st.sidebar:
    st.header("Backup")
    csv = st.session_state.carteira_acoes.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Salvar Backup", csv, "backup_v102.csv", "text/csv")
    up = st.file_uploader("📂 Restaurar", type=['csv'])
    if up:
        try:
            st.session_state.carteira_acoes = pd.read_csv(up)
            st.success("Restaurado!"); st.rerun()
        except: st.error("Erro no arquivo")
    
    st.divider()
    if st.button("🧹 Limpeza Total"): 
        st.cache_data.clear()
        st.rerun()

tabs = st.tabs(["🔎 Análise Global", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# ABA 1: ANÁLISE GLOBAL
with tabs[0]:
    c_input, c_btn = st.columns([3, 1])
    with c_input:
        t_input = st.text_input("Ticker", "MXRF11", label_visibility="collapsed", placeholder="Ex: MXRF11, AAPL, BTC...")
    with c_btn:
        btn_analisar = st.button("Analisar", use_container_width=True)

    if btn_analisar:
        t_fmt = formatar_ticker_global(t_input)
        r = obter_dados(t_input)
        
        if r:
            c_score, c_veredito = st.columns([1, 3])
            cor = "normal" if r.get('score_ia', 0) >= 60 else "inverse"
            c_score.metric("Score IA", f"{r.get('score_ia', 0)}/100")
            c_veredito.info(f"**Veredito:** {r.get('decisao_ia', '-')} | **Motivos:** {r.get('motivos', '-')}")
            if r.get('alertas'): c_veredito.error(f"**Atenção:** {r['alertas']}")
            st.divider()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Preço Atual", f"{r.get('preco', 0):.2f}")
            k2.metric("Teto (Stop Gain)", f"{r.get('stop_gain', 0):.2f}")
            rsi_val = r.get('rsi', 50)
            k3.metric("RSI (14)", f"{rsi_val:.0f}", delta="Sobrecomprado" if rsi_val>70 else "Sobrevendido" if rsi_val<30 else "Neutro", delta_color="inverse")
            k4.metric("Volatilidade", f"{r.get('volatilidade', 0)*100:.1f}%")

            st.divider()
            st.subheader("💰 Raio-X de Proventos")
            motor_div = MotorAnalise()
            div_info = motor_div.consultar_dividendos(t_fmt)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Último Pago", div_info.get('ultimo_valor', '-'), div_info.get('ultimo_data', '-'))
            cor_prox = "normal" if div_info.get('status') == 'AGENDA' else "off"
            d2.metric("Próximo", div_info.get('proximo_valor', '-'), div_info.get('proximo_data', '-'), delta_color=cor_prox)
            d3.metric("DY Anual (12m)", f"{r.get('dy_anual', 0):.2f}%")
            d4.metric("Status", div_info.get('status', 'NEUTRO'))
            st.divider()

            col_val, col_rob = st.columns(2)
            with col_val:
                st.subheader("📋 Valuation")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Div.)", "Graham (Patrim.)", "Gordon (Cresc.)"],
                    "Preço Justo": [f"{r.get('p_bazin', 0):.2f}", f"{r.get('p_graham', 0):.2f}", f"{r.get('p_gordon', 0):.2f}"]
                }))

            with col_rob:
                if r.get('tipo_ativo') == 'FII':
                    st.subheader("🏗️ Setup FIIs (Rigidez: P/VP < 1.02)")
                    pvp = r.get('pvp', 0)
                    lbl_pvp = "🟢 Barato" if pvp < 1.0 else "🔴 Caro (>1.02)" if pvp > 1.02 else "⚪ Justo"
                    df_setup = pd.DataFrame([
                        {"Indicador": "ANÁLISE FII", "Valor": f"{r.get('decisao_ia')}"},
                        {"Indicador": "P/VP (Limite 1.02)", "Valor": f"{pvp:.2f}x ({lbl_pvp})"},
                        {"Indicador": "Preço Teto (Bazin)", "Valor": f"{r.get('p_bazin', 0):.2f}"},
                        {"Indicador": "DY vs Selic", "Valor": f"{r.get('dy_anual',0):.1f}%"},
                    ])
                    st.dataframe(df_setup, use_container_width=True, hide_index=True)
                else:
                    st.subheader("🎯 Setup Operacional (Ações)")
                    sinal = r.get('sinal_tecnico', 'NEUTRO')
                    df_setup = pd.DataFrame([
                        {"Indicador": "SINAL TÉCNICO", "Valor": sinal},
                        {"Indicador": "Entrada Sugerida", "Valor": f"{r.get('preco_alvo_entrada', 0):.2f}"},
                        {"Indicador": "Volume Relativo", "Valor": f"{r.get('vol_relativo', 1):.1f}x"},
                        {"Indicador": "MACD", "Valor": r.get('status_macd', '-')},
                        {"Indicador": "Stop Loss", "Valor": f"{r.get('stop_loss', 0):.2f}"}
                    ])
                    st.dataframe(df_setup, use_container_width=True, hide_index=True)

            st.subheader("Gráfico Interativo")
            if ".SA" in t_fmt: symbol_tv = "BMFBOVESPA:" + t_fmt.replace(".SA", "")
            elif "-USD" in t_fmt: symbol_tv = "BINANCE:" + t_fmt.replace("-USD", "USDT")
            else: symbol_tv = "NASDAQ:" + t_fmt
            widget = f"""<div class="tradingview-widget-container"><div id="tradingview_123"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 500, "symbol": "{symbol_tv}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_123" }});</script></div>"""
            components.html(widget, height=500)
        else: 
            st.error(f"Ativo '{t_input}' não encontrado.")

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
    st.subheader("⚡ Simulador de Opções (Black & Scholes)")
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1: 
            S = st.number_input("Preço Atual (Spot)", 30.0)
            K = st.number_input("Strike (Exercício)", 32.0)
        with c2: 
            T_dias = st.number_input("Dias até Vencimento", 30)
            sig = st.number_input("Volatilidade (%)", 30.0) / 100.0
        
        # Cálculo Formatado
        if st.button("Calcular Gregas"):
            bs = BlackScholes(S, K, T_dias/365, 0.13, sig, "call")
            gregas = bs.calcular_gregas()
            
            # Painel Bonito de Gregas
            st.divider()
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Delta (Δ)", f"{gregas['Delta']:.3f}", help="Sensibilidade ao Preço")
            g2.metric("Gamma (Γ)", f"{gregas['Gamma']:.3f}", help="Aceleração do Delta")
            g3.metric("Theta (Θ)", f"{gregas['Theta']:.3f}", help="Perda de valor por dia (Time Decay)")
            g4.metric("Vega (ν)", f"{gregas['Vega']:.3f}", help="Sensibilidade à Volatilidade")