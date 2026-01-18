import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. IMPORTAÇÃO SEGURA ---
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    # Módulos Opcionais
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
    try: from scanner import scanner_fiis_csv
    except: scanner_fiis_csv = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from options import BlackScholes
    except: BlackScholes = None
except ImportError as e:
    st.error(f"Erro crítico: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo v69.0", layout="wide")

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

# Sidebar
with st.sidebar:
    st.header("🎮 Painel")
    if st.button("🧹 Limpar Cache"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.header("📄 Relatórios")
    if gerar_pdf_carteira:
        total_rf = st.session_state.carteira_rf["Saldo Atual"].sum()
        df_rep = st.session_state.carteira_acoes.copy()
        if "Valor_Atual" not in df_rep.columns: df_rep["Valor_Atual"] = df_rep["Qtd"] * df_rep["PM"]
        total_patrimonio = total_rf + df_rep["Valor_Atual"].sum()
        dict_metas = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        
        if st.button("Gerar PDF"):
            pdf_bytes = gerar_pdf_carteira(df_rep, st.session_state.carteira_rf, total_patrimonio, dict_metas)
            st.download_button("📥 Baixar PDF", data=pdf_bytes, file_name="Relatorio.pdf", mime="application/pdf")
    else: st.info("Instale 'fpdf'.")

tabs = st.tabs(["🔎 Análise Completa", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# ABA 1: ANÁLISE
with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            st.subheader("📊 Raio-X")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r.get('preco', 0):.2f}")
            c2.metric("DY Anual", f"{r.get('dy_anual', 0):.2f}%")
            
            sc = r.get('score_ia', 0)
            if sc == 0: c3.error("BLOQUEADO (0/100)")
            else: c3.metric("Score IA", f"{sc}/100", delta=r.get('decisao_ia', '-'))
            
            justo = r.get('preco_justo', 0)
            delta_j = (r['preco'] - justo)/justo*100 if justo > 0 else 0
            c4.metric("💎 Valor Justo", f"R$ {justo:.2f}", delta=f"{delta_j:+.1f}%", delta_color="inverse")
            
            st.divider()
            
            k1, k2 = st.columns(2)
            k1.markdown("**📋 Valuation**")
            k1.table(pd.DataFrame({"Modelo": ["Bazin", "Graham", "Gordon"], "Valor": [f"R$ {r.get('p_bazin',0):.2f}", f"R$ {r.get('p_graham',0):.2f}", f"R$ {r.get('p_gordon',0):.2f}"]}))
            k2.markdown("**🧠 Inteligência**")
            motivos = r.get('motivos', '')
            if "⚠️" in motivos or "⛔" in motivos: k2.error(motivos)
            else: k2.info(motivos)

            st.subheader("📈 Técnico (Algo-Trading)")
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Tendência", r.get('sinal_tecnico', '-'))
            t2.metric("MACD", "COMPRA" if r.get('macd',0) > r.get('macd_signal',0) else "VENDA")
            t3.metric("Stop Loss", f"R$ {r.get('stop_loss',0):.2f}")
            t4.metric("Stop Gain", f"R$ {r.get('stop_gain',0):.2f}")
            
            rsi_val = r.get('rsi', 50); vol_val = r.get('volatilidade', 0); vol_rel = r.get('vol_relativo', 1.0)
            df_algo = pd.DataFrame([
                {"Indicador": "RSI (14)", "Valor": f"{rsi_val:.0f}", "Status": "Sobrevendido" if rsi_val<30 else "Sobrecomprado" if rsi_val>70 else "Neutro"},
                {"Indicador": "Volatilidade", "Valor": f"{vol_val*100:.1f}%", "Status": "Risco Anual"},
                {"Indicador": "Volume Rel.", "Valor": f"{vol_rel:.2f}x", "Status": "Alto" if vol_rel > 1 else "Baixo"},
                {"Indicador": "Suporte", "Valor": f"R$ {r.get('suporte', 0):.2f}", "Status": "60d"},
                {"Indicador": "Resistência", "Valor": f"R$ {r.get('resistencia', 0):.2f}", "Status": "60d"}
            ])
            st.dataframe(df_algo, use_container_width=True)
            
            st.markdown("---")
            sym = f"BMFBOVESPA:{t.replace('.SA','')}"
            components.html(f"""<script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width":"100%","height":500,"symbol":"{sym}","interval":"D","theme":"light"}});</script>""", height=500)
        else: st.error("Ativo não encontrado.")

# ABA 2: CARTEIRA
with tabs[1]:
    c_left, c_right = st.columns([2, 1])
    with c_right:
        st.subheader("🎯 Estratégia")
        df_metas_edit = st.data_editor(st.session_state.df_metas, column_config={"Meta (%)": st.column_config.NumberColumn("Alvo %", max_value=100, format="%.1f%%")}, num_rows="dynamic")
        st.session_state.df_metas = df_metas_edit
        soma = df_metas_edit["Meta (%)"].sum()
        if abs(soma-100)>0.1: st.warning(f"Soma: {soma:.1f}%")
        else: st.success("100% OK")
    
    with c_left:
        st.subheader("💼 Ativos")
        if st.button("🤖 Classificar"): auto_classificar(); st.rerun()
        opt_setores = df_metas_edit["Setor"].tolist()
        st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True, column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=opt_setores)})
        
        aporte = st.number_input("Aporte (R$)", value=5000.0)
        if st.button("🚀 Rebalancear"):
            if abs(soma-100)>0.1: st.error("Ajuste metas para 100%.")
            else:
                d_metas = dict(zip(df_metas_edit["Setor"], df_metas_edit["Meta (%)"]))
                dados = []
                for _, row in st.session_state.carteira_acoes.iterrows():
                    d = obter_dados(row["Ticker"])
                    if d: dados.append({**row.to_dict(), "Preço": d["preco"], "Valor_Atual": row["Qtd"]*d["preco"], "Score": d["score_ia"]})
                    else: dados.append({**row.to_dict(), "Preço": 10, "Valor_Atual": row["Qtd"]*10, "Score": 50})
                
                final = rebalancear_e_aportar(pd.DataFrame(dados), aporte, d_metas)
                st.dataframe(final[final["Aporte Sugerido (R$)"]>1].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# Demais abas
with tabs[2]:
    st.subheader("Scanner"); up = st.file_uploader("CSV", type=["csv"])
    if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))
with tabs[3]:
    st.subheader("Renda Fixa"); st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")
with tabs[4]:
    st.subheader("Monte Carlo"); 
    if st.button("Simular"):
        h = download_historico_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: st.line_chart(MotorAnalise().monte_carlo_carteira(h.pct_change().dropna().mean(axis=1) if len(h.shape)>1 else h.pct_change().dropna(), 100000, 2000))
with tabs[5]:
    st.subheader("Fiscal"); 
    if st.button("Calcular") and calcular_darf: st.write(calcular_darf(st.session_state.carteira_acoes))

# ABA 7: OPÇÕES (RESTAURADA)
with tabs[6]:
    st.subheader("⚡ Simulador Black-Scholes")
    if BlackScholes:
        col_op1, col_op2 = st.columns(2)
        with col_op1:
            tipo = st.radio("Tipo", ["Call", "Put"], horizontal=True)
            s = st.number_input("Preço Atual (Spot)", value=30.0, step=0.1)
            k = st.number_input("Strike", value=32.0, step=0.1)
        with col_op2:
            t_dias = st.number_input("Dias até Vencimento", value=30, step=1)
            sigma = st.number_input("Volatilidade (%)", value=30.0, step=1.0)
            r = st.number_input("Taxa de Juros (%)", value=12.0, step=0.5)
        
        bs = BlackScholes(s, k, t_dias/365, r/100, sigma/100, tipo)
        preco = bs.calcular_preco()
        gregas = bs.calcular_gregas()
        
        st.divider()
        c_res1, c_res2 = st.columns([1, 2])
        c_res1.metric(f"Preço {tipo}", f"R$ {preco:.2f}")
        
        with c_res2:
            st.write("**Gregas (Risco):**")
            g1, g2, g3, g4, g5 = st.columns(5)
            g1.metric("Delta", f"{gregas['Delta']:.2f}")
            g2.metric("Gamma", f"{gregas['Gamma']:.3f}")
            g3.metric("Theta", f"{gregas['Theta']:.3f}")
            g4.metric("Vega", f"{gregas['Vega']:.3f}")
            g5.metric("Rho", f"{gregas['Rho']:.3f}")
    else:
        st.warning("Módulo options.py não encontrado. Instale scipy e crie o arquivo.")