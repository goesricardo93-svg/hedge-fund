import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Ricardo - Hedge Fund", layout="wide")

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

st.sidebar.header("🕹️ Comando Central")
ticker_raw = st.sidebar.text_input("Ticker:", value="BBSE3")
ticker_final = formatar_ticker(ticker_raw)

aba1, aba2, aba3 = st.tabs(["📊 Inteligência de Mercado", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with aba1:
    try:
        data, info = carregar_dados_completos(ticker_final)
        if not data.empty:
            res = MotorAnalise().analisar(data, info, ticker_final)
            
            if res:
                # --- DASHBOARD SUPERIOR ---
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
                c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}" if res['preco_teto'] > 0 else "N/A", f"{res['upside']:.1f}%")
                c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
                c4.metric("Tendência", res['tendencia'])

                st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
                
                # --- GRÁFICO PLOTLY COM LEGENDAS FIXAS ---
                fig = go.Figure()

                # Linha Principal de Preço
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=res['precos_serie'].values, 
                                         name='PREÇO ATUAL', line=dict(color='#29b5e8', width=3)))
                
                # Linha de Suporte (Verde Tracejada)
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['suporte']]*len(res['precos_serie']), 
                                         name='🛡️ SUPORTE ANUAL', line=dict(color='#2ecc71', width=2, dash='dash')))
                
                # Linha de Stop Loss (Vermelha Pontilhada)
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['stop_loss']]*len(res['precos_serie']), 
                                         name='🚫 STOP LOSS (SAÍDA)', line=dict(color='#e74c3c', width=2, dash='dot')))
                
                # Linha de Stop Gain/Alvo (Dourada)
                if res['preco_teto'] > 0:
                    fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['stop_gain']]*len(res['precos_serie']), 
                                             name='🎯 ALVO / STOP GAIN', line=dict(color='#f1c40f', width=2, dash='dashdot')))

                # Ajustes de Layout para Legendagem Visível
                fig.update_layout(
                    height=500,
                    margin=dict(l=10, r=10, t=50, b=10),
                    legend=dict(
                        orientation="h",       # Legenda Horizontal
                        yanchor="bottom",      # Ancorada embaixo
                        y=1.02,                # Acima do gráfico
                        xanchor="center",
                        x=0.5,
                        font=dict(size=14)     # Fonte maior para leitura direta
                    ),
                    hovermode="x unified"
                )
                
                st.plotly_chart(fig, use_container_width=True)

                # --- BLOCOS DE ANALISE DETALHADA ---
                col_val, col_tec, col_risk = st.columns(3)
                with col_val:
                    st.subheader("🏛️ Valuation")
                    st.write(f"**Graham:** R$ {res['p_graham']:.2f}")
                    st.write(f"**Bazin:** R$ {res['p_bazin']:.2f}")
                    st.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")
                with col_tec:
                    st.subheader("📈 Técnico")
                    st.write(f"**Média 252:** R$ {res['ma252']:.2f}")
                    st.write(f"**Resistência:** R$ {res['resistencia']:.2f}")
                with col_risk:
                    st.subheader("🛡️ Gestão de Risco")
                    st.error(f"**Stop Loss:** R$ {res['stop_loss']:.2f}")
                    st.success(f"**Stop Gain:** R$ {res['stop_gain']:.2f}")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")

# Abas 2 e 3 (Scanner e PGBL) permanecem as mesmas
with aba2:
    st.header("🏙️ Scanner de FIIs")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        def cl(n): return pd.to_numeric(df_fii[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
        df_fii['P/VP_N'] = cl('P/VP'); df_fii['LIQ_N'] = cl('LIQUIDEZ MEDIA DIARIA'); df_fii['PRECO_N'] = cl('PRECO')
        f = df_fii[(df_fii['P/VP_N'] >= 0.85) & (df_fii['P/VP_N'] <= 1.0) & (df_fii['LIQ_N'] >= 800000)].copy()
        f['Stop Loss'] = f['PRECO_N'] * 0.92
        st.dataframe(f[['TICKER', 'PRECO', 'P/VP', 'DY', 'Stop Loss']])
    except:
        st.info("Carregue o CSV de FIIs na pasta.")

with aba3:
    r = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Teto Isenção PGBL (12%)", f"R$ {r*0.12:.2f}")