# ==============================================================================
# HEDGE FUND RICARDO V156 - LAZY LOAD ARCHITECTURE
# ==============================================================================
import streamlit as st
import time
import datetime

# 1. CONFIGURAÇÃO (PRIMEIRA LINHA)
st.set_page_config(
    page_title="Hedge Fund v156", 
    layout="wide", 
    page_icon="🏦",
    initial_sidebar_state="expanded"
)

# 2. SISTEMA DE IMPORTAÇÃO TARDIA (SEGURANÇA CONTRA CRASH)
# Não importamos yfinance/scipy/plotly aqui no topo para não travar o boot.
# Eles serão chamados apenas dentro das funções.

# ==============================================================================
# 3. MOTOR DE ANÁLISE (COM IMPORTS INTERNOS)
# ==============================================================================
class MotorAnalise:
    def __init__(self):
        # Carrega bibliotecas apenas quando o Motor é acionado
        import pandas as pd
        import numpy as np
        self.pd = pd
        self.np = np

    def baixar_dados(self, ticker):
        import yfinance as yf
        try:
            ticker = str(ticker).upper().strip()
            if not ticker.endswith(".SA") and not ticker.replace('.','').isdigit():
                ticker += ".SA"
            
            t_obj = yf.Ticker(ticker)
            hist = t_obj.history(period="2y")
            
            if hist.empty: return None, {}, ticker
            try: info = t_obj.info
            except: info = {}
            return hist, info, ticker
        except: return None, {}, ticker

    def calcular_indicadores(self, hist, info, ticker, modo_crise):
        try:
            # Imports locais para evitar crash global
            from scipy.signal import argrelextrema
            
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])
            
            # --- 1. Valuation ---
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            div_yield = info.get('dividendYield', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            
            # Modelos
            modelos = {}
            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div_yield > 0: modelos['Bazin'] = (div_yield * atual) / (0.08 if modo_crise else 0.06)
            
            vals = [v for v in modelos.values() if v > 0]
            p_justo = float(self.np.median(vals)) if vals else 0
            margem = (0.25 if modo_crise else 0.15)
            p_teto = p_justo * (1 - margem)

            # --- 2. Técnica ---
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else 0
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50

            # --- 3. Padrões ---
            padrao = None
            try:
                n = 5
                idx = argrelextrema(h.values, self.np.greater_equal, order=n)[0]
                if len(idx) >= 2:
                    t1, t2 = h.iloc[idx[-2]], h.iloc[idx[-1]]
                    if abs(t1-t2)/t1 < 0.05: padrao = "Topo Duplo / Resistência"
            except: pass

            # --- 4. Score ---
            score = 50; motivos = []
            if p_justo > 0 and atual <= p_teto: score += 30; motivos.append("💎 Barato")
            if mme9 > mme21: score += 15; motivos.append("📈 Tendência Alta")
            if rsi < 30: score += 10; motivos.append("📉 Sobrevendido")
            
            decisao = "COMPRA" if score >= 60 else "VENDA" if score <= 40 else "NEUTRO"

            return {
                "score": score, "decisao": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "mm200": mm200,
                "padrao": padrao, "modelos": modelos,
                "fundamentos": {"LPA": lpa, "VPA": vpa, "ROE": roe, "DY": div_yield}
            }
        except Exception as e: return {"erro": str(e)}

    def stress_test(self, ticker, qtd, preco):
        import pandas as pd
        exp = qtd * preco
        return {
            "Crash (-15%)": exp * -0.15,
            "Crise Juros": exp * (-0.20 if "11.SA" in ticker else -0.05),
            "Commodities Boom": exp * 0.25 if "VALE" in ticker or "PETR" in ticker else 0
        }

    def monte_carlo(self, hist, dias=1260, sims=1000):
        import numpy as np
        import pandas as pd
        ret = hist.pct_change().dropna()
        mean = ret.mean(); std = ret.std()
        res = []
        last_price = hist.iloc[-1]
        
        sim_returns = np.random.normal(mean, std, (dias, sims))
        paths = last_price * (1 + sim_returns).cumprod(axis=0)
        
        return pd.DataFrame({
            "Média": paths.mean(axis=1),
            "Otimista (95%)": np.percentile(paths, 95, axis=1),
            "Pessimista (5%)": np.percentile(paths, 5, axis=1)
        })

    def black_scholes(self, S, K, T, r, sigma, tipo='call'):
        from scipy.stats import norm
        import numpy as np
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        if tipo == 'call':
            return S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        else:
            return K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)

# ==============================================================================
# 4. INTERFACE DO USUÁRIO
# ==============================================================================
st.title("💰 Hedge Fund Ricardo v156")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuração")
    modo_crise = st.checkbox("Modo Crise (Defensivo)", value=False)
    
    if st.button("Restaurar Carteira Padrão"):
        import pandas as pd # Import apenas aqui
        st.session_state.carteira = pd.DataFrame([
            ["BBAS3", 1703], ["VALE3", 152], ["PETR4", 900], ["TAEE11", 1000],
            ["ALZR11", 100], ["HGLG11", 20], ["KNCR11", 27]
        ], columns=["Ticker", "Qtd"])
        st.rerun()
        
    if st.button("Limpar Cache"):
        st.cache_data.clear()
        st.rerun()

# Inicializa sessão
if "carteira" not in st.session_state:
    st.session_state.carteira = [] # Vazio até carregar pandas

# --- ABAS (FULL RESTORE) ---
tabs = st.tabs(["Dash", "Análise", "Stress", "Carteira", "Scanner", "Monte Carlo", "Opções"])

# 1. DASHBOARD
with tabs[0]:
    st.subheader("Visão Geral")
    if st.button("🔄 Atualizar Patrimônio", type="primary"):
        import yfinance as yf
        import pandas as pd
        import plotly.express as px
        
        # Garante que carteira é DataFrame
        if isinstance(st.session_state.carteira, list):
             st.session_state.carteira = pd.DataFrame([["VALE3", 100]], columns=["Ticker", "Qtd"])

        df = st.session_state.carteira.copy()
        vals = []
        bar = st.progress(0)
        
        # Download seguro
        for i, row in df.iterrows():
            t = row["Ticker"] + ".SA" if "." not in row["Ticker"] else row["Ticker"]
            try:
                hist = yf.Ticker(t).history(period="1d")
                p = float(hist["Close"].iloc[-1]) if not hist.empty else 0.0
            except: p = 0.0
            vals.append(p * row["Qtd"])
            bar.progress((i+1)/len(df))
            
        df["Total"] = vals
        st.session_state.dash_data = df
        st.rerun()

    if "dash_data" in st.session_state:
        df = st.session_state.dash_data
        total = df["Total"].sum()
        st.metric("Patrimônio Total", f"R$ {total:,.2f}")
        
        import plotly.express as px
        c1, c2 = st.columns([2,1])
        c1.plotly_chart(px.pie(df, values='Total', names='Ticker', hole=0.4), use_container_width=True)
        c2.dataframe(df)

# 2. ANÁLISE
with tabs[1]:
    t_input = st.text_input("Ticker", "VALE3")
    if st.button("Analisar Ativo"):
        motor = MotorAnalise()
        with st.spinner("Analisando..."):
            hist, info, t_fmt = motor.baixar_dados(t_input)
            
            if hist is not None:
                r = motor.calcular_indicadores(hist, info, t_fmt, modo_crise)
                
                if "erro" not in r:
                    # Exibe Resultados
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Decisão", r['decisao'], f"Score: {r['score']}")
                    c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
                    c3.metric("Potencial", f"{((r['p_justo']/r['preco'])-1)*100:.1f}%")
                    c4.metric("RSI", f"{r['rsi']:.0f}")
                    
                    st.info(f"**Motivos:** {r['motivos']}")
                    
                    # Gráfico
                    st.line_chart(hist['Close'])
                    
                    # Detalhes
                    with st.expander("Ver Detalhes Fundamentalistas"):
                        st.json(r['modelos'])
                        st.json(r['fundamentos'])
                else:
                    st.error(f"Erro no cálculo: {r['erro']}")
            else:
                st.error("Falha ao baixar dados.")

# 3. STRESS
with tabs[2]:
    if st.button("Simular Cenários"):
        motor = MotorAnalise()
        import pandas as pd # Local import
        
        # Se carteira não estiver carregada, carrega padrão
        if isinstance(st.session_state.carteira, list):
             st.warning("Carregue a carteira no Dashboard primeiro.")
        else:
            res_total = {}
            for i, row in st.session_state.carteira.iterrows():
                h, _, _ = motor.baixar_dados(row["Ticker"])
                if h is not None:
                    p = float(h["Close"].iloc[-1])
                    s = motor.stress_test(row["Ticker"], row["Qtd"], p)
                    for k, v in s.items(): res_total[k] = res_total.get(k, 0) + v
            
            for k, v in res_total.items():
                st.metric(k, f"R$ {v:,.2f}", delta_color="inverse")

# 4. CARTEIRA
with tabs[3]:
    import pandas as pd
    if isinstance(st.session_state.carteira, list):
        st.session_state.carteira = pd.DataFrame([["VALE3", 100]], columns=["Ticker", "Qtd"])
    
    st.session_state.carteira = st.data_editor(st.session_state.carteira, num_rows="dynamic")

# 5. SCANNER
with tabs[4]:
    if st.button("Escanear IBOV"):
        lista = ["VALE3", "PETR4", "ITUB4", "BBDC4", "WEGE3", "BBAS3"]
        motor = MotorAnalise()
        res = []
        bar = st.progress(0)
        
        for i, t in enumerate(lista):
            h, info, t_fmt = motor.baixar_dados(t)
            if h is not None:
                r = motor.calcular_indicadores(h, info, t_fmt, modo_crise)
                if "score" in r:
                    res.append({"Ticker": t, "Score": r['score'], "Decisão": r['decisao'], "Preço": r['preco']})
            bar.progress((i+1)/len(lista))
            
        import pandas as pd
        st.dataframe(pd.DataFrame(res).style.background_gradient(subset=['Score'], cmap='RdYlGn'))

# 6. MONTE CARLO
with tabs[5]:
    if st.button("Simular Futuro (Monte Carlo)"):
        motor = MotorAnalise()
        h, _, _ = motor.baixar_dados("IVVB11") # Usa IVVB11 como proxy de volatilidade global se não tiver carteira
        if h is not None:
            sim = motor.monte_carlo(h['Close'])
            st.line_chart(sim)
            st.caption("Simulação baseada na volatilidade histórica.")

# 7. OPÇÕES
with tabs[6]:
    st.subheader("Black & Scholes")
    c1, c2 = st.columns(2)
    S = c1.number_input("Preço Ativo", 30.0)
    K = c2.number_input("Strike", 32.0)
    V = c1.number_input("Volatilidade %", 30.0) / 100
    D = c2.number_input("Dias Vencimento", 30)
    
    if st.button("Calcular Prêmio"):
        try:
            motor = MotorAnalise()
            call = motor.black_scholes(S, K, D/365, 0.13, V, 'call')
            put = motor.black_scholes(S, K, D/365, 0.13, V, 'put')
            
            c1.metric("CALL", f"R$ {call:.2f}")
            c2.metric("PUT", f"R$ {put:.2f}")
        except Exception as e:
            st.error(f"Erro (provavelmente falta Scipy): {e}")