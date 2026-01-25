# ==============================================================================
# HEDGE FUND RICARDO - V153 (PÓS-UPDATE ENGINE)
# ==============================================================================
import streamlit as st

# 1. CONFIGURAÇÃO (LINHA 1 OBRIGATÓRIA)
st.set_page_config(
    page_title="Hedge Fund Ricardo v153", 
    layout="wide", 
    page_icon="🏦",
    initial_sidebar_state="expanded"
)

# 2. SISTEMA DE IMPORTAÇÃO COM FEEDBACK VISUAL
# Isso garante que você veja o que está acontecendo antes da tela travar
status_placeholder = st.empty()
status_placeholder.info("🚀 Inicializando Sistema v153... Carregando módulos...")

import time
import pandas as pd
import numpy as np

try:
    import yfinance as yf
    import plotly.express as px
    import scipy
    from scipy.signal import argrelextrema
    from datetime import datetime, timedelta
except ImportError as e:
    st.error(f"❌ Erro de Biblioteca: {e}")
    st.stop()

status_placeholder.empty() # Limpa mensagem se carregou tudo

# ==============================================================================
# 3. NÚCLEO MATEMÁTICO (MOTOR EMBUTIDO)
# ==============================================================================
class MotorAnalise:
    
    def __init__(self):
        pass

    def calcular_stress_test(self, ticker, qtd, preco_atual):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            if hist.empty: return {}
            
            beta = 1.0
            try:
                ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
                df = pd.DataFrame({'Ativo': hist['Close'], 'Ibov': ibov}).dropna()
                if not df.empty:
                    ret = df.pct_change().dropna()
                    cov = ret.cov().iloc[0,1]
                    var = ret['Ibov'].var()
                    if var != 0: beta = cov / var
            except: pass
            
            exp = qtd * preco_atual
            return {
                "Crash Leve (-10%)": exp * (beta * -0.10),
                "Crash Severo (-30%)": exp * (beta * -0.30),
                "Juros Explosivos": exp * (beta * -0.15) if "11.SA" in ticker else exp * (beta * -0.05),
                "Boom Commodities": exp * (beta * 0.20) if "VALE" in ticker or "PETR" in ticker else 0,
                "Beta": beta
            }
        except: return {}

    def calcular_probabilidades(self, hist, preco_atual, dias=21):
        try:
            ret = hist['Close'].pct_change().dropna()
            vol_dia = ret.std()
            vol_anual = vol_dia * (252**0.5)
            
            return {
                "base_min": preco_atual * (1 - (vol_dia * (dias**0.5))),
                "base_max": preco_atual * (1 + (vol_dia * (dias**0.5))),
                "otimista": preco_atual * (1 + 2*(vol_dia * (dias**0.5))),
                "pessimista": preco_atual * (1 - 2*(vol_dia * (dias**0.5))),
                "volatilidade_anual": vol_anual
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

            rf = 0.135 if modo_crise else 0.115 
            g = 0.01 if modo_crise else 0.02
            ke = rf + 0.06

            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div_anual > 0: modelos['Gordon'] = div_anual * (1 + g) / (ke - g)
            if div_anual > 0: modelos['Bazin'] = div_anual / (0.08 if modo_crise else 0.06)
            if roe > 0 and vpa > 0:
                pvp_justo = (roe - g) / (ke - g)
                if 0 < pvp_justo < 5: modelos['ROE'] = pvp_justo * vpa

            vals = [v for v in modelos.values() if v > 0 and v < preco_atual*4]
            p_justo = float(np.median(vals)) if vals else 0
            margem = (0.25 if modo_crise else 0.15) if "11.SA" in ticker else (0.35 if modo_crise else 0.25)
            p_teto = p_justo * (1 - margem)
            
            dados_brutos = {"LPA": lpa, "VPA": vpa, "ROE": roe, "Div": div_anual, "Ke": ke}
            return p_justo, p_teto, margem, modelos, dados_brutos
        except: return 0, 0, 0, {}, {}

    def analisar(self, hist, info, ticker, modo_crise):
        try:
            if hist is None or hist.empty: return None
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])

            p_justo, p_teto, margem, modelos, dados_fund = self.calcular_valuation(info, atual, ticker, modo_crise)
            probs = self.calcular_probabilidades(hist, atual)

            # Técnica
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else 0
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50

            # Score
            score = 50
            motivos = []
            
            if p_justo > 0:
                if atual <= p_teto: score += 30; motivos.append("💎 Barato (Fundamentos)")
                elif atual <= p_justo: score += 10; motivos.append("⚖️ Justo")
                else: score -= 20; motivos.append("💸 Caro")
            
            if mme9 > mme21: score += 15; motivos.append("📈 Tendência Alta (9x21)")
            else: score -= 15
            
            if rsi < 30: score += 10; motivos.append("📉 RSI Sobrevendido")
            
            decisao = "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"

            return {
                "score_ia": score, "decisao_ia": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto, "margem": margem,
                "modelos_val": modelos, "dados_fund": dados_fund, "probs": probs,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "mm200": mm200
            }
        except: return None

    def monte_carlo_carteira(self, retornos, val_ini, sims=1000):
        try:
            days = 252 * 5
            r_mean = retornos.mean(); r_std = retornos.std()
            res = []
            for _ in range(sims):
                daily = np.random.normal(r_mean, r_std, days)
                res.append(np.cumprod(1 + daily) * val_ini)
            df = pd.DataFrame(res).T
            return pd.DataFrame({"Media": df.mean(axis=1), "Otimista": df.quantile(0.95, axis=1), "Pessimista": df.quantile(0.05, axis=1)})
        except: return pd.DataFrame()

# ==============================================================================
# 4. SISTEMA PRINCIPAL (INTERFACE)
# ==============================================================================

# -- CACHE INTELIGENTE --
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
        # Download em lote para velocidade
        data = yf.download(tickers, period="1d", progress=False)['Close']
        if not data.empty:
            prices = data.iloc[-1]
            for _, r in df.iterrows():
                t = r["Ticker"] + ".SA" if "." not in r["Ticker"] else r["Ticker"]
                p = float(prices[t]) if t in prices else 0.0
                vals.append(r["Qtd"] * p)
    except:
        # Fallback individual se lote falhar
        for _, r in df.iterrows():
            d = obter_dados(r["Ticker"], False)
            p = d['preco'] if d else 0.0
            vals.append(r["Qtd"] * p)
    return vals

@st.cache_data(ttl=86400)
def download_longo(tickers):
    l = [t + ".SA" if "." not in t else t for t in tickers]
    return yf.download(l, period="5y", progress=False)['Close']

# -- UI START --
st.title("💰 Hedge Fund Ricardo v153")

# Sidebar
with st.sidebar:
    st.header("⚙️ Controle")
    modo_crise = st.toggle("Modo Crise", value=False) # Agora toggle funciona!
    
    if st.button("Restaurar Padrão"):
        st.session_state.carteira_acoes = pd.DataFrame([
            ["BBAS3", 1703], ["VALE3", 152], ["PETR4", 900], ["TAEE11", 1000], 
            ["ALZR11", 100], ["HGLG11", 20], ["KNCR11", 27]
        ], columns=["Ticker", "Qtd"])
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])
        st.rerun()
    
    if st.button("Limpar Cache"):
        st.cache_data.clear()
        st.rerun()

# Inicializa Sessão
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3", 1703], ["VALE3", 152], ["PETR4", 900], ["TAEE11", 1000]
    ], columns=["Ticker", "Qtd"])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])

# Navegação por Tabs (Agora suportado!)
tabs = st.tabs(["📊 Dash", "🔎 Análise", "🧪 Stress", "🔗 Matriz", "💼 Carteira", "📡 Scanner", "🔮 Futuro", "⚡ Opções"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    if st.button("🔄 Atualizar Patrimônio", type="primary"):
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
            st.write("### Alocação")
            st.plotly_chart(px.pie(df, values='Valor Atual', names='Ticker', hole=0.4), use_container_width=True)
    else:
        st.info("Clique no botão acima para carregar sua carteira.")

# --- TAB 2: ANÁLISE ---
with tabs[1]:
    ticker = st.text_input("Ticker", "VALE3")
    if st.button("Analisar"):
        with st.spinner(f"Analisando {ticker}..."):
            r = obter_dados(ticker, modo_crise)
        
        if r:
            c1, c2, c3 = st.columns(3)
            c1.metric("Score IA", f"{r['score_ia']}/100", r['decisao_ia'])
            c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c3.metric("RSI (14)", f"{r['rsi']:.0f}")
            
            st.info(f"**Motivos:** {r['motivos']}")
            
            st.write("#### 📐 Modelos de Valuation")
            st.json(r['modelos_val'])
            
            st.write("#### 🏗️ Fundamentos Brutos")
            st.dataframe(pd.DataFrame([r['dados_fund']]))
            
            st.write("#### 🎲 Probabilidades (21 dias)")
            st.dataframe(pd.DataFrame([r['probs']]))
        else:
            st.error("Ativo não encontrado ou erro na API.")

# --- TAB 3: STRESS TEST ---
with tabs[2]:
    if st.button("Simular Caos"):
        motor = MotorAnalise()
        total_loss = {}
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"], False)
            if d:
                res = motor.calcular_stress_test(row["Ticker"], row["Qtd"], d['preco'])
                for k, v in res.items(): total_loss[k] = total_loss.get(k, 0) + v
        
        st.subheader("Impacto Estimado na Carteira")
        for k, v in total_loss.items():
            st.metric(k, f"R$ {v:,.2f}", delta_color="inverse")

# --- TAB 4: MATRIZ ---
with tabs[3]:
    if st.button("Gerar Correlação"):
        ts = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_longo(ts)
        st.plotly_chart(px.imshow(h.corr(), text_auto=True, color_continuous_scale="RdBu_r"), use_container_width=True)

# --- TAB 5: CARTEIRA ---
with tabs[4]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Ações & FIIs")
        st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic")
    with c2:
        st.subheader("Renda Fixa")
        st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")

# --- TAB 6: SCANNER ---
with tabs[5]:
    st.write("Scanner Rápido (Top 5 IBOV)")
    if st.button("Escanear"):
        lista = ["VALE3", "PETR4", "ITUB4", "BBDC4", "WEGE3"]
        res = []
        bar = st.progress(0)
        for i, t in enumerate(lista):
            d = obter_dados(t, modo_crise)
            if d: res.append({"Ticker": t, "Score": d['score_ia'], "Decisão": d['decisao_ia'], "Preço": d['preco'], "Justo": d['p_justo']})
            bar.progress((i+1)/len(lista))
        st.dataframe(pd.DataFrame(res).style.background_gradient(subset=['Score'], cmap='RdYlGn'))

# --- TAB 7: FUTURO ---
with tabs[6]:
    if st.button("Simular Monte Carlo (5 Anos)"):
        ts = st.session_state.carteira_acoes["Ticker"].tolist()
        h = download_longo(ts)
        if not h.empty:
            ret = h.pct_change().dropna().mean(axis=1)
            motor = MotorAnalise()
            sim = motor.monte_carlo_carteira(ret, 100000, 500)
            st.line_chart(sim)

# --- TAB 8: OPÇÕES ---
with tabs[7]:
    st.subheader("Black & Scholes")
    from scipy.stats import norm
    S = st.number_input("Preço Ativo", 30.0)
    K = st.number_input("Strike", 32.0)
    V = st.number_input("Volatilidade (%)", 30.0) / 100
    D = st.number_input("Dias Vencimento", 30)
    
    if st.button("Calcular Prêmio"):
        T = D/365; r = 0.13
        d1 = (np.log(S/K) + (r + 0.5*V**2)*T) / (V*np.sqrt(T))
        d2 = d1 - V*np.sqrt(T)
        call = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        put = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        c1, c2 = st.columns(2)
        c1.metric("Call (Compra)", f"R$ {call:.2f}")
        c2.metric("Put (Venda)", f"R$ {put:.2f}")