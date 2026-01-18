import pandas as pd
import numpy as np
import yfinance as yf

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        """Mapeia FIIs e Ações para as categorias corretas"""
        industry = (info.get('industry', '') or '').lower()
        summary = (info.get('longBusinessSummary', '') or '').lower()
        name = (info.get('longName', '') or '').lower()

        # --- LÓGICA FIIs ---
        if ticker.endswith('11.SA') and ticker not in ['IVVB11.SA', 'BOVA11.SA', 'XINA11.SA']:
            tijolo_kws = ['shopping', 'mall', 'logística', 'logistics', 'galpão', 'warehouse', 'laje', 'corporativo', 'urbana', 'renda urbana', 'hospital', 'imóveis', 'properties', 'real estate']
            if any(kw in industry or kw in summary or kw in name for kw in tijolo_kws):
                return "FIIs-Tijolo"
            
            papel_kws = ['recebíveis', 'cri', 'cra', 'papel', 'paper', 'debt', 'dívida', 'crédito', 'fund of funds', 'fof', 'títulos']
            if any(kw in industry or kw in summary or kw in name for kw in papel_kws):
                return "FIIs-Papel"
            
            return "FIIs-Outros"

        # --- LÓGICA AÇÕES & EXTERIOR ---
        if ticker in ['IVVB11.SA', 'BDRX19.SA'] or not ticker.endswith('.SA'): return "Exterior"

        if 'bank' in industry or 'financial' in industry: return "Ações-Bancos"
        if 'utilit' in industry or 'electric' in industry or 'water' in industry: return "Ações-Elétricas"
        if 'insur' in industry or 'segur' in industry: return "Ações-Seguridade"
        if 'mining' in industry or 'oil' in industry or 'gas' in industry or 'steel' in industry or 'basic materials' in industry: return "Ações-Commodities"
        
        return "Ações-Outros"

    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None
            
            fechamento = hist["Close"].iloc[:, 0] if isinstance(hist["Close"], pd.DataFrame) else hist["Close"]
            volume = hist["Volume"].iloc[:, 0] if isinstance(hist["Volume"], pd.DataFrame) else hist["Volume"]
            
            if len(fechamento) < 30: return None
            preco_atual = float(fechamento.iloc[-1])

            # --- 1. DADOS FUNDAMENTALISTAS ---
            def safe_get(key, default=0.0):
                val = info.get(key)
                return float(val) if val is not None else default

            # Dividendos (Cálculo Real)
            try:
                t = yf.Ticker(ticker)
                divs = t.dividends
                if not divs.empty:
                    ultimo_pag = float(divs.iloc[-1])
                    dy_mensal = (ultimo_pag / preco_atual) * 100
                    dt_ano = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(months=12)
                    dy_anual = (float(divs[divs.index >= dt_ano].sum()) / preco_atual) * 100
                else: dy_mensal, dy_anual = 0.0, 0.0
            except: dy_mensal, dy_anual = 0.0, safe_get("dividendYield") * 100

            # Valuation
            div_reais = (dy_anual / 100) * preco_atual
            lpa = safe_get("trailingEps")
            vpa = safe_get("bookValue")
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin

            # --- 2. CÁLCULO DO SCORE (GESTOR DE RISCO) ---
            score = 50
            motivos = []
            
            # Identificação Interna para Regras
            setor_ativo = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor_ativo

            # A) TRAVA 1: LIQUIDEZ (Média 21 dias)
            vol_fin_medio = (fechamento * volume).tail(21).mean()
            limite_liq = 500000 if is_fii else 1000000
            if vol_fin_medio < limite_liq:
                score -= 20
                motivos.append(f"⚠️ Baixa Liquidez (R$ {vol_fin_medio/1000:.0f}k)")
            
            # B) TRAVA 2: PAYOUT (Dividendo Falso)
            payout = safe_get("payoutRatio")
            limite_payout = 1.2 if is_fii else 1.0 # FIIs podem ter lucro caixa > contabil
            if payout > limite_payout:
                score -= 15
                motivos.append(f"⚠️ Payout Estourado ({payout*100:.0f}%)")

            # C) TRAVA 3: FII CARO (P/VP)
            pvp = safe_get("priceToBook")
            if is_fii and pvp > 0:
                if pvp > 1.05:
                    score -= 10
                    motivos.append(f"FII Caro (P/VP {pvp:.2f})")
                
                # A REGRA DE OURO: PAPEL COM ÁGIO = MORTE
                if "Papel" in setor_ativo and pvp > 1.02:
                    score = 0
                    motivos.append("⛔ ÁGIO EM PAPEL (RISCO MÁXIMO)")

            # Critérios Normais (Bonificações)
            mme9 = fechamento.ewm(span=9).mean().iloc[-1]
            mme21 = fechamento.ewm(span=21).mean().iloc[-1]
            
            if mme9 > mme21: score += 15; motivos.append("Tendência Alta")
            else: score -= 15

            if p_bazin > 0 and preco_atual < p_bazin: score += 10; motivos.append("Desc. Bazin")
            if dy_anual > 6.0: score += 10; motivos.append(f"DY Bom ({dy_anual:.1f}%)")
            
            # RSI
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain/loss
            rsi = 100 - (100/(1+rs)).iloc[-1]
            
            if rsi < 30: score += 10; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 10

            # Trava Final de Score (0 a 100)
            score = min(100, max(0, score))
            if "ÁGIO EM PAPEL" in str(motivos): score = 0 # Garante o zero absoluto

            return {
                "preco": preco_atual,
                "score_ia": score,
                "decisao_ia": "🟢 COMPRA" if score >= 60 else "🔴 AGUARDAR",
                "motivos": ", ".join(motivos),
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon,
                "dy_mensal": dy_mensal, "dy_anual": dy_anual,
                "mme9": mme9, "mme21": mme21,
                "liq_media": vol_fin_medio, "pvp": pvp, "payout": payout # Para debug se precisar
            }
        except Exception as e:
            print(f"Erro Motor: {e}")
            return None
    
    # Métodos auxiliares
    def consultar_dividendos(self, ticker): return {"status": "NEUTRO"}
    def monte_carlo_carteira(self, *args): return []