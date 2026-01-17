import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 1. CONFIGURAÇÃO E BASE DE DADOS INTEGRAL
st.set_page_config(page_title="Hedge Fund Ricardo - Terminal v1.0", layout="wide")

if 'meus_ativos' not in st.session_state:
    # Lista integral dos 31 ativos com PM original
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

# 2. FUNÇÕES DE SUPORTE E CÁLCULO
@st.cache_data(ttl=600)
def carregar_dados(tk):
    try:
        obj = yf.Ticker(tk)
        return obj.history(period="2y"), obj.info
    except: return pd.DataFrame(), {}

def veredito_fii_scanner(row):
    try:
        p_vp = row.get('P/VP_N', 0)
        margem = row.get('Margem Seg. (%)', 0)
        segmento = str(row.get('SEGMENTO', 'N/A')).upper()
        vacancia = row.get('VACANCIA_N', 0)
        if "PAPEL" in segmento:
            return "🔥 COMPRA SEGURA (Papel)" if 0.97 <= p_vp <= 1.00 else "🟡 ANALISAR"
        if vacancia and vacancia > 15:
            return "❌ EVITAR (Vacância Alta)"
        if p_vp < 0.95 and margem > 5:
            return "🏢 OPORTUNIDADE (Tijolo)"
        return "✅ COMPRA"
    except: return "Análise Manual"

def recomendacao_carteira(tk, pr, pm, info):
    try:
        p_vp = info.get('priceToBook', 0) or 0
        dy = info.get('dividendYield', 0) or 0
        teto_bazin = (pr * dy) / 0.06 if dy > 0 else 0
        if "11" in tk:
            if p_vp < 0.96: return "🔥 APORTAR (Desconto)"
            if p_vp > 1.05: return "⚠️ CARO (Aguardar)"
            return "✅ MANTER"
        else:
            if pr < teto_bazin: return "💰 OPORTUNIDADE (Bazin)"
            if pr > pm * 1.2: return "🚀 ALTA (Manter)"
            return "✅ EM VALOR"
    except: return "---"

# 3. INTERFACE PRINCIPAL
st.sidebar.header("🕹️ Comando Central")
tk_raw = st.sidebar.text_input("Consultar Ticker:", value="BBSE3")
tk_final = tk_raw.strip().upper() if "." in tk_raw else f"{tk_raw.strip().upper()}.SA"

t1, t2, t3, t4 = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 MINHA CARTEIRA"])

# --- ABA 1: INTELIGÊNCIA ---
with t1:
    df_h, info = carregar_dados(tk_final)
    if not df_h.empty:
        res = MotorAnalise().analisar(df_h, info, tk_final)
        if res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
            c2.metric("Alvo (Stop Gain)", f"R$ {res['stop_gain']:.2f}")
            c3.metric("P. Teto (Bazin)", f"R$ {res['p_bazin']:.2f}", f"{res['upside']:.1f}%")
            c4.metric("RSI (14d)", f"{res['rsi']:.1f}")
            
            st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_h.index, y=df_h['Close'], name='PREÇO', line=dict(color='#29b5e8', width=3)))
            fig.add_trace(go.Scatter(x=df_h.index, y=[res['suporte']]*len(df_h), name='🛡️ SUPORTE', line=dict(color='#2ecc71', dash='dash')))
            fig.add_trace(go.Scatter(x=df_h.index, y=[res['stop_loss']]*len(df_h), name='🚫 STOP LOSS', line=dict(color='#e74c3c', dash='dot')))
            fig.add_trace(go.Scatter(x=df_h.index, y=[res['stop_gain']]*len(df_h), name='🎯 ALVO', line=dict(color='#f1c40f', dash='dashdot')))
            fig.update_layout(height=450, margin=dict(l=0,r=0,b=0,t=40), legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            col_v, col_t, col_r = st.columns(3)
            with col_v:
                st.subheader("🏛️ Valuation")
                st.write(f"**Graham:** R$ {res['p_graham']:.2f}")
                st.write(f"**Bazin:** R$ {res['p_bazin']:.2f}")
                st.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")
            with col_t:
                st.subheader("📈 Técnico")
                st.write(f"**Suporte:** R$ {res['suporte']:.2f}")
                st.write(f"**Resistência:** R$ {res['resistencia']:.2f}")
                st.write(f"**Tendência:** {res['tendencia']}")
            with col_r:
                st.subheader("🛡️ Risco")
                st.error(f"**Stop Loss:** R$ {res['stop_loss']:.2f}")
                st.success(f"**Stop Gain:** R$ {res['stop_gain']:.2f}")
                st.write(f"**Dívida/EBITDA:** {info.get('debtToEbitda', 0):.2f}")

# --- ABA 2: SCANNER FIIS ---
with t2:
    st.header("🏙️ Scanner FII - Stress Test")
    try:
        try: df_f = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        except: df_f = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="iso-8859-1")
        
        def limpar_coluna(n):
            if n in df_f.columns:
                return pd.to_numeric(df_f[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
            return None
        
        df_f['P/VP_N'] = limpar_coluna('P/VP')
        df_f['DY_N'] = limpar_coluna('DY')
        df_f['PRECO_N'] = limpar_coluna('PRECO')
        df_f['LIQ_N'] = limpar_coluna('LIQUIDEZ MEDIA DIARIA')
        df_f['VACANCIA_N'] = limpar_coluna('VACANCIA FISICA')
        
        df_f['Preço Teto Bazin'] = (df_f['PRECO_N'] * (df_f['DY_N'] / 100)) / 0.06
        df_f['Margem Seg. (%)'] = ((df_f['Preço Teto Bazin'] / df_f['PRECO_N']) - 1) * 100
        
        filt = df_f[(df_f['P/VP_N'] >= 0.85) & (df_f['P/VP_N'] <= 1.05) & (df_f['LIQ_N'] >= 500000)].copy()
        if not filt.empty:
            filt['ANÁLISE'] = filt.apply(veredito_fii_scanner, axis=1)
            st.dataframe(filt[['TICKER', 'ANÁLISE', 'P/VP', 'DY', 'VACANCIA FISICA', 'Margem Seg. (%)']].sort_values('Margem Seg. (%)', ascending=False))
        else: st.warning("Nenhum FII nos critérios técnicos.")
    except Exception as e: st.error(f"Erro ao ler CSV: {e}")

# --- ABA 3: PGBL ---
with t3:
    st.header("🛡️ Planejamento Fiscal")
    r_anual = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Aporte Máximo Isenção (12%)", f"R$ {r_anual * 0.12:,.2f}")

# --- ABA 4: CARTEIRA INTELIGENTE ---
with t4:
    st.header("💼 Gestão de Patrimônio Ricardo")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    st.session_state.meus_ativos = df_ed
    
    if st.button("🔄 Sincronizar e Analisar Carteira"):
        with st.spinner("Analisando mercado e gerando recomendações..."):
            res_carteira = []
            for _, row in df_ed.iterrows():
                t = yf.Ticker(row['Ticker'])
                preco = t.fast_info['lastPrice']
                rec = recomendacao_carteira(row['Ticker'], preco, row['PM'], t.info)
                res_carteira.append({'Preço Atual': preco, 'Recomendação': rec})
            
            df_final = pd.concat([df_ed, pd.DataFrame(res_carteira)], axis=1)
            df_final['Total'] = df_final['Qtd'] * df_final['Preço Atual']
            df_final['Lucro'] = (df_final['Preço Atual'] - df_final['PM']) * df_final['Qtd']
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Patrimônio Total", f"R$ {df_final['Total'].sum():,.2f}")
            m2.metric("Lucro/Prejuízo Absoluto", f"R$ {df_final['Lucro'].sum():,.2f}")
            
            c_p1, c_p2 = st.columns(2)
            with c_p1: st.plotly_chart(px.pie(df_final, values='Total', names='Ticker', title="Distribuição de Ativos"), use_container_width=True)
            with c_p2: st.plotly_chart(px.bar(df_final.sort_values('Lucro'), x='Ticker', y='Lucro', color='Recomendação', title="Performance por Ativo"), use_container_width=True)
            
            st.dataframe(df_final.style.applymap(
                lambda x: 'background-color: #27ae60' if 'APORTAR' in str(x) or 'OPORTUNIDADE' in str(x) else ('background-color: #c0392b' if 'CARO' in str(x) else ''),
                subset=['Recomendação']
            ))