# ==============================================================================
# ARQUITETURA V151 - BOOT ZERO (Nenhum import pesado no topo)
# ==============================================================================
import streamlit as st
import time
import sys

# 1. GARANTIA DE VIDA
st.set_page_config(page_title="Hedge Fund v151", layout="wide")

# 2. SELETOR DE MODO DE CARREGAMENTO
if "system_loaded" not in st.session_state:
    st.session_state.system_loaded = False

if not st.session_state.system_loaded:
    st.title("🛡️ Hedge Fund System - Bootloader")
    st.info("O sistema está pronto. Clique abaixo para carregar os módulos pesados.")
    
    start = st.button("🚀 INICIAR SISTEMA (Carregar Bibliotecas)", type="primary")
    
    if start:
        status = st.empty()
        bar = st.progress(0)
        
        try:
            # Passo 1: Pandas/Numpy
            status.text("Carregando Pandas & Numpy...")
            import pandas as pd
            import numpy as np
            bar.progress(25)
            time.sleep(0.2)
            
            # Passo 2: Plotly
            status.text("Carregando Interface Gráfica (Plotly)...")
            import plotly.express as px
            bar.progress(50)
            time.sleep(0.2)
            
            # Passo 3: YFinance (Risco de Rede)
            status.text("Conectando API Financeira (YFinance)...")
            import yfinance as yf
            bar.progress(75)
            time.sleep(0.2)
            
            # Passo 4: SciPy (Risco de Compilador)
            status.text("Carregando Motor Matemático (SciPy)...")
            try:
                import scipy
                from scipy.signal import argrelextrema
            except ImportError:
                st.warning("⚠️ SciPy não encontrado. Usando modo de compatibilidade (sem gráficos avançados).")
                scipy = None
                
            bar.progress(100)
            status.success("✅ Tudo carregado! Iniciando Interface...")
            time.sleep(1)
            
            # Salva que carregou
            st.session_state.system_loaded = True
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ O SISTEMA FALHOU AO CARREGAR: {e}")
            st.code(f"Erro detalhado: {type(e).__name__}", language="python")
            st.stop()

# ==============================================================================
# 3. SISTEMA PRINCIPAL (Só roda se o Boot passou)
# ==============================================================================
if st.session_state.system_loaded:
    # Re-importa bibliotecas (agora sabemos que funcionam)
    import pandas as pd
    import numpy as np
    import yfinance as yf
    import plotly.express as px
    try: from scipy.signal import argrelextrema
    except: argrelextrema = None
    from datetime import datetime, timedelta

    # --- CLASSE MOTOR (Embutida para garantir integridade) ---
    class MotorAnalise:
        def calcular_stress_test(self, ticker, qtd, preco_atual):
            try:
                exp = qtd * preco_atual
                return {
                    "Crash Leve (-10%)": exp * -0.10,
                    "Crash Severo (-30%)": exp * -0.30,
                    "Juros (+1%)": exp * -0.05,
                    "Commodities (+20%)": exp * 0.20 if "VALE" in ticker or "PETR" in ticker else 0
                }
            except: return {}

        def calcular_valuation(self, info, preco_atual, ticker, modo_crise):
            modelos = {}
            try:
                lpa = info.get('trailingEps', 0) or 0
                vpa = info.get('bookValue', 0) or 0
                div = info.get('dividendRate', 0) or (info.get('dividendYield', 0) or 0) * preco_atual
                
                # Graham
                if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
                # Gordon
                ke = 0.12 if modo_crise else 0.10; g = 0.01
                if div > 0: modelos['Gordon'] = div * (1+g) / (ke-g)
                # Bazin
                if div > 0: modelos['Bazin'] = div / (0.08 if modo_crise else 0.06)

                vals = [v for v in modelos.values() if v > 0]
                p_justo = float(np.median(vals)) if vals else 0
                
                return p_justo, modelos, {"LPA": lpa, "VPA": vpa, "DIV": div}
            except: return 0, {}, {}

        def analisar(self, hist, info, ticker, modo_crise):
            if hist is None or hist.empty: return None
            try:
                c = hist["Close"]
                atual = float(c.iloc[-1])
                p_justo, modelos, dados = self.calcular_valuation(info, atual, ticker, modo_crise)
                
                # Técnica
                mme9 = c.ewm(span=9).mean().iloc[-1]
                mme21 = c.ewm(span=21).mean().iloc[-1]
                
                delta = c.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = -delta.clip(upper=0).rolling(14).mean()
                rsi = 50
                if loss.iloc[-1] > 0:
                    rsi = 100 - (100 / (1 + gain.iloc[-1]/loss.iloc[-1]))

                score = 50
                motivos = []
                if p_justo > 0 and atual < p_justo: score += 20; motivos.append("Barato")
                if mme9 > mme21: score += 15; motivos.append("Tend. Alta")
                if rsi < 30: score += 15; motivos.append("Sobrevendido")
                
                decisao = "COMPRA" if score > 60 else "VENDA" if score < 40 else "NEUTRO"
                
                return {
                    "score": score, "decisao": decisao, "motivos": ", ".join(motivos),
                    "preco": atual, "p_justo": p_justo, "modelos": modelos,
                    "rsi": rsi, "mme9": mme9, "mme21": mme21, "dados": dados
                }
            except: return None

    # --- UI PRINCIPAL ---
    st.title("💰 Hedge Fund Ricardo v151 (Full)")
    
    # Menu Lateral Seguro (Sem Tabs novas)
    st.sidebar.header("Menu")
    modo_crise = st.sidebar.checkbox("Modo Crise", value=False)
    menu = st.sidebar.radio("Navegar", ["Dashboard", "Análise", "Scanner", "Opções"])

    if st.sidebar.button("Resetar Sistema"):
        st.session_state.system_loaded = False
        st.rerun()

    # DASHBOARD
    if menu == "Dashboard":
        st.subheader("📊 Carteira")
        if "carteira" not in st.session_state:
            st.session_state.carteira = pd.DataFrame([
                ["BBAS3.SA", 1703], ["VALE3.SA", 152], ["PETR4.SA", 900], ["TAEE11.SA", 1000]
            ], columns=["Ticker", "Qtd"])
        
        st.dataframe(st.session_state.carteira)
        
        if st.button("Atualizar Valores"):
            total = 0
            motor = MotorAnalise()
            prog = st.progress(0)
            
            for i, row in st.session_state.carteira.iterrows():
                try:
                    t = row["Ticker"]
                    tick = yf.Ticker(t)
                    h = tick.history(period="1d")
                    if not h.empty:
                        total += float(h["Close"].iloc[-1]) * row["Qtd"]
                except: pass
                prog.progress((i+1)/len(st.session_state.carteira))
            
            st.metric("Patrimônio Total", f"R$ {total:,.2f}")

    # ANÁLISE
    elif menu == "Análise":
        st.subheader("🔎 Deep Dive")
        t = st.text_input("Ticker", "VALE3.SA")
        if st.button("Analisar"):
            motor = MotorAnalise()
            with st.spinner("Analisando..."):
                try:
                    tick = yf.Ticker(t)
                    hist = tick.history(period="1y")
                    if not hist.empty:
                        try: info = tick.info
                        except: info = {}
                        
                        res = motor.analisar(hist, info, t, modo_crise)
                        
                        if res:
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Score", f"{res['score']}", res['decisao'])
                            c2.metric("Preço Justo", f"R$ {res['p_justo']:.2f}")
                            c3.metric("RSI", f"{res['rsi']:.0f}")
                            st.info(f"Motivos: {res['motivos']}")
                            st.write("#### Detalhes Valuation")
                            st.write(res['modelos'])
                            st.write("#### Stress Test")
                            st.write(motor.calcular_stress_test(t, 100, res['preco']))
                            st.line_chart(hist['Close'])
                        else:
                            st.error("Erro ao calcular indicadores.")
                    else:
                        st.error("Ativo não encontrado ou sem dados.")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")

    # SCANNER
    elif menu == "Scanner":
        st.subheader("📡 Scanner")
        if st.button("Escanear Lista Padrão"):
            lista = ["VALE3.SA", "PETR4.SA", "ITUB4.SA", "BBDC4.SA", "WEGE3.SA"]
            res = []
            motor = MotorAnalise()
            bar = st.progress(0)
            
            for i, t in enumerate(lista):
                try:
                    hist = yf.Ticker(t).history(period="6mo")
                    if not hist.empty:
                        r = motor.analisar(hist, {}, t, modo_crise)
                        if r: res.append({"Ticker": t, "Score": r['score'], "Decisão": r['decisao']})
                except: pass
                bar.progress((i+1)/len(lista))
            
            if res: st.dataframe(pd.DataFrame(res))
            else: st.warning("Nenhum dado encontrado.")

    # OPÇÕES
    elif menu == "Opções":
        st.subheader("⚡ Black & Scholes")
        try:
            from scipy.stats import norm
            S = st.number_input("Preço", 30.0); K = st.number_input("Strike", 32.0)
            if st.button("Calcular Call"):
                d1 = (np.log(S/K) + (0.12 + 0.5*0.3**2)*0.08) / (0.3*np.sqrt(0.08))
                d2 = d1 - 0.3*np.sqrt(0.08)
                price = S * norm.cdf(d1) - K * np.exp(-0.12*0.08) * norm.cdf(d2)
                st.success(f"Prêmio Teórico: R$ {price:.2f}")
        except:
            st.warning("Biblioteca scipy.stats necessária para opções.")