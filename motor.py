import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        """Mapeia automaticamente a indústria do Yahoo para as categorias do Ricardo"""
        # Se for FII (termina com 11 e não é ETF conhecido)
        if ticker.endswith('11.SA') and ticker not in ['IVVB11.SA', 'BOVA11.SA']:
            industry = (info.get('industry', '') or '').lower()
            if 'paper' in industry or 'receivables' in industry: return "FIIs-Papel"
            if 'brick' in industry or 'office' in industry or 'malls' in industry: return "FIIs-Tijolo"
            return "FIIs-Outros"

        # Se for Exterior (Exemplo IVVB11 ou ativos sem .SA)
        if ticker in ['IVVB11.SA'] or not ticker.endswith('.SA'):
            return "Exterior"

        # Ações Brasil - Mapeamento por Indústria e Setor
        industry = (info.get('industry', '') or '').lower()
        sector = (info.get('sector', '') or '').lower()

        if 'banks' in industry: return "Ações-Bancos"
        if 'utilities' in sector or 'electricity' in industry: return "Ações-Elétricas"
        if 'insurance' in industry: return "Ações-Seguridade"
        if 'mining' in industry or 'oil' in industry or 'steel' in industry: return "Ações-Commodities"
        
        return "Ações-Outros"

    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None
            fechamento = hist["Close"] if "Close" in hist.columns else hist.iloc[:, 0]
            volume = hist["Volume"] if "Volume" in hist.columns else pd.Series([0]*len(fechamento))
            if len(fechamento) < 30: return None
            
            preco_atual = float(fechamento.iloc[-1])
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()

            def safe_get(key, default=0.0):
                val = info.get(key); return float(val) if val is not None else default

            div_rate = safe_get("trailingAnnualDividendRate")
            dy = div_rate / preco_atual if preco_atual > 0 else safe_get("dividendYield")
            
            # Cálculo de Score simplificado para este bloco
            score = 70 # Valor base
            decisao = "🟢 COMPRA" if score > 60 else "⚪ MANTER"

            window = 60
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())

            return {
                "preco": preco_atual, "rsi": 50, "volatilidade": 0.2, 
                "p_bazin": div_rate/0.06 if div_rate > 0 else 0,
                "p_graham": np.sqrt(22.5 * safe_get("trailingEps") * safe_get("bookValue")) if safe_get("trailingEps") > 0 else 0,
                "p_gordon": div_rate/0.06 if div_rate > 0 else 0,
                "dy": dy, "suporte": suporte, "resistencia": resistencia,
                "stop_loss": suporte * 0.97, "stop_gain": resistencia * 1.02,
                "score_ia": score, "decisao_ia": decisao, "motivos": "Análise Técnica e Fundamentalista",
                "pl": safe_get("trailingPE"), "pvp": safe_get("priceToBook"),
                "roe": safe_get("returnOnEquity"), "margem": safe_get("profitMargins"),
                "divida_ebitda": safe_get("debtToEbitda"),
                "sinal_tecnico": "TENDÊNCIA ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "TENDÊNCIA BAIXA",
                "preco_alvo_entrada": mme9.iloc[-1], "vol_relativo": 1.2,
                "mme9": mme9.iloc[-1], "mme21": mme21.iloc[-1],
                "macd": macd_line.iloc[-1], "macd_signal": signal_line.iloc[-1],
                "liq_corrente": safe_get("currentRatio"), "cresc_receita": safe_get("revenueGrowth")
            }
        except: return None

    def monte_carlo_carteira(self, retornos, val_ini, aporte, anos=10, sims=1000):
        if len(retornos) == 0: return np.array([])
        mu, sigma = np.log(1 + retornos).mean(), np.log(1 + retornos).std()
        res = []
        for _ in range(sims):
            path = np.exp((mu - 0.5 * sigma**2) + sigma * np.random.normal(0, 1, anos*252))
            bal = val_ini
            for i, r in enumerate(path):
                bal *= r
                if (i+1) % 21 == 0: bal += aporte
            res.append(bal)
        return np.array(res)

    def consultar_dividendos(self, ticker):
        try:
            t = yf.Ticker(ticker); divs = t.dividends
            hoje = pd.Timestamp.now().normalize()
            res = {"ultimo_data": "-", "ultimo_valor": "-", "proximo_data": "-", "proximo_valor": "-", "status": "NEUTRO"}
            if not divs.empty:
                res["ultimo_data"] = divs.index[-1].strftime('%d/%m/%Y')
                res["ultimo_valor"] = f"R$ {float(divs.iloc[-1]):.2f}"
            return res
        except: return {"status": "ERRO"}