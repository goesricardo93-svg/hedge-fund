import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

# 1. SETUP E CARTEIRA
st.set_page_config(page_title="Hedge Fund Ricardo | Terminal v1.0", layout="wide")

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

# 2. FUNÇÕES DE CÁLCULO
def get_rsi_status(val):
    if val < 30: return f"{val:.1f} 🟢 (SOBREVENDA)"
    if val > 70: return f"{val:.1f} 🔴 (SOBRECOMPRA)"
    return f"{val:.1f}"

def recomendacao_final(preco, pm, info):
    dy = info.get('dividendYield', 0) or 0
    teto = (preco * dy) / 0.06 if dy > 0 else 0
    if preco < pm * 0.96: return "💰 COMPRAR"
    if teto > 0 and preco > teto * 1.15: return "⚠️ VENDER"
    return "✅ MANTÉM"

# 3. INTERFACE PRINCIPAL
st.sidebar.header("🕹️ Ricardo Central")
q_tk = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
tk = q_tk if "." in q_tk else f"{q_tk}.SA"

tabs = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 CARTEIRA"])

with tabs[0]:
    obj = yf.Ticker(tk)
    hist, info = obj.history(period="2y"), obj.info
    if not hist.empty:
        r = MotorAnalise().analisar(hist, info, tk)
        rsi_txt = get_rsi_status(r['rsi'])
        
        m = st.columns(6)
        m[0].metric("Preço", f"R$ {r['preco']:.2f}")
        m[1].metric("Alvo", f"R$ {r['stop_gain']:.2f}")
        m[2].metric("RSI (14d)", rsi_txt)
        m[3].metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
        m[4].metric("DY", f"{info.get('dividendYield', 0)*100:.2f}%")
        m[5].metric("P. Bazin", f"R$ {r['p_bazin']:.2f}")
        
        st.markdown(f"### Veredito: :{r['cor']}[{r['recomendacao']}]")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Preço'))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_gain']]*len(hist), name='🎯 ALVO', line=dict(dash='dash', color='gold')))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['suporte']]*len(hist), name='🛡️ SUPORTE', line=dict(dash='dash', color='green')))
        fig.add_trace(go.Scatter(x=hist.index, y=[r['stop_loss']]*len(hist), name='🚫 STOP', line=dict(dash='dot', color='red')))
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📋 Resumo Fundamentalista e Técnico")
        fund_df = pd.DataFrame({
            "Métrica": ["RSI", "P/L", "P/VP", "DY (%)", "ROE (%)", "Margem (%)", "Dívida/EBITDA", "Graham", "Bazin", "Gordon"],
            "Valor": [
                rsi_txt, f"{info.get('trailingPE', 0):.2f}", f"{info.get('priceToBook', 0):.2f}",
                f"{info.get('dividendYield', 0)*100:.2f}%", f"{info.get('returnOnEquity', 0)*100:.1f}%",
                f"{info.get('profitMargins', 0)*100:.1f}%", f"{info.get('debtToEbitda', 0):.2f}",
                f"R$ {r['p_graham']:.2f}", f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_gordon']:.2f}"
            ]
        })
        st.table(fund_df)

with tabs[1]:
    st.header("🏙️ Scanner FII 360º")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="latin-1")
        df_fii.columns = [str(c).strip().upper() for c in df_fii.columns]
        
        # Busca flexível de coluna
        col_vac = next((c for c in df_fii.columns if 'VACANCIA' in c), None)
        col_dy = next((c for c in df_fii.columns if 'DY' in c), None)
        col_pvp = next((c for c in df_fii.columns if 'P/VP' in c), None)
        col_prc = next((c for c in df_fii.columns if 'PRECO' in c), None)

        def to_num(df, c): return pd.to_numeric(df[c].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
        
        df_fii['P/VP_N'] = to_num(df_fii, col_pvp) if col_pvp else 0
        df_fii['DY_N'] = to_num(df_fii, col_dy) if col_dy else 0
        df_fii['VAC_N'] = to_num(df_fii, col_vac) if col_vac else 0
        df_fii['PRC_N'] = to_num(df_fii, col_prc) if col_prc else 0

        df_fii['Teto Bazin'] = (df_fii['PRC_N'] * (df_fii['DY_N']/100)) / 0.06
        df_fii['Margem Seg. (%)'] = ((df_fii['Teto Bazin'] / df_fii['PRC_N']) - 1) * 100
        
        st.dataframe(df_fii[['TICKER', col_pvp, col_dy, col_vac, 'Margem Seg. (%)']].sort_values('Margem Seg. (%)', ascending=False))
    except Exception as e: st.error(f"Erro no Scanner: {e}")

with tabs[3]:
    st.header("💼 Gestão de Carteira")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    if st.button("🔄 Sincronizar Tudo"):
        res = []
        for _, row in df_ed.iterrows():
            t = yf.Ticker(row['Ticker'])
            p_atual = t.fast_info['last_price']
            rec = recomendacao_final(p_atual, row['PM'], t.info)
            res.append({"Cotação": p_atual, "Recomendação": rec, "Lucro/Prejuízo": (p_atual - row['PM']) * row['Qtd']})
        
        df_final = pd.concat([df_ed, pd.DataFrame(res)], axis=1)
        st.dataframe(df_final.style.applymap(lambda x: 'background-color: #2ecc71' if 'COMPRAR' in str(x) else ('background-color: #e74c3c' if 'VENDER' in str(x) else ''), subset=['Recomendação']))