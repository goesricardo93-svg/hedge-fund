import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import time

# Configuração da página do site
st.set_page_config(page_title="Painel de Controle Macro", layout="wide")

st.title("📊 Monitor de Divergência Macro (252 Períodos)")
st.write("Análise objetiva de tendência e força relativa.")

def rodar_site():
    watchlist = ["BTC-USD", "ETH-USD", "PETR4.SA", "VALE3.SA", "AAPL", "TSLA"]
    motor = MotorAnalise()
    
    # Criamos uma lista para armazenar os resultados e exibir em uma tabela
    resultados_finais = []

    # Barra de progresso para o usuário saber que o site está trabalhando
    progresso = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(watchlist):
        status_text.text(f"Analisando {ticker}...")
        try:
            data = yf.download(ticker, period="3y", progress=False)
            
            if not data.empty:
                data = data.reset_index()
                data.columns = [c.lower() for c in data.columns]
                
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)

                res = motor.analisar(data)
                
                # Definir cor do sinal
                cor = "⚪"
                if "ALTA" in res['sinal']: cor = "🟢"
                elif "BAIXA" in res['sinal']: cor = "🔴"

                resultados_finais.append({
                    "Ativo": ticker,
                    "Preço": f"$ {res['preco']:,.2f}",
                    "RSI 252p": res.get('rsi_252', 'N/A'),
                    "Status": f"{cor} {res['sinal']}"
                })
            
        except Exception as e:
            st.error(f"Erro em {ticker}: {e}")
        
        progresso.progress((i + 1) / len(watchlist))
        time.sleep(0.1)

    status_text.empty()
    progresso.empty()

    # Exibe os dados em uma tabela bonitinha no Streamlit
    df_mostrar = pd.DataFrame(resultados_finais)
    st.table(df_mostrar)

if __name__ == "__main__":
    rodar_site()