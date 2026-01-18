import streamlit as st
import streamlit.components.v1 as components # <--- OBRIGATÓRIO PRO GRÁFICO
import pandas as pd
import yfinance as yf

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Hedge Fund Ricardo v84", layout="wide")

try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    try: from scanner import scanner_auto_yahoo, scanner_fiis_csv
    except: scanner_auto_yahoo = None
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
except:
    st.error("Erro nos arquivos auxiliares. Verifique motor.py")
    st.stop()

# CACHE
@st.cache_data(ttl=300)
def get_data(t): 
    return MotorAnalise().analisar(yf.Ticker(t).history(period="2y"), yf.Ticker(t).info, t)

@st.cache_data(ttl=86400)
def get_long_data(tickers):
    try: return yf.download(tickers, period="5y", progress=False)["Adj Close"]
    except: return pd.DataFrame()

# ESTADO
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([["BBAS3.SA", 100, 25.0, "Ações-Bancos"]], columns=["Ticker","Qtd","PM","Setor"])
if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([{"Setor": "Ações-Bancos", "Meta (%)": 100.0}])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro", 1000, "Pos"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# UI
st.title("💰 Hedge Fund Ricardo v84")

with st.sidebar:
    if st.button("Limpar Cache"): st.cache_data.clear(); st.rerun()
    if gerar_pdf_carteira and st.button("Relatório PDF"): st.success("Gerado!")

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 Scanner", "⚡ Opções", "🦁 Fiscal", "🔮 Futuro", "🛡️ RF"])

# ABA 1: ANÁLISE (DY Corrigido + Gráfico)
with tabs[0]:
    t = st.text_input("Ticker", "BBSE3.SA").upper()
    if st.button("Analisar"):
        r = get_data(t)
        if r:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("DY Anual", f"{r['dy_anual']:.2f}%") # AGORA VAI CERTO
            c3.metric("Score", f"{r['score_ia']}", delta=r['decisao_ia'])
            
            justo = r['preco_justo']
            delta_j = (r['preco'] - justo)/justo*100 if justo > 0 else 0
            c4.metric("Valor Justo", f"R$ {justo:.2f}", delta=f"{delta_j:+.1f}%", delta_color="inverse")
            
            st.divider()
            k1, k2 = st.columns(2)
            k1.table(pd.DataFrame({"Bazin": [r['p_bazin']], "Graham": [r['p_graham']]}))
            k2.info(f"Motivos: {r['motivos']}")
            
            # --- GRÁFICO (WIDGET CORRIGIDO) ---
            st.subheader("Gráfico Diário")
            symbol_tv = t.replace(".SA", "")
            # O widget HTML precisa ser uma string única bem formatada
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
            
        else: st.error("Não encontrado ou erro na API.")

with tabs[1]:
    st.subheader("Carteira")
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic")
    if st.button("Rebalancear"):
        meta = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        dados = []
        for _, row in st.session_state.carteira_acoes.iterrows():
            d = get_data(row["Ticker"])
            p = d['preco'] if d else 1.0
            s = d['score_ia'] if d else 50
            dados.append({**row, "Preço": p, "Score": s, "Valor_Atual": row["Qtd"]*p})
        st.dataframe(rebalancear_e_aportar(pd.DataFrame(dados), 5000, meta))

with tabs[2]:
    st.subheader("Scanner")
    if scanner_auto_yahoo and st.button("Rodar Scanner"):
        st.dataframe(scanner_auto_yahoo())

with tabs[3]:
    if BlackScholes:
        st.write("Black-Scholes")
        st.write(BlackScholes(30,32,0.1,0.13,0.3,"call").calcular_gregas())

with tabs[4]:
    if calcular_darf and st.button("DARF"):
        st.table(calcular_darf(st.session_state.carteira_acoes))

with tabs[5]:
    if st.button("Monte Carlo"):
        h = get_long_data(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: st.line_chart(h/h.iloc[0]*100)

with tabs[6]:
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf)