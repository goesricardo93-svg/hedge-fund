import streamlit as st
import yfinance as yf
from motor import MotorAnalise
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Terminal Ricardo - Hedge Fund", layout="wide")

# Função para automatizar a análise que fizemos no chat
def gerar_veredito_fii(row):
    try:
        margem = row['Margem Seg. (%)']
        pvp = row['P/VP_N']
        dy = row['DY_N']
        
        if pvp < 0.93 and margem > 10 and dy > 0.7:
            return "🔥 COMPRA FORTE (Desconto + Yield)"
        elif pvp <= 1.0 and margem > 0:
            return "✅ COMPRA (Preço Justo)"
        elif pvp > 1.05:
            return "⚠️ AGUARDAR (Acima do VP)"
        else:
            return "🟡 NEUTRO"
    except:
        return "Analisando..."

@st.cache_data(ttl=600)
def carregar_dados_completos(ticker):
    try:
        data = yf.download(ticker, period="2y", progress=False)
        info = yf.Ticker(ticker).info
        return data, info
    except:
        return pd.DataFrame(), {}

def formatar_ticker(t):
    t = t.strip().upper()
    if "." in t: return t
    if t in ["VWRA", "VUSA", "CSPX"]: return f"{t}.L"
    return f"{t}.SA"

st.sidebar.header("🕹️ Comando Central")
ticker_raw = st.sidebar.text_input("Ticker:", value="BBSE3")
ticker_final = formatar_ticker(ticker_raw)

aba1, aba2, aba3 = st.tabs(["📊 Inteligência de Mercado", "🏙️ Scanner FIIs", "🛡️ PGBL"])

with aba1:
    try:
        data, info = carregar_dados_completos(ticker_final)
        if not data.empty:
            res = MotorAnalise().analisar(data, info, ticker_final)
            if res:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço Atual", f"R$ {res['preco']:.2f}")
                c2.metric("Preço Teto", f"R$ {res['preco_teto']:.2f}" if res['preco_teto'] > 0 else "N/A", f"{res['upside']:.1f}%")
                c3.metric("RSI (14d)", f"{res['rsi']:.1f}")
                c4.metric("Tendência", res['tendencia'])

                st.markdown(f"### Veredito: :{res['cor']}[{res['recomendacao']}]")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=res['precos_serie'].values, name='PREÇO ATUAL', line=dict(color='#29b5e8', width=3)))
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['suporte']]*len(res['precos_serie']), name='🛡️ SUPORTE ANUAL', line=dict(color='#2ecc71', width=2, dash='dash')))
                fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['stop_loss']]*len(res['precos_serie']), name='🚫 STOP LOSS', line=dict(color='#e74c3c', width=2, dash='dot')))
                if res['preco_teto'] > 0:
                    fig.add_trace(go.Scatter(x=res['precos_serie'].index, y=[res['stop_gain']]*len(res['precos_serie']), name='🎯 ALVO / STOP GAIN', line=dict(color='#f1c40f', width=2, dash='dashdot')))

                fig.update_layout(height=500, margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=14)), hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                col_val, col_tec, col_risk = st.columns(3)
                with col_val:
                    st.subheader("🏛️ Valuation")
                    st.write(f"**Graham:** R$ {res['p_graham']:.2f}"); st.write(f"**Bazin:** R$ {res['p_bazin']:.2f}"); st.write(f"**Gordon:** R$ {res['p_gordon']:.2f}")
                with col_tec:
                    st.subheader("📈 Técnico")
                    st.write(f"**Média 252:** R$ {res['ma252']:.2f}"); st.write(f"**Resistência:** R$ {res['resistencia']:.2f}")
                with col_risk:
                    st.subheader("🛡️ Gestão de Risco")
                    st.error(f"**Stop Loss:** R$ {res['stop_loss']:.2f}"); st.success(f"**Stop Gain:** R$ {res['stop_gain']:.2f}")
    except Exception as e:
        st.error(f"Erro: {e}")

with aba2:
    st.header("🏙️ Scanner com Veredito de Compra/Venda")
    try:
        df_fii = pd.read_csv("statusinvest-busca-avancada.csv", sep=";", encoding="utf-8")
        def cl(n): return pd.to_numeric(df_fii[n].astype(str).str.replace('.','').str.replace(',','.'), errors='coerce')
        
        df_fii['P/VP_N'] = cl('P/VP')
        df_fii['DY_N'] = cl('DY')
        df_fii['PRECO_N'] = cl('PRECO')
        df_fii['LIQ_N'] = cl('LIQUIDEZ MEDIA DIARIA')
        
        # Valuation Bazin para a lista
        df_fii['Preço Teto Bazin'] = (df_fii['PRECO_N'] * (df_fii['DY_N'] / 100)) / 0.06
        df_fii['Margem Seg. (%)'] = ((df_fii['Preço Teto Bazin'] / df_fii['PRECO_N']) - 1) * 100
        
        # Filtro Ricardo 
        f = df_fii[(df_fii['P/VP_N'] >= 0.85) & (df_fii['P/VP_N'] <= 1.05) & (df_fii['LIQ_N'] >= 700000)].copy()
        
        # --- APLICAÇÃO DO VEREDITO INTELIGENTE ---
        f['VEREDITO'] = f.apply(gerar_veredito_fii, axis=1)
        
        # Organização final
        f = f.sort_values(by='Margem Seg. (%)', ascending=False)

        st.write(f"🔍 Analisando **{len(f)}** ativos filtrados...")
        
        st.dataframe(f[[
            'TICKER', 'VEREDITO', 'PRECO', 'P/VP', 'DY', 
            'Preço Teto Bazin', 'Margem Seg. (%)'
        ]].style.format({'Preço Teto Bazin': '{:.2f}', 'Margem Seg. (%)': '{:.2f}%'}))
        
        st.info("💡 A análise de veredito combina P/VP abaixo de 1.0 com Yield sustentável pelo modelo de Bazin.")

    except Exception as e:
        st.info("Coloque o CSV na pasta.")

with aba3:
    st.header("🛡️ Gestão PGBL")
    r = st.number_input("Renda Bruta Anual:", value=200000.0)
    st.metric("Teto Isenção PGBL (12%)", f"R$ {r*0.12:.2f}")