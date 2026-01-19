import pandas as pd
import numpy as np
import yfinance as yf
from datetime import timedelta

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        TIJOLO_VIP = ['XPML11.SA', 'VISC11.SA', 'MALL11.SA', 'HGBS11.SA', 'CPSH11.SA', 'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', 'LVBI11.SA', 'HGRU11.SA', 'KNRI11.SA', 'HGRE11.SA', 'JSRE11.SA', 'BRCO11.SA', 'TRXF11.SA', 'ALZR11.SA', 'GGRC11.SA']
        PAPEL_VIP = ['MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'RECR11.SA', 'IRDM11.SA', 'KNIP11.SA', 'HGCR11.SA', 'VGIR11.SA', 'CVBI11.SA', 'KNSC11.SA']
        
        if ticker in TIJOLO_VIP: return "FIIs-Tijolo"
        if ticker in PAPEL_VIP: return "FIIs-Papel"

        industry = (info.get('industry', '') or '').lower()
        if ticker.endswith('11.SA'): return "FIIs-Indefinido"
        if 'bank' in industry: return "Ações-Bancos"
        if 'electric' in industry: return "Ações-Elétricas"
        return "Ações-Outros"

    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None
            
            # --- 1. DADOS DE MERCADO ---
            fechamento = hist["Close"]
            volume = hist["Volume"]
            if len(fechamento) < 30: return None
            preco_atual = float(fechamento.iloc[-1])

            # --- 2. ANÁLISE TÉCNICA (LÓGICA V49 RESTAURADA) ---
            # Médias Móveis (Atual e Anterior para detectar cruzamento)
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            
            curta = mme9.iloc[-1]
            longa = mme21.iloc[-1]
            curta_ant = mme9.iloc[-2]
            longa_ant = mme21.iloc[-2]

            # MACD
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_val = macd_line.iloc[-1]
            signal_val = signal_line.iloc[-1]

            # Volume Relativo
            vol_media = volume.rolling(20).mean().iloc[-1]
            vol_relativo = (volume.iloc[-1] / vol_media) if vol_media > 0 else 0

            # Volatilidade e RSI
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5) if not retornos.empty else 0.0
            
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            if loss.iloc[-1] == 0: rsi = 50
            else: rsi = 100 - (100 / (1 + (gain.iloc[-1]/loss.iloc[-1])))

            # Suportes e Resistências
            suporte = float(fechamento.tail(60).min())
            resistencia = float(fechamento.tail(60).max())

            # --- 3. SINAL TÉCNICO E PREÇO ALVO (A LÓGICA V49) ---
            sinal_tecnico = "NEUTRO"
            preco_alvo_entrada = 0.0

            if curta > longa and curta_ant <= longa_ant:
                sinal_tecnico = "⚡ COMPRA (CRUZAMENTO)"
                preco_alvo_entrada = preco_atual # Entra no rompimento
            elif curta > longa:
                sinal_tecnico = "📈 TENDÊNCIA ALTA"
                preco_alvo_entrada = curta # Entra no pullback da MME9
            elif curta < longa and curta_ant >= longa_ant:
                sinal_tecnico = "☠️ VENDA (CRUZAMENTO)"
            elif curta < longa:
                sinal_tecnico = "📉 TENDÊNCIA BAIXA"

            # --- 4. DIVIDENDOS (LÓGICA V91 - PARA CORRIGIR O BUG 1214%) ---
            dy_anual = 0.0
            try:
                t_obj = yf.Ticker(ticker)
                divs = t_obj.dividends
                if not divs.empty:
                    corte = pd.Timestamp.now(tz=divs.index.tz) - timedelta(days=365)
                    soma = divs[divs.index >= corte].sum()
                    if preco_atual > 0: dy_anual = (soma/preco_atual)*100
            except: pass

            if dy_anual == 0: # Fallback
                val = info.get("dividendYield", 0)
                if val is not None: dy_anual = val * 100
            
            if dy_anual > 200.0: dy_anual /= 100.0 # Trava de segurança

            # --- 5. FUNDAMENTOS COMPLETOS (V49 + BLINDAGEM) ---
            def safe_float(v, default=0.0): 
                try: 
                    if v is None: return default
                    return float(v) 
                except: return default

            pvp = safe_float(info.get("priceToBook"))
            if pvp == 0:
                vpa_calc = safe_float(info.get("bookValue"))
                if vpa_calc > 0: pvp = preco_atual / vpa_calc
                elif "11.SA" in ticker: pvp = 1.0

            # Indicadores Extras da V49
            liq_corrente = safe_float(info.get("currentRatio"))
            cresc_receita = safe_float(info.get("revenueGrowth"))
            roe = safe_float(info.get("returnOnEquity"))
            divida_ebitda = safe_float(info.get("debtToEbitda"))
            
            # Valuation
            lpa = safe_float(info.get("trailingEps"))
            vpa = safe_float(info.get("bookValue"))
            
            div_reais = (dy_anual / 100) * preco_atual
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa>0 and vpa>0) else 0
            p_gordon = (div_reais * 1.03) / 0.03 if div_reais > 0 else 0

            setor = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor
            
            if is_fii: preco_justo = p_bazin
            else: 
                validos = [x for x in [p_bazin, p_graham] if x > 0]
                preco_justo = sum(validos)/len(validos) if validos else 0

            # --- 6. SCORE AVANÇADO (CRITÉRIOS V49) ---
            score = 50
            motivos = []
            alertas = []

            # Critérios Técnicos
            if "COMPRA" in sinal_tecnico: 
                score += 15; motivos.append("Sinal Cruzamento")
            elif "VENDA" in sinal_tecnico: 
                score -= 15; alertas.append("Sinal Venda")
            
            if macd_val > signal_val: score += 5; motivos.append("MACD Positivo")
            if vol_relativo > 1.2: score += 5; motivos.append("Volume Alto")
            
            if rsi < 30: score += 10; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 10; alertas.append("RSI Esticado")

            # Critérios Fundamentais
            if is_fii:
                if 0.85 <= pvp <= 1.10: score += 15; motivos.append("P/VP Justo")
                elif pvp > 1.15: score -= 10
                if dy_anual > 8.0: score += 10; motivos.append("DY Alto")
            else:
                if preco_justo > preco_atual: score += 15; motivos.append("Desconto Valuation")
                if roe > 0.15: score += 10; motivos.append(f"ROE {roe*100:.0f}%")
                if cresc_receita > 0.10: score += 10; motivos.append("Cresc. Receita")
                elif cresc_receita < -0.05: score -= 10; alertas.append("Receita Caindo")
                if liq_corrente > 1.5: score += 5
                if divida_ebitda > 3.5: score -= 10; alertas.append("Alavancado")

            score = min(100, max(0, score))

            if score >= 80: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 40: decisao = "🔴 VENDA"
            else: decisao = "⚪ AGUARDAR"

            # Retorno unificado (V91 app compatible + V49 logic)
            return {
                "preco": preco_atual,
                "score_ia": score,
                "decisao_ia": decisao,
                "motivos": ", ".join(motivos),
                "alertas": ", ".join(alertas),
                "dy_anual": dy_anual,
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon,
                "preco_justo": preco_justo,
                "pvp": pvp,
                # Dados Técnicos V49
                "sinal_tecnico": sinal_tecnico,
                "preco_alvo_entrada": preco_alvo_entrada,
                "mme9": curta, "mme21": longa,
                "macd": macd_val, "macd_signal": signal_val,
                "status_macd": "COMPRA" if macd_val > signal_val else "VENDA",
                "vol_relativo": vol_relativo,
                "rsi": rsi, "volatilidade": volatilidade,
                "suporte": suporte, "resistencia": resistencia,
                "stop_loss": suporte * 0.97, "stop_gain": resistencia * 1.02,
                # Dados Extras V49
                "liq_corrente": liq_corrente, "cresc_receita": cresc_receita
            }

        except Exception as e: return None

    def monte_carlo_carteira(self, retornos, val_ini, aporte, anos=10, sims=1000):
        try:
            days = anos * 252
            r_mean = retornos.mean()
            r_std = retornos.std()
            res = []
            for _ in range(sims):
                saldo = val_ini
                daily_returns = np.random.normal(r_mean, r_std, days)
                for d, r in enumerate(daily_returns):
                    saldo = saldo * (1 + r)
                    if (d+1) % 21 == 0: saldo += aporte
                res.append(saldo)
            return np.array(res)
        except: return np.array([])
    
    def consultar_dividendos(self, t): return {}