import pandas as pd
import numpy as np

class MotorAnalise:
    def __init__(self):
        self.p_curto = 14
        self.p_longo = 252

    def calcular_rsi(self, serie, window):
        try:
            delta = serie.diff()
            ganho = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            perda = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = ganho / perda
            return 100 - (100 / (1 + rs))
        except:
            return pd.Series(50, index=serie.index)

    def analisar(self, df):
        # Proteção contra dados insuficientes
        if len(df) < 10: return None
        
        # Cálculos Base
        df['ma252'] = df['close'].rolling(window=min(len(df), self.p_longo)).mean()
        df['rsi_14'] = self.calcular_rsi(df['close'], self.p_curto)
        df['rsi_252'] = self.calcular_rsi(df['close'], self.p_longo)
        
        preco_atual = df['close'].iloc[-1]
        
        # Suporte e Resistência (com proteção de erro)
        resistencia_anual = df['close'].tail(self.p_longo).max()
        suporte_anual = df['close'].tail(self.p_longo).min()
        
        # Fibonacci
        diff = resistencia_anual - suporte_anual
        fib = {}
        if diff > 0:
            fib = {
                "61.8%": round(resistencia_anual - (0.382 * diff), 2),
                "50.0%": round(resistencia_anual - (0.5 * diff), 2),
                "38.2%": round(resistencia_anual - (0.618 * diff), 2)
            }

        return {
            "preco": round(preco_atual, 2),
            "rsi_14": round(df['rsi_14'].fillna(50).iloc[-1], 2),
            "rsi_252": round(df['rsi_252'].fillna(50).iloc[-1], 2),
            "ma252": round(df['ma252'].fillna(preco_atual).iloc[-1], 2),
            "tendencia": "ALTA" if preco_atual > df['ma252'].iloc[-1] else "BAIXA",
            "suporte": round(suporte_anual, 2),
            "resistencia": round(resistencia_anual, 2),
            "stop_loss": round(preco_atual * 0.97, 2),
            "stop_gain": round(preco_atual * 1.06, 2),
            "fibonacci": fib
        }

    def processar_df(self, df):
        df['ma252'] = df['close'].rolling(window=min(len(df), self.p_longo)).mean()
        return df