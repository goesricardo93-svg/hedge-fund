import yfinance as yf
from Motor import MotorAnalise
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
            if data.empty: continue
            
            # Formatação básica para o Motor
            data = data.reset_index()
            data.columns = [c.lower() for c in data.columns]
            
            # Se a API trouxer colunas multi-index (comum no yfinance novo), limpamos:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            res = motor.analisar(data)
            
            # Lógica de ícones para o Painel
            icone = "⚪"
            if "ALTA" in res['sinal']: icone = "🟢"
            if "BAIXA" in res['sinal']: icone = "🔴"

            print(f"{ticker:<12} | {res['preco']:<10.2f} | {res.get('rsi_252', 'N/A'):<8} | {icone} {res['sinal']}")
            
        except Exception as e:
            print(f"{ticker:<12} | Erro no processamento.")
        
        time.sleep(0.2) # Evita bloqueio da API

if __name__ == "__main__":
    rodar_painel()