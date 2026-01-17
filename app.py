import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Ricardo - Hedge Fund", layout="wide")

# --- LÓGICA DE ANÁLISE SEGURO 360º ---
def gerar_veredito_seguro(row):
    try:
        pvp = row['P/VP_N']
        dy = row['DY_N']
        margem = row['Margem Seg. (%)']
        segmento = str(row['SEGMENTO']).upper()
        
        if "PAPEL" in segmento or "TÍTULOS" in segmento:
            if 0.97 <= pvp <= 1.00:
                return "🔥 COMPRA SEGURA (Papel Conservador)"
            else:
                return "🟡 ANALISAR (Risco de Crédito/Ágio)"
        else: # Tijolo (Logística, Shoppings, Lajes)
            if pvp < 0.96 and margem > 5:
                return "🏢 OPORTUNIDADE (Tijolo Barato)"
            return "✅ COMPRA (Valor Patrimonial)"
    except:
        return "Analisando..."

@st.cache_data(ttl=600)
def carregar_dados_completos(ticker):
    try:
        data = yf.download(ticker, period="2y", progress=False)
        info = yf.Ticker(ticker).info
        return data, info
    except:
        return pd.DataFrame(), {}

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX"]: return f"{t}.L"
    return f"{t}.SA"

# --- INTERFACE ---
st.sidebar.header("🕹️ Comando Central")
ticker_raw = st.sidebar.text_input("Ticker Ação/ETF:", value="BBSE3")
ticker_final = formatar_ticker(ticker_raw)

tab1, tab2, tab3 = st.tabs(["📊 Inteligência de Mercado", "🏙️ Scanner FIIs", "🛡️ Gestão PGBL"])

# --- ABA 1: AÇÕES E ETFS ---
with tab1:
    try:
        data, info = carregar_dados_completos(ticker_final)
        if not data.empty:
            res = MotorAnalise().analisar(data, info, ticker_final)
            if res:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
                c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}" if res['preco_teto'] > 0 else "N/A", f"{res['upside']:.1f}%")
                c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
                c4.metric("Tendência", res['tendencia'])

                st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
                
                # Gráfico com Legendas Fixas
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=res['precos_serie'].values, name='PREÇO', line=dict(color='#29b5e8', width=3)))
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['suporte']]*len(res['precos_serie']), name='🛡️ SUPORTE', line=dict(color='#2ecc71', dash='dash')))
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['stop_loss']]*len(res['precos_serie']), name='🚫 STOP LOSS', line=dict(color='#e74c3c', dash='dot')))
                if res['preco_teto'] > 0:
                    fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['stop_gain']]*len(res['precos_serie']), name='🎯 ALVO', line=dict(color='#f1c40f', dash='dashdot')))

                fig.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5), margin=dict(l=0,r=0,b=0,t=50))
                st.plotly_chart(fig, use_container_width=True)

                col_val, col_tec, col_risk = st.columns(3)
                with col_val:
                    st.subheader("🏛️ Valuation")
                    st.write(f"**Graham:** R$ {res['p_graham']:.2f}"); st.write(f"**Bazin:** R$ {res['p_bazin']:.2f}"); st.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")
                with col_tec:
                    st.subheader("📈 Técnico")
                    st.write(f"**Suporte:** R$ {res['suporte']:.2f}"); st.write(f"**Resistência:** R$ {res['resistencia']:.2f}")
                with col_risk:
                    st.subheader("🛡️ Risco")
                    st.error(f"**Stop Loss:** R$ {res['stop_loss']:.2f}"); st.success(f"**Stop Gain:** R$ {res['stop_gain']:.2f}")
    except Exception as e:
        st.error