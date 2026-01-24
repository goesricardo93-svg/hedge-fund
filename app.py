# ======================================================
# 1. BOOTLOADER (Linha 1 Obrigatória)
# ======================================================
import streamlit as st
st.set_page_config(page_title="Hedge Fund Ricardo v138", layout="wide", page_icon="🏦")

# Mensagem de Debug para garantir que não é tela branca
debug_msg = st.empty()
debug_msg.info("🚀 Sistema inicializando... Carregando núcleo...")

import pandas as pd
import numpy as np
import time

# ======================================================
# 2. IMPORTAÇÃO BLINDADA (EVITA CRASH)
# ======================================================
try:
    import yfinance as yf
    import plotly.express as px
    import scipy
    from scipy.signal import argrelextrema
except ImportError as e:
    st.error(f"❌ ERRO: Biblioteca faltando: {e}")
    st.stop()

# Carrega Motor (Crítico)
try:
    from motor import MotorAnalise
except Exception as e:
    st.error(f"❌ ERRO NO MOTOR.PY: {e}")
    st.stop()

# Carrega Módulos Opcionais com Fallback (Para não travar se faltar arquivo)
try: from rebalance import rebalancear_e_aportar
except: 
    # Fallback interno se o arquivo não existir
    def rebalancear_e_aportar(df, aporte, metas):
        return pd.DataFrame({"Info": ["Módulo rebalance.py não encontrado."]})

try: from scanner import executar_scanner
except: 
    def executar_scanner(tipo): return pd.DataFrame()

try: from options import BlackScholes
except: BlackScholes = None

try: from tax import calcular_darf
except: calcular_darf = None

debug_msg.empty() # Limpa mensagem de carregamento

# ======================================================
# 3. LÓGICA DE DADOS
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v138":
    st.session_state.versao_sistema = "v138"
    st.cache_data.clear()
    st.toast("Sistema v138 Online", icon="✅")

def carregar_carteira_padrao():
    dados = [
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
    return pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_acoes" not in st.session_state or st.session_state.carteira_acoes.empty:
    st.session_state.carteira_acoes = carregar_carteira_padrao()
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós-Fixado"]], columns=["Ativo", "Saldo Atual", "Tipo"])

def formatar_ticker_global(t):
    t = str(t).upper().strip()
    if any(char.isdigit() for char in t) and "." not in t: return f"{t}.SA"
    return t

# --- CACHE DE DADOS (CRÍTICO: SHOW_SPINNER=FALSE PARA EVITAR THREAD ERROR) ---
@st.cache_data(ttl=300, show_spinner=False)
def obter_dados(ticker, modo_crise):
    t = formatar_ticker_global(ticker)
    try:
        t_obj = yf.Ticker(t)
        hist = t_obj.history(period="2y")
        if hist.empty: return None
        try: info = t_obj.info
        except: info = {"symbol": t, "quoteType": "EQUITY"}
        return MotorAnalise().analisar(hist, info, t, modo_crise)
    except: return None

@st.cache_data(ttl=3600, show_spinner=False)
def calcular_consolidado_cached(df_dict):
    df = pd.DataFrame(df_dict)
    tickers = [formatar_ticker_global(t) for t in df["Ticker"]]
    prices = pd.Series(dtype=float)
    try: 
        data = yf.download(tickers, period="1d", progress=False)['Close']
        if not data.empty: prices = data.iloc[-1]
    except: pass
    
    vals = []
    for _, r in df.iterrows():
        t = formatar_ticker_global(r["Ticker"])
        p = 0.0
        try:
            if t in prices: p = float(prices[t])
            else:
                d = obter_dados(t, False)
                p = d.get('preco', 0) if d else 0.0
        except: p = 0.0
        vals.append(r["Qtd"] * p)
    return vals

@st.cache_data(ttl=86400, show_spinner=False)
def download_longo(tickers):
    l = [formatar_ticker_global(t) for t in tickers]
    try: return yf.download(l, period="5y", progress=False)['Close']
    except: return pd.DataFrame()

# ======================================================
# 4. UI - APLICAÇÃO
# ======================================================
st.title("💰 Hedge Fund Ricardo v138 (Stable)")

with st.sidebar:
    modo_crise = st.toggle("🔴 MODO CRISE", value=False)
    if modo_crise: st.error("⚠️ DEFESA ATIVA")
    
    st.divider()
    if st.button("Restaurar Padrão"): 
        st.session_state.carteira_acoes = carregar_carteira_padrao(); st.rerun()
    if st.button("Limpar Cache"): st.cache_data.clear(); st.rerun()

# --- ABAS ---
tabs = st.tabs([
    "📊 Dash", "🔎 Análise", "🧪 Stress", "🔗 Correlação", 
    "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", 
    "💰 Futuro", "🦁 Fiscal", "⚡ Opções"
])

# 0. DASHBOARD
with tabs[0]:
    st.subheader("Visão Geral")
    
    # Botão de Carregamento Manual (Evita Timeout na Inicialização)
    if st.button("🔄 Atualizar Carteira", type="primary"):
        with st.spinner("Conectando à B3..."):
            vals = calcular_consolidado_cached(st.session_state.carteira_acoes.to_dict())
            st.session_state.carteira_acoes["Valor Atual"] = vals
            st.session_state.last_update = time.time()
            st.rerun()

    if "last_update" in st.session_state:
        df = st.session_state.carteira_acoes
        rf = st.session_state.carteira_rf["Saldo Atual"].sum()
        rv = df["Valor Atual"].sum() if "Valor Atual" in df.columns else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Patrimônio", f"R$ {rf+rv:,.2f}")
        c2.metric("Renda Variável", f"R$ {rv:,.2f}")
        c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
        
        if rv > 0:
            df_g = df.groupby("Setor")["Valor Atual"].sum().reset_index()
            if rf > 0: df_g = pd.concat([df_g, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": rf}])])
            import plotly.express as px
            st.plotly_chart(px.pie(df_g, values='Valor Atual', names='Setor', title="Alocação"), use_container_width=True)
    else:
        st.info("Clique no botão acima para carregar os dados.")

# 1. ANÁLISE
with tabs[1]:
    ticker = st.text_input("Ticker", "VALE3")
    if st.button("Analisar"):
        with st.spinner(f"Analisando {ticker}..."):
            r = obter_dados(ticker, modo_crise)
        
        if r:
            # Score
            st.markdown("### 1. Painel de Controle")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Score", f"{r.get('score_ia')}/100", r.get('decisao_ia'))
            c2.metric("Qualidade", f"{r.get('score_qualidade')}/100")
            c3.metric("Convicção", f"{r.get('score_conviccao')}/100")
            c4.metric("Sentimento", f"{r.get('macro')}", r.get('news'))
            st.info(f"**Tese:** {r.get('motivos')}")
            if r.get('alertas'): st.error(f"**Riscos:** {r.get('alertas')}")
            st.divider()
            
            # Valuation
            st.markdown("### 2. Fundamentos")
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Preço Tela", f"R$ {r.get('preco',0):.2f}")
            v2.metric("Preço Justo", f"R$ {r.get('p_justo',0):.2f}")
            v3.metric("Preço Teto", f"R$ {r.get('p_teto',0):.2f}")
            v4.metric("Margem", f"{r.get('margem',0)*100:.0f}%")
            
            mod = r.get('modelos_val', {})
            if mod:
                st.caption("Modelos:")
                cols = st.columns(len(mod))
                idx = 0
                for k, v in mod.items():
                    cols[idx].metric(k, f"R$ {v:.2f}")
                    idx += 1
            
            # Dados Brutos
            st.write("#### Indicadores")
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("P/VP", f"{r.get('pvp',0):.2f}")
            f2.metric("ROE", f"{r.get('roe',0)*100:.1f}%")
            f3.metric("DY (12m)", f"{r.get('dy_anual',0):.2f}%")
            f4.metric("Dívida/EBITDA", f"{r.get('divida_ebitda',0):.2f}")
            f5.metric("Margem Líq.", f"{r.get('margem_liq',0)*100:.1f}%")
            
            st.divider()

            # Técnica
            st.markdown("### 3. Técnica")
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("RSI (14)", f"{r.get('rsi',50):.0f}")
            t2.metric("MME 9 vs 21", "Alta" if r.get('mme9',0) > r.get('mme21',0) else "Baixa")
            t3.metric("Padrão", r.get('padrao_grafico') or "-")
            
            import streamlit.components.v1 as components
            t_fmt = formatar_ticker_global(ticker)
            symbol = f"BMFBOVESPA:{t_fmt.replace('.SA','')}"
            components.html(f"""<div class="tradingview-widget-container"><div id="tv"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 400, "symbol": "{symbol}", "interval": "D", "theme": "light", "container_id": "tv" }});</script></div>""", height=400)

# 2. STRESS
with tabs[2]:
    if st.button("Rodar Stress Test"):
        motor = MotorAnalise(); total = {}
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"], False)
            p = d.get('preco', 0) if d else 0
            res = motor.calcular_stress_test(row["Ticker"], row["Qtd"], p)
            for k, v in res.items(): total[k] = total.get(k, 0) + v
        for k, v in total.items(): st.metric(k, f"R$ {v:,.2f}", delta_color="inverse")

# 3. CORRELAÇÃO
with tabs[3]:
    if st.button("Gerar Matriz"):
        ts = [formatar_ticker_global(t) for t in st.session_state.carteira_acoes["Ticker"]]
        corr = yf.download(ts, period="6mo", progress=False)['Close'].corr()
        st.plotly_chart(px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r"), use_container_width=True)

# 4. CARTEIRA
with tabs[4]: st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)

# 5. SCANNER
with tabs[5]:
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("Escanear Ações"): st.dataframe(executar_scanner("ACOES"))
    with c2: 
        if st.button("Escanear FIIs"): st.dataframe(executar_scanner("FIIS"))

# 6. RENDA FIXA
with tabs[6]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)

# 7. FUTURO
with tabs[7]:
    if st.button("Simular Monte Carlo"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty:
            ret = h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna()
            v_atual = st.session_state.carteira_acoes["Qtd"].mul(h.iloc[-1].values, fill_value=0).sum() if not h.empty else 10000
            sim = MotorAnalise().monte_carlo_carteira(ret, v_atual, 2000)
            st.line_chart(sim)

# 8. FISCAL
with tabs[8]:
    if calcular_darf: st.table(calcular_darf(st.session_state.carteira_acoes))
    else: st.warning("Módulo Fiscal não encontrado (tax.py).")

# 9. OPÇÕES
with tabs[9]:
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1: 
            S = st.number_input("Preço", 30.0); K = st.number_input("Strike", 32.0)
        with c2: 
            D = st.number_input("Dias", 30); V = st.number_input("Vol %", 30.0)/100
        if st.button("Calc Gregas"):
            g = BlackScholes(S, K, D/365, 0.13, V, "call").calcular_gregas()
            st.write(g)
    else: st.warning("Módulo Opções não encontrado (options.py).")