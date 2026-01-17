import numpy as np
import pandas as pd

class MotorAnalise:

    def analisar(self, hist, info, ticker):
        if hist is None or hist.empty:
            return None

        preco = hist["Close"].iloc[-1]

        # RSI
        delta = hist["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi = float(rsi.iloc[-1])

        # Volatilidade e Drawdown
        retornos = hist["Close"].pct_change().dropna()
        volatilidade = retornos.std() * np.sqrt(252)
        topo = hist["Close"].cummax()
        drawdown = ((hist["Close"] - topo) / topo).min() * 100

        # Fundamentalista
        dy = info.get("dividendYield", 0) or 0
        lpa = info.get("trailingEps", 0) or 0
        vpa = info.get("bookValue", 0) or 0

        dpa = preco * dy
        p_bazin = dpa / 0.06 if dpa > 0 else 0
        p_graham = np.sqrt(22.5 * lpa * vpa) if lpa > 0 and vpa > 0 else 0

        # Técnico
        suporte = hist["Close"].tail(60).min()
        resistencia = hist["Close"].tail(60).max()

        # SCORE IA (100% determinístico)
        score = 50
        motivos = []

        if preco < p_bazin and p_bazin > 0:
            score += 15
            motivos.append("Preço < Bazin")

        if preco < p_graham and p_graham > 0:
            score += 15
            motivos.append("Preço < Graham")

        if rsi < 30:
            score += 20
            motivos.append("RSI sobrevendido")

        if rsi > 70:
            score -= 20
            motivos.append("RSI sobrecomprado")

        if preco <= suporte * 1.02:
            score += 10
            motivos.append("Perto do suporte")

        score = max(0, min(100, score))

        if score >= 75:
            decisao = "🟢🟢 COMPRA FORTE"
        elif score >= 60:
            decisao = "🟢 COMPRA"
        elif score <= 30:
            decisao = "🔴 VENDA"
        else:
            decisao = "⚪ MANTER"

        return {
            "preco": preco,
            "rsi": rsi,
            "volatilidade": volatilidade,
            "drawdown": drawdown,
            "dy": dy,
            "p_bazin": p_bazin,
            "p_graham": p_graham,
            "score_ia": score,
            "decisao_ia": decisao,
            "motivos": ", ".join(motivos)
        }

    def monte_carlo(self, patrimonio, aporte, anos=10, sims=1000):
        meses =
