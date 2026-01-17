import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 1. SETUP E CARTEIRA INTEGRAL (31 ATIVOS)
st.set_page_config(page_title="Hedge Fund Ricardo - Terminal Pro", layout="wide")

if 'meus_ativos' not in st.session_state:
    st.session_state.meus_ativos = pd.DataFrame([
        {"Ticker": "ALZR11.SA", "Qtd": 100, "PM": 10.81}, {"Ticker": "BBAS3.SA", "Qtd": 1703, "PM": 24.48},
        {"Ticker": "BBSE3.SA", "Qtd": 55, "PM": 35.64}, {"Ticker": "BTCI11.SA", "Qtd": 502, "PM": 10.16},
        {"Ticker": "BTLG11.SA", "Qtd": 60, "PM": 98.50}, {"Ticker": "CCME11.SA", "Qtd": 152, "PM": 8.55},
        {"Ticker": "CMIG4.SA", "Qtd": 1644, "PM": 11.12}, {"Ticker": "CPLE3.SA", "Qtd": 617, "PM": 9.64},
        {"Ticker": "CPSH11.SA", "Qtd": 169, "PM": 10.10}, {"Ticker": "CPTS11.SA", "Qtd": 276, "PM": 8.52},
        {"Ticker": "CXSE3.SA", "Qtd": 800, "PM": 14.20}, {"Ticker": "EQTL3.SA", "Qtd": 200, "PM": 30.21},
        {"Ticker": "HGCR11.SA", "Qtd": 20, "PM": 95.81}, {"Ticker": "HGLG11.SA", "Qtd": 20, "PM": 158.03},
        {"Ticker": "ITSA4.SA", "Qtd": 1174, "PM": 9.63}, {"Ticker": "IVVB11.SA", "Qtd": 6, "PM": 366.97},
        {"Ticker": "KLBN4.SA", "Qtd": 2323, "PM": 3.63}, {"Ticker": "KNCR11.SA", "Qtd": 27, "PM": 103.11},
        {"Ticker": "KNHF11.SA", "Qtd": 15, "PM": 93.23}, {"Ticker": "KNRI11.SA", "Qtd": 30, "PM": 152.49},
        {"Ticker": "KNSC11.SA", "Qtd": 373, "PM": 8.78}, {"Ticker": "KNUQ11.SA", "Qtd": 16, "PM": 102.45},
        {"Ticker": "PETR4.SA", "Qtd": 900, "PM": 32.07}, {"Ticker": "SAPR11.SA", "Qtd": 300, "PM": 37.97},
        {"Ticker": "TAEE4.SA", "Qtd": 1000, "PM": 11.36}, {"Ticker": "VALE3.SA", "Qtd": 152, "PM": 54.79},
        {"Ticker": "VGIR11.SA", "Qtd": 296, "PM": 9.58}, {"Ticker": "VISC11.SA", "Qtd": 16, "PM": 109.70},
        {"Ticker": "XPCA11.SA", "Qtd": 110, "PM": 8.77}, {"Ticker": "XPLG11.SA", "Qtd": 26, "PM": 102.31},
        {"Ticker": "XPML11.SA", "Qtd": 10, "PM": 106.05}
    ])

# 2. FUNÇÕES TÉCNICAS
@st.cache_data(ttl=600)
def load_data(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

def veredito_fii(row):
    try:
        p_vp = row.get('P/VP_N', 0)
        # Tenta pegar a coluna de vacância mesmo se o nome variar no CSV
        vac = row.get('VACANCIA FISICA', row.get('VACANCIA', 0))
        if p_vp < 0.95: return "🔥 OPORTUNIDADE"
        if p_vp > 1.05: return "⚠️ CARO"
        return "✅ MANTÉM"
    except: return "---"

def recomendacao_final(tk, preco, pm, info):
    dy = info.get('dividendYield', 0) or 0
    teto = (preco * dy) / 0.06 if dy > 0 else 0
    if preco < pm and (teto == 0 or preco < teto): return "💰 COMPRAR (Abaixo PM)"
    if teto > 0 and preco > teto * 1.15: return "⚠️ VENDER / CARO"
    return "✅ MANTÉM"

# 3. INTERFACE
st.sidebar.title("Comando Ricardo")
q_tk = st.sidebar.text_input("Ticker:", value="BBSE3").strip().upper()
tk = q_tk if "." in q_tk else f"{q_tk}.SA"

t1, t2, t3, t4 = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 CARTEIRA"])

with t1:
    hist, info = load_data(tk)
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, tk)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Preço", f"R$ {r['preco']:.2f}")
        c2.metric("Alvo", f"R$ {r['stop_gain']:.2f}")
        c3.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
        c4.metric("Margem Líq.", f"{info.get('profitMargins', 0)*100:.1f}%")
        c5.metric("P. Bazin", f"R$ {r['p_bazin']:.2f}")
        
        st.subheader(f"Veredito: :{r['cor']}[{r['recomendacao']}]")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Preço'))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_gain']]*len(hist), name='ALVO', line=dict(dash='dash', color='gold')))
        st.plotly_chart(fig, use_container_width=True)

with t2:
    st.header("Análise de FIIs")
    try:
        df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="latin-1")
        # Limpeza para evitar erro de index
        df.columns = [c.strip().upper() for c in df.columns]
        df['P/VP_N'] = pd.to_numeric(df['P/VP'].astype(str).str.replace(',','.'), errors='coerce')
        df['RECOMENDAÇÃO'] = df.apply(veredito_fii, axis=1)
        st.dataframe(df[['TICKER', 'RECOMENDAÇÃO', 'P/VP']].head(20))
    except Exception as e: st.error(f"Erro no CSV: {e}")

with t4:
    st.header("Minha Carteira - Gestão de Ativos")
    df_edit = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic")
    if st.button("🚀 Analisar e Gerar Recomendações"):
        res = []
        for _, row in df_edit.iterrows():
            obj = yf.Ticker(row['Ticker'])
            p_atual = obj.fast_info['last_price']
            rec = recomendacao_final(row['Ticker'], p_atual, row['PM'], obj.info)
            res.append({"Atual": p_atual, "Recomendação": rec, "Lucro/Prej": (p_atual - row['PM']) * row['Qtd']})
        
        df_f = pd.concat([df_edit, pd.DataFrame(res)], axis=1)
        st.dataframe(df_f.style.applymap(lambda x: 'color: green' if 'COMPRAR' in str(x) else ('color: red' if 'VENDER' in str(x) else ''), subset=['Recomendação']))