import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import time

st.set_page_config(page_title="Painel Macro", layout="wide")

st.title("📊 Monitor de Divergência Macro (252 Períodos)")

def rodar_site():
    watchlist = ["BTC-USD", "ETH-USD", "PETR4.SA", "VALE3.SA", "AAPL", "TSLA"]
    motor = MotorAnalise()
    resultados_finais = []

    progresso = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(watchlist):
        status_text.text(f"Analisando {ticker}...")
        try:
            # Baixamos os dados
            data = yf.download(ticker, period="3y", progress=False)
            
            if not data.empty:
                # CORREÇÃO AQUI: Limpando os nomes das colunas de forma segura
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                
                # Garante que as colunas sejam apenas strings simples e minúsculas
                data.columns = [str(col).lower() for col in data.columns]
                
                # Reset do index para ter a coluna 'date'
                data = data.reset_index()
                data.columns = [str(col).lower() for col in data.columns]

                # Processamento no Motor
                res = motor.analisar(data)
                
                icone = "⚪"
                if "ALTA" in res['sinal']: icone = "🟢"
                elif "BAIXA" in res['sinal']: icone = "🔴"

                resultados_finais.append({
                    "Ativo": ticker,
                    "Preço": f"$ {res['preco']:,.2f}",
                    "RSI 252p": res.get('rsi_252', 'N/A'),
                    "Status": f"{icone} {res['sinal']}"
                })
            
        except Exception as e:
            st.error(f"Erro em {ticker}: {str(e)}")
        
        progresso.progress((i + 1) / len(watchlist))
        time.sleep(0.1)

    status_text.empty()
    progresso.empty()

    if resultados_finais:
        df_mostrar = pd.DataFrame(resultados_finais)
        st.table(df_mostrar)
    else:
        st.warning("Nenhum dado foi processado.")

if __name__ == "__main__":
    rodar_site()