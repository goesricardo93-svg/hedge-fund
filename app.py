import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")

# Inicializa o Motor
motor = MotorAnalise()

# --- TÍTULO ---
st.title("🏛️ Terminal Hedge Fund - Inteligência Visual")

# --- CONSULTA DE ATIVO ---
ticker_raw = st.text_input("Consultar Ativo (Ex: PETR4, BBAS3, BTC-USD):", value="PETR4").upper().strip()

# Correção automática para B3
ticker = ticker_raw
if "-" not in ticker_raw and "." not in ticker_raw and any(c.isdigit() for c in ticker_raw):
    ticker = f"{ticker_raw}.SA"

if ticker:
    try:
        # Busca dados
        df_raw = yf.download(ticker, period="4y", progress=False)
        
        if not df_raw.empty:
            # Padronização de Colunas (Evita erro de Tupla e Date)
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_raw.columns = df_raw.columns.get_level_values(0)
            df_raw.columns = [str(c).lower() for c in df_raw.columns]
            df_proc = df_raw.reset_index()
            df_proc.columns = [str(c).lower() for c in df_proc.columns]
            
            res = motor.analisar(df_proc)
            
            if res:
                # 1. VEREDITO OBJETIVO
                st.markdown("---")
                color_hex = {"green": "#00CC96", "red": "#FF4B4B", "yellow": "#FFA500", "blue": "#1F77B4", "gray": "#808080"}
                cor = color_hex.get(res['cor_sinal'], "#FFFFFF")
                st.markdown(f"<h2 style='color:{cor};'>🎯 Veredito: {res['recomendacao']}</h2>", unsafe_allow_html=True)
                
                # 2. MÉTRICAS
                c1, c2, c3, c4 = st.columns(4)
                moeda = "R$" if ".SA" in ticker else "$"
                c1.metric("Preço Atual", f"{moeda} {res['preco']:,.2f}")
                c2.metric("Tendência (252p)", res['tendencia'])
                c3.metric("RSI 14p", res['rsi_14'])
                c4.metric("RSI 252p", res['rsi_252'])

                # 3. GRÁFICO OPERACIONAL
                st.subheader(f"📈 Gráfico Operacional: {ticker}")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='white')))
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'].rolling(252).mean(), name="Média 252", line=dict(color='orange', dash='dot')))
                
                # Linhas de Sinal
                fig.add_hline(y=res['resistencia'], line_dash="dash", line_color="yellow", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=res['suporte'], line_dash="dash", line_color="cyan", annotation_text="SUPORTE")
                fig.add_hline(y=res['stop_loss'], line_color="#FF4B4B", line_width=2, annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="#00CC96", line_width=2, annotation_text="STOP GAIN")
                
                fig.update_layout(template="plotly_dark", height=600)
                st.plotly_chart(fig, use_container_width=True)

                # 4. DETALHES
                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.subheader("🛡️ Risco")
                    st.write(f"**STOP LOSS:** {res['stop_loss']}")
                    st.write(f"**STOP GAIN:** {res['stop_gain']}")
                with col_b:
                    st.subheader("🚧 Barreiras")
                    st.write(f"**RESISTÊNCIA:** {res['resistencia']}")
                    st.write(f"**SUPORTE:** {res['suporte']}")
                with col_c:
                    st.subheader("📐 Fibonacci")
                    for k, v in res['fibonacci'].items():
                        st.write(f"**{k}:** {v}")
        else:
            st.error("Ativo não encontrado.")
    except Exception as e:
        st.error(f"Erro: {e}")