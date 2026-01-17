import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
motor = MotorAnalise()

st.title("🏛️ Terminal Hedge Fund - Inteligência Total")

# Barra Lateral para Configurações de Capital
st.sidebar.header("⚙️ Gestão de Banca")
capital_total = st.sidebar.number_input("Seu Capital Total (R$):", value=50000.0, step=1000.0)
risco_por_op = st.sidebar.slider("Risco Máximo por Operação (%):", 0.5, 5.0, 1.0) / 100

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
                # 1. VEREDITO
                st.markdown("---")
                c_map = {"green": "#00CC96", "red": "#FF4B4B", "blue": "#1F77B4", "yellow": "#FFA500", "gray": "#808080"}
                st.markdown(f"<h2 style='text-align: center; color:{c_map.get(res['cor_sinal'], '#FFF')};'>🎯 Veredito: {res['recomendacao']}</h2>", unsafe_allow_html=True)

                # 2. VALUATIONS E PREÇOS
                v1, v2, v3, v4, v5 = st.columns(5)
                v1.metric("Graham", f"R$ {res['val_graham']}")
                v2.metric("Bazin", f"R$ {res['val_bazin']}")
                v3.metric("Gordon", f"R$ {res['val_gordon']}")
                v4.metric("PREÇO TETO", f"R$ {res['preco_teto']}", delta=f"{res['upside']}%")
                v5.metric("PREÇO ATUAL", f"R$ {res['preco']}")

                # 3. CALCULADORA DE LOTE (NOVIDADE)
                st.markdown("---")
                st.subheader("📏 Calculadora de Exposição (Gerenciamento de Risco)")
                
                distancia_stop = res['preco'] - res['stop_loss']
                perda_maxima_financeira = capital_total * risco_por_op
                
                if distancia_stop > 0:
                    lote_sugerido = int(perda_maxima_financeira / distancia_stop)
                    financeiro_total = lote_sugerido * res['preco']
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Qtd. de Ações (Lote)", f"{lote_sugerido} papéis")
                    c2.metric("Valor do Investimento", f"R$ {financeiro_total:,.2f}")
                    c3.metric("Risco Caso Stopado", f"R$ {perda_maxima_financeira:,.2f}", delta="-1% do Capital", delta_color="inverse")
                    
                    st.warning(f"⚠️ Se o preço cair para **R$ {res['stop_loss']}**, você vende tudo e perde apenas R$ {perda_maxima_financeira:,.2f} do seu patrimônio de R$ {capital_total:,.2f}.")
                else:
                    st.error("Preço atual está abaixo do suporte. Não há margem para cálculo de lote.")

                # 4. GRÁFICO E TABELAS
                st.markdown("---")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_p['date'], y=df_p['close'], name="Preço", line=dict(color='#00f2ff', width=2)))
                fig.add_hline(y=res['stop_loss'], line_color="red", line_dash="dash", annotation_text="STOP LOSS (SUPORTE)")
                fig.add_hline(y=res['stop_gain'], line_color="green", line_dash="dash", annotation_text="ALVO (TETO)")
                fig.update_layout(template="plotly_dark", height=500)
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Erro: {str(e)}")