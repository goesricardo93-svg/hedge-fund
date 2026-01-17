import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 1. SETUP E CARTEIRA (31 ATIVOS)
st.set_page_config(page_title="Hedge Fund Ricardo | Terminal", layout="wide")

if 'meus_ativos' not in st.session_state:
    data = [
        ["ALZR11.SA", 100, 10.81], ["BBAS3.SA", 1703, 24.48], ["BBSE3.SA", 55, 35.64],
        ["BTCI11.SA", 502, 10.16], ["BTLG11.SA", 60, 98.50], ["CCME11.SA", 152, 8.55],
        ["CMIG4.SA", 1644, 11.12], ["CPLE3.SA", 617, 9.64], ["CPSH11.SA", 169, 10.10],
        ["CPTS11.SA", 276, 8.52], ["CXSE3.SA", 800, 14.20], ["EQTL3.SA", 200, 30.21],
        ["HGCR11.SA", 20, 95.81], ["HGLG11.SA", 20, 158.03], ["ITSA4.SA", 1174, 9.63],
        ["IVVB11.SA", 6, 366.97], ["KLBN4.SA", 2323, 3.63], ["KNCR11.SA", 27, 103.11],
        ["KNHF11.SA", 15, 93.23], ["KNRI11.SA", 30, 152.49], ["KNSC11.SA", 373, 8.78],
        ["KNUQ11.SA", 16, 102.45], ["PETR4.SA", 900, 32.07], ["SAPR11.SA", 300, 37.97],
        ["TAEE4.SA", 1000, 11.36], ["VALE3.SA", 152, 54.79], ["VGIR11.SA", 296, 9.58],
        ["VISC11.SA", 16, 109.70], ["XPCA11.SA", 110, 8.77], ["XPLG11.SA", 26, 102.31],
        ["XPML11.SA", 10, 106.05]
    ]
    st.session_state.meus_ativos = pd.DataFrame(data, columns=["Ticker", "Qtd", "PM"])

# 2. FUNÇÕES DE SUPORTE
@st.cache_data(ttl=600)
def load_market_data(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

def analise_360_fii(row):
    try:
        p_vp = row.get('P/VP_N', 0)
        vac = row.get('VAC_N', 0)
        seg = str(row.get('SEGMENTO', '')).upper()
        if "PAPEL" in seg:
            return "🔥 COMPRA" if 0.98 <= p_vp <= 1.01 else "🟡 OBSERVAR"
        return "🏢 OPORTUNIDADE" if vac < 10 and p_vp < 0.96 else "✅ MANTÉM"
    except: return "Analise Manual"

def rec_carteira(tk, preco, pm, info):
    dy = info.get('dividendYield', 0) or 0
    teto = (preco * dy) / 0.06 if dy > 0 else 0
    if preco < pm * 0.96: return "💰 COMPRAR"
    if teto > 0 and preco > teto * 1.15: return "⚠️ VENDER"
    return "✅ MANTÉM"

# 3. INTERFACE
st.sidebar.header("🕹️ Ricardo Central")
q_tk = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
tk = q_tk if "." in q_tk else f"{q_tk}.SA"

t1, t2, t3, t4 = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 CARTEIRA"])

# --- ABA 1: INTELIGÊNCIA COMPLETA ---
with t1:
    hist, info = load_market_data(tk)
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, tk)
        m = st.columns(5)
        m[0].metric("Preço", f"R$ {r['preco']:.2f}")
        m[1].metric("Alvo", f"R$ {r['stop_gain']:.2f}")
        m[2].metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
        m[3].metric("DY", f"{info.get('dividendYield', 0)*100:.2f}%")
        m[4].metric("P. Bazin", f"R$ {r['p_bazin']:.2f}")
        
        st.markdown(f"### Veredito: :{r['cor']}[{r['recomendacao']}]")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Preço'))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_gain']]*len(hist), name='ALVO', line=dict(dash='dash', color='gold')))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['suporte']]*len(hist), name='SUPORTE', line=dict(dash='dash', color='green')))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_loss']]*len(hist), name='STOP', line=dict(dash='dot', color='red')))
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📋 Resumo Fundamentalista")
        fund_data = {
            "Métrica": ["P/L", "P/VP", "DY (%)", "ROE (%)", "Margem Líq (%)", "Dívida/EBITDA", "Graham", "Bazin", "Gordon"],
            "Valor": [
                f"{info.get('trailingPE', 0):.2f}", f"{info.get('priceToBook', 0):.2f}",
                f"{info.get('dividendYield', 0)*100:.2f}%", f"{info.get('returnOnEquity', 0)*100:.1f}%",
                f"{info.get('profitMargins', 0)*100:.1f}%", f"{info.get('debtToEbitda', 0):.2f}",
                f"R$ {r['p_graham']:.2f}", f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_gordon']:.2f}"
            ]
        }
        st.table(pd.DataFrame(fund_data))

# --- ABA 2: SCANNER FII INTEGRAL ---
with t2:
    st.header("🏙️ Scanner FII 360º")
    try:
        df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="latin-1")
        # Correção do Erro de Syntax:
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        for c in ['P/VP', 'DY', 'PRECO', 'VACANCIA FISICA']:
            if c in df.columns:
                df[c+'_N'] = pd.to_numeric(df[c].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
        
        df['VAC_N'] = df.get('VACANCIA FISICA_N', 0)
        df['Teto Bazin'] = (df['PRECO_N'] * (df['DY_N']/100)) / 0.06
        df['Margem Seg. (%)'] = ((df['Teto Bazin'] / df['PRECO_N']) - 1) * 100
        df['VEREDITO 360º'] = df.apply(analise_360_fii, axis=1)
        
        st.dataframe(df[['TICKER', 'VEREDITO 360º', 'P/VP', 'DY', 'VACANCIA FISICA', 'Margem Seg. (%)']].sort_values('Margem Seg. (%)', ascending=False))
    except Exception as e: st.error(f"Erro no Scanner: {e}")

# --- ABA 4: CARTEIRA E RECOMENDAÇÃO ---
with t4:
    st.header("💼 Gestão de Carteira")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    if st.button("🔄 Sincronizar Tudo"):
        res = []
        for _, row in df_ed.iterrows():
            obj = yf.Ticker(row['Ticker'])
            p_a = obj.fast_info['last_price']
            rec = rec_carteira(row['Ticker'], p_a, row['PM'], obj.info)
            res.append({"Atual": p_a, "Recomendação": rec, "Total": p_a * row['Qtd'], "Lucro": (p_a - row['PM']) * row['Qtd']})
        
        df_f = pd.concat([df_ed, pd.DataFrame(res)], axis=1)
        st.metric("Patrimônio Total", f"R$ {df_f['Total'].sum():,.2f}")
        st.dataframe(df_f.style.applymap(lambda x: 'background-color: #2ecc71' if 'COMPRAR' in str(x) else ('background-color: #e74c3c' if 'VENDER' in str(x) else ''), subset=['Recomendação']))