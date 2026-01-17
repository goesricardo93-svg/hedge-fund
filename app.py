import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Ricardo - Hedge Fund", layout="wide")

# --- LÓGICA DE VEREDITO SEGURO 360º (FIIs) ---
def gerar_veredito_seguro_fii(row):
    try:
        pvp = row['P/VP_N']
        dy = row['DY_N']
        margem = row['Margem Seg. (%)']
        segmento = str(row.get('SEGMENTO', 'Indefinido')).upper()
        vacancia = row.get('VACANCIA_N', 0)
        imoveis = row.get('IMOVEIS_N', 0)
        
        if "PAPEL" in segmento or "TÍTULOS" in segmento:
            if 0.97 <= pvp <= 1.00: return "🔥 COMPRA SEGURA (Papel)"
            return "🟡 ANALISAR (Risco de Crédito)"
        else:
            if vacancia > 15: return "❌ EVITAR (Vacância Alta)"
            if imoveis > 0 and imoveis < 5: return "⚠️ RISCO (Poucos Imóveis)"
            if pvp < 0.95 and margem > 5: return "🏢 OPORTUNIDADE (Tijolo Barato)"
            return "✅ COMPRA (Valor Patrimonial)"
    except: return "Analisando..."

@st.cache_data(ttl=600)
def carregar_dados_completos(ticker):
    try:
        t = yf.Ticker(ticker)
        data = t.history(period="2y")
        return data, t.info
    except: return pd.DataFrame(), {}

def formatar_ticker(t):
    t = t.strip().upper()
    if not t: return "BBSE3.SA"
    return t if "." in t else f"{t}.SA"

# --- INTERFACE ---
st.sidebar.header("🕹️ Comando Central")
ticker_raw = st.sidebar.text_input("Ticker Ação/ETF:", value="BBSE3")
ticker_final = formatar_ticker(ticker_raw)

tab1, tab2, tab3 = st.tabs(["📊 Inteligência de Mercado", "🏙️ Scanner FIIs - SEGURANÇA", "🛡️ Gestão PGBL"])

# --- ABA 1: AÇÕES (Com Filtros de Dívida e Eficiência) ---
with tab1:
    data, info = carregar_dados_completos(ticker_final)
    if not data.empty:
        res = MotorAnalise().analisar(data, info, ticker_final)
        if res:
            # Filtro Adicional de Segurança para Ações
            divida_ok = info.get('debtToEbitda', 0) < 3 if info.get('debtToEbitda') else True
            roe_ok = info.get('returnOnEquity', 0) > 0.10 if info.get('returnOnEquity') else True
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            
            # Veredito com trava de segurança
            veredito_final = res['recomendacao']
            if not divida_ok: veredito_final = "⚠️ ALERTA (Dívida Alta)"
            
            st.markdown(f"### Veredito: :{res['cor']}[{veredito_final}]")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=res['precos_serie'].values, name='PREÇO', line=dict(color='#29b5e8', width=3)))
            fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['suporte']]*len(res['precos_serie']), name='🛡️ SUPORTE', line=dict(color='#2ecc71', dash='dash')))
            fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['stop_loss']]*len(res['precos_serie']), name='🚫 STOP LOSS', line=dict(color='#e74c3c', dash='dot')))
            fig.update_layout(height=400, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"), margin=dict(l=0,r=0,b=0,t=50))
            st.plotly_chart(fig, use_container_width=True)

            col_val, col_risk = st.columns(2)
            with col_val:
                st.subheader("🏛️ Valuation & Saúde")
                st.write(f"**Graham:** R$ {res['p_graham']:.2f} | **Bazin:** R$ {res['p_bazin']:.2f}")
                st.write(f"**Dívida/EBITDA:** {info.get('debtToEbitda', 'N/A')} (Ideal < 3)")
                st.write(f"**ROE:** {info.get('returnOnEquity', 0)*100:.1f}% (Ideal > 10%)")

# --- ABA 2: SCANNER FIIS (Segurança Máxima) ---
with tab2:
    st.header("🏙️ Scanner FII - Stress Test")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding