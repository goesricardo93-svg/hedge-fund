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
            
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            if np.isnan(rsi): rsi = 50

            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5) if not retornos.empty else 0.0
            
            suporte = float(fechamento.tail(60).min())
            resistencia = float(fechamento.tail(60).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02
            
            # --- PREÇO ALVO DE ENTRADA (NOVO - PARA O ROBÔ) ---
            # Se tendência de alta, entrada na média curta (pullback).
            # Se baixa/lateral, entrada no suporte.
            if mme9.iloc[-1] > mme21.iloc[-1]:
                preco_alvo_entrada = float(mme9.iloc[-1])
            else:
                preco_alvo_entrada = suporte

            # --- DY ---
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
                try: return float(v) 
                except: return 0.0

            pvp = safe_float(info.get("priceToBook"))
            if pvp == 0 or pvp is None:
                vpa = safe_float(info.get("bookValue"))
                if vpa == 0:
                    a = safe_float(info.get("totalAssets"))
                    s = safe_float(info.get("sharesOutstanding"))
                    if a>0 and s>0: vpa = a/s
                if vpa > 0: pvp = preco_atual/vpa
                elif "11.SA" in ticker: pvp = 1.0

            div_reais = (dy_anual / 100) * preco_atual
            p_bazin = div_reais / 0.06 if div_reais > 0 else 0
            
            lpa = safe_float(info.get("trailingEps"))
            vpa = safe_float(info.get("bookValue"))
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa>0 and vpa>0) else 0
            p_gordon = (div_reais * 1.03) / 0.03 if div_reais > 0 else 0

            setor = self.identificar_setor(info, ticker)
            is_fii = "FII" in setor
            
            if is_fii: preco_justo = p_bazin
            else: 
                validos = [x for x in [p_bazin, p_graham] if x > 0]
                preco_justo = sum(validos)/len(validos) if validos else 0

            # --- SCORE ---
            score = 50
            motivos = []
            alertas = []
            vol_medio = (fechamento * volume).tail(21).mean()

            if is_fii:
                if vol_medio < 300000: score -= 30; alertas.append("Baixa Liquidez")
                if 0.85 <= pvp <= 1.10: score += 20; motivos.append("P/VP Justo")
                elif pvp > 1.15: score -= 15; alertas.append("Caro")
                if dy_anual > 6.0: score += 15; motivos.append("Bom DY")
                if volatilidade < 0.20: score += 10; motivos.append("Estável")
            else:
                if vol_medio < 1000000: score -= 20; alertas.append("Baixa Liquidez")
                if mme9.iloc[-1] > mme21.iloc[-1]: score += 20; motivos.append("Tendência Alta")
                else: score -= 15
                if macd_line.iloc[-1] > signal_line.iloc[-1]: score += 10; motivos.append("MACD Compra")
                if preco_justo > preco_atual: score += 15; motivos.append("Upside")

            return {
                "preco": preco_atual,
                "score_ia": min(100, max(0, score)),
                "decisao_ia": "COMPRA" if score >= 60 else "AGUARDAR",
                "motivos": ", ".join(motivos),
                "alertas": ", ".join(alertas),
                "dy_anual": dy_anual,
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon,
                "preco_justo": preco_justo,
                "pvp": pvp,
                "sinal_tecnico": "ALTA" if mme9.iloc[-1] > mme21.iloc[-1] else "BAIXA",
                "status_macd": "COMPRA" if macd_line.iloc[-1] > signal_line.iloc[-1] else "VENDA",
                "macd": macd_line.iloc[-1], "macd_signal": signal_line.iloc[-1], # Adicionado para o Robô
                "mme9": mme9.iloc[-1], "mme21": mme21.iloc[-1], # Adicionado para o Robô
                "preco_alvo_entrada": preco_alvo_entrada, # Adicionado para o Robô
                "rsi": rsi, "volatilidade": volatilidade,
                "suporte": suporte, "resistencia": resistencia,
                "stop_loss": stop_loss, "stop_gain": stop_gain,
                "vol_relativo": 1.0
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