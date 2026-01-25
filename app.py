# ==============================================================================
# HEDGE FUND RICARDO V154 - RESTAURAÇÃO TOTAL (FULL FEATURES)
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import time
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="Hedge Fund Ricardo v154", 
    layout="wide", 
    page_icon="🏦",
    initial_sidebar_state="expanded"
)

# --- 2. SISTEMA DE IMPORTAÇÃO (MOTOR EMBUTIDO) ---
try:
    from scipy.signal import argrelextrema
    from scipy.stats import norm
except ImportError:
    st.warning("⚠️ Biblioteca SciPy não detectada. Algumas funções matemáticas (Black-Scholes/Padrões) podem ser limitadas.")
    argrelextrema = None
    norm = None

# --- CLASSE MOTOR DE ANÁLISE (CÉREBRO) ---
class MotorAnalise:
    def __init__(self):
        pass

    def calcular_stress_test(self, ticker, qtd, preco_atual):
        try:
            t = yf.Ticker(ticker); hist = t.history(period="1y")
            if hist.empty: return {}
            
            # Beta simplificado (Fallback se falhar download do IBOV)
            beta = 1.0
            try:
                ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
                df = pd.DataFrame({'Ativo': hist['Close'], 'Ibov': ibov}).dropna()
                if not df.empty:
                    ret = df.pct_change().dropna()
                    if not ret.empty:
                        cov = ret.cov().iloc[0,1]
                        var = ret['Ibov'].var()
                        if var != 0: beta = cov / var
            except: pass
            
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

            # Parâmetros
            rf = 0.135 if modo_crise else 0.115 
            g = 0.01 if modo_crise else 0.02
            ke = rf + 0.06

            # Modelos Matemáticos
            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div_anual > 0: modelos['Gordon'] = div_anual * (1 + g) / (ke - g)
            if div_anual > 0: modelos['Bazin'] = div_anual / (0.08 if modo_crise else 0.06)
            if roe > 0 and vpa > 0:
                pvp_justo = (roe - g) / (ke - g)
                if 0 < pvp_justo < 5: modelos['ROE'] = pvp_justo * vpa

            # Consenso
            vals = [v for v in modelos.values() if v > 0 and v < preco_atual*4]
            p_justo = float(np.median(vals)) if vals else 0
            
            # Margem
            margem_pct = (0.25 if modo_crise else 0.15) if "11.SA" in ticker else (0.35 if modo_crise else 0.25)
            p_teto = p_justo * (1 - margem_pct)
            
            dados_brutos = {"LPA": lpa, "VPA": vpa, "ROE": roe, "Div": div_anual, "Ke": ke}
            return p_justo, p_teto, margem_pct, modelos, dados_brutos
        except: return 0, 0, 0, {}, {}

    def detectar_padroes(self, h, l, c):
        if argrelextrema is None: return None
        try:
            n = 5
            idx_t = argrelextrema(h.values, np.greater_equal, order=n)[0]
            topos = [(i, h.iloc[i]) for i in idx_t]
            if len(topos) >= 2:
                t1, t2 = topos[-2], topos[-1]
                if (t2[0]-t1[0]>20) and abs(t1[1]-t2[1])/t1[1]<0.05: return "☕ Cup & Handle"
            return None
        except: return None

    def analisar(self, hist, info, ticker, modo_crise):
        try:
            if hist is None or hist.empty: return None
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])

            # Valuation e Fundamentos
            p_justo, p_teto, margem, modelos, dados_fund = self.calcular_valuation(info, atual, ticker, modo_crise)
            
            # Técnica
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else 0
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50

            # Score System
            score = 50; motivos = []
            
            # Qualidade
            if p_justo > 0:
                if atual <= p_teto: score += 30; motivos.append("💎 Muito Barato")
                elif atual <= p_justo: score += 10; motivos.append("⚖️ Preço Justo")
                else: score -= 20; motivos.append("💸 Caro")
            
            # Convicção
            if mme9 > mme21: score += 15; motivos.append("📈 Tendência Alta (9x21)")
            else: score -= 15
            if rsi < 30: score += 10; motivos.append("📉 RSI Sobrevenda")
            
            padrao = self.detectar_padroes(h, l, c)
            if padrao: score += 10; motivos.append(padrao)

            decisao = "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"
            
            return {
                "score_ia": score, "decisao_ia": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto, "margem": margem,
                "modelos_val": modelos, "dados_fund": dados_fund,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "mm200": mm200, "padrao": padrao
            }
        except: return None

    def monte_carlo(self, retornos, val_ini, sims=1000):
        try:
            days = 252 * 5
            r_mean = retornos.mean(); r_std = retornos.std()
            res = []
            # Loop otimizado
            sim_returns = np.random.normal(r_mean, r_std, (days, sims))
            res = val_ini * (1 + sim_returns).cumprod(axis=0)
            df = pd.DataFrame(res)
            
            return pd.DataFrame({
                "Média": df.mean(axis=1),
                "Otimista (95%)": df.quantile(0.95, axis=1),
                "Pessimista (5%)": df.quantile(0.05, axis=1)
            })
        except: return pd.DataFrame()

# ==============================================================================
# 4. FUNÇÕES DE SUPORTE E CACHE
# ==============================================================================
@st.cache_data(ttl=300)
def obter_dados(ticker, modo_crise):
    t = str(ticker).upper().strip()
    if any(char.isdigit() for char in t) and "." not in t: t += ".SA"
    try:
        motor = MotorAnalise()
        t_obj = yf.Ticker(t)
        hist = t_obj.history(period="2y")
        if hist.empty: return None
        try: info = t_obj.info
        except: info = {"symbol": t}
        return motor.analisar(hist, info, t, modo_crise)
    except: return None

@st.cache_data(ttl=3600)
def calcular_consolidado(df_dict):
    df = pd.DataFrame(df_dict)
    tickers = [t+".SA" if "." not in t else t for t in df["Ticker"]]
    vals = []
    try: 
        data = yf.download(tickers, period="1d", progress=False)['Close']
        if not data.empty:
            prices = data.iloc[-1]
            for _, r in df.iterrows():
                t = r["Ticker"] + ".SA" if "." not in r["Ticker"] else r["Ticker"]
                p = float(prices[t]) if t in prices else 0.0
                vals.append(r["Qtd"] * p)
    except:
        for _, r in df.iterrows():
            d = obter_dados(r["Ticker"], False)
            p = d['preco'] if d else 0.0
            vals.append(r["Qtd"] * p)
    return vals

@st.cache_data(ttl=86400)
def download_longo(tickers):
    l = [t + ".SA" if "." not in t else t for t in tickers]
    return yf.download(l, period="5y", progress=False)['Close']

# ==============================================================================
# 5. INTERFACE PRINCIPAL
# ==============================================================================
st.title("💰 Hedge Fund Ricardo v154 (Ultimate)")

# Sidebar
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    modo_crise = st.checkbox("🔴 MODO CRISE (Defensivo)", value=False)
    
    st.divider()
    if st.button("🔄 Recarregar Carteira Padrão"):
        st.session_state.carteira_acoes = pd.DataFrame([
            ["ALZR11.SA", 100], ["BBAS3.SA", 1703], ["BBSE3.SA", 55], ["BTCI11.SA", 502], 
            ["BTLG11.SA", 60], ["CMIG4.SA", 1644], ["CPLE3.SA", 617], ["CPSH11.SA", 169], 
            ["CXSE3.SA", 800], ["EQTL3.SA", 200], ["HGLG11.SA", 20], ["ITSA4.SA", 1174], 
            ["KLBN4.SA", 2323], ["KNCR11.SA", 27], ["KNRI11.SA", 30], ["PETR4.SA", 900], 
            ["SAPR11.SA", 300], ["TAEE4.SA", 1000], ["VALE3.SA", 152], ["XPML11.SA", 10]
        ], columns=["Ticker", "Qtd"])
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])
        st.rerun()
        
    if st.button("🧹 Limpar Cache"):
        st.cache_data.clear()
        st.rerun()

# Inicialização de Estado
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([["VALE3.SA", 100], ["PETR4.SA", 200]], columns=["Ticker", "Qtd"])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["CDB", 10000.0]], columns=["Ativo", "Saldo"])

# Abas
tabs = st.tabs(["📊 Dash", "🔎 Análise", "🧪 Stress", "🔗 Matriz", "💼 Carteira", "📡 Scanner", "🛡️ Renda Fixa", "🔮 Futuro", "🦁 Fiscal", "⚡ Opções"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    if st.button("Atualizar Patrimônio", type="primary"):
        with st.spinner("Conectando à B3..."):
            vals = calcular_consolidado(st.session_state.carteira_acoes.to_dict())
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
        
        if rv > 0:
            c_chart, c_table = st.columns([2,1])
            with c_chart:
                st.plotly_chart(px.pie(df, values='Valor Atual', names='Ticker', title="Alocação", hole=0.4), use_container_width=True)
            with c_table:
                st.dataframe(df[["Ticker", "Valor Atual"]].sort_values("Valor Atual", ascending=False), height=400)
    else:
        st.info("Clique no botão acima para carregar sua carteira.")

# --- TAB 2: ANÁLISE ---
with tabs[1]:
    ticker = st.text_input("Ticker", "VALE3")
    if st.button("Analisar Ativo"):
        with st.spinner(f"Analisando {ticker}..."):
            r = obter_dados(ticker, modo_crise)
        
        if r:
            # Score e Decisão
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Score Final", f"{r['score_ia']}/100", r['decisao_ia'])
            c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c3.metric("Potencial", f"{((r['p_justo']/r['preco'])-1)*100:.1f}%")
            c4.metric("RSI (14)", f"{r['rsi']:.0f}")
            
            st.info(f"**Tese de Investimento:** {r['motivos']}")
            
            # Gráfico TradingView
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
            
            # Valuation Detalhado
            st.subheader("📐 Modelos de Valuation")
            cols_mod = st.columns(len(r['modelos_val']))
            for i, (k, v) in enumerate(r['modelos_val'].items()):
                cols_mod[i].metric(k, f"R$ {v:.2f}")
            
            # Fundamentos Brutos
            st.subheader("🏗️ Fundamentos & Técnica")
            d = r['dados_fund']
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("LPA", f"R$ {d.get('LPA',0):.2f}")
            f2.metric("VPA", f"R$ {d.get('VPA',0):.2f}")
            f3.metric("MME 9", f"R$ {r['mme9']:.2f}")
            f4.metric("MME 21", f"R$ {r['mme21']:.2f}")

        else:
            st.error("Ativo não encontrado ou erro na API do Yahoo.")

# --- TAB 3: STRESS ---
with tabs[2]:
    st.subheader("🧪 Simulador de Caos")
    if st.button("Rodar Stress Test na Carteira"):
        motor = MotorAnalise(); total_loss = {}
        prog = st.progress(0)
        
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"], False)
            if d:
                res = motor.calcular_stress_test(row["Ticker"], row["Qtd"], d['preco'])
                for k, v in res.items(): total_loss[k] = total_loss.get(k, 0) + v
            prog.progress((i+1)/len(st.session_state.carteira_acoes))
            
        st.write("#### Impacto Estimado no Patrimônio:")
        cols = st.columns(len(total_loss))
        for i, (cenario, perda) in enumerate(total_loss.items()):
            cols[i].metric(cenario, f"R$ {perda:,.2f}", delta_color="inverse")

# --- TAB 4: MATRIZ ---
with tabs[3]:
    if st.button("Gerar Matriz de Correlação"):
        ts = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_longo(ts)
        st.plotly_chart(px.imshow(h.corr(), text_auto=True, color_continuous_scale="RdBu_r", title="Correlação 5 Anos"), use_container_width=True)

# --- TAB 5: CARTEIRA ---
with tabs[4]:
    st.subheader("Gestão de Ações")
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)

# --- TAB 6: SCANNER ---
with tabs[5]:
    st.subheader("📡 Radar de Oportunidades")
    st.info("Scanner Rápido (Demonstração com Top 5 IBOV)")
    if st.button("Escanear"):
        lista = ["VALE3", "PETR4", "ITUB4", "BBDC4", "WEGE3"]
        res = []
        bar = st.progress(0)
        for i, t in enumerate(lista):
            d = obter_dados(t, modo_crise)
            if d: res.append({"Ticker": t, "Score": d['score_ia'], "Decisão": d['decisao_ia'], "Preço": d['preco'], "Justo": d['p_justo']})
            bar.progress((i+1)/len(lista))
        st.dataframe(pd.DataFrame(res).style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)

# --- TAB 7: RENDA FIXA ---
with tabs[6]:
    st.subheader("🛡️ Renda Fixa & Tesouro")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)

# --- TAB 8: FUTURO ---
with tabs[7]:
    st.subheader("🔮 Previsão Monte Carlo (5 Anos)")
    if st.button("Simular Futuro da Carteira"):
        ts = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_longo(ts)
        if not h.empty:
            ret = h.pct_change().dropna().mean(axis=1)
            # Valor total aproximado para simulação
            val_total = 100000 
            motor = MotorAnalise()
            sim = motor.monte_carlo(ret, val_total, 500)
            st.line_chart(sim)
            st.success("Simulação baseada na volatilidade histórica dos últimos 5 anos.")

# --- TAB 9: FISCAL ---
with tabs[8]:
    st.subheader("🦁 Calculadora de DARF (Beta)")
    st.warning("Esta aba requer o módulo 'tax.py' completo para cálculos exatos.")
    st.dataframe(st.session_state.carteira_acoes)

# --- TAB 10: OPÇÕES ---
with tabs[9]:
    st.subheader("⚡ Black & Scholes Calculator")
    if norm:
        c1, c2 = st.columns(2)
        S = c1.number_input("Preço do Ativo", 30.0)
        K = c2.number_input("Strike (Exercício)", 32.0)
        V = c1.number_input("Volatilidade (%)", 30.0) / 100
        D = c2.number_input("Dias até Vencimento", 30)
        
        if st.button("Calcular Prêmio"):
            T = D/365; r = 0.13
            d1 = (np.log(S/K) + (r + 0.5*V**2)*T) / (V*np.sqrt(T))
            d2 = d1 - V*np.sqrt(T)
            call = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
            put = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
            res_col1, res_col2 = st.columns(2)
            res_col1.metric("CALL (Compra)", f"R$ {call:.2f}")
            res_col2.metric("PUT (Venda)", f"R$ {put:.2f}")
    else:
        st.error("Biblioteca SciPy necessária para cálculo de opções.")