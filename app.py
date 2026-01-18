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

st.set_page_config(page_title="Hedge Fund Ricardo v62.0", layout="wide")

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
    data = yf.download(tickers, period="5y", progress=False)
    if isinstance(data, pd.DataFrame):
        return data["Adj Close"] if "Adj Close" in data else data["Close"]
    return data

def auto_classificar():
    motor = MotorAnalise()
    progress_text = "Classificando ativos via IA..."
    my_bar = st.progress(0, text=progress_text)
    total = len(st.session_state.carteira_acoes)
    for idx, row in st.session_state.carteira_acoes.iterrows():
        try:
            t = yf.Ticker(row["Ticker"])
            setor = motor.identificar_setor(t.info, row["Ticker"])
            st.session_state.carteira_acoes.at[idx, "Setor"] = setor
        except: st.session_state.carteira_acoes.at[idx, "Setor"] = "Outros"
        my_bar.progress((idx + 1) / total)
    my_bar.empty()
    st.success("Classificação Concluída!")

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

tabs = st.tabs(["🔎 Análise Completa", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# === ABA 1: ANÁLISE TÉCNICA + FUNDAMENTALISTA ===
with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            # --- BLOCO 1: RAIO-X & RISCO ---
            st.subheader("📊 Raio-X & Segurança")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r['preco']:.2f}")
            c2.metric("DY Anual (Real)", f"{r.get('dy_anual', 0):.2f}%")
            
            # Score com Trava de Segurança
            score_val = r['score_ia']
            if score_val == 0: c3.error("BLOQUEADO (0/100)")
            else: c3.metric("Score IA", f"{score_val}/100", delta=r['decisao_ia'])
            
            c4.metric("Liquidez Média", f"R$ {r.get('liq_media', 0)/1000:.0f}k")
            
            st.divider()

            # --- BLOCO 2: VALUATION & MOTIVOS ---
            k1, k2 = st.columns(2)
            with k1:
                st.markdown("**📋 Valuation**")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Teto)", "Graham (Justo)", "Gordon (Cresc)"], 
                    "Valor": [f"R$ {r.get('p_bazin',0):.2f}", f"R$ {r.get('p_graham',0):.2f}", f"R$ {r.get('p_gordon',0):.2f}"]
                }))
            with k2:
                st.markdown("**🧠 Análise IA (Riscos & Bônus)**")
                motivos = r.get('motivos', '')
                if "⚠️" in motivos or "⛔" in motivos: st.error(motivos)
                else: st.info(motivos)

            # --- BLOCO 3: SETUP TÉCNICO (RESTAURADO E COMPLETO) ---
            st.subheader("🎯 Setup Técnico & Alvos")
            col_tec1, col_tec2, col_tec3, col_tec4 = st.columns(4)
            col_tec1.metric("Sinal Técnico", r.get('sinal_tecnico', 'Neutro'))
            col_tec2.metric("Média Curta (9)", f"R$ {r.get('mme9', 0):.2f}")
            col_tec3.metric("🛑 Stop Loss", f"R$ {r.get('stop_loss', 0):.2f}")
            col_tec4.metric("✅ Stop Gain", f"R$ {r.get('stop_gain', 0):.2f}")
            
            # Tabela técnica detalhada
            st.table(pd.DataFrame([{
                "Indicador": "RSI (14)", "Valor": f"{r.get('rsi', 50):.0f}", "Status": "Sobrecomprado" if r.get('rsi',50)>70 else "Sobrevendido" if r.get('rsi',50)<30 else "Neutro"
            }, {
                "Indicador": "Volatilidade", "Valor": f"{r.get('volatilidade', 0)*100:.1f}%", "Status": "Risco Calculado"
            }]))

            # --- BLOCO 4: GRÁFICO TRADINGVIEW (RESTAURADO) ---
            st.markdown("---")
            symbol_tv = f"BMFBOVESPA:{t.replace('.SA','')}"
            components.html(f"""
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <div id="tv_chart"></div>
                <script type="text/javascript">
                new TradingView.widget({{
                  "width": "100%", "height": 500, "symbol": "{symbol_tv}",
                  "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light",
                  "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false,
                  "container_id": "tv_chart"
                }});
                </script>
            """, height=500)
            
        else: st.error("Ativo não encontrado. Tente limpar o cache.")

# === ABA 2: CARTEIRA ===
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
            else: dados.append({**row.to_dict(), "Preço": 10, "Valor_Atual": row["Qtd"]*10, "Score": 50}) 
        
        df_final = rebalancear_e_aportar(pd.DataFrame(dados), aporte, METAS)
        
        # Filtra compras válidas e seguras (Score > 0)
        df_show = df_final[(df_final["Aporte Sugerido (R$)"] > 1) & (df_final["Score"] > 0)]
        
        if df_show.empty and df_final["Aporte Sugerido (R$)"].sum() > 0:
            st.warning("Compras sugeridas foram bloqueadas por Travas de Segurança (Score 0) ou metas atingidas.")
        else:
            st.success("Plano de Compra Gerado:")
            st.dataframe(df_show[["Ticker", "Setor", "Score", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# === DEMAIS ABAS (RESTAURADAS) ===
with tabs[2]:
    st.subheader("Scanner FIIs")
    up = st.file_uploader("Upload CSV StatusInvest", type=["csv"])
    if up and scanner_fiis_csv:
        st.dataframe(scanner_fiis_csv(up))
    elif up: st.warning("Módulo scanner.py não encontrado.")

with tabs[3]:
    st.subheader("Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total RF", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

with tabs[4]:
    st.subheader("Simulação de Monte Carlo")
    if st.button("Rodar Simulação"):
        tickers = st.session_state.carteira_acoes["Ticker"].tolist()
        hist = download_historico_longo(tickers)
        if not hist.empty:
            retornos = hist.pct_change().dropna().mean(axis=1)
            motor = MotorAnalise()
            res = motor.monte_carlo_carteira(retornos, 100000, 2000, 10, 100) # 10 anos, 100 simulações
            st.line_chart(res)
        else: st.error("Sem dados para simulação.")

with tabs[5]:
    st.subheader("Fiscal (DARF)")
    if st.button("Calcular") and calcular_darf:
        st.write(calcular_darf(st.session_state.carteira_acoes))

with tabs[6]:
    st.subheader("Opções (Black-Scholes)")
    if BlackScholes:
        s = st.number_input("Preço", 30.0); k = st.number_input("Strike", 32.0)
        st.metric("Call Teórica", f"R$ {BlackScholes(s, k, 1/12, 0.12, 0.3, 'call').calcular_preco():.2f}")