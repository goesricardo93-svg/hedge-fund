# ==============================================================================
# HEDGE FUND RICARDO V164 - STABILITY MODE (SINGLE THREAD)
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import time
import yfinance as yf
import plotly.express as px
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="Hedge Fund Ricardo v164", 
    layout="wide", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# --- 2. IMPORTAÇÃO SEGURA ---
try:
    from scipy.signal import argrelextrema
    from scipy.stats import norm
except ImportError:
    st.warning("⚠️ Biblioteca SciPy não detectada. Instale via requirements.txt.")
    argrelextrema = None; norm = None

# --- 3. MOTOR DE INTELIGÊNCIA COMPLETO ---
class MotorAnalise:
    def formatar_ticker(self, ticker):
        t = str(ticker).upper().strip()
        if not t.endswith(".SA") and not any(c.isdigit() for c in t): return t
        if not t.endswith(".SA"): return f"{t}.SA"
        return t

    # [MÓDULO 1] MACRO & NEWS
    def analisar_macro(self):
        try:
            # threads=False para não estourar o limite do servidor
            ibov = yf.download("^BVSP", period="1y", progress=False, threads=False)['Close']
            if ibov.empty: return 0, "Neutro"
            atual = ibov.iloc[-1]
            mm200 = ibov.rolling(200).mean().iloc[-1]
            if atual > mm200: return 5, "🟢 Bull Market (Ibov > MM200)"
            return -10, "🔴 Bear Market (Ibov < MM200)"
        except: return 0, "⚪ Macro Indefinido"

    def analisar_sentimento_news(self, ticker_obj):
        try:
            news = ticker_obj.news
            if not news: return "Neutro", 0, ["Sem Notícias recentes"]
            score = 0
            pos = ["lucro", "alta", "dividend", "compra", "recorde", "aprovado", "forte", "upgrade", "bonificação"]
            neg = ["prejuízo", "queda", "fraude", "corrupção", "divida", "risco", "fraco", "downgrade", "investigação"]
            manchetes = []
            for n in news[:5]:
                t = n.get('title', '').lower()
                manchetes.append(n.get('title', ''))
                score += sum(2 for w in pos if w in t)
                score -= sum(2 for w in neg if w in t)
            sentimento = "🟢 Positivo" if score > 2 else "🔴 Negativo" if score < -2 else "⚪ Neutro"
            return sentimento, score, manchetes
        except: return "Neutro", 0, ["Erro ao ler notícias"]

    # [MÓDULO 2] PADRÕES GRÁFICOS & CANDLES
    def identificar_candle(self, o, h, l, c):
        corpo = abs(c - o); range_total = h - l
        if range_total == 0: return None
        sombra_sup = h - max(c, o); sombra_inf = min(c, o) - l
        
        if corpo <= range_total * 0.1: return "🕯️ Doji (Indecisão)"
        if sombra_inf >= 2 * corpo and sombra_sup <= 0.1 * corpo: return "🔨 Martelo (Alta)"
        if sombra_sup >= 2 * corpo and sombra_inf <= 0.1 * corpo: return "☄️ Estrela Cadente (Baixa)"
        return None

    def detectar_padroes_graficos(self, h, l):
        if argrelextrema is None: return None
        try:
            n = 5
            idx_t = argrelextrema(h.values, np.greater_equal, order=n)[0]
            idx_f = argrelextrema(l.values, np.less_equal, order=n)[0]
            topos = [(i, h.iloc[i]) for i in idx_t]
            fundos = [(i, l.iloc[i]) for i in idx_f]
            padroes = []
            if len(topos) >= 2:
                if abs(topos[-2][1]-topos[-1][1])/topos[-2][1] < 0.02: padroes.append("📉 Topo Duplo")
            if len(fundos) >= 2:
                if abs(fundos[-2][1]-fundos[-1][1])/fundos[-2][1] < 0.02: padroes.append("🚀 Fundo Duplo")
            return ", ".join(padroes) if padroes else None
        except: return None

    # [MÓDULO 3] DIVIDENDOS & VALUATION
    def consultar_dividendos_reais(self, ticker_obj):
        try:
            divs = ticker_obj.dividends
            if divs.empty: return 0.0
            corte = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
            return divs[divs.index >= corte].sum()
        except: return 0.0

    def calcular_valuation(self, info, preco, ticker, modo_crise, dy_val):
        modelos = {}
        try:
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            div = dy_val if dy_val > 0 else (info.get('dividendRate', 0) or 0)

            rf = 0.135 if modo_crise else 0.115 
            g = 0.01; ke = rf + 0.06

            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div > 0: modelos['Gordon'] = div * (1+g) / (ke-g)
            if div > 0: modelos['Bazin'] = div / (0.08 if modo_crise else 0.06)
            if roe > 0 and vpa > 0:
                p_roe = (roe - g) / (ke - g) * vpa
                if p_roe > 0: modelos['Justo (ROE)'] = p_roe

            vals = [v for v in modelos.values() if v > 0 and v < preco*5]
            p_justo = float(np.median(vals)) if vals else 0
            
            margem = (0.25 if modo_crise else 0.15)
            if "11.SA" in ticker: margem = 0.10
            
            dados = {"LPA": lpa, "VPA": vpa, "ROE": roe, "DY 12m": div}
            return p_justo, p_justo*(1-margem), margem, modelos, dados
        except: return 0, 0, 0, {}, {}

    # [MÓDULO 4] CORE & SCORING
    def analisar(self, hist, info, ticker, modo_crise, ticker_obj):
        try:
            if hist is None or hist.empty: return None
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]; o = hist["Open"]
            atual = float(c.iloc[-1])

            # Chamada dos Módulos
            macro_score, macro_txt = self.analisar_macro()
            sentimento, score_news, manchetes = self.analisar_sentimento_news(ticker_obj)
            dy_val = self.consultar_dividendos_reais(ticker_obj)
            p_justo, p_teto, margem, modelos, dados_fund = self.calcular_valuation(info, atual, ticker, modo_crise, dy_val)
            padrao_grafico = self.detectar_padroes_graficos(h, l)
            candle = self.identificar_candle(o.iloc[-1], h.iloc[-1], l.iloc[-1], atual)

            # Indicadores Técnicos
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else atual
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50

            # Score System
            score = 50; motivos = []
            
            if p_justo > 0:
                if atual <= p_teto: score += 30; motivos.append("💎 Muito Barato")
                elif atual <= p_justo: score += 10; motivos.append("⚖️ Preço Justo")
                else: score -= 20; motivos.append("💸 Caro")
            
            score += macro_score
            score += score_news
            
            if mme9 > mme21: score += 15; motivos.append("📈 Tendência Alta")
            else: score -= 15
            
            if rsi < 30: score += 10; motivos.append("📉 RSI Oportunidade")
            if padrao_grafico: score += 10; motivos.append(padrao_grafico)
            if candle: motivos.append(candle)

            decisao = "🟢 COMPRA FORTE" if score >= 80 else "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"
            
            # Tabela Técnica
            dy_pct = (dy_val/atual)*100 if atual > 0 else 0
            tec_data = [
                {"Ind": "RSI (14)", "Val": f"{rsi:.0f}", "Sinal": "🟢" if rsi < 30 else "🔴" if rsi > 70 else "⚪"},
                {"Ind": "MME 9x21", "Val": "Cruzamento", "Sinal": "🟢" if mme9 > mme21 else "🔴"},
                {"Ind": "Macro (Ibov)", "Val": macro_txt, "Sinal": "🟢" if macro_score > 0 else "🔴"},
                {"Ind": "Notícias", "Val": sentimento, "Sinal": "🟢" if "Positivo" in sentimento else "🔴" if "Negativo" in sentimento else "⚪"},
                {"Ind": "Padrão", "Val": padrao_grafico or "-", "Sinal": "🟢" if padrao_grafico else "⚪"},
                {"Ind": "Candle", "Val": candle or "-", "Sinal": "⚪"}
            ]

            return {
                "score_ia": max(0, min(100, score)), "decisao_ia": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto, "margem": margem,
                "modelos_val": modelos, "dados_fund": dados_fund, "dy_pct": dy_pct,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "tabela_tecnica": pd.DataFrame(tec_data),
                "manchetes": manchetes, "sentimento": sentimento
            }
        except: return None

    # [MÓDULO 5] RISCO & FUTURO
    def calcular_stress_test(self, ticker, qtd, preco):
        try:
            exp = qtd * preco
            return {
                "📉 Crash (-10%)": exp * -0.10, "🔥 Crash (-30%)": exp * -0.30,
                "🏦 Juros (+1%)": exp * (-0.15 if "11.SA" in ticker else -0.05),
                "🛢️ Commodities (+20%)": exp * 0.20 if "VALE" in ticker or "PETR" in ticker else 0
            }
        except: return {}

    def monte_carlo(self, retornos, val_ini, sims=1000):
        try:
            days = 252 * 5
            r_mean = retornos.mean(); r_std = retornos.std()
            sim_returns = np.random.normal(r_mean, r_std, (days, sims))
            res = val_ini * (1 + sim_returns).cumprod(axis=0)
            df = pd.DataFrame(res)
            return pd.DataFrame({
                "Cenário Médio": df.mean(axis=1),
                "Otimista (95%)": df.quantile(0.95, axis=1),
                "Pessimista (5%)": df.quantile(0.05, axis=1)
            })
        except: return pd.DataFrame()

# --- 4. CACHE (THREADS=FALSE PARA EVITAR CRASH) ---
@st.cache_data(ttl=600)
def obter_dados_v164(ticker, modo_crise):
    motor = MotorAnalise()
    t = motor.formatar_ticker(ticker)
    try:
        t_obj = yf.Ticker(t)
        # threads=False é CRUCIAL para evitar o erro "can't start new thread"
        hist = t_obj.history(period="2y") 
        if hist.empty: return None
        try: info = t_obj.info
        except: info = {"symbol": t}
        return motor.analisar(hist, info, t, modo_crise, t_obj)
    except: return None

@st.cache_data(ttl=3600)
def calcular_consolidado_v164(df_dict):
    df = pd.DataFrame(df_dict)
    motor = MotorAnalise()
    tickers = [motor.formatar_ticker(t) for t in df["Ticker"]]
    vals = []
    try:
        # threads=False AQUI TAMBÉM
        data = yf.download(tickers, period="1d", progress=False, threads=False)['Close']
        if not data.empty:
            prices = data.iloc[-1]
            for _, r in df.iterrows():
                t = motor.formatar_ticker(r["Ticker"])
                try: p = float(prices[t])
                except: p = 0.0
                vals.append(r["Qtd"] * p)
            return vals
    except: pass
    for _, r in df.iterrows():
        try:
            t = motor.formatar_ticker(r["Ticker"])
            h = yf.Ticker(t).history(period="1d")
            p = float(h["Close"].iloc[-1])
            vals.append(r["Qtd"] * p)
        except: vals.append(0.0)
    return vals

@st.cache_data(ttl=86400)
def download_longo(tickers):
    motor = MotorAnalise()
    l = [motor.formatar_ticker(t) for t in tickers]
    # threads=False novamente
    return yf.download(l, period="5y", progress=False, threads=False)['Close']

# --- 5. INTERFACE ---
st.title("💰 Hedge Fund Ricardo v164 (Estável)")

with st.sidebar:
    st.header("⚙️ Painel")
    modo_crise = st.toggle("🔴 MODO CRISE", value=False)
    st.divider()
    b3_file = st.file_uploader("📂 Importar B3 (Excel)", type=['xlsx'])
    if st.button("🔄 Restaurar Padrão"):
        st.session_state.carteira_acoes = pd.DataFrame([
            ["ALZR11", 100], ["BBAS3", 1703], ["VALE3", 152], ["PETR4", 900], 
            ["TAEE11", 1000], ["HGLG11", 20], ["KNCR11", 27]
        ], columns=["Ticker", "Qtd"])
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])
        st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([["VALE3", 100]], columns=["Ticker", "Qtd"])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["CDB", 0.0]], columns=["Ativo", "Saldo"])

tabs = st.tabs(["📊 Dash", "🔎 Análise", "🧪 Stress", "🔗 Matriz", "💼 Carteira", "📡 Scanner", "🛡️ Renda Fixa", "🔮 Futuro", "🦁 Fiscal", "⚡ Opções"])

# DASHBOARD
with tabs[0]:
    if st.button("🚀 Atualizar Patrimônio", type="primary"):
        with st.spinner("Conectando (Modo Seguro)..."):
            vals = calcular_consolidado_v164(st.session_state.carteira_acoes.to_dict())
            st.session_state.carteira_acoes["Valor Atual"] = vals
            st.session_state.last_update = time.time()
            st.rerun()

    if "last_update" in st.session_state:
        df = st.session_state.carteira_acoes
        rf = st.session_state.carteira_rf["Saldo"].sum()
        rv = df["Valor Atual"].sum() if "Valor Atual" in df.columns else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", f"R$ {rf+rv:,.2f}")
        c2.metric("Renda Variável", f"R$ {rv:,.2f}")
        c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
        if rv > 0: st.plotly_chart(px.pie(df, values='Valor Atual', names='Ticker', hole=0.4), use_container_width=True)
    else: st.info("Clique no botão acima para carregar.")

# ANÁLISE DETALHADA
with tabs[1]:
    col_in, col_btn = st.columns([3, 1])
    ticker = col_in.text_input("Ticker", "VALE3")
    if col_btn.button("Analisar"):
        with st.spinner(f"Analisando {ticker}..."):
            r = obter_dados_v164(ticker, modo_crise)
        
        if r:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Decisão", r['decisao_ia'], f"Score: {r['score_ia']}")
            c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c3.metric("Potencial", f"{((r['p_justo']/r['preco'])-1)*100:.1f}%")
            c4.metric("Sentimento", r['sentimento'])
            
            st.success(f"**Tese:** {r['motivos']}")
            with st.expander("📰 Manchetes Recentes (Yahoo)"):
                if r['manchetes']:
                    for m in r['manchetes']: st.write(f"- {m}")
                else: st.write("Nenhuma notícia recente encontrada.")
            
            t_fmt = ticker.upper().replace(".SA", "")
            components.html(f"""<div class="tradingview-widget-container"><div id="tradingview_chart"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 400, "symbol": "BMFBOVESPA:{t_fmt}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_chart" }});</script></div>""", height=400)
            
            c_tec, c_val = st.columns(2)
            with c_tec:
                st.subheader("📊 Quadro Técnico & Macro")
                tabela = r.get('tabela_tecnica', pd.DataFrame())
                if not tabela.empty: st.dataframe(tabela, use_container_width=True, hide_index=True)
            with c_val:
                st.subheader("🏗️ Fundamentos & Dividendos")
                d = r['dados_fund']
                st.metric("Dividend Yield (12m Real)", f"R$ {d['DY 12m']:.2f}", f"{r['dy_pct']:.2f}%")
                st.write(f"**LPA:** R$ {d.get('LPA',0):.2f} | **VPA:** R$ {d.get('VPA',0):.2f}")
                st.write(f"**ROE:** {d.get('ROE',0)*100:.1