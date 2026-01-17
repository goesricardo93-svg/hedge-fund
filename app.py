import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

# 1. SETUP E CARTEIRA (ESTÁVEL)
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

# 2. FUNÇÕES TÉCNICAS
def get_rsi_status(val):
    if val < 30: return f"{val:.1f} 🟢 (SOBREVENDA)"
    if val > 70: return f"{val:.1f} 🔴 (SOBRECOMPRA)"
    return f"{val:.1f}"

# 3. INTERFACE
st.sidebar.header("🕹️ Ricardo Central")
q_tk = st.sidebar.text_input("Ticker:", "BBSE3").strip().upper()
tk = q_tk if "." in q_tk else f"{q_tk}.SA"

tabs = st.tabs(["📊 Inteligência", "🏙️ Scanner FIIs", "🛡️ PGBL", "💼 CARTEIRA"])

# ABA 1: INTELIGÊNCIA (Simplificada para o exemplo)
with tabs[0]:
    st.write(f"Análise de {tk}")
    # ... (Seu motor de análise entra aqui)

# ABA 2: SCANNER (Mantendo sua lógica de busca no CSV)
with tabs[1]:
    st.header("🏙️ Scanner FII 360º")
    # ... (Seu código de leitura de CSV aqui)

# ABA 3: PGBL (CORREÇÃO - AGORA COM CONTEÚDO)
with tabs[2]:
    st.header("🛡️ Calculadora de Benefício PGBL")
    col1, col2 = st.columns(2)
    renda = col1.number_input("Renda Bruta Anual (R$):", value=100000.0)
    aporte = col2.number_input("Aporte Mensal PGBL (R$):", value=500.0)
    
    limite_12 = renda * 0.12
    total_anual = aporte * 12
    restituicao = min(total_anual, limite_12) * 0.275
    
    st.metric("Restituição Estimada (IR)", f"R$ {restituicao:,.2f}")
    st.info(f"O limite de dedução para sua renda é R$ {limite_12:,.2f} por ano.")

# ABA 4: CARTEIRA (CORREÇÃO - RECOMENDAÇÃO AGORA APARECE)
with tabs[3]:
    st.header("💼 Gestão de Carteira")
    df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True)
    
    if st.button("🔄 Sincronizar e Gerar Recomendações"):
        with st.spinner("Buscando preços e calculando..."):
            res = []
            for index, row in df_ed.iterrows():
                try:
                    t = yf.Ticker(row['Ticker'])
                    # Tenta pegar preço rápido primeiro, se falhar usa history
                    p_atual = t.fast_info['last_price'] if 'last_price' in t.fast_info else t.history(period="1d")['Close'].iloc[-1]
                    
                    # Lógica de Recomendação (Bazin/Preço Médio)
                    info = t.info
                    dy = info.get('dividendYield', 0) or 0
                    teto_bazin = (p_atual * dy) / 0.06 if dy > 0 else 0
                    
                    # Regra: Comprar se preço < PM ou Preço < Teto Bazin
                    if p_atual < row['PM'] * 0.95:
                        rec = "💰 COMPRAR"
                    elif teto_bazin > 0 and p_atual > teto_bazin * 1.15:
                        rec = "⚠️ VENDER"
                    else:
                        rec = "✅ MANTÉM"
                        
                    res.append({
                        "Cotação": p_atual,
                        "Recomendação": rec,
                        "Lucro Total": (p_atual - row['PM']) * row['Qtd']
                    })
                except:
                    res.append({"Cotação": 0, "Recomendação": "❌ ERRO", "Lucro Total": 0})
            
            # Unir dados editados com os resultados da API
            df_final = pd.concat([df_ed.reset_index(drop=True), pd.DataFrame(res)], axis=1)
            
            st.subheader("📋 Relatório de Ação")
            st.dataframe(df_final.style.applymap(
                lambda x: 'background-color: #2ecc71' if 'COMPRAR' in str(x) else ('background-color: #e74c3c' if 'VENDER' in str(x) else ''), 
                subset=['Recomendação']
            ))