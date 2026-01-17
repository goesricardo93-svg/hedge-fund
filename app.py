import yfinance as yf
import pandas as pd
from motor import MotorAnalise  # Ajustado para minúsculo conforme seu arquivo
import time

def rodar_painel():
    # Sua lista de ativos personalizada
    watchlist = ["BTC-USD", "ETH-USD", "PETR4.SA", "VALE3.SA", "AAPL", "TSLA"]
    motor = MotorAnalise()
    
    print("\n" + "="*60)
    print(f"{'ATIVO':<12} | {'PREÇO':<10} | {'RSI 252':<8} | {'SINAL MACRO'}")
    print("="*60)

    for ticker in watchlist:
        try:
            # Baixa 3 anos para garantir os 252 períodos úteis
            data = yf.download(ticker, period="3y", progress=False)
            
            if data.empty:
                print(f"{ticker:<12} | Erro: Dados vazios.")
                continue
            
            # Limpeza de colunas para garantir que o Motor entenda
            data = data.reset_index()
            data.columns = [c.lower() for c in data.columns]
            
            # Ajuste para versões novas do yfinance (MultiIndex)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Executa a análise no Motor
            res = motor.analisar(data)
            
            if "status" in res:
                print(f"{ticker:<12} | {res['status']}")
                continue

            # Lógica de ícones
            icone = "⚪"
            if "ALTA" in res['sinal']: icone = "🟢"
            if "BAIXA" in res['sinal']: icone = "🔴"

            print(f"{ticker:<12} | {res['preco']:<10.2f} | {res.get('rsi_252', 'N/A'):<8} | {icone} {res['sinal']}")
            
        except Exception as e:
            print(f"{ticker:<12} | Erro: {str(e)[:30]}...")
        
        time.sleep(0.2)

if __name__ == "__main__":
    rodar_painel()