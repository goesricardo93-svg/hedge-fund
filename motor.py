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

            # FUNDAMENTOS (DY BLINDADO)
            div_rate = info.get("trailingAnnualDividendRate", 0)
            if div_rate is None: div_rate = 0
            
            div_yield_api = info.get("dividendYield", 0)
            if div_yield_api is None: div_yield_api = 0

            if div_rate > 0:
                dy = div_rate / preco_atual
            else:
                dy = div_yield_api
                if dy > 2.0: dy = dy / 100
            
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            # Dados Extras para Score Rigoroso
            roe = info.get("returnOnEquity", 0) or 0
            margem_liq = info.get("profitMargins", 0) or 0
            divida_ebitda = info.get("debtToEbitda", 0)

            # VALUATION
            val_div = div_rate if div_rate > 0 else (preco_atual * dy)
            p_bazin = val_div / 0.06 if val_div > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin

            # SCORE IA (RIGOROSO)
            score = 50
            motivos = []
            alertas = []

            # 1. Valuation
            if p_bazin > 0 and preco_atual < p_bazin: score += 15; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 15; motivos.append("Desconto Graham")
            
            # 2. Qualidade
            if roe > 0.15: score += 10; motivos.append(f"ROE Alto ({roe*100:.0f}%)")
            elif roe < 0.05: score -= 10; alertas.append("Rentabilidade Baixa")

            if divida_ebitda is not None and divida_ebitda > 3.5:
                score -= 15; alertas.append("Alavancado")

            # 3. Dividendos
            if dy > 0.06: score += 10; motivos.append(f"DY Atrativo ({dy*100:.1f}%)")

            # 4. Técnica
            if rsi < 30: score += 15; motivos.append("Sobrevendido (RSI)")
            elif rsi > 70: score -= 15; alertas.append("Esticado (RSI)")
            if preco_atual <= suporte * 1.03: score += 10; motivos.append("Em Suporte")

            score = min(100, max(0, score))

            if score >= 75: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 35: decisao = "🔴 VENDA"
            else: decisao = "⚪ MANTER"

            # Resumo Inteligente
            txt_motivos = ", ".join(motivos[:3])
            if not txt_motivos and alertas: txt_motivos = "Atenção aos Riscos"
            elif not txt_motivos: txt_motivos = "Neutro"
            
            full_motivo = txt_motivos
            if alertas: full_motivo += f" | ⚠️ {', '.join(alertas[:2])}"

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
                "motivos": full_motivo,
                "pl": info.get("trailingPE", 0) or 0,
                "pvp": info.get("priceToBook", 0) or 0,
                "roe": roe,
                "margem": margem_liq,
                "divida_ebitda": divida_ebitda if divida_ebitda else 0
            }
        except Exception as e:
            print(f"Erro ao analisar {ticker}: {e}")
            return None

    # MONTE CARLO GBM
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

    # --- CORREÇÃO DA LÓGICA DE DIVIDENDOS ---
    def consultar_dividendos(self, ticker):
        """Busca histórico real se calendário futuro for incerto"""
        try:
            t = yf.Ticker(ticker)
            
            # 1. Tenta pegar Histórico (Mais garantido)
            # O .dividends retorna uma Series com datas
            history = t.dividends
            
            last_date = "-"
            last_val = 0.0
            status = "SEM DADOS"

            if not history.empty:
                # Pega o último pagamento registrado
                last_val = float(history.iloc[-1])
                last_date = history.index[-1].strftime('%d/%m/%Y')
                status = "ÚLTIMO PAGO"

            # 2. Tenta pegar Calendário Futuro (Só se tiver data de DIVIDENDO explícita)
            # O yfinance as vezes retorna um dict com 'Earnings Date' mas sem 'Dividend Date'
            try:
                cal = t.calendar
                # Verifica se é dict e tem a chave certa
                if isinstance(cal, dict) and ('Dividend Date' in cal or 'Ex-Dividend Date' in cal):
                    # Se achou futuro, ele ganha prioridade
                    dt_futura = cal.get('Dividend Date') or cal.get('Ex-Dividend Date')
                    if dt_futura:
                        return {"status": "CONFIRMADO", "data": str(dt_futura), "valor": "Aguardando"}
            except:
                pass # Falha silenciosa no calendário, mantém o histórico

            # Retorno Final
            if status == "ÚLTIMO PAGO":
                return {"status": "ÚLTIMO PAGO", "data": last_date, "valor": f"R$ {last_val:.2f}"}
            
            return {"status": "SEM DADOS", "data": "-", "valor": "-"}

        except Exception as e:
            print(f"Erro Div: {e}")
            return {"status": "ERRO", "data": "-", "valor": "-"}