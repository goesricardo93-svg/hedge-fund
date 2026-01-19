import streamlit as st
import streamlit.components.v1 as components # Essencial para o gráfico
import pandas as pd
import yfinance as yf

# ======================================================
# 1. CONFIGURAÇÃO (PRIMEIRA LINHA)
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v87", layout="wide", page_icon="💰")

# ======================================================
# 2. IMPORTAÇÃO E TRATAMENTO DE ERROS
# ======================================================
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    # Módulos opcionais
    try: from scanner import scanner_fiis_csv, scanner_auto_yahoo
    except: scanner_fiis_csv = None; scanner_auto_yahoo = None
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
except Exception as e:
    st.error(f"Erro crítico na importação: {e}")
    st.stop()

# ======================================================
# 3. INICIALIZAÇÃO DO BANCO DE DADOS (CRÍTICO)
# ======================================================
# Define as metas completas e a carteira ANTES de desenhar a tela
if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([
        {"Setor": "Renda Fixa", "Meta (%)": 30.0},
        {"Setor": "Exterior", "Meta (%)": 20.0},
        {"Setor": "Ações-Bancos", "Meta (%)": 7.5},
        {"Setor": "Ações-Elétricas", "Meta (%)": 7.5},
        {"Setor": "Ações-Seguridade", "Meta (%)": 6.0},
        {"Setor": "Ações-Commodities", "Meta (%)": 6.0},
        {"Setor": "Ações-Outros", "Meta (%)": 3.0},
        {"Setor": "FIIs-Papel", "Meta (%)": 10.0},
        {"Setor": "FIIs-Tijolo", "Meta (%)": 6.0},
        {"Setor": "FIIs-Outros", "Meta (%)": 4.0}
    ])

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Ações-Bancos"],
        ["XPML11.SA", 10, 115.00, "FIIs-Tijolo"],
        ["IVVB11.SA", 5, 280.00, "Exterior"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000.0, "Pós-Fixado"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

# ======================================================
# 4. FUNÇÕES E CACHE
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
        try: 
            st.session_state.carteira_acoes.at[i, "Setor"] = motor.identificar_setor(yf.Ticker(row["Ticker"]).info, row["Ticker"])
        except: 
            st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    prog.empty()
    st.success("Setores atualizados!")

# ======================================================
# 5. INTERFACE (FRONT-END)
# ======================================================
st.title("💰 Hedge Fund Ricardo v87")

with st.sidebar:
    st.header("Controles")
    if st.button("🧹 Limpar Cache / Reset"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    if gerar_pdf_carteira and st.button("📄 Gerar Relatório PDF"):
        # Prepara dados
        df_view = st.session_state.carteira_acoes.copy()
        dados_pdf = []
        for _, r in df_view.iterrows():
            d = obter_dados(r["Ticker"])
            p = d["preco"] if d else 0
            dados_pdf.append({**r.to_dict(), "Preço Atual": p, "Valor_Atual": r["Qtd"]*p})
        
        df_pdf = pd.DataFrame(dados_pdf)
        total_patrimonio = st.session_state.carteira_rf["Saldo Atual"].sum() + df_pdf["Valor_Atual"].sum()
        dict_metas = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        
        try:
            st.download_button("📥 Baixar PDF", gerar_pdf_carteira(df_pdf, st.session_state.carteira_rf, total_patrimonio, dict_metas), "Relatorio.pdf", "application/pdf")
        except: st.error("Erro ao gerar PDF.")

tabs = st.tabs(["🔎 Análise Técnica", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# --- ABA 1: ANÁLISE TÉCNICA E FUNDAMENTAL ---
with tabs[0]:
    t = st.text_input("Ticker para Análise", "BBSE3.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            # LINHA 1: KPIs
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("DY (12m Real)", f"{r['dy_anual']:.2f}%")
            
            # Score IA
            cor_score = "normal" if r['score_ia'] >= 60 else "inverse"
            c3.metric("Score IA", f"{r['score_ia']}/100", delta=r['decisao_ia'], delta_color=cor_score)
            
            # Valor Justo
            justo = r['preco_justo']
            delta_j = (r['preco'] - justo)/justo*100 if justo > 0 else 0
            lbl_j = "Ágio" if delta_j > 0 else "Desconto"
            c4.metric("Valor Justo", f"R$ {justo:.2f}", delta=f"{delta_j:+.1f}% ({lbl_j})", delta_color="inverse")
            
            st.divider()
            
            # LINHA 2: VALUATION E TÉCNICA
            col_val, col_tec = st.columns(2)
            
            with col_val:
                st.subheader("📊 Valuation Misto")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Teto)", "Graham (Patrimonial)", "Gordon (Crescimento)"],
                    "Valor Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
                }))
                st.info(f"**Motivos:** {r['motivos']}")
                if r['alertas']: st.error(f"**Alertas:** {r['alertas']}")

            with col_tec:
                st.subheader("📈 Algo-Trading")
                m1, m2 = st.columns(2)
                m1.metric("Tendência", r['sinal_tecnico'])
                m2.metric("MACD", r['status_macd'])
                
                st.dataframe(pd.DataFrame([
                    {"Ind": "RSI (14)", "Valor": f"{r['rsi']:.0f}", "Status": "Venda" if r['rsi']>70 else "Compra" if r['rsi']<30 else "Neutro"},
                    {"Ind": "Volatilidade", "Valor": f"{r['volatilidade']*100:.1f}%", "Status": "Risco Alto" if r['volatilidade']>0.3 else "Ok"},
                    {"Ind": "Suporte", "Valor": f"R$ {r['suporte']:.2f}", "Status": "Piso"},
                    {"Ind": "Resistência", "Valor": f"R$ {r['resistencia']:.2f}", "Status": "Teto"}
                ]), use_container_width=True)

            # LINHA 3: GRÁFICO (WIDGET HTML)
            st.subheader("Gráfico Interativo")
            sym = t.replace(".SA", "")
            widget = f"""
            <div class="tradingview-widget-container">
              <div id="tradingview_123"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget(
              {{
              "width": "100%",
              "height": 500,
              "symbol": "BMFBOVESPA:{sym}",
              "interval": "D",
              "timezone": "America/Sao_Paulo",
              "theme": "light",
              "style": "1",
              "locale": "br",
              "toolbar_bg": "#f1f3f6",
              "enable_publishing": false,
              "allow_symbol_change": true,
              "container_id": "tradingview_123"
              }});
              </script>
            </div>
            """
            components.html(widget, height=500)
            
        else: st.error("Ativo não encontrado ou dados insuficientes.")

# --- ABA 2: CARTEIRA COMPLETA ---
with tabs[1]:
    c_metas, c_ativos = st.columns([1, 2])
    
    with c_metas:
        st.subheader("🎯 Metas de Alocação")
        st.session_state.df_metas = st.data_editor(st.session_state.df_metas, num_rows="dynamic")
        total = st.session_state.df_metas["Meta (%)"].sum()
        if abs(total - 100) > 0.1: st.error(f"Total: {total}%. Ajuste para 100%.")
        else: st.success(f"Total: {total}% (Ok)")

    with c_ativos:
        st.subheader("💼 Meus Ativos")
        if st.button("Classificar Setores (Auto)"): auto_classificar()
        
        st.session_state.carteira_acoes = st.data_editor(
            st.session_state.carteira_acoes,
            num_rows="dynamic",
            column_config={
                "Setor": st.column_config.SelectboxColumn("Setor", options=st.session_state.df_metas["Setor"].tolist())
            },
            use_container_width=True
        )
        
        aporte = st.number_input("Aporte (R$)", 5000.0)
        if st.button("Calcular Rebalanceamento"):
            metas_dict = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
            dados_calc = []
            
            # Barra de progresso para não parecer travado
            bar = st.progress(0, "Consultando preços...")
            for idx, row in st.session_state.carteira_acoes.iterrows():
                d = obter_dados(row["Ticker"])
                preco = d["preco"] if d else 0
                score = d["score_ia"] if d else 0
                dados_calc.append({
                    **row.to_dict(),
                    "Preço": preco,
                    "Valor_Atual": row["Qtd"] * preco,
                    "Score": score
                })
                bar.progress((idx+1)/len(st.session_state.carteira_acoes))
            bar.empty()
            
            res = rebalancear_e_aportar(pd.DataFrame(dados_calc), aporte, metas_dict)
            st.dataframe(res[res["Aporte Sugerido (R$)"] > 0.01].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# --- ABA 3: SCANNER ---
with tabs[2]:
    st.subheader("Scanner de Oportunidades")
    modo = st.radio("Fonte", ["Automático (Yahoo)", "CSV StatusInvest"], horizontal=True)
    if "Auto" in modo:
        if st.button("Iniciar Varredura") and scanner_auto_yahoo:
            with st.spinner("Analisando FIIs..."):
                df = scanner_auto_yahoo()
                st.dataframe(df, use_container_width=True, column_config={
                    "Score IA": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "DY (12m)": st.column_config.NumberColumn(format="%.2f%%")
                })
    else:
        up = st.file_uploader("CSV", type=["csv"])
        if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))

# --- DEMAIS ABAS ---
with tabs[3]:
    st.subheader("Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total RF", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

with tabs[4]:
    st.subheader("Monte Carlo (10 Anos)")
    if st.button("Simular"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty:
            ret = h.pct_change().dropna()
            media = ret.mean(axis=1) if isinstance(ret, pd.DataFrame) else ret
            st.line_chart(MotorAnalise().monte_carlo_carteira(media, 100000, 2000))

with tabs[5]:
    st.subheader("Fiscal")
    if st.button("Calc. DARF") and calcular_darf:
        st.table(calcular_darf(st.session_state.carteira_acoes))

with tabs[6]:
    st.subheader("Opções")
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1: S=st.number_input("Ativo", 30.0); K=st.number_input("Strike", 32.0); tipo=st.selectbox("Tipo", ["call","put"])
        with c2: T=st.number_input("Dias", 30)/365; sig=st.number_input("Vol %", 30.0)/100
        bs = BlackScholes(S,K,T,0.13,sig,tipo)
        st.write(bs.calcular_gregas())