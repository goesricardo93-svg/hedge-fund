import pandas as pd
import numpy as np
import yfinance as yf

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # --- DADOS DE PREÇO E TÉCNICA ---
            # Tratamento robusto para formatos do yfinance
            if isinstance(hist, pd.DataFrame):
                if "Close" in hist.columns: fechamento = hist["Close"]
                else: fechamento = hist.iloc[:, 0]
            else: fechamento = hist

            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            
            preco_atual = float(fechamento.iloc[-1])
            
            # Indicadores Técnicos
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            
            if loss.iloc[-1] == 0: rs = 100 
            else: rs = gain / loss
            
            rsi = 100 - (100 / (1 + rs.iloc[-1])) if not pd.isna(rs.iloc[-1]) else 50
            
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            
            topo = fechamento.cummax()
            drawdown = ((fechamento - topo) / topo).min() * 100

            # Médias Móveis (Tendência)
            mm50 = fechamento.rolling(50).mean().iloc[-1]
            mm200 = fechamento.rolling(200).mean().iloc[-1]

            # Suporte e Resistência (60 dias)
            window = 60 
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02 

            # --- FUNDAMENTOS PROFISSIONAIS ---
            # Dividendos
            div_rate = info.get("trailingAnnualDividendRate", 0) or info.get("dividendRate", 0) or 0
            if div_rate > 0: dy = div_rate / preco_atual
            else: dy = (info.get("dividendYield", 0) or 0)
            if dy > 2.0: dy = dy / 100 # Trava escala

            # Métricas de Valor e Qualidade
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            roe = info.get("returnOnEquity", 0) or 0 # Retorno sobre Patrimônio
            margem_liq = info.get("profitMargins", 0) or 0 # Margem Líquida
            divida_ebitda = info.get("debtToEbitda", 0) # Dívida/EBITDA (Risco)
            
            # VALUATION (Preços Justos)
            # Bazin (Focado em Dividendos)
            val_div = div_rate if div_rate > 0 else (preco_atual * dy)
            p_bazin = val_div / 0.06 if val_div > 0 else 0
            
            # Graham (Focado em Patrimônio e Lucro)
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            
            # Gordon (Proxy)
            p_gordon = p_bazin

            # --- ALGORITMO DE SCORE CRUZADO (RIGOROSO) ---
            score = 50 # Base Neutra
            motivos = []
            alertas_risco = []

            # 1. VALUATION (Peso 30)
            if p_bazin > 0 and preco_atual < p_bazin: score += 15; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 15; motivos.append("Desconto Graham")
            
            # 2. QUALIDADE E EFICIÊNCIA (Peso 20)
            if roe > 0.15: score += 10; motivos.append(f"ROE Alto ({roe*100:.1f}%)")
            elif roe < 0.05: score -= 10; alertas_risco.append("Rentabilidade Baixa")
            
            if margem_liq > 0.10: score += 10; motivos.append("Margem Sólida")
            elif margem_liq < 0.03: score -= 5; alertas_risco.append("Margem Apertada")

            # 3. SAÚDE FINANCEIRA (Dívida) (Peso 20 - Penaliza forte)
            # FIIs geralmente não têm esse dado no campo padrão, então ignoramos se for None
            if divida_ebitda is not None:
                if divida_ebitda > 3.5: 
                    score -= 20; alertas_risco.append(f"Alavancado ({divida_ebitda:.1f}x EBITDA)")
                elif divida_ebitda < 1.5: 
                    score += 10; motivos.append("Caixa Forte/Dívida Baixa")

            # 4. DIVIDENDOS (Peso 10)
            if dy > 0.06: score += 10; motivos.append(f"DY Atrativo ({dy*100:.1f}%)")

            # 5. TÉCNICA E MOMENTO (Peso 20)
            if rsi < 30: score += 15; motivos.append("Sobrevendido (Oportunidade Téc.)")
            elif rsi > 70: score -= 15; alertas_risco.append("Sobrecomprado (Caro Téc.)")
            
            # Tendência (MM200)
            if preco_atual > mm200: motivos.append("Tendência Alta (Acima MM200)")
            else: alertas_risco.append("Tendência Baixa (Abaixo MM200)")

            # --- VEREDITO IA ---
            score = min(100, max(0, score))

            if score >= 75: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 35: decisao = "🔴 VENDA/RISCO"
            else: decisao = "⚪ MANTER/NEUTRO"

            # Resumo Inteligente
            txt_motivos = ", ".join(motivos[:3]) # Pega os 3 principais positivos
            txt_riscos = ", ".join(alertas_risco[:2]) # Pega os 2 principais riscos
            analise_final = f"✅ {txt_motivos}" 
            if txt_riscos: analise_final += f" | ⚠️ CUIDADO: {txt_riscos}"

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
                "motivos": analise_final, # Texto combinado
                "pl": info.get("trailingPE", 0) or 0,
                "pvp": info.get("priceToBook", 0) or 0,
                "roe": roe,
                "margem": margem_liq,
                "divida_ebitda": divida_ebitda if divida_ebitda else 0
            }
        except Exception:
            return None

    # MONTE CARLO GBM (Mantido e Robusto)
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

    # PLUGIN DIVIDENDOS (Mantido)
    def consultar_dividendos(self, ticker):
        try:
            t = yf.Ticker(ticker)
            cal = t.calendar
            if isinstance(cal, dict) and cal:
                 return {"status": "CALENDÁRIO", "data": "Verificar RI", "valor": "N/A"}
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                 return {"status": "CONFIRMADO", "data": "Próx. Data", "valor": "Verificar"}
            
            divs = t.dividends
            if not divs.empty:
                ultimo = divs.iloc[-1]
                data = divs.index[-1].strftime('%d/%m/%Y')
                return {"status": "ÚLTIMO PAGO", "data": data, "valor": f"R$ {ultimo:.2f}"}
            
            return {"status": "SEM DADOS", "data": "-", "valor": "-"}
        except:
            return {"status": "ERRO", "data": "-", "valor": "-"}