import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
motor = MotorAnalise()

st.title("🏛️ Terminal Hedge Fund - Inteligência Total")

ticker_raw = st.text_input("Consultar Ativo (Ex: PETR4, BBAS3, AAPL):", value="PETR4").upper().strip()
ticker = f"{ticker_raw}.SA" if "-" not in ticker_raw and "." not in ticker_raw and any(c.isdigit() for c in ticker_raw) else ticker_raw

if ticker:
    try:
        obj = yf.Ticker(ticker)
        df = obj.history(period="4y")
        
        if not df.empty:
            df_proc = df.reset_index()
            df_proc.columns = [str(c).lower() for c in df_proc.columns]
            
            # Passa o 'obj.info' para o motor calcular Valuation
            res = motor.analisar(df_proc, obj.info)
            
            if res:
                # 1. VEREDITO
                st.markdown("---")
                color_map = {"green": "#00CC96", "red": "#FF4B4B", "blue": "#1F77B4", "yellow": "#FFA500", "gray": "#808080"}
                cor = color_map.get(res['cor_sinal'], "#FFFFFF")
                st.markdown(f"<h2 style='color:{cor};'>🎯 Veredito: {res['recomendacao']}</h2>", unsafe_allow_html=True)

                # 2. MÉTRICAS E VALUATION
                st.subheader("💎 Valuation e Projeção")
                v1, v2, v3, v4 = st.columns(4)
                v1.metric(" Graham", f"R$ {res['val_graham']}")
                v2.metric(" Bazin", f"R$ {res['val_bazin']}")
                v3.metric(" Gordon", f"R$ {res['val_gordon']}")
                v4.metric("Upside Longo Prazo", f"{res['upside_longo_prazo']}%")

                # 3. GRÁFICO OPERACIONAL
                st.markdown("---")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='white')))
                fig.add_hline(y=res['stop_loss'], line_color="red", line_dash="dash", annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="green", line_dash="dash", annotation_text="STOP GAIN")
                fig.update_layout(template="plotly_dark", height=500)
                st.plotly_chart(fig, use_container_width=True)

                # 4. TABELA DE RISCO
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("🛡️ Gestão de Risco")
                    st.write(f"**STOP LOSS:** R$ {res['stop_loss']}")
                    st.write(f"**STOP GAIN:** R$ {res['stop_gain']}")
                with col2:
                    st.subheader("📐 Fibonacci")
                    st.write(res['fibonacci'])

    except Exception as e:
        st.error(f"Erro: {str(e)}")