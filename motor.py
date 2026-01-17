import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise

st.set_page_config(page_title="Hedge Fund Dashboard", layout="wide")
st.title("🏛️ Terminal Hedge Fund - Inteligência 252p")

motor = MotorAnalise()

# --- INPUT DE TICKER ---
ticker = st.text_input("Consultar Ativo:", value="BTC-USD").upper().strip()

if ticker:
    try:
        df_ind = yf.download(ticker, period="4y", progress=False)
        if not df_ind.empty:
            # Padronização de Colunas
            if isinstance(df_ind.columns, pd.MultiIndex): df_ind.columns = df_ind.columns.get_level_values(0)
            df_ind.columns = [str(col).lower() for col in df_ind.columns]
            df_proc = df_ind.reset_index()
            df_proc.columns = [str(col).lower() for col in df_proc.columns]

            res = motor.analisar(df_proc)
            
            # --- BLOCO 1: MÉTRICAS DE FORÇA (RSI E TENDÊNCIA) ---
            st.markdown(f"### 📈 Análise de Momentum: {ticker}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"$ {res['preco']:,.2f}")
            c2.metric("Tendência (252p)", res['tendencia'])
            c3.metric("RSI Tático (14p)", res['rsi_14'])
            c4.metric("RSI Macro (252p)", res['rsi_252'])

            st.markdown("---")

            # --- BLOCO 2: SUPORTE, RESISTÊNCIA E RISCO ---
            col_risk, col_sr, col_fib = st.columns(3)

            with col_risk:
                st.subheader("🛡️ Gestão de Risco")
                st.error(f"STOP LOSS: $ {res['stop_loss']:,.2f}")
                st.success(f"STOP GAIN: $ {res['stop_gain']:,.2f}")
                st.info(f"MÉDIA ANUAL: $ {res['ma252']:,.2f}")

            with col_sr:
                st.subheader("🚧 Barreiras de Preço")
                st.warning(f"RESISTÊNCIA (Topo): $ {res['resistencia']:,.2f}")
                st.write(f"**SUPORTE (Fundo):** $ {res['suporte']:,.2f}")

            with col_fib:
                st.subheader("📐 Fibonacci (252p)")
                for n, v in res['fibonacci'].items():
                    st.write(f"**{n}:** $ {v:,.2f}")

            # --- BLOCO 3: GRÁFICO ---
            st.markdown("---")
            st.write("### Gráfico de Preço e Média Anual")
            df_vis = motor.processar_df(df_proc).set_index('date')
            st.line_chart(df_vis[['close', 'ma252']])
            
    except Exception as e:
        st.error(f"Erro na análise: {e}")