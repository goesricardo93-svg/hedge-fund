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
        ma252_serie = df['close'].rolling(window=min(len(df), self.p_longo)).mean()
        ma252 = ma252_serie.iloc[-1]
        rsi14 = self.calcular_rsi(df['close'], self.p_curto).iloc[-1]
        rsi252 = self.calcular_rsi(df['close'], self.p_longo).iloc[-1]
        
        # --- VALUATIONS ---
        # Puxa dados reais do Yahoo Finance ou usa estimativas conservadoras
        lpa = info.get('trailingEps', 0) if info else 0
        vpa = info.get('bookValue', 0) if info else 0
        dpa = info.get('dividendRate', 0) if info else 0
        
        # 1. Graham: Raiz(22.5 * LPA * VPA)
        preco_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
        
        # 2. Bazin: DPA / 0.06 (Yield de 6%)
        preco_bazin = dpa / 0.06 if dpa else 0
        
        # 3. Gordon: D1 / (k - g) -> Simplificado para Yield de 8% se k e g ocultos
        preco_gordon = dpa / 0.08 if dpa else 0

        # Média dos Valuations para Projeção
        vals = [p for p in [preco_graham, preco_bazin, preco_gordon] if p > 0]
        preco_justo = np.mean(vals) if vals else preco_atual
        upside = ((preco_justo / preco_atual) - 1) * 100

        # --- LÓGICA DE VEREDITO ---
        tendencia_alta = preco_atual > ma252
        if tendencia_alta and rsi14 < 45:
            rec, cor = "COMPRA FORTE (Desconto Técnico)", "green"
        elif tendencia_alta:
            rec, cor = "MANTER (Tendência de Alta)", "blue"
        elif not tendencia_alta and rsi14 > 65:
            rec, cor = "VENDA (Repique na Baixa)", "red"
        else:
            rec, cor = "FORA (Tendência de Baixa)", "gray"

        # Fibonacci
        max_anual = float(df['close'].tail(252).max())
        min_anual = float(df['close'].tail(252).min())
        diff = max_anual - min_anual
        fib = {"61.8%": round(max_anual - (0.382 * diff), 2),
               "50.0%": round(max_anual - (0.5 * diff), 2),
               "38.2%": round(max_anual - (0.618 * diff), 2)}

        return {
            "preco": round(preco_atual, 2),
            "ma252": round(ma252, 2),
            "rsi_14": round(rsi14, 2),
            "rsi_252": round(rsi252, 2),
            "tendencia": "ALTA" if tendencia_alta else "BAIXA",
            "recomendacao": rec,
            "cor_sinal": cor,
            "val_graham": round(preco_graham, 2),
            "val_bazin": round(preco_bazin, 2),
            "val_gordon": round(preco_gordon, 2),
            "upside_longo_prazo": round(upside, 2),
            "suporte": round(min_anual, 2),
            "resistencia": round(max_anual, 2),
            "stop_loss": round(preco_atual * 0.97, 2),
            "stop_gain": round(preco_atual * 1.06, 2),
            "fibonacci": fib
        }