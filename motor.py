import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from scipy.signal import argrelextrema

class MotorAnalise:
    
    # --- 1. STRESS TEST ---
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

    # --- 2. VALUATION ---
    def calcular_valuation_consenso(self, info, preco_atual, ticker, modo_crise=False):
        modelos = {}
        dados_brutos = {}
        try:
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            div_yield = info.get('dividendYield', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            div_anual = info.get('dividendRate', 0)
            if not div_anual: div_anual = div_yield * preco_atual

            rf = 0.135 if modo_crise else 0.115 
            g = 0.01 if modo_crise else 0.02
            ke = rf + 0.06

            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div_anual > 0: modelos['Gordon'] = div_anual * (1 + g) / (ke - g)
            if div_anual > 0: modelos['Bazin'] = div_anual / (0.08 if modo_crise else 0.06)
            if roe > 0 and vpa > 0:
                pvp_justo = (roe - g) / (ke - g)
                if 0 < pvp_justo < 5: modelos['ROE'] = pvp_justo * vpa

            vals = [v for v in modelos.values() if v > 0 and v < preco_atual * 4]
            p_justo = float(np.median(vals)) if vals else 0
            
            margem = (0.25 if modo_crise else 0.15) if "11.SA" in ticker else (0.35 if modo_crise else 0.25)
            p_teto = p_justo * (1 - margem)
            
            dados_brutos = {"LPA": lpa, "VPA": vpa, "ROE": roe, "Div": div_anual}
            return p_justo, p_teto, margem, modelos, dados_brutos
        except: return 0, 0, 0, {}, {}

    # --- 3. EXTRAS ---
    def analisar_sentimento_news(self, ticker):
        try:
            t = yf.Ticker(ticker); news = t.news
            if not news: return 0, "Sem Notícias"
            score = 0
            pos = ["lucro", "alta", "dividend", "compra", "recorde"]
            neg = ["prejuízo", "queda", "fraude", "corrupção", "divida"]
            for n in news[:5]:
                ti = n.get('title', '').lower()
                s = (sum(1 for w in pos if w in ti) - sum(1 for w in neg if w in ti)) * 5
                score += s
            return score, ("Positivo" if score > 5 else "Negativo" if score < -5 else "Neutro")
        except: return 0, "Erro News"

    def analisar_macro(self):
        try:
            ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
            if ibov.empty: return 0, "Neutro"
            bull = ibov.iloc[-1] > ibov.rolling(200).mean().iloc[-1]
            return (5, "Bull Market") if bull else (-10, "Bear Market")
        except: return 0, "Neutro"

    def detectar_padroes_graficos(self, h, l, c):
        padroes = []; pts = 0
        try:
            n = 5
            idx_t = argrelextrema(h.values, np.greater_equal, order=n)[0]
            idx_f = argrelextrema(l.values, np.less_equal, order=n)[0]
            
            topos = [(i, h.iloc[i]) for i in idx_t]
            fundos = [(i, l.iloc[i]) for i in idx_f]
            
            if len(topos)>=2:
                if (topos[-1][0]-topos[-2][0]>20) and abs(topos[-2][1]-topos[-1][1])/topos[-2][1]<0.05:
                     padroes.append("Cup & Handle"); pts += 25
            
            return ", ".join(padroes) if padroes else None, pts
        except: return None, 0

    def identifying_candle_pattern(self, o, h, l, c):
        co = abs(c-o); r = h-l
        if r==0: return None
        ss = h-max(c,o); si = min(c,o)-l
        if co <= r*0.03: return "Doji"
        if si >= 2*co and ss <= 0.1*co: return "Martelo"
        return None

    def calcular_probabilidades(self, hist, preco_atual, dias=21):
        try:
            ret = hist['Close'].pct_change().dropna()
            vol = ret.std() * (252**0.5)
            return {"vol_anual": vol}
        except: return {}

    # --- CORE ---
    def analisar(self, hist, info, ticker, modo_crise=False):
        try:
            if hist is None or hist.empty: return None
            hist = hist.ffill().bfill()
            if len(hist) < 30: return None
            
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])

            macro_sc, macro_txt = self.analisar_macro()
            news_sc, news_txt = self.analisar_sentimento_news(ticker)
            p_justo, p_teto, margem, modelos, dados_fund = self.calcular_valuation_consenso(info, atual, ticker, modo_crise)
            fig_name, fig_sc = self.detectar_padroes_graficos(h, l, c)
            candle = self.identifying_candle_pattern(hist["Open"].iloc[-1], h.iloc[-1], l.iloc[-1], atual)
            probs = self.calcular_probabilidades(hist, atual)

            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else 0
            
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50
            
            dy = (info.get('dividendYield', 0) or 0) * 100
            pvp = info.get('priceToBook', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            divida = info.get('debtToEbitda', 0) or 0
            margem_liq = info.get('profitMargins', 0) or 0

            sc_q = 50; sc_c = 50
            motivos = []; alertas = []

            if p_justo > 0:
                if atual <= p_teto: sc_q += 30; motivos.append("Barato")
                elif atual <= p_justo: sc_q += 10
                else: sc_q -= 30; alertas.append("Caro")
            
            if "11.SA" in ticker:
                if dy > 10: sc_q += 10
                if 0.85 <= pvp <= 1.05: sc_q += 10
            else:
                if roe > 0.15: sc_q += 10
                if pvp < 1.5 and pvp > 0: sc_q += 5

            sc_c += macro_sc + news_sc
            if mme9 > mme21: sc_c += 15; motivos.append("Tend. Alta")
            else: sc_c -= 15
            
            if rsi < 30: sc_c += 10; motivos.append("RSI Baixo")
            if fig_name: sc_c += fig_sc; motivos.append(fig_name)

            pq = 0.7 if modo_crise else 0.5
            pc = 0.3 if modo_crise else 0.5
            final = int((sc_q * pq) + (sc_c * pc))
            final = min(100, max(0, final))
            
            decisao = "🟢 COMPRA" if final >= 60 else "🔴 VENDA" if final <= 40 else "⚪ NEUTRO"

            return {
                "score_ia": final, "decisao_ia": decisao,
                "score_qualidade": int(sc_q), "score_conviccao": int(sc_c),
                "motivos": ", ".join(motivos), "alertas": ", ".join(alertas),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto, "margem": margem, 
                "modelos_val": modelos, "dados_fund": dados_fund,
                "macro": macro_txt, "news": news_txt, "probs": probs,
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "mm200": mm200,
                "padrao_grafico": fig_name, "candle": candle,
                "dy_anual": dy, "pvp": pvp, "roe": roe, "divida_ebitda": divida, "margem_liq": margem_liq
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
            return pd.DataFrame({"Media": df.mean(axis=1), "Pessimista": df.quantile(0.05, axis=1)})
        except: return pd.DataFrame()