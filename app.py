import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
st.title("🏛️ Terminal Hedge Fund - Inteligência Visual")

motor = MotorAnalise()

# Entrada de Ticker com Auto-Correção B3
ticker_raw = st.text_input("Consultar Ativo (Ex: PETR4, BBAS3, BTC-USD):", value="PETR4").upper().strip()
ticker = f"{ticker_raw}.SA" if "-" not in ticker_raw and "." not in ticker_raw and any(c.isdigit() for c in ticker_raw) else ticker_raw

if ticker:
    try:
        df = yf.download(ticker, period="4y", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).lower() for c in df.columns]
            df = df.reset_index()
            df.columns = [str(c).lower() for c in df.columns]
            
            res = motor.analisar(df)
            
            if res:
                # 1. MÉTRICAS DE TOPO
                c1, c2, c3, c4 = st.columns(4)
                moeda = "R$" if ".SA" in ticker else "$"
                c1.metric("Preço Atual", f"{moeda} {res['preco']:,.2f}")
                c2.metric("Tendência (252p)", res['tendencia'])
                c3.metric("RSI 14p", res['rsi_14'])
                c4.metric("RSI 252p", res['rsi_252'])

                # 2. O GRÁFICO OPERACIONAL (PLOTLY)
                st.subheader(f"📈 Gráfico Operacional: {ticker}")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['date'], y=df['close'], name="Preço", line=dict(color='#ffffff', width=2)))
                fig.add_trace(go.Scatter(x=df['date'], y=df['close'].rolling(252).mean(), name="Média 252", line=dict(color='orange', dash='dot')))
                
                # LINHAS HORIZONTAIS
                fig.add_hline(y=res['resistencia'], line_dash="dash", line_color="yellow", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=res['suporte'], line_dash="dash", line_color="cyan", annotation_text="SUPORTE")
                fig.add_hline(y=res['stop_loss'], line_color="#FF4B4B", line_width=2, annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="#00CC96", line_width=2, annotation_text="STOP GAIN")
                
                for nivel, valor in res['fibonacci'].items():
                    fig.add_hline(y=valor, line_color="gray", line_width=1, line_dash="dot", annotation_text=f"Fib {nivel}")

                fig.update_layout(template="plotly_dark", height=600)
                st.plotly_chart(fig, use_container_width=True)

                # 3. CARDS DE INFORMAÇÃO
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
        st.error(f"Erro no processamento: {str(e)}")