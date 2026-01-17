import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Ricardo", layout="wide")

# 1. DADOS DA CARTEIRA
if 'meus_ativos' not in st.session_state:
    d = [
        ["ALZR11.SA",100,10.81],["BBAS3.SA",1703,24.48],["BBSE3.SA",55,35.64],
        ["BTCI11.SA",502,10.16],["BTLG11.SA",60,98.50],["CCME11.SA",152,8.55],
        ["CMIG4.SA",1644,11.12],["CPLE3.SA",617,9.64],["CPSH11.SA",169,10.10],
        ["CPTS11.SA",276,8.52],["CXSE3.SA",800,14.20],["EQTL3.SA",200,30.21],
        ["HGCR11.SA",20,95.81],["HGLG11.SA",20,158.03],["ITSA4.SA",1174,9.63],
        ["IVVB11.SA",6,366.97],["KLBN4.SA",2323,3.63],["KNCR11.SA",27,103.11],
        ["KNHF11.SA",15,93.23],["KNRI11.SA",30,152.49],["KNSC11.SA",373,8.78],
        ["KNUQ11.SA",16,102.45],["PETR4.SA",900,32.07],["SAPR11.SA",300,37.97],
        ["TAEE4.SA",1000,11.36],["VALE3.SA",152,54.79],["VGIR11.SA",296,9.58],
        ["VISC11.SA",16,109.70],["XPCA11.SA",110,8.77],["XPLG11.SA",26,102.31],
        ["XPML11.SA",10,106.05]
    ]
    st.session_state.meus_ativos = pd.DataFrame(d, columns=["Ticker","Qtd","PM"])

# 2. FUNÇÕES
def carregar(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

# 3. INTERFACE
tk_in = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
tk = tk_in if "." in tk_in else f"{tk_in}.SA"
t1, t2, t3, t4 = st.tabs(["📊 Inteligência", "🏙️ Scanner", "🛡️ PGBL", "💼 CARTEIRA"])

with t1:
    h, info = carregar(tk)
    if not h.empty:
        r = MotorAnalise().analisar(h, info, tk)
        if r:
            st.metric("Preço Atual", f"R$ {r['preco']:.2f}")
            st.write(f"**Veredito:** {r['recomendacao']}")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='Preço'))
            fig.add_trace(go.Scatter(x=h.index, y=[r['suporte']]*len(h), name='Suporte'))
            st.plotly_chart(fig, use_container_width=True)
            st.write(f"**Bazin:** {r['p_bazin']:.2f} | **Graham:** {r['p_graham']:.2f}")

with t2:
    try:
        df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";")
        st.dataframe(df[['TICKER','P/VP','DY']].head(10))
    except: st.info("Arquivo CSV não encontrado.")

with t3:
    rb = st.number_input("Renda Bruta:", 200000.0)
    st.write(f"Aporte 12%: R$ {rb*0.12:,.2f}")

with t4:
    st.subheader("Minha Carteira")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    if st.button("Sincronizar"):
        res = []
        for _, row in df_ed.iterrows():
            p = yf.Ticker(row['Ticker']).fast_info['lastPrice']
            res.append({"Atual": p, "Total": p*row['Qtd']})
        df_f = pd.concat([df_ed, pd.DataFrame(res)], axis=1)
        st.dataframe(df_f)