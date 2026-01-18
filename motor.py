import pandas as pd
import numpy as np
import yfinance as yf

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        # LISTA VIP (Garante acerto)
        TIJOLO_VIP = ['XPML11.SA', 'VISC11.SA', 'MALL11.SA', 'HGBS11.SA', 'CPSH11.SA', 'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', 'LVBI11.SA', 'HGRU11.SA', 'KNRI11.SA', 'HGRE11.SA', 'JSRE11.SA', 'BRCO11.SA', 'TRXF11.SA', 'ALZR11.SA', 'GGRC11.SA']
        PAPEL_VIP = ['MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'RECR11.SA', 'IRDM11.SA', 'KNIP11.SA', 'HGCR11.SA', 'VGIR11.SA', 'CVBI11.SA', 'KNSC11.SA']
        
        if ticker in TIJOLO_VIP: return "FIIs-Tijolo"
        if ticker in PAPEL_VIP: return "FIIs-Papel"

        # IA DE CONTEXTO
        industry = (info.get('industry', '') or '').lower()
        summary = (info.get('longBusinessSummary', '') or '').lower()
        name = (info.get('longName', '') or '').lower()

        if ticker.endswith('11.SA') and ticker not in ['IVVB11.SA', 'BOVA11.SA', 'XINA11.SA', 'BDRX19.SA']:
            tijolo_kws = ['shopping', 'mall', 'logística', 'logistics', 'galpão', 'warehouse', 'laje', 'corporativo', 'urbana', 'hospital', 'imóveis', 'properties', 'real estate', 'predial']
            if any(kw in industry or kw in summary or kw in name for kw in tijolo_kws): return "FIIs-Tijolo"
            
            papel_kws = ['recebíveis', 'cri', 'cra', 'papel', 'paper', 'debt', 'dívida', 'crédito', 'fund of funds', 'fof', 'títulos', 'financeiro', 'security']
            if any(kw in industry or kw in summary or kw in name for kw in papel_kws): return "FIIs-Papel"
            
            return "FIIs-Outros"

        if ticker in ['IVVB11.SA', 'BDRX19.SA'] or not ticker.endswith('.SA'): return "Exterior"
        if 'bank' in industry or 'financial' in industry: return "Ações-Bancos"
        if 'utilit' in industry or 'electric' in industry or 'water' in industry: return "Ações-Elétricas"
        if 'insur' in industry or 'segur' in industry: return "Ações-Seguridade"
        if 'mining' in industry or 'oil' in industry or 'gas' in industry or 'steel' in industry: return "Ações-Commodities"
        return "Ações-Outros"

    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None
            
            # Dados Básicos
            fechamento = hist["Close"].iloc[:, 0] if isinstance(hist["Close"], pd.DataFrame) else hist["Close"]
            volume = hist["Volume"].iloc[:, 0] if isinstance(hist["Volume"], pd.DataFrame) else hist["Volume"]
            
            if len(fechamento) < 30: return None
            preco_atual = float(fechamento.iloc[-1])

            # --- 1. TÉCNICA (ALGO-TRADING) ---
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi = rsi_series.iloc[-1] if not np.isnan(rsi_series.iloc[-1]) else 50

            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5) if not retornos.empty else 0.0
            
            media_vol_20 = volume.rolling(20).mean().iloc[-1]
            vol_relativo = (volume.iloc[-1] / media_vol_20) if (media_vol_20 and media_vol_20 > 0) else 1.0

            suporte = float(fechamento.tail(60).min())
            resistencia = float(fechamento.tail(60).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02

            # --- 2. DIVIDENDOS (REAL) ---
            try:
                t = yf.Ticker(ticker); divs = t.dividends
                if not divs.empty:
                    ultimo_pag = float(divs.iloc[-1])
                    dy_mensal = (ultimo_pag / preco_atual) * 100
                    dt_ano = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(months=12)
                    dy_anual = (float(divs[divs.index >= dt_ano].sum()) / preco_atual) * 100
                else: dy_mensal, dy_anual = 0.0, 0.0
            except: dy_mensal, dy_anual = 0.0, (info.get('dividendYield') or 0.0) * 100

            # --- 3. VALUATION ---
            def safe_get(key, default=0.0): return float(info.get(key) or default)
            lpa = safe_get("trailingEps")
            vpa = safe_get("bookValue")
            div_reais = (dy_anual / 100) * preco_atual
            
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin 

            # ROBÔ DE PREÇO JUSTO (Média inteligente)
            validos = [x for x in [p_bazin, p_graham] if x > 0]
            preco_justo = sum(validos) / len(validos) if validos else 0

            # --- 4. SCORE & RISCO ---
            score = 50
            motivos = []
            alertas = []
            setor_ativo = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor_ativo

            # Travas
            vol_fin_medio = (fechamento * volume).tail(21).mean()
            limite_liq = 500000 if is_fii else 1000000
            if vol_fin_medio < limite_liq: score -= 20; alertas.append(f"Baixa Liquidez (R${vol_fin_medio/1000:.0f}k)")
            
            payout = safe_get("payoutRatio")
            limite_payout = 1.2 if is_fii else 1.0 
            if payout > limite_payout: score -= 15; alertas.append(f"Payout Alto ({payout*100:.0f}%)")

            pvp = safe_get("priceToBook")
            if is_fii and pvp > 0:
                if pvp > 1.05: score -= 10; alertas.append(f"FII Caro (P/VP {pvp:.2f})")
                if "Papel" in setor_ativo and pvp > 1.02: score = 0; alertas.append("⛔ ÁGIO EM PAPEL")

            # Pontuação
            tendencia = "ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "BAIXA"
            if tendencia == "ALTA": score += 15; motivos.append("Tendência Alta")
            else: score -= 15
            
            status_macd = "COMPRA" if macd_line.iloc[-1] > signal_line.iloc[-1] else "VENDA"
            if status_macd == "COMPRA": score += 5; motivos.append("MACD Positivo")
            if vol_relativo > 1.2: score += 5; motivos.append("Volume Forte")

            # Valuation Score
            if preco_justo > 0 and preco_atual < preco_justo: 
                score += 15; motivos.append("Abaixo Valor Justo")
            elif preco_justo > 0: score -= 10

            if dy_anual > 6.0: score += 10; motivos.append(f"DY {dy_anual:.1f}%")
            if rsi < 30: score += 10; motivos.append("RSI Sobrevendido")

            score = min(100, max(0, score))
            if "⛔ ÁGIO EM PAPEL" in alertas: score = 0

            return {
                "preco": preco_atual,
                "score_ia": score,
                "decisao_ia": "🟢 COMPRA" if score >= 60 else "🔴 AGUARDAR",
                "motivos": ", ".join(motivos) + (" | ⚠️ " + ", ".join(alertas) if alertas else ""),
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon,
                "preco_justo": preco_justo,
                "dy_mensal": dy_mensal, "dy_anual": dy_anual,
                "mme9": mme9.iloc[-1], "mme21": mme21.iloc[-1], "tendencia": tendencia,
                "macd": macd_line.iloc[-1], "macd_signal": signal_line.iloc[-1], "status_macd": status_macd,
                "rsi": rsi, "volatilidade": volatilidade, "vol_relativo": vol_relativo,
                "stop_loss": stop_loss, "stop_gain": stop_gain, "suporte": suporte, "resistencia": resistencia,
                "liq_media": vol_fin_medio, "pvp": pvp, "sinal_tecnico": tendencia
            }
        except Exception as e: return None

    def monte_carlo_carteira(self, retornos, val_ini, aporte, anos=10, sims=1000):
        if len(retornos) == 0: return np.array([])
        log_returns = np.log(1 + retornos)
        mu, sigma = log_returns.mean(), log_returns.std()
        drift = mu - (0.5 * sigma**2)
        days = anos * 252
        simulacoes = []
        for _ in range(sims):
            shocks = drift + sigma * np.random.normal(0, 1, days)
            path = np.exp(shocks)
            saldo = val_ini
            for d, ret in enumerate(path):
                saldo *= ret
                if (d+1)%21 == 0: saldo += aporte
            simulacoes.append(saldo)
        return np.array(simulacoes)
    
    def consultar_dividendos(self, ticker): return {"status": "NEUTRO"}