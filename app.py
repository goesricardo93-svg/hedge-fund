import streamlit as st
import time

# --- MODO DE SEGURANÇA MÁXIMA ---
# Não usamos set_page_config aqui para evitar erros de ordem
# Não usamos sidebar complexa

st.header("💰 Hedge Fund Ricardo v152 (Diagnóstico)")
st.write("---")

# 1. TESTE DE BIBLIOTECAS
status = st.empty()
status.info("1. Carregando bibliotecas essenciais...")

try:
    import pandas as pd
    import numpy as np
    import yfinance as yf
    status.success("✅ Bibliotecas Carregadas: Pandas, Numpy, YFinance")
except Exception as e:
    st.error(f"❌ ERRO CRÍTICO DE IMPORTAÇÃO: {e}")
    st.stop()

# 2. DEFINIÇÃO DO MOTOR (LOCAL)
status.info("2. Definindo lógica matemática...")

class MotorSimples:
    def analisar(self, ticker):
        try:
            # Baixa dados
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period="1y")
            
            if hist.empty: return None, "Sem dados históricos"
            
            # Cálculos Simples (Sem scipy para não travar)
            atual = float(hist["Close"].iloc[-1])
            mme9 = hist["Close"].ewm(span=9).mean().iloc[-1]
            mme21 = hist["Close"].ewm(span=21).mean().iloc[-1]
            
            # Valuation Simplificado (Sem depender de info quebrada)
            try: info = ticker_obj.info
            except: info = {}
            
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            
            p_justo = (22.5 * lpa * vpa)**0.5 if (lpa>0 and vpa>0) else 0
            
            return {
                "preco": atual,
                "mme9": mme9,
                "mme21": mme21,
                "p_justo": p_justo,
                "hist": hist
            }, "Sucesso"
        except Exception as e:
            return None, str(e)

status.success("✅ Motor Definido.")

# 3. INTERFACE SIMPLIFICADA
status.info("3. Renderizando Interface...")
time.sleep(0.5)
status.empty() # Limpa logs

# --- APLICAÇÃO ---

col1, col2 = st.columns(2)
with col1:
    ticker = st.text_input("Digite o Ticker:", "VALE3.SA")
with col2:
    st.write("")
    st.write("")
    botao = st.button("🔎 ANALISAR AGORA")

if botao:
    st.write(f"⏳ Processando {ticker}...")
    
    motor = MotorSimples()
    dados, msg = motor.analisar(ticker)
    
    if dados:
        # Exibe Resultados
        p_atual = dados['preco']
        p_justo = dados['p_justo']
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Preço Atual", f"R$ {p_atual:.2f}")
        c2.metric("Preço Justo (Graham)", f"R$ {p_justo:.2f}")
        
        tendencia = "ALTA 🟢" if dados['mme9'] > dados['mme21'] else "BAIXA 🔴"
        c3.metric("Tendência (9x21)", tendencia)
        
        st.subheader("Gráfico de Preços")
        st.line_chart(dados['hist']['Close'])
        
        st.success("Análise concluída com sucesso.")
    else:
        st.error(f"Falha ao analisar: {msg}")

st.write("---")
st.caption("Se você consegue ver esta tela e clicar no botão, o problema de 'Tela Branca' foi resolvido.")