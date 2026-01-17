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
        # Tratamento do MultiIndex do yfinance
        if isinstance(df_prices.columns, pd.MultiIndex):
            df = df_prices.xs(ticker, level=1, axis=1)
        else:
            df = df_prices

        if df.empty: return None
        
        precos = df['Close'].ffill().dropna()
        preco_atual = float(precos.iloc[-1])
        
        # --- ANÁLISE TÉCNICA ESTRUTURADA ---
        ma252 = precos.rolling(window=min(len(precos), self.p_longo)).mean().iloc[-1]
        rsi14 = self.calcular_rsi(precos, self.p_curto).iloc[-1]
        suporte = float(precos.tail(252).min())
        resistencia = float(precos.tail(252).max())
        tendencia = "ALTA" if preco_atual > ma252 else "BAIXA"
        
        # Gerenciamento de Risco (Stops)
        stop_loss = suporte * 0.97  # 3% abaixo do suporte anual (técnico)
        
        # --- VALUATION FUNDAMENTALISTA (Bazin, Graham, Gordon) ---
        dpa = info.get('dividendRate') or info.get('trailingAnnualDividendRate') or 0
        lpa = info.get('trailingEps') or 0
        vpa = info.get('bookValue') or 0
        # Gordon: Crescimento estimado (usa 5% se não encontrar)
        g = info.get('earningsGrowth') or 0.05 
        
        # Modelos
        p_graham = np.sqrt(max(0, 22.5 * lpa * vpa)) if (lpa > 0 and vpa > 0) else 0
        p_bazin = dpa / 0.06 if dpa > 0 else 0
        p_gordon = (dpa * (1 + g)) / (0.10 - g) if (0.10 - g) > 0 and dpa > 0 else 0
        
        is_etf = ".L" in ticker or (info and info.get('quoteType') == 'ETF')
        is_fii = ticker.endswith('11.SA') and not is_etf
        
        # Preço Teto Consolidado
        if is_etf:
            preco_teto = 0
        elif is_fii:
            preco_teto = p_bazin
        else:
            metodos = [v for v in [p_graham, p_bazin, p_gordon] if v > 0]
            preco_teto = np.mean(metodos) if metodos else 0

        # Margem de Segurança e Stop Gain
        upside = ((preco_teto / preco_atual) - 1) * 100 if preco_teto > 0 else 0
        stop_gain = preco_teto if preco_teto > preco_atual else resistencia

        # Veredito
        if is_etf:
            if rsi14 < 35: rec, cor = "COMPRA (Oportunidade Técnica)", "green"
            elif rsi14 > 68: rec, cor = "AGUARDAR (Sobrecomprado)", "yellow"
            else: rec, cor = f"MANTER ({tendencia})", "blue"
        else:
            if preco_teto > preco_atual * 1.1 and tendencia == "ALTA" and rsi14 < 65:
                rec, cor = "COMPRA SEGURA (Margem + Tendência)", "green"
            elif preco_atual > preco_teto or rsi14 > 70:
                rec, cor = "AGUARDAR / CARO", "yellow"
            else:
                rec, cor = "NEUTRO / OBSERVAR", "gray"

        return {
            "tipo": "ETF" if is_etf else ("FII" if is_fii else "AÇÃO"),
            "preco": preco_atual,
            "rsi": rsi14,
            "ma252": ma252,
            "suporte": suporte,
            "resistencia": resistencia,
            "tendencia": tendencia,
            "p_graham": p_graham,
            "p_bazin": p_bazin,
            "p_gordon": p_gordon,
            "preco_teto": preco_teto,
            "upside": upside,
            "stop_loss": stop_loss,
            "stop_gain": stop_gain,
            "recomendacao": rec,
            "cor": cor,
            "precos_serie": precos
        }