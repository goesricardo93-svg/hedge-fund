import pandas as pd
import numpy as np

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # --- DADOS DE PREÇO ---
            fechamento = hist["Close"]
            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            preco_atual = float(fechamento.iloc[-1])
            
            # --- TÉCNICA ---
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            topo = fechamento.cummax()
            drawdown = ((fechamento - topo) / topo).min() * 100

            window = 60 
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02 # Teto Técnico IA

            # --- FUNDAMENTOS (Blindagem de DY) ---
            # Prioridade: Cálculo manual (Div em R$ / Preço)
            div_rate = info.get("trailingAnnualDividendRate", 0) or info.get("dividendRate", 0) or 0
            if div_rate > 0:
                dy = div_rate / preco_atual
            else:
                dy = info.get("dividendYield", 0) or 0
                if dy > 2.0: dy = dy / 100 # Trava de escala
            
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            # VALUATION
            dpa = div_rate if div_rate > 0 else (preco_atual * dy)
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin

            # SCORE IA (0-100)
            score = 50
            motivos = []

            # Fundamentalista
            if p_bazin > 0 and preco_atual < p_bazin: score += 20; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 20; motivos.append("Desconto Graham")
            if dy > 0.06: score += 10; motivos.append(f"DY > 6% ({dy*100:.1f}%)")

            # Técnico
            if rsi < 30: score += 20; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 20; motivos.append("RSI Esticado")
            if preco_atual <= suporte * 1.03: score += 10; motivos.append("Suporte Forte")

            score = min(100, max(0, score))

            if score >= 75: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 30: decisao = "🔴 VENDA"
            else: decisao = "⚪ MANTER"

            return {
                "preco": preco_atual,
                "rsi": rsi,
                "volatilidade": volatilidade,
                "drawdown": drawdown,
                "p_bazin": p_bazin,
                "p_graham": p_graham,
                "p_gordon": p_gordon,
                "dy": dy,
                "suporte": suporte,
                "resistencia": resistencia,
                "stop_loss": stop_loss,
                "stop_gain": stop_gain,
                "score_ia": score,
                "decisao_ia": decisao,
                "motivos": ", ".join(motivos),
                "pl": info.get("trailingPE", 0) or 0,
                "pvp": info.get("priceToBook", 0) or 0,
                "roe": info.get("returnOnEquity", 0) or 0,
                "margem": info.get("profitMargins", 0) or 0,
                "divida_ebitda": info.get("debtToEbitda", 0) or 0
            }
        except Exception:
            return None

    def monte_carlo_carteira(self, retornos_carteira, valor_inicial, aporte_mensal, anos=10, sims=1000):
        # Simulação Baseada na Matriz de Retornos Reais da Carteira
        if len(retornos_carteira) == 0: return np.array([])
        
        # Média e Volatilidade da Carteira
        mu = retornos_carteira.mean().mean()
        sigma = retornos_carteira.std().mean()
        
        meses = anos * 12
        dias_mes = 21
        resultados = []
        
        mu_mensal = mu * dias_mes
        sigma_mensal = sigma * np.sqrt(dias_mes)

        for _ in range(sims):
            pat = valor_inicial
            for _ in range(meses):
                retorno_mes = np.random.normal(mu_mensal, sigma_mensal)
                pat = pat * (1 + retorno_mes) + aporte_mensal
            resultados.append(pat)
        return np.array(resultados)