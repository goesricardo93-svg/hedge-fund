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
        
        # --- VALUATIONS (Fundamentalista) ---
        # Extração de dados (ou valores fictícios para teste se info estiver vazio)
        lpa = info.get('trailingEps', 2.0) if info else 2.0
        vpa = info.get('bookValue', 15.0) if info else 15.0
        dpa = info.get('dividendRate', 1.0) if info else 1.0
        g = 0.05 # Crescimento esperado de 5%
        k = 0.11 # Taxa de desconto (Selic/Oportunidade)

        # 1. Graham
        preco_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
        
        # 2. Bazin (Dividend Yield 6%)
        preco_bazin = dpa / 0.06 if dpa else 0
        
        # 3. Gordon
        preco_gordon = (dpa * (1 + g)) / (k - g) if (k > g) else 0

        # --- PROJEÇÕES ---
        media_valua = np.mean([p for p in [preco_graham, preco_bazin, preco_gordon] if p > 0])
        upside = ((media_valua / preco_atual) - 1) * 100

        return {
            "preco": round(preco_atual, 2),
            "ma252": round(ma252, 2),
            "rsi_14": round(self.calcular_rsi(df['close'], self.p_curto).iloc[-1], 2),
            "recomendacao": "COMPRA" if preco_atual < media_valua and preco_atual > ma252 else "AGUARDAR",
            "val_graham": round(preco_graham, 2),
            "val_bazin": round(preco_bazin, 2),
            "val_gordon": round(preco_gordon, 2),
            "upside_longo_prazo": round(upside, 2),
            "suporte": round(df['close'].tail(252).min(), 2),
            "resistencia": round(df['close'].tail(252).max(), 2),
            "fibonacci": {"61.8%": round(preco_atual * 1.1, 2)} # Simplificado para o exemplo
        }