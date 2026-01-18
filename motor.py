import pandas as pd
import numpy as np
import yfinance as yf

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        # 1. LISTA VIP
        TIJOLO_VIP = ['XPML11.SA', 'VISC11.SA', 'MALL11.SA', 'HGBS11.SA', 'CPSH11.SA', 'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', 'LVBI11.SA', 'HGRU11.SA', 'KNRI11.SA', 'HGRE11.SA', 'JSRE11.SA', 'BRCO11.SA', 'TRXF11.SA', 'ALZR11.SA', 'GGRC11.SA']
        PAPEL_VIP = ['MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'RECR11.SA', 'IRDM11.SA', 'KNIP11.SA', 'HGCR11.SA', 'VGIR11.SA', 'CVBI11.SA', 'KNSC11.SA']
        
        if ticker in TIJOLO_VIP: return "FIIs-Tijolo"
        if ticker in PAPEL_VIP: return "FIIs-Papel"

        # 2. IA DE CONTEXTO
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
            
            # --- DADOS DE MERCADO ---
            fechamento = hist["Close"].iloc[:, 0] if isinstance(hist["Close"], pd.DataFrame) else hist["Close"]
            volume = hist["Volume"].iloc[:, 0] if isinstance(hist["Volume"], pd.DataFrame) else hist["Volume"]
            
            if len(fechamento) < 30: return None
            preco_atual = float(fechamento.iloc[-1])

            # --- INDICADORES TÉCNICOS ---
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

            def safe_float(val):
                try: return float(val)
                except: return 0.0

            # --- CORREÇÃO DE DIVIDENDOS (LÓGICA V50.1 RESTAURADA) ---
            # Prioridade: Calcular na mão (Soma 12 meses / Preço)
            dy_anual = 0.0
            
            try:
                # Baixa histórico de dividendos direto da fonte
                t_obj = yf.Ticker(ticker)
                divs = t_obj.dividends
                
                if not divs.empty:
                    # Filtra últimos 12 meses exatos
                    data_limite = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(months=12)
                    soma_12m = divs[divs.index >= data_limite].sum()
                    
                    if preco_atual > 0:
                        dy_anual = (soma_12m / preco_atual) * 100
            except:
                pass

            # Se o cálculo manual falhar ou der 0, usa o metadata do Yahoo com "sanity check"
            if dy_anual == 0:
                raw_dy = safe_float(info.get("dividendYield"))
                if raw_dy > 0:
                    # Se for menor que 3.0 (ex: 0.12), assume decimal -> multiplica por 100
                    if raw_dy < 3.0:
                        dy_anual = raw_dy * 100
                    # Se for maior (ex: 12.0), assume que já é % -> mantém
                    else:
                        dy_anual = raw_dy

            # --- CORREÇÃO P/VP ---
            pvp = safe_float(info.get("priceToBook"))
            if pvp == 0 or pvp is None:
                vpa = safe_float(info.get("bookValue"))
                if vpa == 0:
                    total_assets = safe_float(info.get("totalAssets"))
                    shares = safe_float(info.get("sharesOutstanding"))
                    if total_assets > 0 and shares > 0: vpa = total_assets / shares
                if vpa > 0: pvp = preco_atual / vpa
                else: 
                    if "11.SA" in ticker: pvp = 1.0

            # --- VALUATION ---
            lpa = safe_float(info.get("trailingEps"))
            vpa = safe_float(info.get("bookValue"))
            
            # Bazin usa o DY Calculado
            div_reais = (dy_anual / 100) * preco_atual
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin 

            setor_ativo = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor_ativo

            if is_fii: preco_justo = p_bazin
            else: 
                validos = [x for x in [p_bazin, p_graham] if x > 0]
                preco_justo = sum(validos) / len(validos) if validos else 0

            # --- DUAL SCORE ---
            score = 50
            motivos = []
            alertas = []
            vol_fin_medio = (fechamento * volume).tail(21).mean()

            if is_fii: # FIIs
                limite_liq = 300000
                if vol_fin_medio < limite_liq: score -= 30; alertas.append(f"Baixa Liquidez ({vol_fin_medio/1000:.0f}k)")

                if 0.85 <= pvp <= 1.08: score += 20; motivos.append(f"P/VP Justo ({pvp:.2f})")
                elif pvp > 1.15: score -= 15; alertas.append(f"Caro (P/VP {pvp:.2f})")
                elif pvp < 0.80: score -= 5; motivos.append(f"Desconto ({pvp:.2f})")
                
                if "Papel" in setor_ativo and pvp > 1.05: score = 0; alertas.append("⛔ ÁGIO EM PAPEL")

                if dy_anual > 6.0: score += 15; motivos.append(f"DY {dy_anual:.1f}%")
                else: score -= 10
                
                if volatilidade < 0.20: score += 10; motivos.append("Baixa Volatilidade")

            else: # AÇÕES
                limite_liq = 1000000
                if vol_fin_medio < limite_liq: score -= 20; alertas.append("Baixa Liquidez")

                if mme9.iloc[-1] > mme21.iloc[-1]: score += 20; motivos.append("Tendência Alta")
                else: score -= 15

                if macd_line.iloc[-1] > signal_line.iloc[-1]: score += 10; motivos.append("MACD Compra")
                
                if preco_justo > preco_atual: 
                    upside = (preco_justo - preco_atual) / preco_atual
                    if upside > 0.15: score += 15; motivos.append(f"Upside +{upside*100:.0f}%")

            score = max(0, min(100, score))

            return {
                "preco": preco_atual,
                "score_ia": score,
                "decisao_ia": "🟢 COMPRA" if score >= 60 else "🔴 AGUARDAR",
                "motivos": ", ".join(motivos),
                "alertas": ", ".join(alertas),
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon,
                "preco_justo": preco_justo,
                "dy_anual": dy_anual,
                "mme9": mme9.iloc[-1], "mme21": mme21.iloc[-1],
                "tendencia": "ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "BAIXA",
                "macd": macd_line.iloc[-1], "macd_signal": signal_line.iloc[-1],
                "status_macd": "COMPRA" if macd_line.iloc[-1] > signal_line.iloc[-1] else "VENDA",
                "rsi": rsi, "volatilidade": volatilidade, "vol_relativo": vol_relativo,
                "stop_loss": preco_atual * 0.95, "stop_gain": preco_atual * 1.05,
                "suporte": suporte, "resistencia": resistencia,
                "liq_media": vol_fin_medio, "pvp": pvp, "sinal_tecnico": "ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "BAIXA",
                "dy_mensal": 0
            }
        except Exception as e: return None

    def monte_carlo_carteira(self, retornos, val_ini, aporte, anos=10, sims=1000):
        try:
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
                    if (d + 1) % 21 == 0: saldo += aporte
                simulacoes.append(saldo)
            return np.array(simulacoes)
        except: return np.array([])
    
    def consultar_dividendos(self, ticker): return {"status": "NEUTRO"}