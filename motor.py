import pandas as pd
import numpy as np
import yfinance as yf

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        # 1. LISTA VIP (Garante classificação correta dos principais)
        TIJOLO_VIP = ['XPML11.SA', 'VISC11.SA', 'MALL11.SA', 'HGBS11.SA', 'CPSH11.SA', 'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', 'LVBI11.SA', 'HGRU11.SA', 'KNRI11.SA', 'HGRE11.SA', 'JSRE11.SA', 'BRCO11.SA', 'TRXF11.SA', 'ALZR11.SA', 'GGRC11.SA']
        PAPEL_VIP = ['MXRF11.SA', 'KNCR11.SA', 'CPTS11.SA', 'RECR11.SA', 'IRDM11.SA', 'KNIP11.SA', 'HGCR11.SA', 'VGIR11.SA', 'CVBI11.SA', 'KNSC11.SA']
        
        if ticker in TIJOLO_VIP: return "FIIs-Tijolo"
        if ticker in PAPEL_VIP: return "FIIs-Papel"

        # 2. IA DE CONTEXTO (Fallback)
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

            # --- CORREÇÃO P/VP ROBUSTA (AQUI ESTÁ A FIXAÇÃO) ---
            def safe_float(val):
                try: return float(val)
                except: return 0.0

            pvp = safe_float(info.get("priceToBook"))
            
            # Se o Yahoo devolveu 0 ou None, tentamos calcular na mão
            if pvp == 0 or pvp is None:
                vpa = safe_float(info.get("bookValue"))
                
                # Se não tem VPA direto, tenta estimar pelo Equity (Patrimônio) / Shares
                if vpa == 0:
                    total_assets = safe_float(info.get("totalAssets"))
                    shares = safe_float(info.get("sharesOutstanding"))
                    if total_assets > 0 and shares > 0:
                        vpa = total_assets / shares # Aproximação

                if vpa > 0:
                    pvp = preco_atual / vpa
                else:
                    # Se falhar tudo e for FII, assume 1.0 para não travar o Score com zero
                    if "11.SA" in ticker: pvp = 1.0

            # --- DIVIDENDOS (COM FALLBACK) ---
            dy_anual = safe_float(info.get("dividendYield")) * 100
            # Se vier zerado do info, tenta calcular pelo histórico de pagamentos
            if dy_anual == 0:
                 try: 
                    t_obj = yf.Ticker(ticker)
                    divs = t_obj.dividends
                    if not divs.empty:
                        # Soma últimos 12 meses
                        start_date = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(months=12)
                        dy_anual = (divs[divs.index >= start_date].sum() / preco_atual) * 100
                 except: pass

            # --- VALUATION (BAZIN REINANDO EM FIIs) ---
            lpa = safe_float(info.get("trailingEps"))
            vpa = safe_float(info.get("bookValue"))
            
            div_reais = (dy_anual / 100) * preco_atual
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin 

            setor_ativo = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor_ativo

            # Decisão de Preço Justo
            if is_fii:
                preco_justo = p_bazin # FII = Renda (Bazin)
            else:
                validos = [x for x in [p_bazin, p_graham] if x > 0]
                preco_justo = sum(validos) / len(validos) if validos else 0

            # --- DUAL SCORE (LÓGICA V50.1 RESTAURADA) ---
            score = 50
            motivos = []
            alertas = []
            
            vol_fin_medio = (fechamento * volume).tail(21).mean()

            # LÓGICA 1: FIIs (Estabilidade)
            if is_fii:
                limite_liq = 300000
                if vol_fin_medio < limite_liq: 
                    score -= 30; alertas.append(f"Baixa Liquidez ({vol_fin_medio/1000:.0f}k)")

                # P/VP (Agora confiável com a correção acima)
                if 0.85 <= pvp <= 1.08: score += 20; motivos.append(f"P/VP Justo ({pvp:.2f})")
                elif pvp > 1.15: score -= 15; alertas.append(f"FII Caro (P/VP {pvp:.2f})")
                elif pvp < 0.80: score -= 5; motivos.append(f"Desconto Elevado ({pvp:.2f})")
                
                # Trava de Ágio em Papel
                if "Papel" in setor_ativo and pvp > 1.05: 
                    score = 0; alertas.append("⛔ ÁGIO EM PAPEL")

                if dy_anual > 6.0: score += 15; motivos.append(f"DY {dy_anual:.1f}%")
                else: score -= 10
                
                if volatilidade < 0.20: score += 10; motivos.append("Baixa Volatilidade")

            # LÓGICA 2: AÇÕES (Crescimento)
            else:
                limite_liq = 1000000
                if vol_fin_medio < limite_liq: score -= 20; alertas.append("Baixa Liquidez")

                if mme9.iloc[-1] > mme21.iloc[-1]: score += 20; motivos.append("Tendência Alta")
                else: score -= 15

                if macd_line.iloc[-1] > signal_line.iloc[-1]: score += 10; motivos.append("MACD Compra")
                
                if preco_justo > preco_atual: 
                    upside = (preco_justo - preco_atual) / preco_atual
                    if upside > 0.15: score += 15; motivos.append(f"Upside +{upside*100:.0f}%")

            score = max(0, min(100, score))

            # --- RETORNO COMPLETO ---
            return {
                "preco": preco_atual,
                "score_ia": score,
                "decisao_ia": "🟢 COMPRA" if score >= 60 else "🔴 AGUARDAR",
                "motivos": ", ".join(motivos),
                "alertas": ", ".join(alertas),
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon,
                "preco_justo": preco_justo,
                "dy_mensal": 0, "dy_anual": dy_anual,
                "mme9": mme9.iloc[-1], "mme21": mme21.iloc[-1],
                "tendencia": "ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "BAIXA",
                "macd": macd_line.iloc[-1], "macd_signal": signal_line.iloc[-1],
                "status_macd": "COMPRA" if macd_line.iloc[-1] > signal_line.iloc[-1] else "VENDA",
                "rsi": rsi, "volatilidade": volatilidade, "vol_relativo": vol_relativo,
                "stop_loss": preco_atual * 0.95, "stop_gain": preco_atual * 1.05,
                "suporte": suporte, "resistencia": resistencia,
                "liq_media": vol_fin_medio, "pvp": pvp, "sinal_tecnico": "ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "BAIXA"
            }
        except Exception as e: return None

    # --- MONTE CARLO RESTAURADO (COM MATEMÁTICA) ---
    def monte_carlo_carteira(self, retornos, val_ini, aporte, anos=10, sims=1000):
        try:
            if len(retornos) == 0: return np.array([])
            
            # Parâmetros de Movimento Browniano Geométrico
            log_returns = np.log(1 + retornos)
            mu = log_returns.mean()
            sigma = log_returns.std()
            drift = mu - (0.5 * sigma**2)
            
            days = anos * 252
            simulacoes = []
            
            for _ in range(sims):
                # Geração de choques aleatórios
                shocks = drift + sigma * np.random.normal(0, 1, days)
                path = np.exp(shocks)
                
                saldo = val_ini
                for d, ret in enumerate(path):
                    saldo *= ret
                    # Aporte mensal (a cada 21 dias úteis)
                    if (d + 1) % 21 == 0: 
                        saldo += aporte
                simulacoes.append(saldo)
                
            return np.array(simulacoes)
        except:
            return np.array([])
    
    def consultar_dividendos(self, ticker): return {"status": "NEUTRO"}