import numpy as np
import pandas as pd

class MotorAnalise:

    # =========================
    # AÇÕES – SCORE IA (0–100)
    # =========================
    def analisar_acao(self, hist, info):
        try:
            close = hist["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            
            preco = float(close.iloc[-1])

            # RSI
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            # Tratamento para divisão por zero se loss for 0
            if loss.iloc[-1] == 0:
                rsi = 100
            else:
                rsi = 100 - (100 / (1 + rs.iloc[-1]))

            # Risco
            vol = close.pct_change().dropna().std() * np.sqrt(252)
            max_cum = close.cummax()
            dd = ((close - max_cum) / max_cum).min()

            # Fundamentos
            dy = info.get("dividendYield", 0) or 0
            # Correção de escala de DY se necessário
            if dy > 2.0: dy = dy / 100
            
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0

            p_bazin = (preco * dy) / 0.06 if dy > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0

            # SCORE IA
            score = 0
            # Pontuação por Valuation
            score += 30 if (p_bazin > 0 and preco < p_bazin) else 10
            # Pontuação por Dividendos
            score += 25 if dy >= 0.06 else 10
            # Pontuação Técnica (RSI)
            score += 25 if rsi < 40 else 10
            # Pontuação de Risco (Drawdown)
            score += 20 if dd > -0.30 else 10
            
            score = min(100, max(0, score))

            decisao = (
                "🟢🟢 COMPRA FORTE" if score >= 80 else
                "🟢 COMPRA" if score >= 65 else
                "⚪ MANTER" if score >= 45 else
                "🔴 EVITAR"
            )

            return {
                "preco": preco,
                "score": score,
                "rsi": rsi,
                "vol": vol,
                "drawdown": dd,
                "dy": dy,
                "decisao": decisao,
                "p_bazin": p_bazin,
                "p_graham": p_graham
            }
        except Exception as e:
            print(f"Erro na análise: {e}")
            return None

    # =========================
    # MONTE CARLO – CARTEIRA
    # =========================
    def monte_carlo_carteira(self, retornos, valor_inicial, aporte, anos=10, sims=2000):
        if len(retornos) == 0:
            return np.array([])
            
        meses = anos * 12
        # Média e desvio padrão mensal aproximado
        mu = retornos.mean() * 21 
        sigma = retornos.std() * np.sqrt(21)

        resultados = []
        for _ in range(sims):
            v = valor_inicial
            # Vetorização para performance: gera todos os retornos de uma vez
            retornos_simulados = np.random.normal(mu, sigma, meses)
            for r in retornos_simulados:
                v = v * (1 + r) + aporte
            resultados.append(v)

        return np.array(resultados)