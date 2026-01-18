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

st.set_page_config(page_title="Hedge Fund Ricardo v67.0", layout="wide")

# --- 2. CACHE E MOTOR ---
@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker); hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_historico_longo(tickers):
    try:
        data = yf.download(tickers, period="5y", progress=False)
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

# --- 3. ESTADO INICIAL ---
if "df_metas" not in st.session_state:
    dados_metas = [
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
    ]
    st.session_state.df_metas = pd.DataFrame(dados_metas)

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Aguardando..."],
        ["CPSH11.SA", 50, 10.10, "Aguardando..."],
        ["XPML11.SA", 10, 115.00, "Aguardando..."],
        ["IVVB11.SA", 5, 280.00, "Aguardando..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# --- 4. INTERFACE ---
st.title("💰 Hedge Fund Ricardo")
st.sidebar.button("🧹 Limpar Cache", on_click=lambda: st.cache_data.clear())

tabs = st.tabs(["🔎 Análise Algo-Trading", "💼 Carteira & Metas", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# === ABA 1: ANÁLISE ===
with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            st.subheader("📊 Raio-X & Segurança")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {r.get('preco', 0):.2f}")
            c2.metric("DY Anual (Real)", f"{r.get('dy_anual', 0):.2f}%")
            
            score = r.get('score_ia', 0)
            if score == 0: c3.error("BLOQUEADO (0/100)")
            else: c3.metric("Score IA", f"{score}/100", delta=r.get('decisao_ia', '-'))
            
            # AQUI ESTÁ A CORREÇÃO (ROBÔ DE PREÇO JUSTO)
            justo = r.get('preco_justo', 0)
            delta_justo = (r['preco'] - justo) / justo * 100 if justo > 0 else 0
            label_delta = f"{delta_justo:+.1f}% (Ágio)" if delta_justo > 0 else f"{delta_justo:+.1f}% (Desc)"
            cor_delta = "inverse" if delta_justo > 0 else "normal" # Vermelho se ágio, Verde se desconto
            
            c4.metric("💎 Valor Justo (IA)", f"R$ {justo:.2f}", delta=label_delta, delta_color=cor_delta, help="Média ponderada de Graham e Bazin.")
            
            st.divider()

            k1, k2 = st.columns(2)
            k1.markdown("**📋 Valuation**")
            k1.table(pd.DataFrame({
                "Modelo": ["Bazin (Teto)", "Graham (Patrim)", "Gordon (Cresc)"], 
                "Valor": [f"R$ {r.get('p_bazin',0):.2f}", f"R$ {r.get('p_graham',0):.2f}", f"R$ {r.get('p_gordon',0):.2f}"]
            }))
            
            k2.markdown("**🧠 Inteligência Artificial**")
            motivos = r.get('motivos', '')
            if "⚠️" in motivos or "⛔" in motivos: k2.error(motivos)
            else: k2.info(motivos)

            st.subheader("📈 Painel Algo-Trading")
            tec1, tec2, tec3, tec4 = st.columns(4)
            tec1.metric("Tendência", r.get('sinal_tecnico', '-'))
            
            macd_val = r.get('macd', 0)
            macd_sig = r.get('macd_signal', 0)
            status_macd = "COMPRA" if macd_val > macd_sig else "VENDA"
            tec2.metric("MACD Status", status_macd, delta=f"{macd_val:.2f}")
            
            tec3.metric("🛑 Stop Loss", f"R$ {r.get('stop_loss', 0):.2f}")
            tec4.metric("✅ Stop Gain", f"R$ {r.get('stop_gain', 0):.2f}")

            rsi_val = r.get('rsi', 50)
            vol_val = r.get('volatilidade', 0)
            vol_rel = r.get('vol_relativo', 1.0)
            
            df_algo = pd.DataFrame([
                {"Indicador": "RSI (14)", "Valor": f"{rsi_val:.0f}", "Interpretação": "Sobrevendido (<30)" if rsi_val<30 else "Sobrecomprado (>70)" if rsi_val>70 else "Neutro"},
                {"Indicador": "Volatilidade", "Valor": f"{vol_val*100:.1f}%", "Interpretação": "Risco de Mercado"},
                {"Indicador": "Volume Relativo", "Valor": f"{vol_rel:.2f}x", "Interpretação": "Alto (>1.0)" if vol_rel > 1 else "Baixo"},
                {"Indicador": "Suporte", "Valor": f"R$ {r.get('suporte', 0):.2f}", "Interpretação": "Piso Forte"},
                {"Indicador": "Resistência", "Valor": f"R$ {r.get('resistencia', 0):.2f}", "Interpretação": "Teto Forte"}
            ])
            st.dataframe(df_algo, use_container_width=True)

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

# === ABA 2: CARTEIRA & METAS ===
with tabs[1]:
    c_left, c_right = st.columns([2, 1])
    
    with c_right:
        st.subheader("🎯 Configuração da Estratégia")
        st.info("Edite as porcentagens abaixo.")
        df_metas_edit = st.data_editor(st.session_state.df_metas, column_config={"Meta (%)": st.column_config.NumberColumn("Alvo %", min_value=0, max_value=100, format="%.1f%%")}, num_rows="dynamic", use_container_width=True)
        st.session_state.df_metas = df_metas_edit
        
        soma = df_metas_edit["Meta (%)"].sum()
        if abs(soma - 100.0) > 0.1: st.warning(f"⚠️ Soma: {soma:.1f}%")
        else: st.success("✅ Balanceado (100%)")

    with c_left:
        st.subheader("💼 Gestão de Ativos")
        if st.button("🤖 1. Classificar (IA)"): auto_classificar(); st.rerun()
        
        lista_setores = df_metas_edit["Setor"].tolist()
        df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True, column_config={
            "Setor": st.column_config.SelectboxColumn("Setor", options=lista_setores, required=True),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=0, format="%d"),
            "PM": st.column_config.NumberColumn("Preço Médio", format="R$ %.2f")
        })
        st.session_state.carteira_acoes = df_ed
        
        st.divider()
        aporte = st.number_input("💰 Aporte Disponível (R$)", value=5000.0)
        
        if st.button("🚀 2. Executar Rebalanceamento"):
            if abs(soma - 100.0) > 0.1: st.error("Ajuste as metas para 100%.")
            else:
                DICT_METAS = dict(zip(df_metas_edit["Setor"], df_metas_edit["Meta (%)"]))
                dados = []
                for _, row in df_ed.iterrows():
                    d = obter_dados(row["Ticker"])
                    if d: dados.append({**row.to_dict(), "Preço": d["preco"], "Valor_Atual": row["Qtd"]*d["preco"], "Score": d["score_ia"]})
                    else: dados.append({**row.to_dict(), "Preço": 10, "Valor_Atual": row["Qtd"]*10, "Score": 50})
                
                df_final = rebalancear_e_aportar(pd.DataFrame(dados), aporte, DICT_METAS)
                df_show = df_final[(df_final["Aporte Sugerido (R$)"] > 1) & (df_final["Score"] > 0)]
                
                if df_show.empty and df_final["Aporte Sugerido (R$)"].sum() > 0: st.warning("Compras sugeridas bloqueadas por Risco (Score 0).")
                else:
                    st.success("✅ Plano de Compra:")
                    st.dataframe(df_show[["Ticker", "Setor", "Score", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# === DEMAIS ABAS ===
with tabs[2]:
    st.subheader("Scanner FIIs")
    up = st.file_uploader("Upload CSV", type=["csv"])
    if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))

with tabs[3]:
    st.subheader("Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total RF", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

with tabs[4]:
    st.subheader("Monte Carlo")
    if st.button("Simular"):
        tks = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_historico_longo(tks)
        if not h.empty:
            r = h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna()
            if len(r) > 0: st.line_chart(MotorAnalise().monte_carlo_carteira(r, 100000, 2000))
            else: st.warning("Dados insuficientes.")
        else: st.error("Erro ao baixar dados.")

with tabs[5]:
    st.subheader("Fiscal")
    if st.button("Calcular") and calcular_darf: st.write(calcular_darf(st.session_state.carteira_acoes))

with tabs[6]:
    st.subheader("Opções")
    if BlackScholes:
        s = st.number_input("Spot", 30.0); k = st.number_input("Strike", 32.0)
        st.metric("Call", f"R$ {BlackScholes(s, k, 1/12, 0.12, 0.3, 'call').calcular_preco():.2f}")