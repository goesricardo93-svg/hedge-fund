import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
motor = MotorAnalise()

st.title("🏛️ Terminal Hedge Fund - Inteligência Visual")

ticker_raw = st.text_input("Consultar Ativo:", value="PETR4").upper().strip()
ticker = f"{ticker_raw}.SA" if "-" not in ticker_raw and "." not in ticker_raw and any(c.isdigit() for c in ticker_raw) else ticker_raw

if ticker:
    try:
        df_raw = yf.download(ticker, period="4y", progress=False)
        if not df_raw.empty:
            if isinstance(df_raw.columns, pd.MultiIndex): df_raw.columns = df_raw.columns.get_level_values(0)
            df_raw.columns = [str(c).lower() for c in df_raw.columns]
            df_proc = df_raw.reset_index()
            df_proc.columns = [str(c).lower() for c in df_proc.columns]
            
            res = motor.analisar(df_proc)
            
            if res:
                # 1. VEREDITO
                st.markdown("---")
                color_hex = {"green": "#00CC96", "red": "#FF4B4B", "yellow": "#FFA500", "blue": "#1F77B4", "gray": "#808080"}
                cor = color_hex.get(res['cor_sinal'], "#FFFFFF")
                st.markdown(f"<h2 style='color:{cor};'>🎯 Veredito: {res['recomendacao']}</h2>", unsafe_allow_html=True)
                
                # 2. MÉTRICAS
                c1, c2, c3, c4 = st.columns(4)
                moeda = "R$" if ".SA" in ticker else "$"
                c1.metric("Preço Atual", f"{moeda} {res['preco']:,.2f}")
                c2.metric("Tendência", res['tendencia'])
                c3.metric("RSI 14p", res['rsi_14'])
                c4.metric("RSI 252p", res['rsi_252'])

                # 3. GRÁFICO OPERACIONAL
                st.subheader("📈 Gráfico Operacional")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='white')))
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'].rolling(252).mean(), name="Média 252", line=dict(color='orange', dash='dot')))
                
                # Linhas de Suporte, Resistência e Stops
                fig.add_hline(y=res['resistencia'], line_dash="dash", line_color="yellow", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=res['suporte'], line_dash="dash", line_color="cyan", annotation_text="SUPORTE")
                fig.add_hline(y=res['stop_loss'], line_color="#FF4B4B", line_width=2, annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="#00CC96", line_width=2, annotation_text="STOP GAIN")
                
                fig.update_layout(template="plotly_dark", height=500)
                st.plotly_chart(fig, use_container_width=True)

                # 4. TABELA DE FIBONACCI
                st.markdown("---")
                st.subheader("📐 Níveis de Fibonacci")
                st.write(res['fibonacci'])
        else:
            st.error("Ativo não encontrado.")
    except Exception as e:
        st.error(f"Erro: {str(e)}")