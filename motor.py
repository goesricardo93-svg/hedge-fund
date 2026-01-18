import pandas as pd
import numpy as np

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # TRATAMENTO ROBUSTO DE DADOS (Correção para atualizações do yfinance)
            # Tenta pegar 'Close' ou a primeira coluna se for Série única
            if isinstance(hist, pd.DataFrame):
                if "Close" in hist.columns:
                    fechamento = hist["Close"]
                else:
                    fechamento = hist.iloc[:, 0] # Fallback
            else:
                fechamento = hist

            # Garante que é uma Series unidimensional
            if isinstance(fechamento, pd.DataFrame):
                fechamento = fechamento.iloc[:, 0]
            
            preco_atual = float(fechamento.iloc[-1])
            
            # --- TÉCNICA ---
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            
            # Evita divisão por zero
            if loss.iloc[-1] == 0:
                rs = 100 
            else:
                rs = gain / loss
            
            rsi = 100 - (100 / (1 + rs.iloc[-1])) if not pd.isna(rs.iloc[-1]) else 50
            
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            topo = fechamento.cummax()
            drawdown = ((fechamento - topo) / topo).min() * 100

            window = 60 
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02 

            # --- FUNDAMENTOS (DY BLINDADO) ---
            div_rate = info.get("trailingAnnualDividendRate", 0) or info.get("dividendRate", 0) or 0
            if div_rate > 0:
                dy = div_rate / preco_atual
            else:
                dy = info.get("dividendYield", 0) or 0
                if dy > 2.0: dy = dy / 100
            
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            # --- VALUATION ---
            val_div = div_rate if div_rate > 0 else (preco_atual * dy)
            p_bazin = val_div / 0.06 if val_div > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin

            # --- SCORE IA ---
            score = 50
            motivos = []

            if p_bazin > 0 and preco_atual < p_bazin: score += 20; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 20; motivos.append("Desconto Graham")
            if dy > 0.06: score += 10; motivos.append(f"DY Atrativo ({dy*100:.1f}%)")

            if rsi < 30: score += 20; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 20; motivos.append("RSI Esticado")
            if preco_atual <= suporte * 1.03: score += 10; motivos.append("Em Suporte")

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

    # --- MONTE CARLO GBM (Correção Matemática) ---
    def monte_carlo_carteira(self, retornos_carteira, valor_inicial, aporte_mensal, anos=10, sims=1000):
        if len(retornos_carteira) == 0: return np.array([])
        
        # Converte retornos simples para log-retornos (padrão Black-Scholes)
        # Adiciona pequena constante para evitar log(0) ou log(negativo) se houver erro nos dados
        log_returns = np.log(1 + retornos_carteira)
        
        # Parâmetros Anualizados
        mu_diario = log_returns.mean()
        sigma_diario = log_returns.std()
        
        # Projeção Diária
        dias_uteis_ano = 252
        total_dias = anos * dias_uteis_ano
        passos_por_mes = 21 # Aprox. dias úteis por mês
        
        resultados_finais = []
        
        # Drift (Tendência) da simulação
        drift = mu_diario - (0.5 * sigma_diario**2)
        
        for _ in range(sims):
            # Gera caminho aleatório de retornos para todo o período
            choques = np.random.normal(0, 1, total_dias)
            retornos_diarios_sim = np.exp(drift + sigma_diario * choques)
            
            saldo = valor_inicial
            dia = 0
            
            for r in retornos_diarios_sim:
                saldo = saldo * r
                dia += 1
                # Aporte mensal
                if dia % passos_por_mes == 0:
                    saldo += aporte_mensal
            
            resultados_finais.append(saldo)

        return np.array(resultados_finais)