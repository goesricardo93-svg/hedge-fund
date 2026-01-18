import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. IMPORTAÇÃO SEGURA ---
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    try: from scanner import scanner_fiis_csv
    except: scanner_fiis_csv = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from options import BlackScholes
    except: BlackScholes = None
except ImportError as e:
    st.error(f"Erro crítico: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo v64.1", layout="wide")

# --- 2. ESTRATÉGIA ---
METAS = {
    "Renda Fixa": 30.0, "Exterior": 20.0,
    "Ações-Bancos": 7.5, "Ações-Elétricas": 7.5, "Ações-Seguridade": 6.0, "Ações-Commodities": 6.0, "Ações-Outros": 3.0,
    "FIIs-Papel": 10.0, "FIIs-Tijolo": 6.0, "FIIs-Outros": 4.0
}

# --- 3. CACHE E MOTOR ---
@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker); hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_historico_longo(tickers):
    # Função segura para baixar dados de múltiplos tickers para Monte Carlo
    try:
        data = yf.download(tickers, period="5y", progress=False)
        # Ajuste para diferentes formatos de retorno do yfinance
        if isinstance(data, pd.DataFrame):
            if "Adj Close" in data: return data["Adj Close"]
            if "Close" in data: return data["Close"]
        return data
    except: return pd.DataFrame()

def auto_classificar():
    motor = MotorAnalise()
    prog = st.progress(0, text="Classificando...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        try:
            t = yf.Ticker(row["Ticker"])
            st.session_state.carteira_acoes.at[i, "Setor"] = motor.identificar_setor(t.info, row["Ticker"])
        except: st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    prog.empty()
    st.success("Concluído!")

# --- 4. INICIALIZAÇÃO ---
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Aguardando..."],
        ["CPSH11.SA", 50, 10.10, "Aguardando..."],
        ["XPML11.SA", 10, 115.00, "Aguardando..."],
        ["IVVB11.SA", 5, 280.00, "Aguardando..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# --- 5. INTERFACE ---
st.title("💰 Hedge Fund Ricardo")
st.sidebar.button("🧹 Limpar Cache", on_click=lambda: st.cache_data.clear())

tabs = st.tabs(["🔎 Análise Algo-Trading", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# === ABA 1: ANÁLISE COMPLETA (TUDO INCLUSO) ===
with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            # 1. HEADER: Preço, DY e Risco
            st.subheader("📊 Raio-X & Segurança")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("DY Anual (Real)", f"{r.get('dy_anual', 0):.2f}%")
            if r['score_ia'] == 0: c3.error("BLOQUEADO (0/100)")
            else: c3.metric("Score IA", f"{r['score_ia']}/100", delta=r['decisao_ia'])
            c4.metric("Liquidez", f"R$ {r.get('liq_media', 0)/1000:.0f}k")
            
            st.divider()

            # 2. VALUATION & ALERTAS
            k1, k2 = st.columns(2)
            k1.markdown("**📋 Valuation**")
            k1.table(pd.DataFrame({"Modelo": ["Bazin (Teto)", "Graham (Patrim)", "Gordon (Cresc)"], "Valor": [f"R$ {r.get('p_bazin',0):.2f}", f"R$ {r.get('p_graham',0):.2f}", f"R$ {r.get('p_gordon',0):.2f}"]}))
            
            k2.markdown("**🧠 Inteligência**")
            motivos = r.get('motivos', '')
            if "⚠️" in motivos or "⛔" in motivos: k2.error(motivos)
            else: k2.info(motivos)

            # 3. PAINEL ALGO-TRADING (RESTAURADO)
            st.subheader("📈 Painel Algo-Trading (Técnico)")
            
            # Métricas em Colunas
            tec1, tec2, tec3, tec4 = st.columns(4)
            tec1.metric("Tendência (9x21)", r.get('sinal_tecnico', '-'))
            tec2.metric("MACD Status", "COMPRA" if r['macd'] > r['macd_signal'] else "VENDA", delta=f"{r['macd']:.2f}")
            tec3.metric("🛑 Stop Loss", f"R$ {r['stop_loss']:.2f}")
            tec4.metric("✅ Stop Gain", f"R$ {r['stop_gain']:.2f}")

            # Tabela Técnica Detalhada
            df_algo = pd.DataFrame([
                {"Indicador": "RSI (14)", "Valor": f"{r['rsi']:.0f}", "Interpretação": "Sobrevendido (<30)" if r['rsi']<30 else "Sobrecomprado (>70)" if r['rsi']>70 else "Neutro"},
                {"Indicador": "Volatilidade Anual", "Valor": f"{r['volatilidade']*100:.1f}%", "Interpretação": "Risco de Mercado"},
                {"Indicador": "Volume Relativo", "Valor": f"{r['vol_relativo']:.2f}x", "Interpretação": "Volume acima da média" if r['vol_relativo'] > 1 else "Volume baixo"},
                {"Indicador": "Suporte (60d)", "Valor": f"R$ {r['suporte']:.2f}", "Interpretação": "Piso do preço"},
                {"Indicador": "Resistência (60d)", "Valor": f"R$ {r['resistencia']:.2f}", "Interpretação": "Teto do preço"}
            ])
            st.dataframe(df_algo, use_container_width=True)

            # 4. GRÁFICO TRADINGVIEW
            st.markdown("---")
            tv_sym = f"BMFBOVESPA:{t.replace('.SA','')}"
            components.html(f"""
            <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
            <div id="tv_chart"></div>
            <script type="text/javascript">
            new TradingView.widget({{"width": "100%", "height": 500, "symbol": "{tv_sym}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "container_id": "tv_chart"}});
            </script>
            """, height=500)
        else: st.error("Ativo não encontrado. Limpe o cache.")

# === ABA 2: CARTEIRA ===
with tabs[1]:
    st.subheader("Gestão de Carteira")
    if st.button("🤖 1. Classificar (IA)"): auto_classificar(); st.rerun()
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True, column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=list(METAS.keys()))})
    st.session_state.carteira_acoes = df_ed
    aporte = st.number_input("Aporte (R$)", value=5000.0)
    if st.button("🚀 2. Rebalancear"):
        dados = []
        for _, row in df_ed.iterrows():
            d = obter_dados(row["Ticker"])
            if d: dados.append({**row.to_dict(), "Preço": d["preco"], "Valor_Atual": row["Qtd"]*d["preco"], "Score": d["score_ia"]})
            else: dados.append({**row.to_dict(), "Preço": 10, "Valor_Atual": row["Qtd"]*10, "Score": 50})
        
        df_final = rebalancear_e_aportar(pd.DataFrame(dados), aporte, METAS)
        df_show = df_final[(df_final["Aporte Sugerido (R$)"] > 1) & (df_final["Score"] > 0)]
        
        if df_show.empty and df_final["Aporte Sugerido (R$)"].sum() > 0: st.warning("Compras sugeridas bloqueadas por Risco (Score 0).")
        else:
            st.success("Plano de Compra:")
            st.dataframe(df_show[["Ticker", "Setor", "Score", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# === ABA 3: SCANNER ===
with tabs[2]:
    st.subheader("Scanner FIIs")
    up = st.file_uploader("Upload CSV", type=["csv"])
    if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))

# === ABA 4: RENDA FIXA ===
with tabs[3]:
    st.subheader("Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total RF", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

# === ABA 5: FUTURO (MONTE CARLO) - CORRIGIDO AQUI ===
with tabs[4]:
    st.subheader("Monte Carlo")
    if st.button("Simular"):
        # AQUI ESTAVA O ERRO ANTES, AGORA ESTÁ CORRIGIDO:
        tks = st.session_state.carteira_acoes["Ticker"].tolist()
        
        h = download_historico_longo(tks)
        if not h.empty:
            # Tratamento para garantir que pct_change funcione
            r = h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna()
            # Chama o motor se a serie não estiver vazia
            if len(r) > 0:
                st.line_chart(MotorAnalise().monte_carlo_carteira(r, 100000, 2000))
            else:
                st.warning("Dados insuficientes para simulação.")
        else: st.error("Erro ao baixar histórico para simulação.")

# === ABA 6: FISCAL ===
with tabs[5]:
    st.subheader("Fiscal")
    if st.button("Calcular") and calcular_darf: st.write(calcular_darf(st.session_state.carteira_acoes))

# === ABA 7: OPÇÕES ===
with tabs[6]:
    st.subheader("Opções")
    if BlackScholes:
        s = st.number_input("Spot", 30.0); k = st.number_input("Strike", 32.0)
        st.metric("Call", f"R$ {BlackScholes(s, k, 1/12, 0.12, 0.3, 'call').calcular_preco():.2f}")