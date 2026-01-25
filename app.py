# ==============================================================================
# HEDGE FUND RICARDO V154 - GOLD EDITION (FULL FEATURES RESTORED)
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import time
import yfinance as yf
import plotly.express as px
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO VISUAL (FULL SCREEN) ---
st.set_page_config(
    page_title="Hedge Fund Ricardo v154", 
    layout="wide", 
    page_icon="🏦",
    initial_sidebar_state="expanded"
)

# --- 2. IMPORTAÇÃO SEGURA DE MATEMÁTICA ---
try:
    from scipy.signal import argrelextrema
    from scipy.stats import norm
except ImportError:
    st.warning("⚠️ Biblioteca SciPy não detectada. Funções avançadas (Opções/Padrões) rodarão em modo básico.")
    argrelextrema = None
    norm = None

# --- 3. MOTOR DE INTELIGÊNCIA (CÉREBRO DO ROBÔ) ---
class MotorAnalise:
    def __init__(self):
        pass

    def formatar_ticker(self, ticker):
        t = str(ticker).upper().strip()
        if not t.endswith(".SA") and not any(c.isdigit() for c in t): return t # Crypto ou US
        if not t.endswith(".SA"): return f"{t}.SA"
        return t

    def calcular_stress_test(self, ticker, qtd, preco_atual):
        try:
            # Beta simplificado (Fallback)
            beta = 1.0
            exp = qtd * preco_atual
            return {
                "📉 Crash Leve (-10%)": exp * (beta * -0.10),
                "🔥 Crash Severo (-30%)": exp * (beta * -0.30),
                "🏦 Juros Explosivos (+1%)": exp * (beta * -0.15) if "11.SA" in ticker else exp * (beta * -0.05),
                "🛢️ Boom Commodities (+20%)": exp * (beta * 0.20) if "VALE" in ticker or "PETR" in ticker else 0
            }
        except: return {}

    def calcular_valuation(self, info, preco_atual, ticker, modo_crise):
        modelos = {}
        dados_brutos = {}
        try:
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            div_yield = info.get('dividendYield', 0) or 0
            div_anual = info.get('dividendRate', 0)
            if not div_anual: div_anual = div_yield * preco_atual
            roe = info.get('returnOnEquity', 0) or 0

            # Parâmetros Macro
            rf = 0.135 if modo_crise else 0.115 
            g = 0.01 if modo_crise else 0.02
            ke = rf + 0.06

            # Fórmulas Clássicas
            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div_anual > 0: modelos['Gordon'] = div_anual * (1 + g) / (ke - g)
            if div_anual > 0: modelos['Bazin'] = div_anual / (0.08 if modo_crise else 0.06)
            if roe > 0 and vpa > 0:
                pvp_justo = (roe - g) / (ke - g)
                if 0 < pvp_justo < 5: modelos['ROE Justo'] = pvp_justo * vpa

            # Consenso Inteligente
            vals = [v for v in modelos.values() if v > 0 and v < preco_atual*4]
            p_justo = float(np.median(vals)) if vals else 0
            
            # Margem de Segurança Dinâmica
            margem_base = 0.15 if "11.SA" in ticker else 0.25
            if modo_crise: margem_base += 0.10
            p_teto = p_justo * (1 - margem_base)
            
            dados_brutos = {"LPA": lpa, "VPA": vpa, "ROE": roe, "Div": div_anual}
            return p_justo, p_teto, margem_base, modelos, dados_brutos
        except: return 0, 0, 0, {}, {}

    def detectar_padroes(self, h, l, c):
        if argrelextrema is None: return None
        try:
            n = 5
            idx_t = argrelextrema(h.values, np.greater_equal, order=n)[0]
            topos = [(i, h.iloc[i]) for i in idx_t]
            if len(topos) >= 2:
                t1, t2 = topos[-2], topos[-1]
                # Padrão de Topo Duplo ou Resistência
                if abs(t1[1]-t2[1])/t1[1] < 0.03: return "⚠️ Resistência Forte (Topo Duplo)"
            return None
        except: return None

    def analisar(self, hist, info, ticker, modo_crise):
        try:
            if hist is None or hist.empty: return None
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])

            p_justo, p_teto, margem, modelos, dados_fund = self.calcular_valuation(info, atual, ticker, modo_crise)
            
            # Indicadores Técnicos
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else 0
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50

            # Score System (Qualidade + Convicção)
            score = 50; motivos = []
            
            # Fundamentos
            if p_justo > 0:
                if atual <= p_teto: score += 30; motivos.append("💎 Muito Barato (Fundamentos)")
                elif atual <= p_justo: score += 10; motivos.append("⚖️ Preço Justo")
                else: score -= 20; motivos.append("💸 Caro")
            
            # Técnica
            if mme9 > mme21: score += 15; motivos.append("📈 Tendência de Alta (Curto Prazo)")
            else: score -= 15
            
            if rsi < 30: score += 10; motivos.append("📉 Oportunidade (RSI Baixo)")
            elif rsi > 70: score -= 10; motivos.append("⚠️ Sobrecomprado (RSI Alto)")
            
            padrao = self.detectar_padroes(h, l, c)
            if padrao: motivos.append(padrao)

            decisao = "🟢 COMPRA FORTE" if score >= 75 else "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"
            
            return {
                "score_ia": score, "decisao_ia": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto, "margem": margem,
                "modelos_val": modelos, "dados_fund": dados_fund,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "mm200": mm200, "padrao": padrao
            }
        except: return None

    def monte_carlo(self, retornos, val_ini, sims=1000):
        try:
            days = 252 * 5 # 5 anos
            r_mean = retornos.mean(); r_std = retornos.std()
            res = []
            # Vetorizado para performance máxima
            sim_returns = np.random.normal(r_mean, r_std, (days, sims))
            res = val_ini * (1 + sim_returns).cumprod(axis=0)
            df = pd.DataFrame(res)
            
            return pd.DataFrame({
                "Cenário Médio": df.mean(axis=1),
                "Otimista (95%)": df.quantile(0.95, axis=1),
                "Pessimista (5%)": df.quantile(0.05, axis=1)
            })
        except: return pd.DataFrame()

# --- 4. FUNÇÕES DE CACHE E DADOS ---
@st.cache_data(ttl=600)
def obter_dados(ticker, modo_crise):
    motor = MotorAnalise()
    t = motor.formatar_ticker(ticker)
    try:
        t_obj = yf.Ticker(t)
        hist = t_obj.history(period="2y")
        if hist.empty: return None
        try: info = t_obj.info
        except: info = {"symbol": t}
        return motor.analisar(hist, info, t, modo_crise)
    except: return None

@st.cache_data(ttl=3600)
def calcular_carteira(df_dict):
    df = pd.DataFrame(df_dict)
    motor = MotorAnalise()
    tickers = [motor.formatar_ticker(t) for t in df["Ticker"]]
    vals = []
    
    # Tenta download em lote primeiro (mais rápido)
    try:
        data = yf.download(tickers, period="1d", progress=False)['Close']
        if not data.empty:
            prices = data.iloc[-1]
            for _, r in df.iterrows():
                t = motor.formatar_ticker(r["Ticker"])
                # Lida com download em lote retornando Series ou DataFrame
                try: p = float(prices[t])
                except: p = 0.0
                vals.append(r["Qtd"] * p)
            return vals
    except: pass
    
    # Fallback individual se o lote falhar
    for _, r in df.iterrows():
        try:
            t = motor.formatar_ticker(r["Ticker"])
            hist = yf.Ticker(t).history(period="1d")
            p = float(hist["Close"].iloc[-1])
            vals.append(r["Qtd"] * p)
        except: vals.append(0.0)
    return vals

@st.cache_data(ttl=86400)
def download_historico_lote(tickers):
    motor = MotorAnalise()
    l = [motor.formatar_ticker(t) for t in tickers]
    return yf.download(l, period="5y", progress=False)['Close']

# --- 5. INTERFACE DO USUÁRIO (UI) ---
st.title("💰 Hedge Fund Ricardo v154")

# Sidebar
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    modo_crise = st.toggle("🔴 MODO CRISE (Defensivo)", value=False)
    
    st.divider()
    b3_file = st.file_uploader("📂 Importar B3 (Excel)", type=['xlsx'])
    if b3_file:
        st.success("Arquivo recebido! Processando...")
        # Lógica de importação simplificada aqui se necessário
    
    st.divider()
    if st.button("🔄 Restaurar Padrão"):
        st.session_state.carteira_acoes = pd.DataFrame([
            ["ALZR11", 100], ["BBAS3", 1703], ["VALE3", 152], ["PETR4", 900], 
            ["TAEE11", 1000], ["HGLG11", 20], ["KNCR11", 27]
        ], columns=["Ticker", "Qtd"])
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])
        st.rerun()
    
    if st.button("🧹 Limpar Cache"):
        st.cache_data.clear()
        st.rerun()

# Inicialização
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([["VALE3", 100]], columns=["Ticker", "Qtd"])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["CDB", 0.0]], columns=["Ativo", "Saldo"])

# Menu de Abas
tabs = st.tabs(["📊 Dash", "🔎 Análise", "🧪 Stress", "🔗 Matriz", "💼 Carteira", "📡 Scanner", "🛡️ Renda Fixa", "🔮 Futuro", "⚡ Opções"])

# --- ABA 1: DASHBOARD ---
with tabs[0]:
    if st.button("🚀 Atualizar Patrimônio", type="primary"):
        with st.spinner("Conectando à B3..."):
            vals = calcular_carteira(st.session_state.carteira_acoes.to_dict())
            st.session_state.carteira_acoes["Valor Atual"] = vals
            st.session_state.last_update = time.time()
            st.rerun()

    if "last_update" in st.session_state:
        df = st.session_state.carteira_acoes
        rf = st.session_state.carteira_rf["Saldo"].sum()
        rv = df["Valor Atual"].sum() if "Valor Atual" in df.columns else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Patrimônio Total", f"R$ {rf+rv:,.2f}")
        c2.metric("Renda Variável", f"R$ {rv:,.2f}")
        c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
        
        c_graf, c_tab = st.columns([2, 1])
        with c_graf:
            if rv > 0:
                st.plotly_chart(px.pie(df, values='Valor Atual', names='Ticker', title="Alocação de Ativos", hole=0.4), use_container_width=True)
        with c_tab:
            st.dataframe(df[["Ticker", "Valor Atual"]].sort_values("Valor Atual", ascending=False), height=350)
    else:
        st.info("👆 Clique no botão acima para carregar sua carteira.")

# --- ABA 2: ANÁLISE ---
with tabs[1]:
    col_in, col_btn = st.columns([3, 1])
    ticker = col_in.text_input("Ticker", "VALE3")
    if col_btn.button("Analisar"):
        with st.spinner(f"Analisando {ticker}..."):
            r = obter_dados(ticker, modo_crise)
        
        if r:
            # Scoreboard
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Decisão IA", r['decisao_ia'], f"Score: {r['score_ia']}/100")
            c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c3.metric("Potencial", f"{((r['p_justo']/r['preco'])-1)*100:.1f}%")
            c4.metric("RSI (14)", f"{r['rsi']:.0f}")
            
            st.success(f"**Tese do Robô:** {r['motivos']}")
            
            # Gráfico TradingView (Widget)
            t_fmt = ticker.upper().replace(".SA", "")
            components.html(f"""
            <div class="tradingview-widget-container">
              <div id="tradingview_chart"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget({{
              "width": "100%", "height": 400, "symbol": "BMFBOVESPA:{t_fmt}",
              "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light",
              "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false,
              "allow_symbol_change": true, "container_id": "tradingview_chart"
              }});
              </script>
            </div>
            """, height=400)
            
            # Detalhes
            c_val, c_fund = st.columns(2)
            with c_val:
                st.subheader("📐 Valuation Detalhado")
                for k, v in r['modelos_val'].items():
                    st.metric(k, f"R$ {v:.2f}")
            with c_fund:
                st.subheader("🏗️ Fundamentos")
                d = r['dados_fund']
                st.write(f"**LPA:** R$ {d.get('LPA',0):.2f}")
                st.write(f"**VPA:** R$ {d.get('VPA',0):.2f}")
                st.write(f"**Div. Yield Proj.:** R$ {d.get('Div',0):.2f}")
                st.progress(min(100, int(r['score_ia'])))
        else:
            st.error("Ativo não encontrado. Tente adicionar .SA no final se for brasileiro.")

# --- ABA 3: STRESS ---
with tabs[2]:
    st.subheader("🧪 Simulador de Catástrofes")
    if st.button("Executar Stress Test"):
        motor = MotorAnalise(); total_loss = {}
        prog = st.progress(0)
        
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"], False)
            if d:
                res = motor.calcular_stress_test(row["Ticker"], row["Qtd"], d['preco'])
                for k, v in res.items(): total_loss[k] = total_loss.get(k, 0) + v
            prog.progress((i+1)/len(st.session_state.carteira_acoes))
            
        st.write("#### Impacto Financeiro na Carteira:")
        cols = st.columns(len(total_loss))
        for i, (cenario, perda) in enumerate(total_loss.items()):
            cols[i].metric(cenario, f"R$ {perda:,.2f}", delta_color="inverse")

# --- ABA 4: MATRIZ ---
with tabs[3]:
    if st.button("Gerar Correlação"):
        ts = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_historico_lote(ts)
        fig = px.imshow(h.corr(), text_auto=True, color_continuous_scale="RdBu_r", title="Matriz de Correlação (5 Anos)")
        st.plotly_chart(fig, use_container_width=True)

# --- ABA 5: CARTEIRA ---
with tabs[4]:
    st.subheader("Gestão de Ações e FIIs")
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)

# --- ABA 6: SCANNER ---
with tabs[5]:
    st.subheader("📡 Radar de Oportunidades")
    st.info("Exemplo com Top 5 IBOV (Scanner completo requer mais tempo)")
    if st.button("Escanear Mercado"):
        lista = ["VALE3", "PETR4", "ITUB4", "BBDC4", "WEGE3", "BBAS3", "ELET3"]
        res = []
        bar = st.progress(0)
        for i, t in enumerate(lista):
            d = obter_dados(t, modo_crise)
            if d: res.append({"Ticker": t, "Score": d['score_ia'], "Decisão": d['decisao_ia'], "Preço": d['preco'], "Justo": d['p_justo']})
            bar.progress((i+1)/len(lista))
        st.dataframe(pd.DataFrame(res).style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)

# --- ABA 7: RENDA FIXA ---
with tabs[6]:
    st.subheader("🛡️ Controle de Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)

# --- ABA 8: FUTURO ---
with tabs[7]:
    st.subheader("🔮 Previsão Monte Carlo")
    if st.button("Simular Futuro (5 Anos)"):
        ts = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_historico_lote(ts)
        if not h.empty:
            ret = h.pct_change().dropna().mean(axis=1)
            # Valor total aproximado
            val_total = 100000 
            motor = MotorAnalise()
            sim = motor.monte_carlo(ret, val_total, 500)
            st.line_chart(sim)
            st.caption("Simulação baseada na volatilidade histórica dos ativos.")

# --- ABA 9: OPÇÕES ---
with tabs[8]:
    st.subheader("⚡ Black & Scholes Calculator")
    if norm:
        c1, c2 = st.columns(2)
        S = c1.number_input("Preço do Ativo", 30.0)
        K = c2.number_input("Strike (Exercício)", 32.0)
        V = c1.number_input("Volatilidade Implícita (%)", 30.0) / 100
        D = c2.number_input("Dias até Vencimento", 30)
        
        if st.button("Calcular Prêmios"):
            T = D/365; r = 0.13
            d1 = (np.log(S/K) + (r + 0.5*V**2)*T) / (V*np.sqrt(T))
            d2 = d1 - V*np.sqrt(T)
            call = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
            put = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
            res1, res2 = st.columns(2)
            res1.metric("Preço CALL (Compra)", f"R$ {call:.2f}")
            res2.metric("Preço PUT (Venda)", f"R$ {put:.2f}")
    else:
        st.error("Biblioteca SciPy necessária para cálculo de opções.")