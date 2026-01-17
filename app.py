import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

st.set_page_config(page_title="Hedge Fund Dashboard", layout="wide")

# --- CABEÇALHO ---
st.title("🏛️ Hedge Fund Intelligence")
st.markdown("---")

motor = MotorAnalise()

# --- SEÇÃO 1: PAINEL DE MONITORAMENTO (WATCHLIST) ---
st.subheader("📊 Monitor Macro (252 Períodos)")
watchlist = ["BTC-USD", "ETH-USD", "PETR4.SA", "VALE3.SA", "AAPL", "TSLA"]

resultados_finais = []
cols_resumo = st.columns(len(watchlist))

# Processamento rápido para a tabela
for ticker in watchlist:
    try:
        data = yf.download(ticker, period="3y", progress=False)
        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            data.columns = [str(col).lower() for col in data.columns]
            data = data.reset_index()
            data.columns = [str(col).lower() for col in data.columns]
            
            res = motor.analisar(data)
            icone = "🟢" if "ALTA" in res['sinal'] else "🔴" if "BAIXA" in res['sinal'] else "⚪"
            
            resultados_finais.append({
                "Ativo": ticker,
                "Preço": f"$ {res['preco']:,.2f}",
                "RSI 252p": res['rsi_252'],
                "Status": f"{icone} {res['sinal']}"
            })
    except:
        continue

if resultados_finais:
    st.table(pd.DataFrame(resultados_finais))

st.markdown("---")

# --- SEÇÃO 2: CONSULTA INDIVIDUAL E GRÁFICO ---
st.subheader("🔍 Consulta Detalhada de Ativo")
col_input, col_info = st.columns([1, 3])

with col_input:
    ticker_input = st.text_input("Digite o Ticker (ex: BTC-USD, ITUB4.SA):", value="BTC-USD").upper()
    periodo = st.selectbox("Período do Gráfico:", ["1y", "2y", "5y"], index=0)

if ticker_input:
    try:
        # Busca dados para o gráfico
        df_individual = yf.download(ticker_input, period="3y", progress=False)
        
        if not df_individual.empty:
            # Limpeza padrão para o motor
            if isinstance(df_individual.columns, pd.MultiIndex): df_individual.columns = df_individual.columns.get_level_values(0)
            df_individual.columns = [str(col).lower() for col in df_individual.columns]
            df_proc = df_individual.reset_index()
            df_proc.columns = [str(col).lower() for col in df_proc.columns]
            
            # Análise do Motor
            analise = motor.analisar(df_proc)
            
            # Exibe métricas em destaque
            m1, m2, m3 = st.columns(3)
            m1.metric("Preço Atual", f"$ {analise['preco']:,.2f}")
            m2.metric("RSI 252p", analise['rsi_252'])
            m3.metric("Status", analise['sinal'])

            # --- PLOTAGEM DO GRÁFICO (Plotly) ---
            fig = go.Figure()
            # Preço
            fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='royalblue')))
            # Média 252
            df_motor = motor.processar_df(df_proc)
            fig.add_trace(go.Scatter(x=df_motor['date'], y=df_motor['ma252'], name="Média 252p", line=dict(color='orange', dash='dot')))
            
            fig.update_layout(title=f"Histórico de {ticker_input}", template="plotly_white", height=500)
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("Ticker não encontrado.")
    except Exception as e:
        st.error(f"Erro na consulta: {e}")