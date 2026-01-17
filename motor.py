import pandas as pd
import numpy as np

class MotorAnalise:
    def __init__(self):
        self.p_curto = 14
        self.p_longo = 252

    def calcular_rsi(self, serie, window=14):
        delta = serie.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))

    def analisar(self, df_prices, info=None, ticker=""):
        if isinstance(df_prices.columns, pd.MultiIndex):
            df = df_prices.xs(ticker, level=1, axis=1)
        else:
            df = df_prices

        if df.empty: return None
        precos = df['Close'].ffill().dropna()
        preco_atual = float(precos.iloc[-1])
        
        # --- MÉTRICAS TÉCNICAS & STOPS ---
        ma252 = precos.rolling(window=min(len(precos), self.p_longo)).mean().iloc[-1]
        rsi14 = self.calcular_rsi(precos, self.p_curto).iloc[-1]
        suporte = float(precos.tail(252).min())
        resistencia = float(precos.tail(252).max())
        
        # Cálculo de Stops Profissionais
        stop_loss = suporte * 0.97  # 3% abaixo do suporte anual
        
        # --- FUNDAMENTALISTAS ---
        dpa = info.get('dividendRate') or info.get('trailingAnnualDividendRate') or 0
        lpa = info.get('trailingEps') or 0
        vpa = info.get('bookValue') or 0
        g = info.get('earningsGrowth') or 0.05 # Gordon: Growth estimado ou 5%
        
        # Valuations
        p_graham = np.sqrt(max(0, 22.5 * lpa * vpa)) if (lpa > 0 and vpa > 0) else 0
        p_bazin = dpa / 0.06 if dpa > 0 else 0
        # Gordon Simplificado: D1 / (k - g) -> k=10%
        p_gordon = (dpa * (1 + g)) / (0.10 - g) if (0.10 - g) > 0 and dpa > 0 else 0
        
        is_etf = ".L" in ticker or (info and info.get('quoteType') == 'ETF')
        is_fii = ticker.endswith('11.SA') and not is_etf
        
        # Preço Teto Final (Média das metodologias disponíveis)
        if is_etf:
            preco_teto = 0
        elif is_fii:
            preco_teto = p_bazin
        else:
            metodos = [v for v in [p_graham, p_bazin, p_gordon] if v > 0]
            preco_teto = np.mean(metodos) if metodos else 0

        return {
            "preco": preco_atual,
            "rsi": rsi14,
            "tendencia": "ALTA" if preco_atual > ma252 else "BAIXA",
            "p_graham": p_graham,
            "p_bazin": p_bazin,
            "p_gordon": p_gordon,
            "preco_teto": preco_teto,
            "suporte": suporte,
            "resistencia": resistencia,
            "stop_loss": stop_loss,
            "stop_gain": preco_teto if preco_teto > preco_atual else resistencia,
            "precos_serie": precos,
            "cor": "green" if (preco_teto > preco_atual and preco_atual > ma252) else "yellow" if rsi14 > 70 else "gray"
        }