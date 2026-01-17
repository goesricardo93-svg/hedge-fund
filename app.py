import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
st.title("🏛️ Terminal Hedge Fund - Inteligência Total")

motor = MotorAnalise()

# --- CAMPO DE BUSCA ---
ticker = st.text_input("Consultar Ativo (Ex: BTC-USD, PETR4.SA, NVDA):", value="BTC-USD").upper().strip()

if ticker:
    try:
        df_raw = yf.download(ticker, period="4y", progress=False)
        if not df_raw.empty:
            # Limpeza rigorosa de colunas para evitar o erro de 'tupla'
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_raw.columns = df_raw.columns.get_level_values(0)
            df_raw.columns = [str(c).lower() for c in df_raw.columns]
            df_proc = df_raw.reset_index()
            df_proc.columns = [str(c).lower() for c in df_proc.columns]
            
            res = motor.analisar(df_proc)
            
            if res:
                # 1. MÉTRICAS PRINCIPAIS
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"$ {res['preco']:,.2f}")
                c2.metric("Tendência (252p)", res['tendencia'])
                c3.metric("RSI Tático (14p)", res['rsi_14'])
                c4.metric("RSI Macro (252p)", res['rsi_252'])

                st.markdown("---")
                
                # 2. GESTÃO DE RISCO E BARREIRAS
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.subheader("🛡️ Risco")
                    st.error(f"STOP LOSS: $ {res['stop_loss']:,.2f}")
                    st.success(f"STOP GAIN: $ {res['stop_gain']:,.2f}")
                
                with col_b:
                    st.subheader("🚧 Barreiras Anuais")
                    st.warning(f"RESISTÊNCIA: $ {res['resistencia']:,.2f}")
                    st.info(f"SUPORTE: $ {res['suporte']:,.2f}")
                
                with col_c:
                    st.subheader("📐 Fibonacci (252p)")
                    for k, v in res['fibonacci'].items():
                        st.write(f"**{k}:** $ {v:,.2f}")

                # 3. O GRÁFICO (REINTEGRADO)
                st.markdown("---")
                st.subheader("📈 Gráfico de Preço vs Média Anual (252p)")
                
                # Preparamos os dados para o gráfico
                df_grafico = df_proc.copy()
                df_grafico['ma252'] = df_grafico['close'].rolling(window=252).mean()
                df_grafico = df_grafico.set_index('date')
                
                # Exibimos o gráfico com as duas linhas principais
                st.line_chart(df_grafico[['close', 'ma252']])
                
        else:
            st.error("Ativo não encontrado. Verifique o ticker.")
    except Exception as e:
        st.error(f"Ocorreu um erro no processamento: {e}")

# --- MONITOR GLOBAL (OPCIONAL NO FINAL) ---
with st.expander("📊 Ver Monitor Macro (Watchlist)"):
    st.write("Clique para processar a lista principal.")
    # (Mantive simples para focar no gráfico individual que você pediu)