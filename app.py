import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
st.title("🏛️ Terminal Hedge Fund - Inteligência Total")

motor = MotorAnalise()

# --- SEÇÃO 1: WATCHLIST (PAINEL GERAL) ---
with st.expander("📊 Monitor Global (Watchlist)", expanded=False):
    watchlist = ["BTC-USD", "ETH-USD", "PETR4.SA", "VALE3.SA", "AAPL", "TSLA"]
    if st.button("Atualizar Monitor"):
        dados_monitor = []
        for t in watchlist:
            d = yf.download(t, period="3y", progress=False)
            if not d.empty:
                d.columns = [str(c).lower() for c in (d.columns.get_level_values(0) if isinstance(d.columns, pd.MultiIndex) else d.columns)]
                res = motor.analisar(d.reset_index())
                if res:
                    dados_monitor.append({"Ativo": t, "Preço": res['preco'], "Tendência": res['tendencia'], "RSI 252p": res['rsi_252']})
        st.table(pd.DataFrame(dados_monitor))

# --- SEÇÃO 2: BUSCA INDIVIDUAL ---
st.subheader("🔍 Consulta Detalhada")
ticker = st.text_input("Digite o Ticker (ex: NVDA):", value="BTC-USD").upper().strip()

if ticker:
    try:
        df_raw = yf.download(ticker, period="4y", progress=False)
        if not df_raw.empty:
            # Limpeza de colunas MultiIndex do yfinance novo
            df_raw.columns = [str(c).lower() for c in (df_raw.columns.get_level_values(0) if isinstance(df_raw.columns, pd.MultiIndex) else df_raw.columns)]
            df_proc = df_raw.reset_index()
            
            res = motor.analisar(df_proc)
            
            if res:
                # Layout de colunas
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Preço", f"$ {res['preco']:,.2f}")
                c2.metric("Tendência", res['tendencia'])
                c3.metric("RSI 14p", res['rsi_14'])
                c4.metric("RSI 252p", res['rsi_252'])

                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    st.subheader("🛡️ Risco")
                    st.error(f"STOP LOSS: {res['stop_loss']}")
                    st.success(f"STOP GAIN: {res['stop_gain']}")
                
                with col_b:
                    st.subheader("🚧 Barreiras")
                    st.warning(f"RESISTÊNCIA: {res['resistencia']}")
                    st.info(f"SUPORTE: {res['suporte']}")
                
                with col_c:
                    st.subheader("📐 Fibonacci")
                    for k, v in res['fibonacci'].items():
                        st.write(f"**{k}:** {v}")

                st.line_chart(motor.processar_df(df_proc).set_index('date')[['close', 'ma252']])
        else:
            st.error("Ativo não encontrado ou sem dados.")
    except Exception as e:
        st.error(f"Erro no sistema: {e}")