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
        p, d, m = row['P/VP_N'], row['DY_N'], row['Margem Seg. (%)']
        seg = str(row.get('SEGMENTO', '')).upper()
        vac, imov = row.get('VACANCIA_N', 0), row.get('IMOVEIS_N', 0)
        
        if "PAPEL" in seg or "TÍTULOS" in seg:
            return "🔥 COMPRA SEGURA (Papel)" if 0.97 <= p <= 1.00 else "🟡 ANALISAR"
        if vac > 15: return "❌ EVITAR (Vacância)"
        if 0 < imov < 5: return "⚠️ RISCO (Concentração)"
        return "🏢 OPORTUNIDADE (Tijolo)" if p < 0.95 and m > 5 else "✅ COMPRA"
    except: return "Erro"

@st.cache_data(ttl=600)
def carregar_dados(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

# 3. INTERFACE LATERAL
st.sidebar.header("🕹️ Comando Central")
tk_raw = st.sidebar.text_input("Ticker:", value="BBSE3")
tk_final = tk_raw.strip().upper() if "." in tk_raw else f"{tk_raw.strip().upper()}.SA"

tab1, tab2, tab3 = st.tabs(["📊 Mercado & Segurança", "🏙️ Scanner FIIs", "🛡️ PGBL"])

# --- ABA 1: AÇÕES (Dívida e Eficiência) ---
with tab1:
    df_hist, info = carregar_dados(tk_final)
    if not df_hist.empty:
        res = MotorAnalise().analisar(df_hist, info, tk_final)
        if res:
            # Filtros de Segurança: Dívida < 3 e ROE > 10%
            deb_ebitda = info.get('debtToEbitda', 0)
            roe = info.get('returnOnEquity', 0)
            is_safe = (deb_ebitda < 3 if deb_ebitda else True) and (roe > 0.10)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Dívida/EBITDA", f"{deb_ebitda:.1f}" if deb_ebitda else "N/A")

            status = "🔥 COMPRA SEGURA" if (res['recomendacao'] == "COMPRA" and is_safe) else res['recomendacao']
            if deb_ebitda and deb_ebitda > 4: status = "⚠️ ALERTA (Dívida)"
            
            st.markdown(f"### Veredito: :{res['cor']}[{status}]")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist['Close'], name='PREÇO', line=dict(color='#29b5e8', width=3)))
            fig.add_trace(go.Scatter(x=df_hist.index, y=[res['suporte']]*len(df_hist), name='🛡️ SUPORTE', line=dict(color='#2ecc71', dash='dash')))
            fig.add_trace(go.Scatter(x=df_hist.index, y=[res['stop_loss']]*len(df_hist), name='🚫 STOP LOSS', line=dict(color='#e74c3c', dash='dot')))
            fig.update_layout(height=400, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"), margin=dict(l=0,r=0,b=0,t=40))
            st.plotly_chart(fig, use_container_width=True)

# --- ABA 2: SCANNER FIIs (Filtros Ricardo) ---
with tab2:
    st.header("🏙️ Scanner FII - Stress Test")
    try:
        try: df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        except: df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="iso-8859-1")
            
        def cl(n): return pd.to_numeric(df[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
        
        df['P/VP_N'], df['DY_N'] = cl('P/VP'), cl('DY')
        df['PRECO_N'], df['LIQ_N'] = cl('PRECO'), cl('LIQUIDEZ MEDIA DIARIA')
        df['VACANCIA_N'], df['IMOVEIS_N'] = cl('VACANCIA FISICA'), cl('N DE IMOVEIS')
        
        df['Preço Teto Bazin'] = (df['PRECO_N'] * (df['DY_N'] / 100)) / 0.06
        df['Margem Seg. (%)'] = ((df['Preço Teto Bazin'] / df['PRECO_N']) - 1) * 100
        
        # FILTRO DE SEGURANÇA MÁXIMA
        f = df[
            (df['P/VP_N'] >= 0.85) & (df['P/VP_N'] <= 1.00) & 
            (df['LIQ_N'] >= 1000000) & 
            ((df['VACANCIA_N'] <= 15) | (df['VACANCIA_N'].isna())) &
            ((df['IMOVEIS_N'] >= 5) | (df['IMOVEIS_N'].isna()))
        ].copy()
        
        if not f.empty:
            f['ANÁLISE'] = f.apply(veredito_fii, axis=1)
            st.dataframe(f[['TICKER', 'SEGMENTO', 'ANÁLISE', 'P/VP', 'DY', 'VACANCIA FISICA', 'Margem Seg. (%)']].sort_values('Margem Seg. (%)', ascending=False))
        else:
            st.warning("Nenhum ativo passou nos filtros de segurança (P/VP 0.85-1.00 e Liq > 1M).")
    except Exception as e: 
        st.info(f"Aguardando CSV. Erro: {e}")

# --- ABA 3: PGBL ---
with tab3:
    st.header("🛡️ Planejamento Fiscal")
    r_anual = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Aporte Máximo Isenção (12%)", f"R$ {r_anual * 0.12:.2f}")