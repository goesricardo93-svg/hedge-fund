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
            
            # Proteção de dados mínimos
            if len(fechamento) < 30: return None
            
            preco_atual = float(fechamento.iloc[-1])

            # --- 2. TÉCNICA (CÁLCULOS COMPLETOS) ---
            # Médias Móveis
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            
            # Definição explícita para evitar erro de variável
            curta = float(mme9.iloc[-1])
            longa = float(mme21.iloc[-1])
            curta_ant = float(mme9.iloc[-2])
            longa_ant = float(mme21.iloc[-2])

            # MACD
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            macd_val = float(macd_line.iloc[-1])
            signal_val = float(signal_line.iloc[-1])

            # Volume Relativo
            vol_media = volume.rolling(20).mean().iloc[-1]
            vol_atual = float(volume.iloc[-1])
            vol_relativo = (vol_atual / vol_media) if vol_media > 0 else 0.0

            # RSI & Volatilidade
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5) if not retornos.empty else 0.0
            
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            if loss.iloc[-1] == 0: rsi = 50.0
            else: rsi = 100.0 - (100.0 / (1.0 + (gain.iloc[-1]/loss.iloc[-1])))

            # Níveis
            suporte = float(fechamento.tail(60).min())
            resistencia = float(fechamento.tail(60).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02

            # Sinal Técnico e Preço Alvo (Lógica V49)
            sinal_tecnico = "NEUTRO"
            preco_alvo_entrada = 0.0
            
            if curta > longa and curta_ant <= longa_ant:
                sinal_tecnico = "⚡ COMPRA (CRUZAMENTO)"
                preco_alvo_entrada = preco_atual 
            elif curta > longa:
                sinal_tecnico = "📈 TENDÊNCIA ALTA"
                preco_alvo_entrada = curta 
            elif curta < longa and curta_ant >= longa_ant:
                sinal_tecnico = "☠️ VENDA (CRUZAMENTO)"
            elif curta < longa:
                sinal_tecnico = "📉 TENDÊNCIA BAIXA"

            # --- 3. DIVIDENDOS (CÁLCULO MANUAL OBRIGATÓRIO) ---
            dy_anual = 0.0
            try:
                t_obj = yf.Ticker(ticker)
                divs = t_obj.dividends
                if not divs.empty:
                    corte = pd.Timestamp.now(tz=divs.index.tz) - timedelta(days=365)
                    soma = divs[divs.index >= corte].sum()
                    if preco_atual > 0: dy_anual = (soma/preco_atual)*100
            except: pass

            if dy_anual == 0:
                val = info.get("dividendYield", 0)
                if val is not None: dy_anual = val * 100
            
            if dy_anual > 200.0: dy_anual /= 100.0

            # --- 4. FUNDAMENTOS ---
            def safe_float(v):
                try: 
                    if v is None: return 0.0
                    return float(v) 
                except: return 0.0

            pvp = safe_float(info.get("priceToBook"))
            if pvp == 0:
                vpa_c = safe_float(info.get("bookValue"))
                if vpa_c > 0: pvp = preco_atual/vpa_c
                elif "11.SA" in ticker: pvp = 1.0

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

            # --- 5. SCORE DE PRECISÃO (OS 10 CRITÉRIOS REAIS) ---
            score = 50
            motivos = []
            alertas = []
            
            # [KILL SWITCH] Travas de Segurança Absoluta
            if vol_atual * preco_atual < 50000: # Liquidez < 50k
                 score = 0; alertas.append("⛔ SEM LIQUIDEZ")
            
            else:
                # 1. Tendência (+15/-15)
                if "COMPRA" in sinal_tecnico or "ALTA" in sinal_tecnico:
                    score += 15; motivos.append("Tendência Alta (+15)")
                elif "VENDA" in sinal_tecnico or "BAIXA" in sinal_tecnico:
                    score -= 15; alertas.append("Tendência Baixa (-15)")

                # 2. MACD (+5)
                if macd_val > signal_val: 
                    score += 5; motivos.append("MACD Compra (+5)")

                # 3. Volume (+5)
                if vol_relativo > 1.2: 
                    score += 5; motivos.append("Volume Forte (+5)")

                # 4. RSI (+10 / -10)
                if rsi < 30: 
                    score += 10; motivos.append("RSI Oportunidade (+10)")
                elif rsi > 70: 
                    score -= 10; alertas.append("RSI Esticado (-10)")

                if is_fii:
                    # Lógica FII (Adaptada aos 10 pontos de FII)
                    if 0.85 <= pvp <= 1.05: score += 15; motivos.append("P/VP Justo (+15)")
                    elif pvp > 1.15: score -= 10; alertas.append("FII Caro (-10)")
                    
                    if dy_anual > 8.0: score += 10; motivos.append(f"DY {dy_anual:.1f}% (+10)")
                    elif dy_anual < 4.0: score -= 5
                    
                    if volatilidade < 0.2: score += 5; motivos.append("Baixa Volat. (+5)")

                else:
                    # 5. Valuation Bazin (+10)
                    if p_bazin > preco_atual: 
                        score += 10; motivos.append("Desc. Bazin (+10)")

                    # 6. Valuation Graham (+10)
                    if p_graham > preco_atual: 
                        score += 10; motivos.append("Desc. Graham (+10)")

                    # 7. Qualidade ROE (+10)
                    if roe > 0.15: 
                        score += 10; motivos.append(f"ROE {roe*100:.0f}% (+10)")

                    # 8. Crescimento (+10)
                    if cresc_receita > 0.10: 
                        score += 10; motivos.append("Cresc. Receita (+10)")
                    elif cresc_receita < -0.05: 
                        score -= 5; alertas.append("Receita Caindo (-5)")

                    # 9. Dividendos (+5)
                    if dy_anual > 6.0: 
                        score += 5; motivos.append("Bom Pagador (+5)")

                    # 10. Dívida (Penalidade -15)
                    if divida_ebitda > 3.5: 
                        score -= 15; alertas.append("Dívida Perigosa (-15)")

            # Finalização
            score = min(100, max(0, score))

            if score >= 80: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 40: decisao = "🔴 VENDA"
            else: decisao = "⚪ AGUARDAR"

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
                "sinal_tecnico": sinal_tecnico,
                "preco_alvo_entrada": preco_alvo_entrada,
                "mme9": curta, "mme21": longa,
                "macd": macd_val, "macd_signal": signal_val,
                "status_macd": "COMPRA" if macd_val > signal_val else "VENDA",
                "vol_relativo": vol_relativo,
                "rsi": rsi, "volatilidade": volatilidade,
                "suporte": suporte, "resistencia": resistencia,
                "stop_loss": stop_loss, "stop_gain": stop_gain,
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