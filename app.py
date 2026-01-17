import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
motor = MotorAnalise()

st.title("🏛️ Terminal Hedge Fund - Inteligência Visual")

# --- CONSULTA ---
ticker_raw = st.text_input("Consultar Ativo (Ex: PETR4, BBAS3, BTC-USD):", value="PETR4").upper().strip()
ticker = f"{ticker_raw}.SA" if "-" not in ticker_raw and "." not in ticker_raw and any(c.isdigit() for c in ticker_raw) else ticker_raw

if ticker:
    try:
        df_raw = yf.download(ticker, period="4y", progress=False)
        if not df_raw.empty:
            # Limpeza e Padronização
            if isinstance(df_raw.columns, pd.MultiIndex): df_raw.columns = df_raw.columns.get_level_values(0)
            df_raw.columns = [str(c).lower() for c in df_raw.columns]
            df_proc = df_raw.reset_index()
            df_proc.columns = [str(c).lower() for c in df_proc.columns]
            
            res = motor.analisar(df_proc)
            
            if res:
                # 1. VEREDITO EM DESTAQUE
                st.markdown("---")
                color_hex = {"green": "#00CC96", "red": "#FF4B4B", "yellow": "#FFA500", "blue": "#1F77B4", "gray": "#808080"}
                cor = color_hex.get(res['cor_sinal'], "#FFFFFF")
                st.markdown(f"<h2 style='color:{cor};'>🎯 Veredito: {res['recomendacao']}</h2>", unsafe_allow_html=True)
                
                # 2. MÉTRICAS RÁPIDAS
                c1, c2, c3, c4 = st.columns(4)
                moeda = "R$" if ".SA" in ticker else "$"
                c1.metric("Preço Atual", f"{moeda} {res['preco']:,.2f}")
                c2.metric("Tendência", res['tendencia'])
                c3.metric("RSI 14p", res['rsi_14'])
                c4.metric("RSI 252p", res['rsi_252'])

                # 3. GRÁFICO OPERACIONAL (PLOTLY)
                st.subheader("📈 Gráfico de Sinais")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='white')))
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'].rolling(252).mean(), name="Média 252", line=dict(color='orange', dash='dot')))
                
                # Adicionando Linhas de Sinal no Gráfico
                fig.add_hline(y=res['resistencia'], line_dash="dash", line_color="yellow", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=res['suporte'], line_dash="dash", line_color="cyan", annotation_text="SUPORTE")
                fig.add_hline(y=res['stop_loss'], line_color="#FF4B4B", line_width=2, annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="#00CC96", line_width=2, annotation_text="STOP GAIN")
                
                fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0,r=0,b=0,t=30))
                st.plotly_chart(fig, use_container_width=True)

                # 4. TABELAS DE EXECUÇÃO (O QUE TINHA SUMIDO)
                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    st.subheader("🛡️ Gestão de Risco")
                    st.error(f"**STOP LOSS:** {moeda} {res['stop_loss']:,.2f}")
                    st.success(f"**STOP GAIN:** {moeda} {res['stop_gain']:,.2f}")
                    st.info(f"**ALVO MÉDIA 252:** {moeda} {res['ma252']:,.2f}")
                
                with col_b:
                    st.subheader("🚧 Barreiras de Preço")
                    st.warning(f"**RESISTÊNCIA:** {moeda} {res['resistencia']:,.2f}")
                    st.info(f"**SUPORTE:** {moeda} {res['suporte']:,.2f}")
                
                with col_c:
                    st.subheader("📐 Níveis Fibonacci")
                    for k, v in res['fibonacci'].items():
                        st.write(f"**{k}:** {moeda} {v:,.2f}")

    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")