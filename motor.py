import pandas as pd
import numpy as np

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        if hist is None or hist.empty: return None

        # --- DADOS ---
        preco = hist["Close"].iloc[-1]
        
        # RSI (14)
        delta = hist["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        
        # Volatilidade & Drawdown
        vol = hist["Close"].pct_change().std() * np.sqrt(252)
        topo = hist["Close"].cummax()
        dd = ((hist["Close"] - topo) / topo).min() * 100

        # Valuation
        dy = info.get("dividendYield", 0) or 0
        lpa = info.get("trailingEps", 0) or 0
        vpa = info.get("bookValue", 0) or 0
        
        # Preços Justos
        p_bazin = (preco * dy) / 0.06 if dy > 0 else 0
        p_graham = (22.5 * lpa * vpa) ** 0.5 if (lpa > 0 and vpa > 0) else 0
        
        # Níveis Técnicos
        window = 60
        suporte = hist["Close"].tail(window).min()
        resistencia = hist["Close"].tail(window).max()

        # --- SCORE IA (0 a 100) ---
        score = 50 # Neutro
        motivos = []

        # Regras de Pontuação
        if p_bazin > 0 and preco < p_bazin: 
            score += 20; motivos.append("Abaixo do Teto Bazin")
        if p_graham > 0 and preco < p_graham: 
            score += 20; motivos.append("Abaixo do Valor Graham")
        if dy > 0.06: 
            score += 10; motivos.append("Dividendos Atrativos")
        if rsi < 30: 
            score += 20; motivos.append("RSI Sobrevendido")
        elif rsi > 70: 
            score -= 20; motivos.append("RSI Esticado")
        
        if preco <= suporte * 1.03:
            score += 10; motivos.append("Próximo ao Suporte")

        score = min(100, max(0, score))

        # Decisão Objetiva
        if score >= 75: decisao = "🟢 COMPRA FORTE"
        elif score >= 60: decisao = "🔵 COMPRA"
        elif score <= 30: decisao = "🔴 VENDA"
        else: decisao = "⚪ MANTER"

        # Retorna dicionário simples (Serializável)
        return {
            "preco": preco,
            "rsi": rsi,
            "volatilidade": vol,
            "drawdown": dd,
            "dy": dy,
            "p_bazin": p_bazin,
            "p_graham": p_graham,
            "suporte": suporte,
            "stop_loss": suporte * 0.95,
            "stop_gain": resistencia * 1.05,
            "score_ia": score,
            "decisao_ia": decisao,
            "motivos": ", ".join(motivos)
        }