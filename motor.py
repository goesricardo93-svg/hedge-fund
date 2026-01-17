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
        # Se for MultiIndex, extrai apenas a coluna do ticker
        if isinstance(df_prices.columns, pd.MultiIndex):
            df = df_prices.xs(ticker, level=1, axis=1)
        else:
            df = df_prices

        if df.empty or len(df) < 5: return None
        
        # Garante que temos a coluna Close
        precos = df['Close'].ffill().dropna()
        if precos.empty: return None

        preco_atual = float(precos.iloc[-1])
        ma252 = precos.rolling(window=min(len(precos), self.p_longo)).mean().iloc[-1]
        rsi14 = self.calcular_rsi(precos, self.p_curto).iloc[-1]
        
        is_etf = ".L" in ticker or (info and info.get('quoteType') == 'ETF')
        is_fii = ticker.endswith('11.SA') and not is_etf

        # Captura de dados fundamentalistas
        lpa = info.get('trailingEps', 0) if info else 0
        vpa = info.get('bookValue', 0) if info else 0
        # Dividendos: tenta várias chaves que o Yahoo pode usar
        dpa = info.get('dividendRate') or info.get('trailingAnnualDividendRate') or 0
        
        preco_teto = 0
        tipo_label = "AÇÃO"

        if is_etf:
            tipo_label = "UCITS (IRLANDA)"
        elif is_fii:
            tipo_label = "FII"
            preco_teto = dpa / 0.06 if dpa > 0 else 0
        else:
            p_graham = np.sqrt(max(0, 22.5 * lpa * vpa)) if (lpa > 0 and vpa > 0) else 0
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            # Se tiver os dois, faz a média. Se tiver só um, usa ele.
            vals = [v for v in [p_graham, p_bazin] if v > 0]
            preco_teto = np.mean(vals) if vals else 0

        tendencia_alta = preco_atual > ma252
        sobrecomprado = rsi14 > 68
        sobrevendido = rsi14 < 35
        margem_seg = (preco_teto > preco_atual * 1.05) if preco_teto > 0 else False

        # Recomendação
        if is_etf:
            if sobrevendido: rec, cor = "COMPRA (ETF Descontado)", "green"
            elif sobrecomprado: rec, cor = "AGUARDAR (ETF Esticado)", "yellow"
            else: rec, cor = "MANTER (Tendência Segue)", "blue" if tendencia_alta else "gray"
        else:
            if margem_seg and tendencia_alta and not sobrecomprado:
                rec, cor = f"COMPRA SEGURA ({tipo_label})", "green"
            elif sobrecomprado:
                rec, cor = "AGUARDAR (Preço Esticado)", "yellow"
            elif not tendencia_alta and not margem_seg:
                rec, cor = "FORA / VENDA (Risco Alto)", "red"
            else:
                rec, cor = "NEUTRO / AGUARDAR", "gray"

        return {
            "tipo": tipo_label,
            "preco": preco_atual,
            "rsi": rsi14,
            "recomendacao": rec,
            "cor": cor,
            "preco_teto": preco_teto,
            "suporte": float(precos.tail(252).min()),
            "precos_serie": precos # Retorna a série limpa para o gráfico
        }