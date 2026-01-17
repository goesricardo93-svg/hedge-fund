import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import time

st.set_page_config(page_title="Hedge Fund Dashboard", layout="wide")

st.title("🏛️ Hedge Fund Intelligence")
st.markdown("Análise de 252 períodos (1 ano de pregão)")

motor = MotorAnalise()

# --- SEÇÃO 1: PAINEL DE MONITORAMENTO (WATCHLIST) ---
st.subheader("📊 Monitor Macro Global")
watchlist = ["BTC-USD", "ETH-USD", "PETR4.SA", "VALE3.SA", "AAPL", "TSLA"]

if st.button('Atualizar Monitor'):
    resultados_finais = []
    progresso = st.progress(0)
    
    for i, ticker in enumerate(watchlist):
        try:
            data = yf.download(ticker, period="3y", progress=False)
            if not data.empty:
                # Limpeza de colunas (proteção contra o erro de tupla)
                if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
                data.columns = [str(col).lower() for col in data.columns]
                df_proc = data.reset_index()
                df_proc.columns = [str(col).lower() for col in df_proc.columns]
                
                res = motor.analisar(df_proc)
                icone = "🟢" if "ALTA" in res['sinal'] else "🔴" if "BAIXA" in res['sinal'] else "⚪"
                
                resultados_finais.append({
                    "Ativo": ticker,
                    "Preço": f"$ {res['preco']:,.2f}",
                    "RSI 252p": res['rsi_252'],
                    "Status": f"{icone} {res['sinal']}"
                })
        except: continue
        progresso.progress((i + 1) / len(watchlist))
    
    if resultados_finais:
        st.table(pd.DataFrame(resultados_finais))

st.markdown("---")

# --- SEÇÃO 2: CONSULTA INDIVIDUAL ---
st.subheader("🔍 Consulta Detalhada")
ticker_input = st.text_input("Digite o Ticker para gráfico (ex: ITUB4.SA):", value="BTC-USD").upper()

if ticker_input:
    try:
        df_ind = yf.download(ticker_input, period="3y", progress=False)
        if not df_ind.empty:
            if isinstance(df_ind.columns, pd.MultiIndex): df_ind.columns = df_ind.columns.get_level_values(0)
            df_ind.columns = [str(col).lower() for col in df_ind.columns]
            df_analise = df_ind.reset_index()
            df_analise.columns = [str(col).lower() for col in df_analise.columns]

            res_ind = motor.analisar(df_analise)
            
            # Métricas em destaque
            c1, c2, c3 = st.columns(3)
            c1.metric("Preço", f"$ {res_ind['preco']:,.2f}")
            c2.metric("RSI 252p", res_ind['rsi_252'])
            c3.metric("Sinal", res_ind['sinal'])

            # Gráfico Nativo do Streamlit (mais rápido e não exige Plotly se der erro)
            df_grafico = motor.processar_df(df_analise)
            df_grafico.set_index('date', inplace=True)
            st.line_chart(df_grafico[['close', 'ma252']])
            
    except Exception as e:
        st.error(f"Aguardando dados ou ticker inválido.")