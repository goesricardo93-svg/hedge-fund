import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
st.title("🏛️ Terminal Hedge Fund - Inteligência Visual")

motor = MotorAnalise()

# --- CONSULTA ---
ticker_input = st.text_input("Consultar Ativo (Ex: PETR4, BBAS3, BTC-USD):", value="PETR4").upper().strip()
ticker = f"{ticker_input}.SA" if "-" not in ticker_input and "." not in ticker_input and any(c.isdigit() for c in ticker_input) else ticker_input

if ticker:
    try:
        df_raw = yf.download(ticker, period="4y", progress=False)
        if not df_raw.empty:
            # Padronização de Colunas
            if isinstance(df_raw.columns, pd.MultiIndex): df_raw.columns = df_raw.columns.get_level_values(0)
            df_raw.columns = [str(c).lower() for c in df_raw.columns]
            df_proc = df_raw.reset_index()
            
            res = motor.analisar(df_proc)
            
            if res:
                # 1. MÉTRICAS (IGUAL AO SEU PRINT)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {res['preco']:,.2f}" if ".SA" in ticker else f"$ {res['preco']:,.2f}")
                c2.metric("Tendência (252p)", res['tendencia'])
                c3.metric("RSI 14p", res['rsi_14'])
                c4.metric("RSI 252p", res['rsi_252'])

                st.markdown("---")

                # 2. GRÁFICO AVANÇADO COM LINHAS DE SUPORTE/STOP
                st.subheader(f"📈 Gráfico Operacional: {ticker}")
                
                fig = go.Figure()
                # Linha de Preço
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='white', width=2)))
                # Média 252
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'].rolling(252).mean(), name="Média 252", line=dict(color='orange', dash='dot')))
                
                # ADICIONANDO LINHAS HORIZONTAIS (OPERACIONAL)
                # Resistência e Suporte
                fig.add_hline(y=res['resistencia'], line_dash="dash", line_color="yellow", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=res['suporte'], line_dash="dash", line_color="cyan", annotation_text="SUPORTE")
                # Stops
                fig.add_hline(y=res['stop_loss'], line_color="red", line_width=2, annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="green", line_width=2, annotation_text="STOP GAIN")
                
                fig.update_layout(template="plotly_dark", height=600, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)

                # 3. CARDS INFORMATIVOS (MANTENDO O QUE VOCÊ GOSTOU)
                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.subheader("🛡️ Gestão de Risco")
                    st.error(f"STOP LOSS: {res['stop_loss']}")
                    st.success(f"STOP GAIN: {res['stop_gain']}")
                with col_b:
                    st.subheader("🚧 Barreiras Anuais")
                    st.warning(f"RESISTÊNCIA: {res['resistencia']}")
                    st.info(f"SUPORTE: {res['suporte']}")
                with col_c:
                    st.subheader("📐 Fibonacci (252p)")
                    for k, v in res['fibonacci'].items():
                        st.write(f"**{k}:** {v}")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")