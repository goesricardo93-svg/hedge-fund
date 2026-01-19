import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import yfinance as yf

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v100", layout="wide", page_icon="💰")

# ======================================================
# 2. AUTO-RESET (LIMPEZA PARA A VERSÃO 100)
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v100":
    st.session_state.versao_sistema = "v100"
    st.cache_data.clear()
    # Mantém a carteira salva, só limpa o cache técnico
    st.toast("Versão 100 carregada! Quadro de Dividendos Restaurado.", icon="💎")

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
# 5. FUNÇÕES INTELIGENTES (GLOBAL + DIVIDENDOS)
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
    prog.empty(); st.success("Classificação Concluída!")

# ======================================================
# 6. UI
# ======================================================
st.title("💰 Hedge Fund Ricardo v100")

with st.sidebar:
    st.header("Backup Seguro")
    csv = st.session_state.carteira_acoes.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Salvar Backup", csv, "backup_v100.csv", "text/csv")
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

# ABA 1: ANÁLISE GLOBAL (COM QUADRO DE DIVIDENDOS RESTAURADO)
with tabs[0]:
    c_input, c_btn = st.columns([3, 1])
    with c_input:
        t_input = st.text_input("Ticker", "BBSE3", label_visibility="collapsed", placeholder="Ex: BBSE3, AAPL, BTC...")
    with c_btn:
        btn_analisar = st.button("Analisar", use_container_width=True)

    if btn_analisar:
        t_fmt = formatar_ticker_global(t_input)
        r = obter_dados(t_input)
        
        if r:
            # --- CABEÇALHO ---
            c_score, c_veredito = st.columns([1, 3])
            cor = "normal" if r.get('score_ia', 0) >= 60 else "inverse"
            c_score.metric("Score IA", f"{r.get('score_ia', 0)}/100")
            c_veredito.info(f"**Veredito:** {r.get('decisao_ia', '-')} | **Motivos:** {r.get('motivos', '-')}")
            if r.get('alertas'): c_veredito.error(f"**Atenção:** {r['alertas']}")
            
            st.divider()

            # --- LINHA DE MÉTRICAS ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Preço Atual", f"{r.get('preco', 0):.2f}")
            k2.metric("Teto (Stop Gain)", f"{r.get('stop_gain', 0):.2f}")
            
            rsi_val = r.get('rsi', 50)
            k3.metric("RSI (14)", f"{rsi_val:.0f}", delta="Sobrecomprado" if rsi_val>70 else "Sobrevendido" if rsi_val<30 else "Neutro", delta_color="inverse")
            k4.metric("Volatilidade", f"{r.get('volatilidade', 0)*100:.1f}%")

            # --- QUADRO DE PROVENTOS (RESTAURADO DA V49) ---
            st.divider()
            st.subheader("💰 Raio-X de Proventos (Dividendos)")
            
            # Chama a função de dividendos do Motor (que já existe no v97)
            motor_div = MotorAnalise()
            div_info = motor_div.consultar_dividendos(t_fmt)
            
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Último Pago", div_info.get('ultimo_valor', '-'), div_info.get('ultimo_data', '-'))
            
            # Se tiver próximo agendado, destaca em verde
            cor_prox = "normal" if div_info.get('status') == 'AGENDA' else "off"
            d2.metric("Próximo (Prev.)", div_info.get('proximo_valor', '-'), div_info.get('proximo_data', '-'), delta_color=cor_prox)
            
            d3.metric("DY Anual (12m)", f"{r.get('dy_anual', 0):.2f}%")
            d4.metric("Status", div_info.get('status', 'NEUTRO'))
            
            st.divider()

            # --- FUNDAMENTOS ---
            col_val, col_fund = st.columns(2)
            with col_val:
                st.subheader("📋 Valuation")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Div.)", "Graham (Patrim.)", "Gordon (Cresc.)"],
                    "Preço Justo": [f"{r.get('p_bazin', 0):.2f}", f"{r.get('p_graham', 0):.2f}", f"{r.get('p_gordon', 0):.2f}"]
                }))
                
            with col_fund:
                st.subheader("📊 Segurança & Solvência")
                st.dataframe(pd.DataFrame([
                    {"Indicador": "Liquidez Corrente (>1)", "Valor": f"{r.get('liq_corrente', 0):.2f}"},
                    {"Indicador": "Cresc. Receita", "Valor": f"{r.get('cresc_receita', 0)*100:.1f}%"},
                    {"Indicador": "Dívida/EBITDA (<3)", "Valor": f"{r.get('divida_ebitda', 0):.2f}x"},
                    {"Indicador": "ROE (Rentabilidade)", "Valor": f"{r.get('roe', 0)*100:.1f}%"},
                    {"Indicador": "Margem Líquida", "Valor": f"{r.get('margem_liq', 0)*100:.1f}%"}
                ]), use_container_width=True, hide_index=True)

            # --- SETUP ROBÔ ---
            st.subheader("🎯 Setup Operacional (Robô)")
            sinal = r.get('sinal_tecnico', 'NEUTRO')
            cor_sinal = "🟢" if "COMPRA" in sinal or "ALTA" in sinal else "🔴" if "VENDA" in sinal or "BAIXA" in sinal else "⚪"
            vol = f"{r.get('vol_relativo', 1):.1f}x Média"
            macd_delta = r.get('macd', 0) - r.get('macd_signal', 0)
            macd_s = "↗️ Subindo" if macd_delta > 0 else "↘️ Caindo"
            
            df_setup = pd.DataFrame([
                {"Indicador": "SINAL TÉCNICO", "Valor": f"{cor_sinal} {sinal}"},
                {"Indicador": "Preço de Entrada (Sugerido)", "Valor": f"{r.get('preco_alvo_entrada', 0):.2f}" if r.get('preco_alvo_entrada', 0)>0 else "-"},
                {"Indicador": "Volume Relativo", "Valor": vol},
                {"Indicador": "MACD", "Valor": macd_s},
                {"Indicador": "Média Curta (9)", "Valor": f"{r.get('mme9', 0):.2f}"},
                {"Indicador": "Média Longa (21)", "Valor": f"{r.get('mme21', 0):.2f}"},
                {"Indicador": "Stop Loss (Segurança)", "Valor": f"{r.get('stop_loss', 0):.2f}"}
            ])
            st.dataframe(df_setup, use_container_width=True, hide_index=True)

            # GRÁFICO GLOBAL
            st.subheader("Gráfico Interativo")
            if ".SA" in t_fmt: symbol_tv = "BMFBOVESPA:" + t_fmt.replace(".SA", "")
            elif "-USD" in t_fmt: symbol_tv = "BINANCE:" + t_fmt.replace("-USD", "USDT")
            else: symbol_tv = "NASDAQ:" + t_fmt

            widget = f"""<div class="tradingview-widget-container"><div id="tradingview_123"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 500, "symbol": "{symbol_tv}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_123" }});</script></div>"""
            components.html(widget, height=500)
        else: 
            st.error(f"Ativo '{t_input}' não encontrado (Tentativa: {t_fmt}).")

# ABA 2: CARTEIRA GLOBAL
with tabs[1]:
    c1, c2 = st.columns([1, 2])
    c1.subheader("Metas %")
    st.session_state.df_metas = c1.data_editor(st.session_state.df_metas, num_rows="dynamic")
    
    c2.subheader(f"Meus Ativos ({len(st.session_state.carteira_acoes)})")
    if c2.button("Classificar (Global)"): auto_classificar()
    
    st.session_state.carteira_acoes = c2.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=st.session_state.df_metas["Setor"].tolist())}, use_container_width=True)
    
    aporte = c2.number_input("Aporte", 5000.0)
    if c2.button("Calcular Rebalanceamento"):
        m = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        dados = []
        bar = st.progress(0, "Calculando (Global)...")
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"])
            p = d.get("preco", 0) if d else 0
            s = d.get("score_ia", 0) if d else 0
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