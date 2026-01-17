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

    def analisar(self, df):
        if len(df) < self.p_longo: return None
        df['close'] = df['close'].ffill()
        
        # Cálculos Base
        ma252_serie = df['close'].rolling(window=self.p_longo).mean()
        ma252 = ma252_serie.iloc[-1]
        rsi14 = self.calcular_rsi(df['close'], self.p_curto).iloc[-1]
        rsi252 = self.calcular_rsi(df['close'], self.p_longo).iloc[-1]
        
        preco_atual = float(df['close'].iloc[-1])
        resistencia = float(df['close'].tail(self.p_longo).max())
        suporte = float(df['close'].tail(self.p_longo).min())
        
        # Lógica de Recomendação Objetiva
        tendencia_alta = preco_atual > ma252
        
        if tendencia_alta:
            if rsi14 < 45:
                recomendacao = "COMPRA (Correção na Tendência)"
                cor = "green"
            elif rsi14 > 75:
                recomendacao = "AGUARDAR (Ativo Esticado)"
                cor = "yellow"
            else:
                recomendacao = "MANTER (Tendência de Alta)"
                cor = "blue"
        else:
            if rsi14 > 60:
                recomendacao = "VENDA (Repique na Baixa)"
                cor = "red"
            else:
                recomendacao = "FORA (Tendência de Baixa)"
                cor = "gray"

        # Fibonacci
        diff = resistencia - suporte
        fib = {
            "61.8%": round(resistencia - (0.382 * diff), 2),
            "50.0%": round(resistencia - (0.5 * diff), 2),
            "38.2%": round(resistencia - (0.618 * diff), 2)
        }

        return {
            "preco": round(preco_atual, 2),
            "rsi_14": round(rsi14, 2),
            "rsi_252": round(rsi252, 2),
            "ma252": round(ma252, 2),
            "tendencia": "ALTA" if tendencia_alta else "BAIXA",
            "recomendacao": recomendacao,
            "cor_sinal": cor,
            "suporte": round(suporte, 2),
            "resistencia": round(resistencia, 2),
            "stop_loss": round(preco_atual * 0.97, 2),
            "stop_gain": round(preco_atual * 1.06, 2),
            "fibonacci": fib
        }