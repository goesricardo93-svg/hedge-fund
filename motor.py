# motor.py
import pandas as pd
import numpy as np

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # 1. Basics
            preco_atual = hist["Close"].iloc[-1]
            
            # 2. RSI
            delta = hist["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # 3. Volatility & Drawdown
            retornos = hist["Close"].pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            topo = hist["Close"].cummax()
            drawdown = ((hist["Close"] - topo) / topo).min() * 100

            # 4. Valuation (Bazin, Graham, Gordon)
            dy = info.get("dividendYield", 0) or 0
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            dpa = preco_atual * dy
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            p_graham = (22.5 * lpa * vpa) ** 0.5 if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin # Proxy

            # 5. Technical Levels (New)
            # Simple approach: Support = recent min, Resistance = recent max
            window = 60 # approx 3 months
            suporte = hist["Close"].tail(window).min()
            resistencia = hist["Close"].tail(window).max()
            
            # Simple strategy definitions
            stop_loss = suporte * 0.95
            stop_gain = resistencia * 1.05 # Target price breakout
            
            return {
                "preco": preco_atual,
                "rsi": rsi,
                "volatilidade": volatilidade,
                "drawdown": drawdown,
                "p_bazin": p_bazin,
                "p_graham": p_graham,
                "p_gordon": p_gordon,
                "lpa": lpa,
                "vpa": vpa,
                "dy": dy,
                "suporte": suporte,
                "resistencia": resistencia,
                "stop_loss": stop_loss,
                "stop_gain": stop_gain
            }
        except Exception as e:
            print(f"Erro Motor {ticker}: {e}")
            return None
            
    # ... (Keep monte_carlo and stress_test methods as they were)
    def monte_carlo(self, patrimonio_atual, aporte_mensal, anos=10, sims=1000):
        meses = anos * 12
        resultados = []
        mu, sigma = 0.008, 0.05 
        for _ in range(sims):
            pat = patrimonio_atual
            for _ in range(meses):
                pat = pat * (1 + np.random.normal(mu, sigma)) + aporte_mensal
            resultados.append(pat)
        return np.array(resultados)

    def stress_test(self, valor):
        cenarios = {
            "Crise 2008 (-50%)": -0.50, 
            "COVID-19 (-35%)": -0.35, 
            "Joesley Day (-15%)": -0.15
        }
        dados = {}
        for nome, queda in cenarios.items():
            hist = [valor]
            v = valor * (1 + queda)
            hist.append(v)
            for _ in range(10):
                v = v * 1.005 
                hist.append(v)
            dados[nome] = hist
        return dados