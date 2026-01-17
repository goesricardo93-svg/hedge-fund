import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
motor = MotorAnalise()

st.title("🏛️ Terminal Hedge Fund - Inteligência Total")

t_input = st.text_input("Consultar Ativo:", value="PETR4").upper().strip()
ticker = f"{t_input}.SA" if "-" not in t_input and "." not in t_input and any(c.isdigit() for c in t_input) else t_input

if ticker:
    try:
        t_obj = yf.Ticker(ticker)
        df = yf.download(ticker, period="4y", progress=False)
        
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df_p = df.reset_index()
            df_p.columns = [str(c).lower() for c in df_p.columns]
            
            res = motor.analisar(df_p, t_obj.info)
            
            if res:
                # 1. VEREDITO CENTRALIZADO
                st.markdown("---")
                c_map = {"green": "#00CC96", "red": "#FF4B4B", "blue": "#1F77B4", "yellow": "#FFA500", "gray": "#808080"}
                st.markdown(f"<h2 style='text-align: center; color:{c_map.get(res['cor_sinal'], '#FFF')};'>🎯 Veredito: {res['recomendacao']}</h2>", unsafe_allow_html=True)

                # 2. VALUATIONS E PREÇOS NO TOPO
                st.subheader("💎 Valuation e Comparativo de Preço")
                v1, v2, v3, v4, v5 = st.columns(5)
                v1.metric("Graham", f"R$ {res['val_graham']}")
                v2.metric("Bazin", f"R$ {res['val_bazin']}")
                v3.metric("Gordon", f"R$ {res['val_gordon']}")
                v4.metric("PREÇO TETO", f"R$ {res['preco_teto']}", delta=f"{res['upside']}%")
                v5.metric("PREÇO ATUAL", f"R$ {res['preco']}", delta_color="off")

                # 3. MÉTRICAS AUXILIARES (RSI VOLTOU AQUI)
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("RSI (Índice de Força)", res['rsi_14'], help="Abaixo de 30: Sobrevendido (Compra). Acima de 70: Sobrecomprado (Venda).")
                m2.metric("Tendência Macro", res['tendencia'])
                m3.metric("Média 252p", f"R$ {res['ma252']}")

                # 4. GRÁFICO OPERACIONAL
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_p['date'], y=df_p['close'], name="Preço", line=dict(color='#00f2ff', width=2)))
                fig.add_hline(y=res['stop_loss'], line_color="red", line_dash="dash", annotation_text="STOP LOSS")
                fig.add_hline(y=res['stop_gain'], line_color="green", line_dash="dash", annotation_text="STOP GAIN")
                
                fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0,r=0,b=0,t=20), hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                # 5. TABELAS DE PARÂMETROS
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.subheader("🛡️ Gestão de Risco")
                    st.error(f"**STOP LOSS:** R$ {res['stop_loss']}")
                    st.success(f"**STOP GAIN:** R$ {res['stop_gain']}")
                with col2:
                    st.subheader("🚧 Barreiras Anuais")
                    st.warning(f"**RESISTÊNCIA:** R$ {res['resistencia']}")
                    st.info(f"**SUPORTE:** R$ {res['suporte']}")
                with col3:
                    st.subheader("📐 Fibonacci")
                    for k, v in res['fibonacci'].items():
                        st.write(f"**{k}:** R$ {v}")

    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")