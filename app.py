# ==============================================================================
# ARQUITETURA ZERO - v150 (Debug & Rescue Mode)
# ==============================================================================
import streamlit as st
import time

# 1. GARANTIA DE VIDA: A primeira coisa que acontece é configurar a página
st.set_page_config(page_title="Hedge Fund Debug", layout="wide")

# 2. PROVA DE VIDA: Escreve na tela imediatamente. Se você ver isso, a tela branca acabou.
st.title("🛠️ Hedge Fund Ricardo - Modo Recuperação")
status_box = st.empty()
status_box.info("⏳ Inicializando núcleo do sistema... (Passo 1/4)")
time.sleep(0.1)

# ==============================================================================
# 3. CARREGAMENTO BLINDADO (Imports dentro do fluxo para pegar o erro)
# ==============================================================================
try:
    status_box.info("⏳ Importando Pandas e Numpy... (Passo 2/4)")
    import pandas as pd
    import numpy as np
    
    status_box.info("⏳ Importando YFinance e Plotly... (Passo 3/4)")
    import yfinance as yf
    import plotly.express as px
    
    status_box.info("⏳ Importando Ferramentas Matemáticas... (Passo 4/4)")
    from datetime import datetime, timedelta
    from scipy.signal import argrelextrema
    # Nota: Removemos scipy.stats se ele for o causador, usando numpy no lugar
    
    status_box.success("✅ Todas as bibliotecas carregadas com sucesso!")
    time.sleep(1)
    status_box.empty() # Limpa as mensagens de carregamento

except ImportError as e:
    st.error(f"🛑 ERRO FATAL DE BIBLIOTECA: {e}")
    st.warning("O sistema parou porque uma ferramenta necessária não está instalada.")
    st.stop()
except Exception as e:
    st.error(f"🛑 ERRO DESCONHECIDO NA INICIALIZAÇÃO: {e}")
    st.stop()

# ==============================================================================
# 4. MOTOR LÓGICO (Definido aqui dentro para garantir integridade)
# ==============================================================================
class MotorAnalise:
    def calcular_stress_test(self, ticker, qtd, preco_atual):
        try:
            # Beta simplificado se falhar download
            beta = 1.0
            exp = qtd * preco_atual
            return {
                "Crash (-10%)": exp * -0.10,
                "Crash (-30%)": exp * -0.30,
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
            roe = info.get('returnOnEquity', 0) or 0

            # Graham
            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            # Bazin
            if div > 0: modelos['Bazin'] = div / (0.08 if modo_crise else 0.06)
            # Gordon
            ke = 0.12 if modo_crise else 0.10
            g = 0.01
            if div > 0: modelos['Gordon'] = div * (1+g) / (ke-g)

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
            if loss.iloc[-1] > 0:
                rsi = 100 - (100 / (1 + gain.iloc[-1]/loss.iloc[-1]))
            else: rsi = 50

            score = 50
            motivos = []
            if p_justo > 0 and atual < p_justo: score += 20; motivos.append("Barato")
            if mme9 > mme21: score += 15; motivos.append("Tendência Alta")
            if rsi < 30: score += 15; motivos.append("Sobrevendido")
            
            decisao = "COMPRA" if score > 60 else "VENDA" if score < 40 else "NEUTRO"
            
            return {
                "score": score, "decisao": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "modelos": modelos,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "dados": dados
            }
        except Exception as e:
            st.error(f"Erro na análise matemática: {e}")
            return None

# ==============================================================================
# 5. INTERFACE DO USUÁRIO
# ==============================================================================

# Barra Lateral
st.sidebar.header("⚙️ Configuração")
modo_crise = st.sidebar.checkbox("Modo Crise", value=False)

if st.sidebar.button("Limpar Cache"):
    try: st.cache_data.clear()
    except: st.experimental_rerun()

# Navegação Simples (Funciona em qualquer versão)
menu = st.sidebar.radio("Menu", ["Dashboard", "Análise", "Scanner", "Opções"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.subheader("📊 Carteira")
    
    # Carteira Fixa para Teste
    carteira = pd.DataFrame([
        ["BBAS3.SA", 1703], ["VALE3.SA", 152], ["PETR4.SA", 900], 
        ["TAEE11.SA", 1000], ["ALZR11.SA", 100]
    ], columns=["Ticker", "Qtd"])
    
    if st.button("Atualizar Valores"):
        progress = st.progress(0)
        total = 0
        motor = MotorAnalise()
        
        # Download em Loop (Mais seguro que lote para debug)
        for i, row in carteira.iterrows():
            try:
                t = row["Ticker"]
                ticker_obj = yf.Ticker(t)
                h = ticker_obj.history(period="1d")
                if not h.empty:
                    p = float(h["Close"].iloc[-1])
                    total += p * row["Qtd"]
            except: pass
            progress.progress((i+1)/len(carteira))
        
        st.metric("Patrimônio Total Estimado", f"R$ {total:,.2f}")
        st.dataframe(carteira)
    else:
        st.info("Clique em 'Atualizar Valores' para conectar à B3.")

# --- ANÁLISE ---
elif menu == "Análise":
    st.subheader("🔎 Deep Dive")
    ticker = st.text_input("Ticker", "VALE3.SA")
    
    if st.button("Analisar"):
        with st.spinner("Baixando dados..."):
            try:
                # 1. Baixar Dados
                t_obj = yf.Ticker(ticker)
                hist = t_obj.history(period="1y")
                
                if hist.empty:
                    st.error(f"Não foi possível baixar dados para {ticker}")
                else:
                    try: info = t_obj.info
                    except: info = {}
                    
                    # 2. Rodar Motor
                    motor = MotorAnalise()
                    res = motor.analisar(hist, info, ticker, modo_crise)
                    
                    if res:
                        # Resultados
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Score", f"{res['score']}", res['decisao'])
                        c2.metric("Preço Justo", f"R$ {res['p_justo']:.2f}")
                        c3.metric("RSI", f"{res['rsi']:.0f}")
                        
                        st.info(f"Motivos: {res['motivos']}")
                        
                        st.write("#### Detalhes de Valuation")
                        st.json(res['modelos'])
                        
                        st.write("#### Gráfico")
                        st.line_chart(hist["Close"])
                        
                        st.write("#### Stress Test")
                        stress = motor.calcular_stress_test(ticker, 100, res['preco'])
                        st.write(stress)
                    else:
                        st.error("Erro interno no cálculo da análise.")
                        
            except Exception as e:
                st.error(f"Erro na conexão ou processamento: {e}")

# --- SCANNER ---
elif menu == "Scanner":
    st.subheader("📡 Scanner de Oportunidades")
    st.write("O scanner verifica múltiplos ativos. Isso pode demorar.")
    if st.button("Escanear IBOV"):
        lista_teste = ["VALE3.SA", "PETR4.SA", "ITUB4.SA", "BBDC4.SA", "WEGE3.SA"]
        res_scan = []
        bar = st.progress(0)
        motor = MotorAnalise()
        
        for i, t in enumerate(lista_teste):
            try:
                hist = yf.Ticker(t).history(period="6mo")
                if not hist.empty:
                    r = motor.analisar(hist, {}, t, modo_crise)
                    if r:
                        res_scan.append({
                            "Ticker": t, "Preço": r['preco'], 
                            "Score": r['score'], "Decisão": r['decisao']
                        })
            except: pass
            bar.progress((i+1)/len(lista_teste))
            
        if res_scan:
            df = pd.DataFrame(res_scan)
            st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn'))
        else:
            st.warning("Nenhum ativo retornou dados.")

# --- OPÇÕES ---
elif menu == "Opções":
    st.subheader("⚡ Black & Scholes")
    try:
        from scipy.stats import norm
        def black_scholes(S, K, T, r, sigma, option_type='call'):
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            if option_type == 'call':
                return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            else:
                return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        c1, c2 = st.columns(2)
        S = c1.number_input("Preço Atual", 30.0)
        K = c2.number_input("Strike", 32.0)
        sigma = c1.number_input("Volatilidade (%)", 30.0) / 100
        T = c2.number_input("Dias Vencimento", 30) / 365
        
        if st.button("Calcular Prêmio"):
            call = black_scholes(S, K, T, 0.1375, sigma, 'call')
            put = black_scholes(S, K, T, 0.1375, sigma, 'put')
            st.success(f"Call Teórica: R$ {call:.2f}")
            st.error(f"Put Teórica: R$ {put:.2f}")
            
    except ImportError:
        st.warning("Biblioteca scipy.stats não disponível para cálculo de opções.")