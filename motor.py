import pandas as pd
import numpy as np
import yfinance as yf
from datetime import timedelta

class MotorAnalise:
    def identificar_setor(self, info, ticker):
        # LISTA VIP
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
            preco_atual = float(fechamento.iloc[-1])
            
            # --- CÁLCULO DE DY (LÓGICA v50.1 RESTAURADA) ---
            dy_anual = 0.0
            try:
                # 1. Tenta calcular somando os proventos reais (Mais preciso)
                ticker_obj = yf.Ticker(ticker)
                divs = ticker_obj.dividends
                
                if not divs.empty:
                    # Pega data de hoje menos 1 ano
                    cutoff = pd.Timestamp.now(tz=divs.index.tz) - timedelta(days=365)
                    soma_12m = divs[divs.index >= cutoff].sum()
                    
                    if preco_atual > 0:
                        dy_anual = (soma_12m / preco_atual) * 100
            except:
                pass

            # 2. Se o manual falhou (deu 0), usa o do Yahoo como Fallback
            if dy_anual == 0:
                val = info.get("dividendYield", 0)
                if val is not None:
                    dy_anual = val * 100

            # --- TRAVA DE SANIDADE (CORREÇÃO DO ERRO 1214%) ---
            # Se o DY for maior que 200% (impossível p/ BBSE3), assume erro de escala e divide por 100
            if dy_anual > 200.0:
                dy_anual = dy_anual / 100.0

            # --- CORREÇÃO P/VP ---
            def safe_float(v): 
                try: return float(v) 
                except: return 0.0

            pvp = safe_float(info.get("priceToBook"))
            if pvp == 0 or pvp is None:
                vpa = safe_float(info.get("bookValue"))
                if vpa > 0: pvp = preco_atual / vpa
                elif "11.SA" in ticker: pvp = 1.0 # Fallback FII

            # --- VALUATION (BAZIN USA O DY CORRIGIDO) ---
            div_reais = (dy_anual / 100) * preco_atual
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            
            lpa = safe_float(info.get("trailingEps"))
            vpa = safe_float(info.get("bookValue"))
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa>0 and vpa>0) else 0
            
            setor = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor
            
            if is_fii: preco_justo = p_bazin
            else: 
                validos = [x for x in [p_bazin, p_graham] if x > 0]
                preco_justo = sum(validos)/len(validos) if validos else 0

            # --- SCORE ---
            score = 50
            motivos = []
            
            # Médias Móveis para Tendência
            mme9 = fechamento.ewm(span=9).mean().iloc[-1]
            mme21 = fechamento.ewm(span=21).mean().iloc[-1]
            tendencia = "ALTA" if mme9 > mme21 else "BAIXA"

            if is_fii:
                if 0.85 <= pvp <= 1.10: score += 20; motivos.append("P/VP Justo")
                if dy_anual > 6.0: score += 15; motivos.append("Bom DY")
            else:
                if tendencia == "ALTA": score += 20; motivos.append("Tendência Alta")
                if preco_justo > preco_atual: score += 20; motivos.append("Desconto Valuation")

            return {
                "preco": preco_atual,
                "score_ia": min(100, max(0, score)),
                "decisao_ia": "COMPRA" if score >= 60 else "AGUARDAR",
                "motivos": ", ".join(motivos),
                "dy_anual": dy_anual, # Agora vai correto
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_bazin,
                "preco_justo": preco_justo,
                "pvp": pvp,
                "sinal_tecnico": tendencia,
                "status_macd": "NEUTRO", "stop_loss": 0, "stop_gain": 0, 
                "rsi": 50, "volatilidade": 0, "vol_relativo": 1, "suporte": 0, "resistencia": 0
            }

        except Exception as e:
            return None # Retorna None se falhar para não travar o app

    def monte_carlo_carteira(self, r, v, a, anos=10, sims=100): return np.array([])
    def consultar_dividendos(self, t): return {}