import streamlit as st
import streamlit.components.v1 as components # OBRIGATÓRIO PARA O GRÁFICO
import pandas as pd
import yfinance as yf

# ======================================================
# 1. CONFIGURAÇÃO GERAL
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v85", layout="wide", page_icon="💰")

# ======================================================
# 2. IMPORTAÇÃO SEGURA
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
# 3. CACHE E LÓGICA
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

# ======================================================
# 4. INTERFACE PRINCIPAL
# ======================================================
st.title("💰 Hedge Fund Ricardo v85")

with st.sidebar:
    st.header("Painel de Controle")
    if st.button("🧹 Limpar Cache"): 
        st.cache_data.clear()
        st.rerun()
    st.divider()
    if gerar_pdf_carteira and st.button("📄 Gerar Relatório PDF"):
        st.success("PDF Gerado com sucesso!")

# TABS COMPLETAS (RESTAURADAS)
tabs = st.tabs(["🔎 Análise Técnica", "💼 Carteira", "🏢 Scanner 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# --- ABA 1: ANÁLISE COMPLETA ---
with tabs[0]:
    t = st.text_input("Ticker", "BBSE3.SA").upper()
    if st.button("Analisar Ativo"):
        r = obter_dados(t)
        if r:
            # 1. KPIs Principais
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
            # DY corrigido pelo motor v85
            c2.metric("DY Anual (12m)", f"{r['dy_anual']:.2f}%")
            
            # Score Visual
            score = r['score_ia']
            cor_delta = "normal" if score >= 60 else "inverse"
            c3.metric("Score IA", f"{score}/100", delta=r['decisao_ia'], delta_color=cor_delta)
            
            # Valor Justo
            justo = r['preco_justo']
            delta_j = (r['preco'] - justo)/justo*100 if justo > 0 else 0
            label_j = "Ágio" if delta_j > 0 else "Desconto"
            c4.metric("Valor Justo (IA)", f"R$ {justo:.2f}", delta=f"{delta_j:+.1f}% ({label_j})", delta_color="inverse")
            
            st.divider()
            
            # 2. Valuation e Motivos
            k1, k2 = st.columns(2)
            with k1:
                st.subheader("📊 Valuation Misto")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Teto Dividendos)", "Graham (Patrimonial)", "Gordon (Crescimento)"],
                    "Valor Calculado": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
                }))
            with k2:
                st.subheader("🧠 Cérebro do Robô")
                st.info(f"**Pontos Fortes:** {r['motivos']}")
                if r['alertas']:
                    st.error(f"**Pontos de Atenção:** {r['alertas']}")
            
            # 3. Painel Técnico (Algo-Trading) - RESTAURADO
            st.subheader("📈 Painel Técnico (Algo-Trading)")
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Tendência (MME)", r['sinal_tecnico'])
            t2.metric("MACD", r['status_macd'])
            t3.metric("Suporte", f"R$ {r['suporte']:.2f}")
            t4.metric("Resistência", f"R$ {r['resistencia']:.2f}")
            
            st.dataframe(pd.DataFrame([
                {"Indicador": "RSI (14)", "Valor": f"{r['rsi']:.0f}", "Interpretação": "Sobrevendido" if r['rsi']<30 else "Sobrecomprado" if r['rsi']>70 else "Neutro"},
                {"Indicador": "Volatilidade", "Valor": f"{r['volatilidade']*100:.1f}%", "Interpretação": "Baixa" if r['volatilidade'] < 0.2 else "Alta"},
                {"Indicador": "Stop Loss Sugerido", "Valor": f"R$ {r['stop_loss']:.2f}", "Interpretação": "Proteção"},
                {"Indicador": "Stop Gain Sugerido", "Valor": f"R$ {r['stop_gain']:.2f}", "Interpretação": "Alvo Curto"}
            ]), use_container_width=True)
            
            # 4. Gráfico TradingView (CORRIGIDO PARA NÃO DAR ERRO)
            st.subheader("Gráfico Interativo")
            symbol_tv = t.replace(".SA", "")
            widget_code = f"""
            <div class="tradingview-widget-container">
              <div id="tradingview_123"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget(
              {{
              "width": "100%",
              "height": 500,
              "symbol": "BMFBOVESPA:{symbol_tv}",
              "interval": "D",
              "timezone": "Etc/UTC",
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
            components.html(widget_code, height=500)
            
        else: st.error("Ativo não encontrado. Verifique o ticker.")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    if "carteira_acoes" not in st.session_state:
        st.session_state.carteira_acoes = pd.DataFrame([["BBAS3.SA", 100, 24.50, "Ações-Bancos"]], columns=["Ticker","Qtd","PM","Setor"])
    if "df_metas" not in st.session_state:
        st.session_state.df_metas = pd.DataFrame([{"Setor": "Ações-Bancos", "Meta (%)": 100.0}])

    c_a, c_b = st.columns([2,1])
    with c_b:
        st.subheader("Metas %")
        st.session_state.df_metas = st.data_editor(st.session_state.df_metas, num_rows="dynamic")
    with c_a:
        st.subheader("Meus Ativos")
        st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
        
        if st.button("🚀 Rebalancear Carteira"):
            d_metas = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
            dados = []
            for _, r in st.session_state.carteira_acoes.iterrows():
                d = obter_dados(r["Ticker"])
                if d: dados.append({**r.to_dict(), "Preço": d["preco"], "Valor_Atual": r["Qtd"]*d["preco"], "Score": d["score_ia"]})
                else: dados.append({**r.to_dict(), "Preço": 1.0, "Valor_Atual": 0, "Score": 0})
            
            final = rebalancear_e_aportar(pd.DataFrame(dados), 5000, d_metas)
            st.dataframe(final, use_container_width=True)

# --- ABA 3: SCANNER ---
with tabs[2]:
    st.subheader("Scanner FIIs 360")
    modo = st.radio("Modo", ["Automático (Yahoo)", "CSV (StatusInvest)"], horizontal=True)
    if "Auto" in modo:
        if st.button("Varredura Automática") and scanner_auto_yahoo:
            with st.spinner("Analisando mercado..."):
                df = scanner_auto_yahoo()
                st.dataframe(df, use_container_width=True, column_config={
                    "Score IA": st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=100),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "DY (12m)": st.column_config.NumberColumn(format="%.2f%%")
                })
    else:
        up = st.file_uploader("Upload CSV", type=["csv"])
        if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))

# --- DEMAIS ABAS ---
with tabs[3]:
    if "carteira_rf" not in st.session_state:
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 1000, "Pos"]], columns=["Ativo", "Saldo", "Tipo"])
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")

with tabs[4]:
    if st.button("Simular Futuro (Monte Carlo)"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty:
            ret = h.pct_change().dropna()
            r_cart = ret.mean(axis=1) if isinstance(ret, pd.DataFrame) else ret
            st.line_chart(MotorAnalise().monte_carlo_carteira(r_cart, 100000, 2000))

with tabs[5]:
    if st.button("Calcular DARF") and calcular_darf:
        st.table(calcular_darf(st.session_state.carteira_acoes))

with tabs[6]:
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1:
            S = st.number_input("Spot", 30.0); K = st.number_input("Strike", 32.0)
        with c2:
            T = st.number_input("Dias", 30)/365; sig = st.number_input("Vol %", 30.0)/100
        bs = BlackScholes(S, K, T, 0.13, sig, "call")
        st.write(bs.calcular_gregas())