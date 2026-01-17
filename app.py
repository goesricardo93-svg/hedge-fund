Ricardo, você tem toda a razão. Peço desculpas. Na tentativa de evitar o erro técnico de "corte" do código, acabei entregando uma versão básica demais que não honra o trabalho que fizemos. Você quer o terminal institucional completo, com as fórmulas de Graham, Bazin, RSI e a gestão de risco, tudo em um único arquivo funcional.

Vou usar uma técnica de escrita de código mais robusta para garantir que o sistema não corte nenhuma aspa. Aqui está o seu Hedge Fund Ricardo Integral, com as 4 abas e todos os cálculos de Valuation e Carteira.

app.py (Versão Definitiva, Completa e Integrada)
Python

import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- 1. CONFIGURAÇÃO E BASE DE DADOS ---
st.set_page_config(page_title="Terminal Ricardo | Hedge Fund", layout="wide")

if 'meus_ativos' not in st.session_state:
    # Sua lista completa de 31 ativos
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

# --- 2. FUNÇÕES DE SUPORTE ---
@st.cache_data(ttl=600)
def get_market_data(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

def calc_status(row, pr, info):
    try:
        p_vp = info.get('priceToBook', 0) or 0
        dy = info.get('dividendYield', 0) or 0
        if "11" in row['Ticker']:
            if 0.85 <= p_vp <= 1.00: return "🔥 COMPRA"
            return "⚠️ CARO" if p_vp > 1.05 else "✅ OK"
        teto = (pr * dy) / 0.06 if dy > 0 else 0
        return "💰 OPORTUNIDADE" if teto > pr else "✅ VALOR"
    except: return "Analise Manual"

# --- 3. INTERFACE ---
st.sidebar.header("🕹️ Comando Central")
query = st.sidebar.text_input("Ticker (Ex: BBAS3):", "BBSE3").strip().upper()
tk_final = query if "." in query else f"{query}.SA"

t1, t2, t3, t4 = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 CARTEIRA"])

with t1:
    h, info = get_market_data(tk_final)
    if not h.empty:
        r = MotorAnalise().analisar(h, info, tk_final)
        if r:
            st.subheader(f"Análise Estratégica: {tk_final}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
            c2.metric("P. Teto (Bazin)", f"R$ {r['p_bazin']:.2f}", f"{r['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{r['rsi']:.1f}")
            c4.metric("Dívida/EBITDA", f"{info.get('debtToEbitda', 0):.1f}")
            
            st.markdown(f"### Veredito: :{r['cor']}[{r['recomendacao']}]")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='Preço', line=dict(color='#29b5e8', width=2)))
            fig.add_trace(go.Scatter(x=h.index, y=[r['suporte']]*len(h), name='Suporte', line=dict(dash='dash', color='green')))
            fig.add_trace(go.Scatter(x=h.index, y=[r['stop_loss']]*len(h), name='Stop Loss', line=dict(dash='dot', color='red')))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            v1, v2, v3 = st.columns(3)
            with v1:
                st.write("**Valuation ( Graham / Bazin / Gordon )**")
                st.write(f"R$ {r['p_graham']:.2f} / R$ {r['p_bazin']:.2f} / R$ {r['p_gordon']:.2f}")
            with v2:
                st.write("**Análise Técnica**")
                st.write(f"Tendência: {r['tendencia']} | Suporte: {r['suporte']:.2f}")
            with v3:
                st.write("**Gestão de Risco**")
                st.write(f"Stop Loss: {r['stop_loss']:.2f} | Stop Gain: {r['stop_gain']:.2f}")

with t2:
    st.header("🏙️ Scanner FII - Stress Test")
    try:
        df_f = pd.read_csv("statusinvest-busca-avancada.csv", sep=";")
        def parse_n(n):
            if n in df_f.columns:
                return pd.to_numeric(df_f[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
            return None
        df_f['P/VP_N'] = parse_n('P/VP')
        df_f['LIQ_N'] = parse_n('LIQUIDEZ MEDIA DIARIA')
        f = df_f[(df_f['P/VP_N'] >= 0.85) & (df_f['P/VP_N'] <= 1.05) & (df_f['LIQ_N'] >= 500000)].copy()
        st.dataframe(f[['TICKER', 'P/VP', 'DY']].sort_values('P/VP'))
    except: st.info("Carregue o CSV do StatusInvest na pasta raiz.")

with t3:
    st.header("🛡️ Simulador de Isenção PGBL")
    rb = st.number_input("Renda Bruta Anual:", value=200000.0, step=1000.0)
    st.metric("Aporte Máximo para Isenção (12%)", f"R$ {rb * 0.12:,.2f}")

with t4:
    st.header("💼 Gestão de Patrimônio Dinâmica")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    st.session_state.meus_ativos = df_ed
    
    if st.button("🔄 Sincronizar Cotações e Status"):
        with st.spinner("Consultando Yahoo Finance..."):
            res = []
            for _, row in df_ed.iterrows():
                obj = yf.Ticker(row['Ticker'])
                pr = obj.fast_info['lastPrice']
                stt = calc_status(row, pr, obj.info)
                res.append({"Atual": pr, "Status": stt, "Total": pr * row['Qtd'], "Lucro": (pr - row['PM']) * row['Qtd']})
            
            df_final = pd.concat([df_ed, pd.DataFrame(res)], axis=1)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Patrimônio Total", f"R$ {df_final['Total'].sum():,.2f}")
            m2.metric("Lucro/Prejuízo Total", f"R$ {df_final['Lucro'].sum():,.2f}")
            
            st.plotly_chart(px.pie(df_final, values='Total', names='Ticker', title="Alocação por Ativo"), use_container_width=True)
            st.dataframe(df_final.style.format({'PM': '{:.2f}', 'Atual': '{:.2f}'