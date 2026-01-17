import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

# 1. CONFIGURAÇÃO INICIAL
st.set_page_config(page_title="Terminal Ricardo", layout="wide")

# 2. LÓGICA DE SEGURANÇA FII (PROTEGIDA)
def veredito_fii(row):
    try:
        p, m = row.get('P/VP_N', 0), row.get('Margem Seg. (%)', 0)
        seg = str(row.get('SEGMENTO', 'Não Informado')).upper()
        vac = row.get('VACANCIA_N', 0)
        imov = row.get('IMOVEIS_N', 0)
        
        if "PAPEL" in seg or "TÍTULOS" in seg:
            return "🔥 COMPRA SEGURA (Papel)" if 0.97 <= p <= 1.00 else "🟡 ANALISAR"
        
        # Filtros de Tijolo - Só aplica se os dados existirem
        if vac and vac > 15: return "❌ EVITAR (Vacância)"
        if imov and 0 < imov < 5: return "⚠️ RISCO (Concentração)"
        
        return "🏢 OPORTUNIDADE (Tijolo)" if p < 0.95 and m > 5 else "✅ COMPRA"
    except: return "Análise Manual"

@st.cache_data(ttl=600)
def carregar_dados(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

# 3. INTERFACE
st.sidebar.header("🕹️ Comando Central")
tk_raw = st.sidebar.text_input("Ticker:", value="BBSE3")
tk_final = tk_raw.strip().upper() if "." in tk_raw else f"{tk_raw.strip().upper()}.SA"

tab1, tab2, tab3 = st.tabs(["📊 Mercado & Segurança", "🏙️ Scanner FIIs", "🛡️ PGBL"])

# --- ABA 1: AÇÕES & GRÁFICOS ---
with tab1:
    df_hist, info = carregar_dados(tk_final)
    if not df_hist.empty:
        res = MotorAnalise().analisar(df_hist, info, tk_final)
        if res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}", f"{res['upside']:.1f}%")
            c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
            c4.metric("Dívida/EBITDA", f"{info.get('debtToEbitda', 0):.1f}")

            st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
            
            # Gráfico com linhas horizontais fixas
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist['Close'], name='PREÇO', line=dict(color='#29b5e8', width=3)))
            fig.add_trace(go.Scatter(x=df_hist.index, y=[res['suporte']]*len(df_hist), name='🛡️ SUPORTE', line=dict(color='#2ecc71', dash='dash')))
            fig.add_trace(go.Scatter(x=df_hist.index, y=[res['stop_loss']]*len(df_hist), name='🚫 STOP LOSS', line=dict(color='#e74c3c', dash='dot')))
            
            fig.update_layout(height=450, legend=dict(orientation="h", y=1.1), margin=dict(l=0,r=0,b=0,t=40))
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("🏛️ Valuation Detalhado")
            cv1, cv2, cv3 = st.columns(3)
            cv1.write(f"**Graham:** R$ {res['p_graham']:.2f}")
            cv2.write(f"**Bazin:** R$ {res['p_bazin']:.2f}")
            cv3.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")

# --- ABA 2: SCANNER FIIS (RESILIENTE) ---
with tab2:
    st.header("🏙️ Scanner FII - Stress Test")
    try:
        try: df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        except: df = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="iso-8859-1")
            
        def cl(n): 
            if n in df.columns:
                return pd.to_numeric(df[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
            return None
        
        df['P/VP_N'], df['DY_N'] = cl('P/VP'), cl('DY')
        df['PRECO_N'], df['LIQ_N'] = cl('PRECO'), cl('LIQUIDEZ MEDIA DIARIA')
        df['VACANCIA_N'], df['IMOVEIS_N'] = cl('VACANCIA FISICA'), cl('N DE IMOVEIS')
        
        df['Preço Teto Bazin'] = (df['PRECO_N'] * (df['DY_N'] / 100)) / 0.06
        df['Margem Seg. (%)'] = ((df['Preço Teto Bazin'] / df['PRECO_N']) - 1) * 100
        
        # Filtro de Segurança
        f = df[(df['P/VP_N'] >= 0.85) & (df['P/VP_N'] <= 1.00) & (df['LIQ_N'] >= 500000)].copy()
        
        if not f.empty:
            f['ANÁLISE'] = f.apply(veredito_fii, axis=1)
            
            # Monta a tabela apenas com as colunas que existem no CSV
            cols_exibicao = ['TICKER', 'ANÁLISE', 'P/VP', 'DY', 'Margem Seg. (%)']
            if 'SEGMENTO' in df.columns: cols_exibicao.insert(1, 'SEGMENTO')
            
            st.dataframe(f[cols_exibicao].sort_values('Margem Seg. (%)', ascending=False))
        else:
            st.warning("Nenhum FII no range P/VP 0.85 - 1.00 com liquidez satisfatória.")
    except Exception as e: 
        st.error(f"Erro ao ler CSV: Verifique se o arquivo está na pasta.")

# --- ABA 3: PGBL ---
with tab3:
    r_anual = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Aporte Máximo (12%)", f"R$ {r_anual * 0.12:.2f}")