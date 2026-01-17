import numpy as np
import pandas as pd

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        close = hist["Close"]
        preco_atual = close.iloc[-1]

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_atual = rsi.iloc[-1]

        # Dividendos
        dy = info.get("dividendYield", 0) or 0
        lpa = info.get("trailingEps", 0) or 0
        vpa = info.get("bookValue", 0) or 0
        roe = info.get("returnOnEquity", 0) or 0

        # Preços teóricos
        p_bazin = (preco_atual * dy) / 0.06 if dy > 0 else preco_atual
        p_graham = np.sqrt(22.5 * lpa * vpa) if lpa > 0 and vpa > 0 else preco_atual
        p_gordon = (dy * preco_atual) / 0.08 if dy > 0 else preco_atual

        # Suporte / resistência simples
        suporte = close.tail(60).min()
        stop_gain = close.tail(60).max()

        # Recomendação
        recomendacao = "NEUTRO"
        if preco_atual < p_bazin and rsi_atual < 35:
            recomendacao = "COMPRA"
        elif preco_atual > stop_gain:
            recomendacao = "VENDA"

        return {
            "ticker": ticker,
            "preco": preco_atual,
            "rsi": rsi_atual,
            "p_bazin": p_bazin,
            "p_graham": p_graham,
            "p_gordon": p_gordon,
            "suporte": suporte,
            "stop_gain": stop_gain,
            "recomendacao": recomendacao
        }
