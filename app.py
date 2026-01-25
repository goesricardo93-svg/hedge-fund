# ==============================================================================
# HEDGE FUND RICARDO V155 - DIAGNÓSTICO E CORREÇÃO DO MOTOR
# ==============================================================================
import streamlit as st
import time

# 1. GARANTIA DE VIDA (Primeira linha executável)
st.set_page_config(page_title="Hedge Fund v155", layout="wide", page_icon="🏦")

# 2. PROVA DE VIDA VISUAL (Se você ler isso, a tela branca acabou)
st.title("✅ Sistema Iniciado")
status = st.empty()
status.info("⏳ Carregando motor matemático...")

# ==============================================================================
# 3. MOTOR DE ANÁLISE (Definido AQUI para evitar erro de importação externa)
# ==============================================================================
# Removemos imports globais perigosos. Importamos SOMENTE dentro da classe.
class MotorAnalise:
    
    def __init__(self):
        # Importação tardia: Se der erro aqui, o app já abriu e vai avisar
        try:
            import pandas as pd
            import numpy as np
            import yfinance as yf
            from datetime import datetime, timedelta
            self.pd = pd
            self.np = np
            self.yf = yf
            self.timedelta = timedelta
        except ImportError as e:
            st.error(f"❌ Erro Crítico: Falta instalar bibliotecas! {e}")
            st.stop()

    def baixar_dados(self, ticker):
        try:
            ticker = str(ticker).upper().strip()
            if not ticker.endswith(".SA") and not ticker.replace('.','').isdigit():
                ticker += ".SA"
            
            t_obj = self.yf.Ticker(ticker)
            hist = t_obj.history(period="2y")
            
            if hist.empty: return None, {}, "Sem dados"
            
            try: info = t_obj.info
            except: info = {}
            
            return hist, info, ticker
        except Exception as e:
            return None, {}, str(e)

    def analisar(self, hist, info, ticker):
        try:
            # Dados básicos
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])
            
            # 1. Valuation Simplificado (Para não quebrar se faltar dados)
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            p_justo = (22.5 * lpa * vpa)**0.5 if (lpa>0 and vpa>0) else 0
            
            # 2. Técnica (Pandas puro, sem depender de Scipy por enquanto)
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 50
            if loss.iloc[-1] > 0:
                rsi = 100 - (100 / (1 + gain.iloc[-1]/loss.iloc[-1]))

            # 3. Score
            score = 50
            motivos = []
            
            if p_justo > 0:
                if atual <= p_justo: score += 20; motivos.append("Preço Justo (Graham)")
                else: score -= 20; motivos.append("Caro (Graham)")
            
            if mme9 > mme21: score += 15; motivos.append("Tendência Alta")
            if rsi < 30: score += 15; motivos.append("Sobrevendido")
            
            decisao = "COMPRA" if score >= 60 else "VENDA" if score <= 40 else "NEUTRO"
            
            return {
                "score": score, "decisao": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "rsi": rsi,
                "mme9": mme9, "mme21": mme21
            }
        except Exception as e:
            return {"erro": str(e)}

# ==============================================================================
# 4. INTERFACE
# ==============================================================================
try:
    import plotly.express as px
except: px = None

status.success("✅ Motor Carregado.")
time.sleep(0.5)
status.empty()

# Sidebar
with st.sidebar:
    st.header("⚙️ Painel")
    if st.button("Limpar Cache"):
        st.cache_data.clear()
        st.rerun()

# Layout Principal
tabs = st.tabs(["📊 Análise Rápida", "📋 Carteira"])

with tabs[0]:
    t = st.text_input("Ticker", "VALE3")
    if st.button("Analisar Ativo", type="primary"):
        motor = MotorAnalise()
        with st.spinner("Conectando..."):
            hist, info, t_fmt = motor.baixar_dados(t)
            
            if hist is not None:
                res = motor.analisar(hist, info, t_fmt)
                
                if "erro" in res:
                    st.error(f"Erro no cálculo: {res['erro']}")
                else:
                    # Resultados
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Decisão", res['decisao'], f"Score: {res['score']}")
                    c2.metric("Preço Atual", f"R$ {res['preco']:.2f}")
                    c3.metric("Preço Justo", f"R$ {res['p_justo']:.2f}")
                    
                    st.info(f"**Motivos:** {res['motivos']}")
                    
                    # Gráfico
                    st.subheader("Gráfico de Preços")
                    if px:
                        st.plotly_chart(px.line(hist, y="Close", title=t_fmt), use_container_width=True)
                    else:
                        st.line_chart(hist["Close"])
            else:
                st.error("Falha ao baixar dados. Verifique sua internet ou o ticker.")

with tabs[1]:
    st.write("### Sua Carteira")
    if "carteira" not in st.session_state:
        st.session_state.carteira = [{"Ticker": "BBAS3", "Qtd": 100}]
    
    df = st.data_editor(st.session_state.carteira, num_rows="dynamic")
    st.session_state.carteira = df