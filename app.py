import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise

st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")
st.title("🏛️ Terminal Hedge Fund - Inteligência Global")

motor = MotorAnalise()

st.subheader("🔍 Consulta e Operacional")
ticker_input = st.text_input("Digite o Ticker (Ex: PETR4, BBAS3, BTC-USD):", value="PETR4").upper().strip()

# LOGICA DE CORREÇÃO AUTOMÁTICA PARA B3
ticker = ticker_input
if "-" not in ticker and "." not in ticker and any(char.isdigit() for char in ticker):
    ticker = f"{ticker}.SA"

if ticker:
    try:
        with st.spinner(f'Buscando {ticker}...'):
            df_raw = yf.download(ticker, period="4y", progress=False)
            
            if not df_raw.empty:
                # Limpeza de colunas MultiIndex
                if isinstance(df_raw.columns, pd.MultiIndex):
                    df_raw.columns = df_raw.columns.get_level_values(0)
                df_raw.columns = [str(c).lower() for c in df_raw.columns]
                df_proc = df_raw.reset_index()
                df_proc.columns = [str(col).lower() for col in df_proc.columns]

                res = motor.analisar(df_proc)
                
                if res:
                    # Painel Superior
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Preço Atual", f"R$ {res['preco']:,.2f}" if ".SA" in ticker else f"$ {res['preco']:,.2f}")
                    c2.metric("Tendência (252p)", res['tendencia'])
                    c3.metric("RSI 14p", res['rsi_14'])
                    c4.metric("RSI 252p", res['rsi_252'])

                    st.markdown("---")
                    
                    # Risco e Fibonacci
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.subheader("🛡️ Gestão de Risco")
                        st.error(f"STOP LOSS: {res['stop_loss']}")
                        st.success(f"STOP GAIN: {res['stop_gain']}")
                        st.info(f"ALVO MA252: {res['ma252']}")
                    
                    with col_b:
                        st.subheader("🚧 Barreiras Anuais")
                        st.warning(f"RESISTÊNCIA: {res['resistencia']}")
                        st.info(f"SUPORTE: {res['suporte']}")
                    
                    with col_c:
                        st.subheader("📐 Fibonacci (252p)")
                        for k, v in res['fibonacci'].items():
                            st.write(f"**{k}:** {v}")

                    # GRÁFICO
                    st.markdown("---")
                    st.subheader(f"📈 Gráfico Histórico: {ticker}")
                    df_grafico = df_proc.copy()
                    df_grafico['ma252'] = df_grafico['close'].rolling(window=252).mean()
                    df_grafico = df_grafico.set_index('date')
                    st.line_chart(df_grafico[['close', 'ma252']])
            else:
                st.warning(f"Ativo {ticker} não encontrado. Tente adicionar .SA ao final.")
    except Exception as e:
        st.error(f"Erro na conexão com Yahoo Finance: {e}")

# Monitor Global (Watchlist corrigida)
with st.expander("📊 Monitor Global"):
    if st.button("Recarregar"):
        lista = ["BTC-USD", "PETR4.SA", "VALE3.SA", "BBAS3.SA", "AAPL"]
        resumos = []
        for t in lista:
            d = yf.download(t, period="3y", progress=False)
            if not d.empty:
                d.columns = [str(c).lower() for c in (d.columns.get_level_values(0) if isinstance(d.columns, pd.MultiIndex) else d.columns)]
                r = motor.analisar(d.reset_index())
                if r: resumos.append({"Ativo": t, "Preço": r['preco'], "Sinal": r['tendencia']})
        st.table(pd.DataFrame(resumos))