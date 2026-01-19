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
            
            fechamento = hist["Close"]
            volume = hist["Volume"]
            if len(fechamento) < 30: return None
            preco_atual = float(fechamento.iloc[-1])

            # --- TÉCNICA ---
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            curta, longa = float(mme9.iloc[-1]), float(mme21.iloc[-1])
            curta_ant, longa_ant = float(mme9.iloc[-2]), float(mme21.iloc[-2])

            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_val = float(macd_line.iloc[-1])
            signal_val = float(signal_line.iloc[-1])

            vol_media = volume.rolling(20).mean().iloc[-1]
            vol_atual = float(volume.iloc[-1])
            vol_relativo = (vol_atual / vol_media) if vol_media > 0 else 0.0

            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5) if not retornos.empty else 0.0
            
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            if loss.iloc[-1] == 0: rsi = 50.0
            else: rsi = 100.0 - (100.0 / (1.0 + (gain.iloc[-1]/loss.iloc[-1])))

            suporte = float(fechamento.tail(60).min())
            resistencia = float(fechamento.tail(60).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02

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

            # --- DIVIDENDOS ---
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

            # --- FUNDAMENTOS ---
            def safe_float(v):
                try: return float(v) if v is not None else 0.0
                except: return 0.0

            pvp = safe_float(info.get("priceToBook"))
            if pvp == 0:
                vpa_c = safe_float(info.get("bookValue"))
                if vpa_c > 0: pvp = preco_atual/vpa_c
                elif "11.SA" in ticker: pvp = 1.0
            
            market_cap = safe_float(info.get("marketCap"))

            # DADOS DE DÍVIDA PARA FIIs (ALAVANCAGEM)
            divida_total = safe_float(info.get("totalDebt"))
            ativos_totais = safe_float(info.get("totalAssets"))
            alavancagem = 0.0
            if ativos_totais > 0:
                alavancagem = divida_total / ativos_totais

            liq_corrente = safe_float(info.get("currentRatio"))
            cresc_receita = safe_float(info.get("revenueGrowth"))
            roe = safe_float(info.get("returnOnEquity"))
            divida_ebitda = safe_float(info.get("debtToEbitda"))
            margem_liq = safe_float(info.get("profitMargins"))
            
            lpa = safe_float(info.get("trailingEps"))
            vpa = safe_float(info.get("bookValue"))
            div_reais = (dy_anual / 100) * preco_atual
            
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa>0 and vpa>0) else 0
            p_gordon = (div_reais * 1.03) / 0.03 if div_reais > 0 else 0

            setor = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor or "11.SA" in ticker
            
            if is_fii: preco_justo = p_bazin
            else: 
                validos = [x for x in [p_bazin, p_graham] if x > 0]
                preco_justo = sum(validos)/len(validos) if validos else 0

            # --- SCORE ---
            score = 50
            motivos = []
            alertas = []

            # KILL SWITCH 1: Liquidez
            if vol_atual * preco_atual < 50000: score = 0; alertas.append("SEM LIQUIDEZ ☠️")
            else:
                if is_fii:
                    # KILL SWITCH 2: Micro FII
                    if market_cap > 0 and market_cap < 20000000: score = 0; alertas.append("MICRO FII (Risco)")
                    else:
                        # 1. TENDÊNCIA (NOVO: Penaliza Baixa em FII)
                        if "ALTA" in sinal_tecnico or "COMPRA" in sinal_tecnico:
                            score += 10; motivos.append("Tend. Alta (+10)")
                        elif "BAIXA" in sinal_tecnico or "VENDA" in sinal_tecnico:
                            score -= 15; alertas.append("Tend. Baixa (-15)")

                        # 2. ALAVANCAGEM (NOVO: Penaliza Dívida > 30%)
                        if alavancagem > 0.30: 
                            score -= 10; alertas.append(f"Alavancado {alavancagem*100:.0f}% (-10)")
                        elif alavancagem > 0.01:
                            motivos.append(f"Alav. {alavancagem*100:.0f}% (OK)")

                        # 3. P/VP Rígido
                        if 0.85 <= pvp <= 1.02: score += 20; motivos.append("P/VP Justo (+20)")
                        elif pvp < 0.85: score += 15; motivos.append("Descontado (+15)")
                        elif pvp > 1.02: score -= 20; alertas.append(f"Ágio P/VP {pvp:.2f} (-20)")

                        # 4. DY
                        if dy_anual > 10.0: score += 15; motivos.append(f"DY {dy_anual:.1f}% (+15)")
                        elif dy_anual > 6.0: score += 10; motivos.append("DY Aceitável (+10)")
                        elif dy_anual < 4.0: score -= 10; alertas.append("DY Baixo (-10)")

                # AÇÕES
                else:
                    if "COMPRA" in sinal_tecnico or "ALTA" in sinal_tecnico: score += 15; motivos.append("Tend. Alta")
                    elif "VENDA" in sinal_tecnico or "BAIXA" in sinal_tecnico: score -= 15; alertas.append("Tend. Baixa")
                    if macd_val > signal_val: score += 5; motivos.append("MACD+")
                    if vol_relativo > 1.2: score += 5; motivos.append("Volume+")
                    if rsi < 30: score += 10; motivos.append("RSI Baixo")
                    elif rsi > 70: score -= 10; alertas.append("RSI Alto")

                    if p_bazin > preco_atual: score += 10; motivos.append("Desc. Bazin")
                    if p_graham > preco_atual: score += 10; motivos.append("Desc. Graham")
                    if roe > 0.15: score += 10; motivos.append("ROE Alto")
                    if cresc_receita > 0.10: score += 10; motivos.append("Cresc. Rec.")
                    if divida_ebitda > 3.5: score -= 15; alertas.append("Dívida Alta")

            score = min(100, max(0, score))
            if score >= 80: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 40: decisao = "🔴 VENDA"
            else: decisao = "⚪ AGUARDAR"

            return {
                "tipo_ativo": "FII" if is_fii else "ACAO",
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
                "stop_loss": stop_loss, "stop_gain": stop_gain,
                "liq_corrente": liq_corrente, "cresc_receita": cresc_receita,
                "roe": roe, "divida_ebitda": divida_ebitda, "margem_liq": margem_liq,
                "alavancagem": alavancagem # Novo dado
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