import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from motor import MotorAnalise
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
motor = MotorAnalise()

st.title("🏛️ Terminal Hedge Fund - Inteligência Visual & Fundamentalista")

# --- CONSULTA ---
ticker_raw = st.text_input("Consultar Ativo (Ex: PETR4, BBAS3, AAPL, BTC-USD):", value="PETR4").upper().strip()
ticker = f"{ticker_raw}.SA" if "-" not in ticker_raw and "." not in ticker_raw and any(c.isdigit() for c in ticker_raw) else ticker_raw

if ticker:
    try:
        # Busca Dados de Preço e Fundamentos
        ticker_obj = yf.Ticker(ticker)
        df_raw = ticker_obj.history(period="4y")
        info = ticker_obj.info # Puxa dados para Valuation
        
        if not df_raw.empty:
            # Padronização de Colunas
            df_proc = df_raw.reset_index()
            df_proc.columns = [str(c).lower() for c in df_proc.columns]
            
            # Executa Análise no Motor
            res = motor.analisar(df_proc, info)
            
            if res:
                # 1. VEREDITO E RECOMENDAÇÃO
                st.markdown("---")
                color_hex = {"green": "#00CC96", "red": "#FF4B4B", "yellow": "#FFA500", "blue": "#1F77B4", "gray": "#808080"}
                cor = color_hex.get(res['cor_sinal'], "#FFFFFF")
                st.markdown(f"<h2 style='color:{cor};'>🎯 Veredito: {res['recomendacao']}</h2>", unsafe_allow_html=True)
                
                # 2. MÉTRICAS RÁPIDAS (MARKET DATA)
                c1, c2, c3, c4 = st.columns(4)
                moeda = "R$" if ".SA" in ticker else "$"
                c1.metric("Preço Atual", f"{moeda} {res['preco']:,.2f}")
                c2.metric("Tendência Macro", res['tendencia'])
                c3.metric("RSI Tático (14p)", res['rsi_14'])
                c4.metric("Upside Projetado", f"{res['upside_longo_prazo']}%")

                # 3. VALUATIONS (GRAHAM, BAZIN, GORDON)
                st.subheader("💎 Valuation & Preço Justo")
                v1, v2, v3 = st.columns(3)
                v1.metric("Graham", f"{moeda} {res['val_graham']:,.2f}", help="Baseado em Lucro e Valor Patrimonial")
                v2.metric("Bazin", f"{moeda} {res['val_bazin']:,.2f}", help="Baseado em Dividend Yield de 6%")
                v3.metric("Gordon", f"{moeda} {res['val_gordon']:,.2f}", help="Baseado em Fluxo de Dividendos Futuros")

                # 4. GRÁFICO OPERACIONAL (PLOTLY)
                st.markdown("---")
                st.subheader("📈 Gráfico de Sinais e Médias")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='white')))
                fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'].rolling(252).mean(), name="Média 252", line=dict(color='orange', dash='dot')))
                
                # Linhas de Sinal no Gráfico
                fig.add_hline(y=res['resistencia'], line_dash="dash", line_color="yellow", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=res['suporte'], line_dash="dash", line_color="cyan", annotation_text="SUPORTE")
                fig.add_hline(y=res['stop_loss'], line_color="#FF4B4B", line_width=2, annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="#00CC96", line_width=2, annotation_text="STOP GAIN")
                
                fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0,r=0,b=0,t=30))
                st.plotly_chart(fig, use_container_width=True)

                # 5. EXECUÇÃO TÁTICA E RISCO
                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    st.subheader("🛡️ Gestão de Risco")
                    st.error(f"**STOP LOSS:** {moeda} {res['stop_loss']:,.2f}")
                    st.success(f"**STOP GAIN:** {moeda} {res['stop_gain']:,.2f}")
                    st.info(f"**ALVO MÉDIA 252:** {moeda} {res['ma252']:,.2f}")
                
                with col_b:
                    st.subheader("🚧 Barreiras de Preço")
                    st.warning(f"**MÁXIMA ANUAL:** {moeda} {res['resistencia']:,.2f}")
                    st.info(f"**MÍNIMA ANUAL:** {moeda} {res['suporte']:,.2f}")
                
                with col_c:
                    st.subheader("📐 Níveis Fibonacci")
                    for k, v in res['fibonacci'].items():
                        st.write(f"**{k}:** {moeda} {v:,.2f}")

        else:
            st.error("Ativo não encontrado ou sem dados históricos.")
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")