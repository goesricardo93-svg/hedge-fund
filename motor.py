import pandas as pd
import numpy as np

class MotorAnalise:
    def __init__(self):
        self.p_curto = 14
        self.p_longo = 252

    def calcular_rsi(self, serie, window):
        delta = serie.diff()
        ganho = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        perda = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = ganho / (perda + 1e-9)
        return 100 - (100 / (1 + rs))

    def analisar(self, df, info=None):
        if len(df) < 10: return None
        df['close'] = df['close'].ffill()
        
        preco_atual = float(df['close'].iloc[-1])
        ma252 = df['close'].rolling(window=min(len(df), self.p_longo)).mean().iloc[-1]
        rsi14 = self.calcular_rsi(df['close'], self.p_curto).iloc[-1]
        
        # --- VALUATIONS ---
        lpa = info.get('trailingEps', 0) if info else 0
        vpa = info.get('bookValue', 0) if info else 0
        dpa = info.get('dividendRate', 0) if info else 0
        
        p_graham = np.sqrt(max(0, 22.5 * lpa * vpa)) if (lpa > 0 and vpa > 0) else 0
        p_bazin = dpa / 0.06 if dpa > 0 else 0
        p_gordon = dpa / 0.08 if dpa > 0 else 0
        
        vals = [v for v in [p_graham, p_bazin, p_gordon] if v > 0]
        p_justo = np.mean(vals) if vals else preco_atual
        upside = ((p_justo / preco_atual) - 1) * 100

        # --- RECOMENDAÇÃO ---
        tendencia = "ALTA" if preco_atual > ma252 else "BAIXA"
        if preco_atual > ma252 and rsi14 < 45:
            rec, cor = "COMPRA (Desconto Técnico)", "green"
        elif preco_atual > ma252:
            rec, cor = "MANTER (Tendência de Alta)", "blue"
        else:
            rec, cor = "FORA (Tendência de Baixa)", "gray"

        # --- SUPORTE / RESISTÊNCIA / FIBO ---
        max_252 = float(df['close'].tail(252).max())
        min_252 = float(df['close'].tail(252).min())
        diff = max_252 - min_252

        return {
            "preco": round(preco_atual, 2),
            "ma252": round(ma252, 2),
            "rsi_14": round(rsi14, 2),
            "tendencia": tendencia,
            "recomendacao": rec,
            "cor_sinal": cor,
            "val_graham": round(p_graham, 2),
            "val_bazin": round(p_bazin, 2),
            "val_gordon": round(p_gordon, 2),
            "upside": round(upside, 2),
            "suporte": round(min_252, 2),
            "resistencia": round(max_252, 2),
            "stop_loss": round(preco_atual * 0.97, 2),
            "stop_gain": round(preco_atual * 1.06, 2),
            "fibonacci": {
                "61.8%": round(max_252 - (0.382 * diff), 2),
                "50.0%": round(max_252 - (0.5 * diff), 2),
                "38.2%": round(max_252 - (0.618 * diff), 2)
            }
        }