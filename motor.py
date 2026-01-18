import pandas as pd
import numpy as np
import yfinance as yf

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # TRATAMENTO DE DADOS (Compatível com yfinance novo)
            if isinstance(hist, pd.DataFrame):
                if "Close" in hist.columns:
                    fechamento = hist["Close"]
                else:
                    fechamento = hist.iloc[:, 0]
            else:
                fechamento = hist

            if isinstance(fechamento, pd.DataFrame):
                fechamento = fechamento.iloc[:, 0]
            
            preco_atual = float(fechamento.iloc[-1])
            
            # TÉCNICA
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            
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

            # FUNDAMENTOS
            div_rate = info.get("trailingAnnualDividendRate", 0) or info.get("dividendRate", 0) or 0
            if div_rate > 0:
                dy = div_rate / preco_atual
            else:
                dy = info.get("dividendYield", 0) or 0
                if dy > 2.0: dy = dy / 100
            
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            # VALUATION
            val_div = div_rate if div_rate > 0 else (preco_atual * dy)
            p_bazin = val_div / 0.06 if val_div > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin

            # SCORE IA
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

    # MONTE CARLO GBM (Correção Matemática)
    def monte_carlo_carteira(self, retornos_carteira, valor_inicial, aporte_mensal, anos=10, sims=1000):
        if len(retornos_carteira) == 0: return np.array([])
        
        log_returns = np.log(1 + retornos_carteira)
        mu_diario = log_returns.mean()
        sigma_diario = log_returns.std()
        
        total_dias = anos * 252
        passos_por_mes = 21
        resultados_finais = []
        drift = mu_diario - (0.5 * sigma_diario**2)
        
        for _ in range(sims):
            choques = np.random.normal(0, 1, total_dias)
            retornos_diarios_sim = np.exp(drift + sigma_diario * choques)
            saldo = valor_inicial
            dia = 0
            for r in retornos_diarios_sim:
                saldo = saldo * r
                dia += 1
                if dia % passos_por_mes == 0:
                    saldo += aporte_mensal
            resultados_finais.append(saldo)

        return np.array(resultados_finais)

    # --- PLUGIN DE DIVIDENDOS (REINSERIDO) ---
    def consultar_dividendos(self, ticker):
        try:
            t = yf.Ticker(ticker)
            cal = t.calendar
            # O yfinance mudou o retorno de calendar, as vezes é dict, as vezes DataFrame
            if isinstance(cal, dict) and cal:
                 return {"status": "CALENDÁRIO", "data": "Verificar RI", "valor": "N/A"}
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                 return {"status": "CONFIRMADO", "data": "Próx. Data", "valor": "Verificar"}
            
            # Histórico recente como fallback
            divs = t.dividends
            if not divs.empty:
                ultimo = divs.iloc[-1]
                data = divs.index[-1].strftime('%d/%m/%Y')
                return {"status": "ÚLTIMO PAGO", "data": data, "valor": f"R$ {ultimo:.2f}"}
            
            return {"status": "SEM DADOS", "data": "-", "valor": "-"}
        except:
            return {"status": "ERRO", "data": "-", "valor": "-"}