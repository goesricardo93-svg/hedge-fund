import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta 
from scipy.signal import argrelextrema

class MotorAnalise:
    
    def calcular_stress_test(self, ticker, qtd, preco_atual):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            if hist.empty: return {}
            
            beta = 1.0
            try:
                ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
                df = pd.DataFrame({'Ativo': hist['Close'], 'Ibov': ibov}).dropna()
                if not df.empty:
                    ret = df.pct_change().dropna()
                    cov = ret.cov().iloc[0,1]
                    var = ret['Ibov'].var()
                    if var != 0: beta = cov / var
            except: pass
            
            exp = qtd * preco_atual
            return {
                "Crash (-10%)": exp * (beta * -0.10),
                "Crash (-30%)": exp * (beta * -0.30),
                "Juros (+1%)": exp * (beta * -0.15) if "11.SA" in ticker else exp * (beta * -0.05),
                "Beta": beta
            }
        except: return {}

    def calcular_valuation_consenso(self, info, preco_atual, ticker, modo_crise=False):
        modelos = {}
        dados_brutos = {}
        try:
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            div_yield = info.get('dividendYield', 0) or 0
            div_anual = info.get('dividendRate', 0)
            if not div_anual: div_anual = div_yield * preco_atual
            roe = info.get('returnOnEquity', 0) or 0

            rf = 0.135 if modo_crise else 0.115 
            g = 0.01 if modo_crise else 0.02
            ke = rf + 0.05

            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div_anual > 0: modelos['Gordon'] = div_anual * (1 + g) / (ke - g)
            if div_anual > 0: modelos['Bazin'] = div_anual / 0.06
            
            vals = [v for v in modelos.values() if v > 0]
            p_justo = float(np.median(vals)) if vals else 0
            p_teto = p_justo * (0.85 if "11.SA" in ticker else 0.75)
            
            dados_brutos = {"LPA": lpa, "VPA": vpa, "ROE": roe}
            return p_justo, p_teto, 0.25, modelos, dados_brutos
        except: return 0, 0, 0, {}, {}

    def analisar(self, hist, info, ticker, modo_crise=False):
        try:
            if hist is None or hist.empty: return None
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])

            # Valuation
            p_justo, p_teto, margem, modelos, dados = self.calcular_valuation_consenso(info, atual, ticker, modo_crise)
            
            # Técnica
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else 0
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            if loss.iloc[-1] != 0: rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1]))
            else: rsi = 50

            # Score Simples
            score = 50
            if p_justo > 0 and atual <= p_justo: score += 20
            if mme9 > mme21: score += 20
            if rsi < 30: score += 10
            
            decisao = "COMPRA" if score >= 60 else "VENDA" if score <= 40 else "NEUTRO"

            return {
                "score_ia": score, "decisao_ia": decisao,
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto,
                "modelos_val": modelos, "dados_fund": dados,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "mm200": mm200,
                "motivos": "Análise Técnica + Fundamentalista", "alertas": ""
            }
        except: return None
        
    def monte_carlo_carteira(self, retornos, val_ini, sims=1000):
        try:
            days = 252 * 5
            r_mean = retornos.mean(); r_std = retornos.std()
            res = []
            for _ in range(sims):
                daily = np.random.normal(r_mean, r_std, days)
                res.append(np.cumprod(1 + daily) * val_ini)
            df = pd.DataFrame(res).T
            return pd.DataFrame({"Média": df.mean(axis=1), "Pessimista": df.quantile(0.05, axis=1)})
        except: return pd.DataFrame()