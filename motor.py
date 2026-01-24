import pandas as pd
import numpy as np
import yfinance as yf
from datetime import timedelta
from scipy.signal import argrelextrema
from scipy.stats import norm

class MotorAnalise:
    
    # ==============================================================================
    # 1. RISCO E CENÁRIOS (STRESS TEST)
    # ==============================================================================
    def calcular_stress_test(self, ticker, qtd, preco_atual):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            if hist.empty: return {}
            
            # Cálculo de Beta Manual
            beta = 1.0
            try:
                ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
                # Alinhamento de datas
                df = pd.DataFrame({'Ativo': hist['Close'], 'Ibov': ibov}).dropna()
                if not df.empty:
                    ret = df.pct_change().dropna()
                    cov = ret.cov().iloc[0,1]
                    var = ret['Ibov'].var()
                    beta = cov / var
            except: pass
            
            exposicao = qtd * preco_atual
            
            # Cenários de Choque
            return {
                "Crash Leve (-10% Mercado)": exposicao * (beta * -0.10),
                "Crash Severo (-30% Mercado)": exposicao * (beta * -0.30),
                "Crise Juros (+1% Selic)": exposicao * (beta * -0.15) if "11.SA" in ticker else exposicao * (beta * -0.05),
                "Boom Commodities (+20%)": exposicao * (beta * 0.20) if "VALE" in ticker or "PETR" in ticker else 0,
                "Beta Calculado": beta
            }
        except: return {}

    def calcular_probabilidades(self, hist, preco_atual, dias=21):
        try:
            retornos = hist['Close'].pct_change().dropna()
            vol_diaria = retornos.std()
            vol_anual = vol_diaria * (252**0.5)
            vol_periodo = vol_diaria * np.sqrt(dias)
            
            return {
                "base_min": preco_atual * (1 - vol_periodo),
                "base_max": preco_atual * (1 + vol_periodo),
                "otimista": preco_atual * (1 + 2*vol_periodo),
                "pessimista": preco_atual * (1 - 2*vol_periodo),
                "volatilidade_anual": vol_anual
            }
        except: return {}

    # ==============================================================================
    # 2. VALUATION INSTITUCIONAL (CONSENSO)
    # ==============================================================================
    def calcular_valuation_consenso(self, info, preco_atual, ticker, modo_crise=False):
        modelos = {}
        dados_brutos = {}
        try:
            # Coleta de Dados Brutos
            lpa = info.get('trailingEps', 0) or 0
            vpa = info.get('bookValue', 0) or 0
            div_yield = info.get('dividendYield', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            
            # Prioriza valor nominal do dividendo, senão usa yield
            div_anual = info.get('dividendRate', 0)
            if not div_anual: div_anual = div_yield * preco_atual

            # Parâmetros Macro (Ajustáveis pelo Modo Crise)
            risk_free = 0.135 if modo_crise else 0.115 
            premio_risco = 0.07 if modo_crise else 0.05
            ke = risk_free + premio_risco # Custo de Capital
            g_perp = 0.01 if modo_crise else 0.02 # Crescimento

            # 1. Graham (Valor Patrimonial)
            if lpa > 0 and vpa > 0: 
                modelos['Graham'] = np.sqrt(22.5 * lpa * vpa)

            # 2. Gordon (Fluxo de Dividendos)
            if div_anual > 0: 
                modelos['Gordon'] = div_anual * (1 + g_perp) / (ke - g_perp)

            # 3. Bazin (Preço Teto por Yield)
            if div_anual > 0: 
                yield_exigido = 0.08 if modo_crise else 0.06
                modelos['Bazin'] = div_anual / yield_exigido

            # 4. Valuation por ROE (Justo pelo Retorno)
            if roe > 0 and vpa > 0:
                pvp_justo = (roe - g_perp) / (ke - g_perp)
                if 0 < pvp_justo < 5: # Filtra distorções
                    modelos['Justo (ROE)'] = pvp_justo * vpa

            # Consenso (Mediana dos modelos válidos)
            validos = [v for v in modelos.values() if v > 0 and v < preco_atual * 4]
            p_justo = float(np.median(validos)) if validos else 0
            
            # Margem de Segurança
            is_fii = "11.SA" in ticker
            base_margem = 0.15 if is_fii else 0.25
            if modo_crise: base_margem += 0.10
            
            p_teto = p_justo * (1 - base_margem)
            
            dados_brutos = {"LPA": lpa, "VPA": vpa, "ROE": roe, "Div. Anual": div_anual, "Ke": ke}
            
            return p_justo, p_teto, base_margem, modelos, dados_brutos
        except: return 0, 0, 0, {}, {}

    # ==============================================================================
    # 3. ANÁLISE GRÁFICA & SENTIMENTO
    # ==============================================================================
    def analisar_sentimento_news(self, ticker):
        try:
            t = yf.Ticker(ticker)
            news = t.news
            if not news: return 0, "Sem Notícias"
            
            score_news = 0
            pos = ["lucro", "profit", "alta", "high", "dividend", "aquisição", "buy", "compra", "supera", "recorde", "aprovado"]
            neg = ["prejuízo", "loss", "queda", "low", "fraude", "investigação", "corrupção", "divida", "risco", "rebaixado"]
            
            for n in news[:5]:
                ti = n.get('title', '').lower()
                val = (sum(1 for w in pos if w in ti) - sum(1 for w in neg if w in ti)) * 5
                score_news += val
                
            status = "Positivo" if score_news > 5 else "Negativo" if score_news < -5 else "Neutro"
            return score_news, status
        except: return 0, "Erro News"

    def analisar_macro(self):
        try:
            ibov = yf.download("^BVSP", period="1y", progress=False)['Close']
            if ibov.empty: return 0, "Neutro"
            
            atual = ibov.iloc[-1]
            mm200 = ibov.rolling(200).mean().iloc[-1]
            
            if atual > mm200: return 5, "Bull Market"
            else: return -10, "Bear Market"
        except: return 0, "Neutro"

    def detectar_padroes_graficos(self, h, l, c):
        padroes = []
        pontos = 0
        try:
            n = 5
            # Busca índices de picos e vales
            idx_topos = argrelextrema(h.values, np.greater_equal, order=n)[0]
            idx_fundos = argrelextrema(l.values, np.less_equal, order=n)[0]
            
            topos = [(i, h.iloc[i]) for i in idx_topos]
            fundos = [(i, l.iloc[i]) for i in idx_fundos]
            
            # Padrão: Cup & Handle (Xícara)
            if len(topos) >= 2:
                t_esq = topos[-2]; t_dir = topos[-1]
                # Verifica largura e nivelamento dos topos
                if (t_dir[0] - t_esq[0] > 20) and abs(t_esq[1] - t_dir[1])/t_esq[1] < 0.05:
                     padroes.append("☕ Cup & Handle (Alta)"); pontos += 25
            
            # Padrão: OCO (Ombro-Cabeça-Ombro)
            if len(topos) >= 3:
                # Topo do meio maior que os laterais
                ut = topos[-3:]
                if ut[1][1] > ut[0][1] and ut[1][1] > ut[2][1]: 
                    padroes.append("☠️ OCO (Reversão)"); pontos -= 20
            
            # Padrão: W (Fundo Duplo)
            if len(fundos) >= 2:
                uf = fundos[-2:]
                if abs(uf[0][1] - uf[1][1])/uf[0][1] < 0.03: 
                    padroes.append("🚀 Fundo Duplo (W)"); pontos += 15

            # Padrão: M (Topo Duplo)
            if len(topos) >= 2:
                ut = topos[-2:]
                if abs(ut[0][1] - ut[1][1])/ut[0][1] < 0.03: 
                    padroes.append("📉 Topo Duplo (M)"); pontos -= 15
            
            return ", ".join(padroes) if padroes else None, pontos
        except: return None, 0

    def identifying_candle_pattern(self, o, h, l, c):
        corpo = abs(c - o)
        range_total = h - l
        if range_total == 0: return None
        
        sombra_sup = h - max(c, o)
        sombra_inf = min(c, o) - l
        
        if corpo <= range_total * 0.03: return "Doji (Indecisão)"
        if sombra_inf >= 2 * corpo and sombra_sup <= 0.1 * corpo: return "🔨 Martelo (Alta)"
        if sombra_sup >= 2 * corpo and sombra_inf <= 0.1 * corpo: return "☄️ Estrela Cadente (Baixa)"
        return None

    def consultar_dividendos(self, ticker):
        try:
            t = yf.Ticker(ticker)
            divs = t.dividends
            if divs.empty: return {"ultimo": 0, "data": "-", "dy_12m": 0}
            ult = divs.iloc[-1]
            data = divs.index[-1].strftime('%d/%m/%Y')
            
            # Soma últimos 12 meses
            corte = pd.Timestamp.now(tz=divs.index.tz) - timedelta(days=365)
            dy_12m = divs[divs.index >= corte].sum()
            
            return {"ultimo": ult, "data": data, "dy_12m": dy_12m}
        except: return {"ultimo": 0, "data": "-", "dy_12m": 0}

    # --- 4. MOTOR CENTRAL (A ANÁLISE COMPLETA) ---
    def analisar(self, hist, info, ticker, modo_crise=False):
        try:
            if hist is None or hist.empty: return None
            # Preenche buracos nos dados
            hist = hist.ffill().bfill()
            if len(hist) < 30: return None
            
            close = hist["Close"]; high = hist["High"]; low = hist["Low"]; vol = hist["Volume"]
            atual = float(close.iloc[-1])

            # --- Módulos ---
            macro_score, macro_text = self.analisar_macro()
            news_score, news_text = self.analisar_sentimento_news(ticker)
            p_justo, p_teto, margem, modelos, dados_fund = self.calcular_valuation_consenso(info, atual, ticker, modo_crise)
            padrao_grafico, padrao_score = self.detectar_padroes_graficos(high, low, close)
            candle = self.identifying_candle_pattern(hist["Open"].iloc[-1], high.iloc[-1], low.iloc[-1], atual)
            probs = self.calcular_probabilidades(hist, atual)
            div_info = self.consultar_dividendos(ticker)

            # --- Técnica ---
            mme9 = close.ewm(span=9).mean().iloc[-1]
            mme21 = close.ewm(span=21).mean().iloc[-1]
            mm200 = close.rolling(200).mean().iloc[-1] if len(close) > 200 else 0
            
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            if loss.iloc[-1] != 0:
                rsi = 100 - (100 / (1 + gain.iloc[-1]/loss.iloc[-1]))
            else: rsi = 50
            
            # --- Fundamentos Extras ---
            dy = (info.get('dividendYield', 0) or 0) * 100
            pvp = info.get('priceToBook', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            divida_ebitda = info.get('debtToEbitda', 0) or 0
            margem_liq = info.get('profitMargins', 0) or 0
            beta_info = info.get('beta', 0) or 1.0

            # --- SCORE SYSTEM (Separado: Qualidade vs Convicção) ---
            sc_qualidade = 50
            sc_conviccao = 50
            motivos = []; alertas = []

            # 1. Qualidade (Estrutural / Valor)
            if p_justo > 0:
                if atual <= p_teto: 
                    sc_qualidade += 30; motivos.append("Valuation: Muito Barato")
                elif atual <= p_justo: 
                    sc_qualidade += 10; motivos.append("Valuation: Justo")
                else: 
                    sc_qualidade -= 30; alertas.append("Valuation: Caro")
            
            if "11.SA" in ticker:
                if dy > 10: sc_qualidade += 10
                if 0.85 <= pvp <= 1.05: sc_qualidade += 10
            else:
                if roe > 0.15: sc_qualidade += 10; motivos.append("ROE Alto")
                if pvp < 1.5 and pvp > 0: sc_qualidade += 5
                if divida_ebitda > 3: sc_qualidade -= 15; alertas.append("Dívida Alta")

            # 2. Convicção (Timing / Momentum)
            sc_conviccao += macro_score + news_score
            
            if mme9 > mme21: sc_conviccao += 15; motivos.append("Tend. Alta (Curto)")
            else: sc_conviccao -= 15; alertas.append("Tend. Baixa (Curto)")
            
            if mm200 > 0:
                if atual > mm200: sc_conviccao += 10; sc_qualidade += 5
                else: sc_conviccao -= 20; alertas.append("Abaixo MM200 (Longo)")
            
            if rsi < 30: sc_conviccao += 10; motivos.append("RSI Oportunidade")
            if padrao_grafico: sc_conviccao += padrao_score; motivos.append(padrao_grafico)
            if candle: motivos.append(candle)

            # Consolidação
            peso_q = 0.7 if modo_crise else 0.5
            peso_c = 0.3 if modo_crise else 0.5
            
            score_final = int((sc_qualidade * peso_q) + (sc_conviccao * peso_c))
            score_final = min(100, max(0, score_final))
            
            decisao = "🟢 COMPRA" if score_final >= 60 else "🔴 VENDA" if score_final <= 40 else "⚪ NEUTRO"
            if score_final >= 80: decisao = "🟢🟢 COMPRA FORTE"

            # Retorno Completo (Dicionário Gigante)
            return {
                "score_ia": score_final, "decisao_ia": decisao,
                "score_qualidade": int(sc_qualidade), "score_conviccao": int(sc_conviccao),
                "motivos": ", ".join(motivos), "alertas": ", ".join(alertas),
                # Valuation
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto, "margem": margem, 
                "modelos_val": modelos, "dados_fund": dados_fund,
                # Contexto
                "macro": macro_text, "news": news_text, "probs": probs,
                # Técnica
                "rsi": rsi, "mme9": mme9, "mme21": mme21, "mm200": mm200,
                "padrao_grafico": padrao_grafico, "candle": candle,
                # Fundamentos
                "dy_anual": dy, "pvp": pvp, "roe": roe, "divida_ebitda": divida_ebitda, "margem_liq": margem_liq,
                "beta_info": beta_info, "div_info": div_info
            }
        except: return None

    # Simulação Monte Carlo (Mantida para Aba Futuro)
    def monte_carlo_carteira(self, retornos, val_ini, sims=1000):
        try:
            days = 252 * 5 # 5 anos
            r_mean = retornos.mean()
            r_std = retornos.std()
            res = []
            for _ in range(sims):
                saldo = val_ini
                # Vetorizado para velocidade
                daily_returns = np.random.normal(r_mean, r_std, days)
                caminho = np.cumprod(1 + daily_returns) * saldo
                res.append(caminho)
            
            # Retorna DataFrame para gráfico fácil
            df_sim = pd.DataFrame(res).T
            # Pega média, pior e melhor cenário
            df_final = pd.DataFrame({
                "Média": df_sim.mean(axis=1),
                "Otimista (95%)": df_sim.quantile(0.95, axis=1),
                "Pessimista (5%)": df_sim.quantile(0.05, axis=1)
            })
            return df_final
        except: return pd.DataFrame()