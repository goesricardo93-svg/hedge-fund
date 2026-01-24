import pandas as pd
import numpy as np
import yfinance as yf
from datetime import timedelta
from scipy.signal import argrelextrema
from scipy.stats import norm

class MotorAnalise:
    
    # ==============================================================================
    # 1. SIMULADOR DE STRESS TEST & CENÁRIOS (v126)
    # ==============================================================================
    def calcular_stress_test(self, ticker, qtd, preco_atual):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            if hist.empty: return {}

            try:
                ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
                ret_ativo = hist['Close'].pct_change().dropna()
                ret_ibov = ibov.pct_change().dropna()
                
                df_cov = pd.DataFrame({'Ativo': ret_ativo, 'Ibov': ret_ibov}).dropna()
                cov = df_cov.cov().iloc[0,1]
                var_ibov = df_cov['Ibov'].var()
                beta = cov / var_ibov
            except:
                beta = 1.0

            exposicao = qtd * preco_atual
            
            cenarios = {
                "Crash Leve (-10% Mercado)": exposicao * (beta * -0.10),
                "Crash Severo (-30% Mercado)": exposicao * (beta * -0.30),
                "Juros Explosivos (Tech/FII Sofrem)": exposicao * (beta * -0.15) if "11.SA" in ticker else exposicao * (beta * -0.05),
                "Boom Commodities (+20%)": exposicao * (beta * 0.20) if "VALE" in ticker or "PETR" in ticker else exposicao * (beta * 0.05)
            }
            return cenarios
        except: return {}

    def calcular_probabilidades(self, hist, preco_atual, dias=21):
        try:
            retornos = hist['Close'].pct_change().dropna()
            vol_diaria = retornos.std()
            vol_periodo = vol_diaria * np.sqrt(dias)
            
            cenario_base_min = preco_atual * (1 - vol_periodo)
            cenario_base_max = preco_atual * (1 + vol_periodo)
            otimista = preco_atual * (1 + (2 * vol_periodo))
            pessimista = preco_atual * (1 - (2 * vol_periodo))
            
            return {
                "base_min": cenario_base_min,
                "base_max": cenario_base_max,
                "otimista": otimista,
                "pessimista": pessimista,
                "volatilidade_periodo": vol_periodo
            }
        except: return {}

    # ==============================================================================
    # 2. VALUATION
    # ==============================================================================
    def calcular_valuation_consenso(self, info, preco_atual, ticker, modo_crise=False):
        modelos = {}
        try:
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            div_yield = info.get('dividendYield', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            div_anual = info.get('dividendRate', 0)
            if not div_anual: div_anual = div_yield * preco_atual

            risk_free = 0.135 if modo_crise else 0.115 
            premio_risco = 0.07 if modo_crise else 0.05
            ke = risk_free + premio_risco
            g = 0.01 if modo_crise else 0.02

            if lpa > 0 and vpa > 0: modelos['Graham'] = np.sqrt(22.5 * lpa * vpa)
            if div_anual > 0: modelos['Gordon'] = div_anual * (1 + g) / (ke - g)
            if div_anual > 0: modelos['Bazin'] = div_anual / (0.08 if modo_crise else 0.06)
            if roe > 0 and vpa > 0:
                pvp_justo = (roe - g) / (ke - g)
                if 0 < pvp_justo < 5: modelos['ROE'] = pvp_justo * vpa

            validos = [v for v in modelos.values() if v > 0 and v < preco_atual * 4]
            if not validos: return 0, 0, 0, {}

            p_justo = float(np.median(validos))
            
            is_fii = "11.SA" in ticker
            base_margem = 0.15 if is_fii else 0.25
            if modo_crise: base_margem += 0.10
            
            p_teto = p_justo * (1 - base_margem)
            return p_justo, p_teto, base_margem, modelos
        except: return 0, 0, 0, {}

    # ==============================================================================
    # 3. MÓDULOS AUXILIARES
    # ==============================================================================
    def analisar_sentimento_news(self, ticker):
        try:
            t = yf.Ticker(ticker); news = t.news; score_news = 0
            if not news: return 0, "Sem Notícias"
            pos = ["lucro", "profit", "alta", "high", "dividend", "aquisição", "buy", "compra", "supera", "recorde"]
            neg = ["prejuízo", "loss", "queda", "low", "fraude", "investigação", "corrupção", "falência", "divida", "risco"]
            for n in news[:5]:
                ti = n.get('title', '').lower()
                s = (sum(1 for w in pos if w in ti) - sum(1 for w in neg if w in ti)) * 5
                score_news += s
            return score_news, ("Positivo" if score_news > 5 else "Negativo" if score_news < -5 else "Neutro")
        except: return 0, "Erro News"

    def analisar_macro(self):
        try:
            ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
            if ibov.empty: return 0, "Neutro"
            return (5, "Bull") if ibov.iloc[-1] > ibov.rolling(200).mean().iloc[-1] else (-10, "Bear")
        except: return 0, "Neutro"

    def detectar_padroes_graficos(self, highs, lows, closes):
        padroes = []; pontuacao = 0
        try:
            n = 5
            idx_t = argrelextrema(highs.values, np.greater_equal, order=n)[0]
            idx_f = argrelextrema(lows.values, np.less_equal, order=n)[0]
            topos = [(i, highs.iloc[i]) for i in idx_t]
            fundos = [(i, lows.iloc[i]) for i in idx_f]
            if len(topos)<3 or len(fundos)<3: return None, 0
            ut, uf = topos[-3:], fundos[-3:]

            if len(topos)>=2:
                te, pe = topos[-2]; td, pd = topos[-1]
                if (td-te > 20) and (abs(pe-pd)/pe < 0.05):
                    smin = lows.iloc[te:td].min()
                    if (pe-smin)/pe > 0.10 and abs(closes.iloc[-1]-pd)/pd < 0.05:
                        padroes.append("☕ Cup & Handle"); pontuacao += 25
            try:
                st = np.polyfit([x[0] for x in ut], [x[1] for x in ut], 1)[0]
                sf = np.polyfit([x[0] for x in uf], [x[1] for x in uf], 1)[0]
                if abs(st)<0.05 and sf>0.1: padroes.append("📐 Triângulo Asc."); pontuacao += 15
                elif st<-0.1 and abs(sf)<0.05: padroes.append("🔻 Triângulo Desc."); pontuacao -= 15
            except: pass
            if len(ut)==3:
                if ut[1][1]>ut[0][1] and ut[1][1]>ut[2][1] and abs(ut[0][1]-ut[2][1])/ut[0][1]<0.05:
                    if len(highs)-ut[2][0]<20: padroes.append("☠️ OCO"); pontuacao -= 20
            if len(uf)>=2:
                if abs(uf[-2][1]-uf[-1][1])/uf[-2][1]<0.03 and (len(lows)-uf[-1][0]<15):
                     padroes.append("🚀 Fundo Duplo W"); pontuacao += 15
            if len(ut)>=2:
                if abs(ut[-2][1]-ut[-1][1])/ut[-2][1]<0.03 and (len(highs)-ut[-1][0]<15):
                     padroes.append("📉 Topo Duplo M"); pontuacao -= 15
            return ", ".join(padroes) if padroes else None, pontuacao
        except: return None, 0

    def identifying_candle_pattern(self, open_p, high_p, low_p, close_p):
        c = abs(close_p - open_p); r = high_p - low_p
        if r == 0: return None
        ss = high_p - max(close_p, open_p); si = min(close_p, open_p) - low_p
        if c <= r*0.03: return "Doji"
        if si >= 2*c and ss <= 0.1*c: return "🔨 Martelo"
        if ss >= 2*c and si <= 0.1*c: return "☄️ Estrela Cadente"
        if c >= r*0.90: return "Marubozu"
        return None

    def identificar_setor(self, info, ticker):
        if ticker.endswith('11.SA'): return "FII"
        return "Ação"

    # ==============================================================================
    # 4. ANÁLISE CORE
    # ==============================================================================
    def analisar(self, hist, info, ticker, modo_crise=False):
        try:
            if hist is None or hist.empty: return None
            hist = hist.ffill().bfill()
            if len(hist) < 30: return None
            
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]; v = hist["Volume"]
            atual = float(c.iloc[-1])

            # --- SUB-SCORES ---
            score_qualidade = 50 
            score_conviccao = 50 
            motivos = []; alertas = []

            # 1. MACRO & NEWS
            macro_sc, macro_txt = self.analisar_macro()
            news_sc, news_txt = self.analisar_sentimento_news(ticker)
            score_conviccao += macro_sc + news_sc
            if modo_crise and macro_sc < 0: score_conviccao -= 20 

            # 2. VALUATION
            p_justo, p_teto, margem, modelos = self.calcular_valuation_consenso(info, atual, ticker, modo_crise)
            
            if p_justo > 0:
                if atual <= p_teto: 
                    score_qualidade += 30; motivos.append(f"💎 Muito Barato (Margem {margem*100:.0f}%)")
                elif atual <= p_justo:
                    score_qualidade += 10; motivos.append("⚖️ Preço Justo")
                else:
                    score_qualidade -= 30; alertas.append("💸 Caro")

            # Fundamentos Extras
            dy = (info.get('dividendYield', 0) or 0) * 100
            pvp = info.get('priceToBook', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            
            if "11.SA" in ticker:
                if dy > 10: score_qualidade += 10
                if 0.85 <= pvp <= 1.05: score_qualidade += 10
            else:
                if roe > 0.15: score_qualidade += 10
                if pvp < 1.5 and pvp > 0: score_qualidade += 5

            # 3. TÉCNICA
            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else 0
            
            if mme9 > mme21: score_conviccao += 15; motivos.append("📈 Tend. Alta")
            else: score_conviccao -= 15; alertas.append("📉 Tend. Baixa")
            
            if mm200 > 0:
                if atual > mm200: 
                    score_conviccao += 10
                    score_qualidade += 5 # (Tendencia Longa valida qualidade) - CORRIGIDO AQUI
                else: 
                    score_conviccao -= 20
                    alertas.append("⚠️ Abaixo MM200 (Bear)")

            # Liquidez
            if v.iloc[-1] * atual < 50000: 
                score_conviccao = 0; score_qualidade = 0; alertas.append("☠️ ILÍQUIDO")

            # --- CONSOLIDAÇÃO ---
            peso_qualidade = 0.7 if modo_crise else 0.5
            peso_conviccao = 0.3 if modo_crise else 0.5
            
            score_final = (score_qualidade * peso_qualidade) + (score_conviccao * peso_conviccao)
            score_final = min(100, max(0, int(score_final)))
            decisao = "🟢 COMPRA" if score_final >= 60 else "🔴 VENDA" if score_final <= 40 else "⚪ NEUTRO"
            if score_final >= 80: decisao = "🟢🟢 COMPRA FORTE"

            probs = self.calcular_probabilidades(hist, atual)

            return {
                "score_ia": score_final,
                "score_qualidade": int(score_qualidade),
                "score_conviccao": int(score_conviccao),
                "decisao_ia": decisao,
                "motivos": ", ".join(motivos),
                "alertas": ", ".join(alertas),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto, "margem": margem,
                "macro": macro_txt, "news": news_txt,
                "probs": probs,
                "modelo_crise": modo_crise
            }
        except: return None