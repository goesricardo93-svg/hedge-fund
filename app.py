import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

# 1. CONFIGURAÇÃO INICIAL
st.set_page_config(page_title="Terminal Ricardo", layout="wide")

# 2. LÓGICA DE SEGURANÇA FII
def veredito_fii(row):
    try:
        p, m = row.get('P/VP_N', 0), row.get('Margem Seg. (%)', 0)
        seg = str(row.get('SEGMENTO', 'N/A')).upper()
        vac = row.get('VACANCIA_N', 0)
        imov = row.get('IMOVEIS_N', 0)
        if "PAPEL" in seg or "TÍTULOS" in seg:
            return "🔥 COMPRA SEGURA (Papel)" if 0.97 <= p <= 1.00 else "🟡 ANALISAR"
        if vac and vac > 15: return "❌ EVITAR (Vacância)"
        if imov and 0 < imov < 5: return "⚠️ RISCO (Concentração)"
        return "🏢 OPORTUNIDADE (Tijolo)" if p < 0.95 and m > 5 else "✅ COMPRA"
    except: return "Analise Manual"

@st.cache_data(ttl=600)
def carregar_dados(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

# 3. INTERFACE
st.sidebar.header("🕹️ Comando Central")
tk_raw = st.sidebar.text_input("Ticker Ação/ETF:", value="BBSE3")
tk_final = tk_raw.strip().upper() if "." in tk_raw else f"{tk_raw.strip().upper()}.SA"

tab1, tab2, tab3 = st.tabs(["📊 Inteligência de Mercado", "🏙️ Scanner FIIs", "🛡️ Gestão PGBL"])

# --- ABA 1: AÇÕES (VALUATION E TÉCNICO) ---
with tab1:
    df_h, info = carregar_dados(tk_final)
    if not df_h.empty:
        res = MotorAnalise().analisar(df_h, info, tk_final)
        if res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("P. Teto (Bazin)", f"R$ {res['p_bazin']:.2f}", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Dívida/EBITDA", f"{info.get('debtToEbitda', 0):.1f}")

            st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_h.index, y=df_h['Close'], name='PREÇO', line=dict(color='#29b5e8', width=3)))
            fig.add_trace(go.Scatter(x=df_h.index, y=[res['suporte']]*len(df_h), name='🛡️ SUPORTE', line=dict(color='#2ecc71', dash='dash')))
            fig.add_trace(go.Scatter(x=df_h.index, y=[res['stop_loss']]*len(df_h), name='🚫 STOP LOSS', line=dict(color='#e74c3c', dash='dot')))
            if res['stop_gain'] > 0:
                fig.add_trace(go.Scatter(x=df_h.index, y=[res['stop_gain']]*len(df_h), name='🎯 ALVO', line=dict(color='#f1c40f', dash='dashdot')))
            fig.update_layout(height=400, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"), margin=dict(l=0,r=0,b=0,t=40))
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            col_v, col_t, col_r = st.columns(3)
            with col_v:
                st.subheader("🏛️ Valuation")
                st.write(f"**Graham:** R$ {res['p_graham']:.2f}")
                st.write(f"**Bazin:** R$ {res['p_bazin']:.2f}")
                st.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")
                st.write(f"**Upside:** {res['upside']:.1f}%")
            with col_t:
                st.subheader("📈 Técnico")
                st.write(f"**Suporte:** R$ {res['suporte']:.2f}")
                st.write(f"**Resistência:** R$ {res['resistencia']:.2f}")
                st.write(f"**Tendência:** {res['tendencia']}")
                st.write(f"**RSI:** {res['rsi']:.1f}")
            with col_r:
                st.subheader("🛡️ Risco")
                st.error(f"**Stop Loss:** R$ {res['stop_loss']:.2f}")
                st.success(f"**Stop Gain:** R$ {res['stop_gain']:.2f}")
                st.write(f"**ROE:** {info.get('returnOnEquity', 0)*100:.1f}%")

# --- ABA 2: SCANNER FIIS ---
with tab2:
    st.header("🏙️ Scanner FII - Stress Test")
    try:
        try: df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        except: df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="iso-8859-1")
        def cl(n): 
            if n in df.columns: return pd.to_numeric(df[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
            return None
        df['P/VP_N'], df['DY_N'] = cl('P/VP'), cl('DY')
        df['PRECO_N'], df['LIQ_N'] = cl('PRECO'), cl('LIQUIDEZ MEDIA DIARIA')
        df['VACANCIA_N'], df['IMOVEIS_N'] = cl('VACANCIA FISICA'), cl('N DE IMOVEIS')
        df['Preço Teto Bazin'] = (df['PRECO_N'] * (df['DY_N'] / 100)) / 0.06
        df['Margem Seg. (%)'] = ((df['Preço Teto Bazin'] / df['PRECO_N']) - 1) * 100
        f = df[(df['P/VP_N'] >= 0.85) & (df['P/VP_N'] <= 1.00) & (df['LIQ_N'] >= 500000)].copy()
        if not f.empty:
            f['ANÁLISE'] = f.apply(veredito_fii, axis=1)
            cols = ['TICKER', 'ANÁLISE', 'P/VP', 'DY', 'Margem Seg. (%)']
            if 'SEGMENTO' in df.columns: cols.insert(1, 'SEGMENTO')
            st.dataframe(f[cols].sort_values('Margem Seg. (%)', ascending=False))
        else: st.warning("Nenhum FII nos critérios.")
    except Exception as e: st.info("Carregue o CSV do StatusInvest.")

# --- ABA 3: PGBL ---
with tab3:
    st.header("🛡️ Planejamento Fiscal")
    r_anual = st.number_input("Renda Bruta Anual:", value=200000.0)
    calc_pgbl = r_anual * 0.12
    st.metric("Aporte Máximo Isenção (12%)", f"R$ {calc_pgbl:.2f}")