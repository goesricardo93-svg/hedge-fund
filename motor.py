import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        """Mapeia o ativo conforme a estratégia do Ricardo (v56.0)"""
        industry = (info.get('industry', '') or '').lower()
        sector = (info.get('sector', '') or '').lower()
        business_summary = (info.get('longBusinessSummary', '') or '').lower()

        # --- LÓGICA PARA FIIs (Terminam com 11 e não são Exterior/ETFs) ---
        if ticker.endswith('11.SA') and ticker not in ['IVVB11.SA', 'BOVA11.SA']:
            # Palavras-chave para Papel (Recebíveis/Dívida)
            keywords_papel = ['recebíveis', 'crimes', 'cri', 'certificados', 'papel', 'paper', 'debt', 'receivables']
            if any(k in industry or k in business_summary for k in keywords_papel):
                return "FIIs-Papel"
            
            # Palavras-chave para Tijolo (Ativos Físicos)
            keywords_tijolo = ['logística', 'galpões', 'shoppings', 'malls', 'escritórios', 'offices', 'industrial', 'rent', 'logistics', 'properties']
            if any(k in industry or k in business_summary for k in keywords_tijolo):
                return "FIIs-Tijolo"
            
            return "FIIs-Outros"

        # --- LÓGICA PARA EXTERIOR ---
        if ticker in ['IVVB11.SA'] or not ticker.endswith('.SA'):
            return "Exterior"

        # --- LÓGICA PARA AÇÕES BRASIL ---
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
            
            preco_atual = float(fechamento.iloc[-1])
            
            # Cálculos de Médias e MACD
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()

            # Funções de segurança para dados financeiros
            def safe_get(key, default=0.0):
                val = info.get(key)
                return float(val) if val is not None else default

            div_rate = safe_get("trailingAnnualDividendRate")
            if div_rate == 0: div_rate = safe_get("dividendYield") * preco_atual
            
            # Valuation (Blindagem contra KeyError)
            p_bazin = div_rate / 0.06 if div_rate > 0 else 0
            p_graham = np.sqrt(22.5 * safe_get("trailingEps") * safe_get("bookValue")) if (safe_get("trailingEps") > 0 and safe_get("bookValue") > 0) else 0
            
            # Score IA
            score = 75 if mme9.iloc[-1] > mme21.iloc[-1] else 45
            
            # Volatilidade
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5) if not retornos.empty else 0

            return {
                "preco": preco_atual, "rsi": 50, "volatilidade": volatilidade, 
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_bazin,
                "dy": div_rate/preco_atual if preco_atual > 0 else 0,
                "suporte": float(fechamento.tail(60).min()), 
                "resistencia": float(fechamento.tail(60).max()),
                "stop_loss": float(fechamento.tail(60).min()) * 0.97,
                "stop_gain": float(fechamento.tail(60).max()) * 1.02,
                "score_ia": score, "decisao_ia": "COMPRA" if score > 60 else "MANTER",
                "motivos": "Análise Técnica e Setorial",
                "pl": safe_get("trailingPE"), "pvp": safe_get("priceToBook"),
                "roe": safe_get("returnOnEquity"), "margem": safe_get("profitMargins"),
                "divida_ebitda": safe_get("debtToEbitda"),
                "sinal_tecnico": "ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "BAIXA",
                "preco_alvo_entrada": preco_atual, "vol_relativo": 1.0,
                "mme9": mme9.iloc[-1], "mme21": mme21.iloc[-1],
                "macd": macd_line.iloc[-1], "macd_signal": signal_line.iloc[-1],
                "liq_corrente": safe_get("currentRatio"), "cresc_receita": safe_get("revenueGrowth")
            }
        except Exception as e:
            print(f"Erro no Motor para {ticker}: {e}")
            return None

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
            res = {"ultimo_data": "-", "ultimo_valor": "-", "proximo_data": "-", "proximo_valor": "-", "status": "NEUTRO"}
            if not divs.empty:
                res["ultimo_data"] = divs.index[-1].strftime('%d/%m/%Y')
                res["ultimo_valor"] = f"R$ {float(divs.iloc[-1]):.2f}"
            return res
        except: return {"status": "ERRO"}