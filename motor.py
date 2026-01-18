import pandas as pd
import numpy as np
import yfinance as yf

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        """Mapeamento Setorial Completo (Inclui keywords específicas de FIIs)"""
        industry = (info.get('industry', '') or '').lower()
        summary = (info.get('longBusinessSummary', '') or '').lower()
        name = (info.get('longName', '') or '').lower()

        # --- LÓGICA FIIs (CPSH11, XPML11, etc) ---
        if ticker.endswith('11.SA') and ticker not in ['IVVB11.SA', 'BOVA11.SA', 'XINA11.SA', 'BDRX19.SA']:
            tijolo_kws = ['shopping', 'mall', 'logística', 'logistics', 'galpão', 'warehouse', 'laje', 'corporativo', 'urbana', 'renda urbana', 'hospital', 'imóveis', 'properties', 'real estate', 'predial']
            if any(kw in industry or kw in summary or kw in name for kw in tijolo_kws):
                return "FIIs-Tijolo"
            
            papel_kws = ['recebíveis', 'cri', 'cra', 'papel', 'paper', 'debt', 'dívida', 'crédito', 'fund of funds', 'fof', 'títulos', 'financeiro']
            if any(kw in industry or kw in summary or kw in name for kw in papel_kws):
                return "FIIs-Papel"
            
            return "FIIs-Outros"

        # --- LÓGICA AÇÕES & EXTERIOR ---
        if ticker in ['IVVB11.SA', 'BDRX19.SA'] or not ticker.endswith('.SA'): return "Exterior"

        if 'bank' in industry or 'financial' in industry: return "Ações-Bancos"
        if 'utilit' in industry or 'electric' in industry or 'water' in industry: return "Ações-Elétricas"
        if 'insur' in industry or 'segur' in industry: return "Ações-Seguridade"
        if 'mining' in industry or 'oil' in industry or 'gas' in industry or 'steel' in industry: return "Ações-Commodities"
        
        return "Ações-Outros"

    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None
            
            # Tratamento de dados
            fechamento = hist["Close"].iloc[:, 0] if isinstance(hist["Close"], pd.DataFrame) else hist["Close"]
            volume = hist["Volume"].iloc[:, 0] if isinstance(hist["Volume"], pd.DataFrame) else hist["Volume"]
            
            if len(fechamento) < 30: return None
            preco_atual = float(fechamento.iloc[-1])

            # --- 1. MATEMÁTICA TÉCNICA (COMPLETA) ---
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            
            # MACD
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            # RSI (14)
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi = rsi_series.iloc[-1] if not np.isnan(rsi_series.iloc[-1]) else 50

            # Volatilidade Anualizada
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5) if not retornos.empty else 0.0

            # --- 2. DIVIDENDOS (CÁLCULO REAL) ---
            try:
                t = yf.Ticker(ticker)
                divs = t.dividends
                if not divs.empty:
                    ultimo_pag = float(divs.iloc[-1])
                    dy_mensal = (ultimo_pag / preco_atual) * 100
                    dt_ano = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(months=12)
                    dy_anual = (float(divs[divs.index >= dt_ano].sum()) / preco_atual) * 100
                else: 
                    dy_mensal, dy_anual = 0.0, 0.0
            except:
                dy_mensal = 0.0
                dy_anual = (info.get('dividendYield') or 0.0) * 100

            # --- 3. FUNDAMENTOS & VALUATION ---
            def safe_get(key, default=0.0):
                val = info.get(key)
                return float(val) if val is not None else default

            lpa = safe_get("trailingEps")
            vpa = safe_get("bookValue")
            div_reais = (dy_anual / 100) * preco_atual
            
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin 

            # --- 4. SCORE IA & TRAVAS DE RISCO (COMPLETO) ---
            score = 50
            motivos = []
            alertas = []

            setor_ativo = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor_ativo

            # A) Trava de Liquidez
            vol_fin_medio = (fechamento * volume).tail(21).mean()
            limite_liq = 500000 if is_fii else 1000000
            if vol_fin_medio < limite_liq:
                score -= 20
                alertas.append(f"Baixa Liquidez (R${vol_fin_medio/1000:.0f}k)")
            
            # B) Trava de Payout
            payout = safe_get("payoutRatio")
            limite_payout = 1.2 if is_fii else 1.0 
            if payout > limite_payout:
                score -= 15
                alertas.append(f"Payout Alto ({payout*100:.0f}%)")

            # C) Trava de Ágio FII
            pvp = safe_get("priceToBook")
            if is_fii and pvp > 0:
                if pvp > 1.05:
                    score -= 10
                    alertas.append(f"FII Caro (P/VP {pvp:.2f})")
                if "Papel" in setor_ativo and pvp > 1.02:
                    score = 0
                    alertas.append("⛔ ÁGIO EM PAPEL")

            # Bonificações Técnicas
            curr_mme9 = mme9.iloc[-1]
            curr_mme21 = mme21.iloc[-1]
            if curr_mme9 > curr_mme21: score += 15; motivos.append("Tendência Alta")
            else: score -= 15

            if macd_line.iloc[-1] > signal_line.iloc[-1]: score += 5; motivos.append("MACD Compra")

            # Bonificações Fundamentos
            if p_bazin > 0 and preco_atual < p_bazin: score += 10; motivos.append("Desc. Bazin")
            if dy_anual > 6.0: score += 10; motivos.append(f"DY {dy_anual:.1f}%")
            if rsi < 30: score += 10; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 10

            score = min(100, max(0, score))
            if "⛔ ÁGIO EM PAPEL" in alertas: score = 0

            texto_final = ", ".join(motivos)
            if alertas: texto_final += " | ⚠️ " + ", ".join(alertas)

            # Suportes e Resistências
            suporte = float(fechamento.tail(60).min())
            resistencia = float(fechamento.tail(60).max())

            return {
                "preco": preco_atual,
                "score_ia": score,
                "decisao_ia": "🟢 COMPRA" if score >= 60 else "🔴 AGUARDAR",
                "motivos": texto_final,
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon,
                "dy_mensal": dy_mensal, "dy_anual": dy_anual,
                "mme9": curr_mme9, "mme21": curr_mme21,
                "macd": macd_line.iloc[-1], "macd_signal": signal_line.iloc[-1],
                "rsi": rsi, "volatilidade": volatilidade,
                "stop_loss": suporte * 0.97, "stop_gain": resistencia * 1.02,
                "sinal_tecnico": "ALTA" if curr_mme9 > curr_mme21 else "BAIXA",
                "liq_media": vol_fin_medio, "pvp": pvp, "preco_alvo_entrada": curr_mme9,
                "vol_relativo": (volume.iloc[-1] / volume.rolling(20).mean().iloc[-1]) if volume.iloc[-1] > 0 else 0
            }
        except Exception as e:
            return None

    def monte_carlo_carteira(self, retornos, val_ini, aporte, anos=10, sims=1000):
        """Simulação Monte Carlo Real (NumPy)"""
        if len(retornos) == 0: return np.array([])
        log_returns = np.log(1 + retornos)
        mu, sigma = log_returns.mean(), log_returns.std()
        drift = mu - (0.5 * sigma**2)
        days = anos * 252
        simulacoes = []
        for _ in range(sims):
            shocks = drift + sigma * np.random.normal(0, 1, days)
            caminho_diario = np.exp(shocks)
            saldo = val_ini
            for dia, retorno in enumerate(caminho_diario):
                saldo = saldo * retorno
                if (dia + 1) % 21 == 0: saldo += aporte
            simulacoes.append(saldo)
        return np.array(simulacoes)
    
    def consultar_dividendos(self, ticker):
        return {"status": "NEUTRO"}