import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # --- TRATAMENTO DE DADOS ---
            if isinstance(hist, pd.DataFrame):
                if "Close" in hist.columns: fechamento = hist["Close"]
                else: fechamento = hist.iloc[:, 0]
            else: fechamento = hist

            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            
            preco_atual = float(fechamento.iloc[-1])
            
            # --- TÉCNICA ---
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

            window = 60 
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02 

            # --- FUNDAMENTOS ---
            div_rate = info.get("trailingAnnualDividendRate", 0)
            if div_rate is None: div_rate = 0
            
            div_yield_api = info.get("dividendYield", 0)
            if div_yield_api is None: div_yield_api = 0

            if div_rate > 0: dy = div_rate / preco_atual
            else:
                dy = div_yield_api
                if dy > 2.0: dy = dy / 100
            
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            roe = info.get("returnOnEquity", 0) or 0
            margem_liq = info.get("profitMargins", 0) or 0
            divida_ebitda = info.get("debtToEbitda", 0)

            # --- VALUATION ---
            val_div = div_rate if div_rate > 0 else (preco_atual * dy)
            p_bazin = val_div / 0.06 if val_div > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin

            # --- SCORE IA ---
            score = 50
            motivos = []
            alertas = []

            if p_bazin > 0 and preco_atual < p_bazin: score += 15; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 15; motivos.append("Desconto Graham")
            
            if roe > 0.15: score += 10; motivos.append(f"ROE Alto ({roe*100:.0f}%)")
            elif roe < 0.05: score -= 10; alertas.append("Rentabilidade Baixa")

            if divida_ebitda is not None and divida_ebitda > 3.5:
                score -= 15; alertas.append("Alavancado")

            if dy > 0.06: score += 10; motivos.append(f"DY Atrativo ({dy*100:.1f}%)")

            if rsi < 30: score += 15; motivos.append("Sobrevendido")
            elif rsi > 70: score -= 15; alertas.append("Esticado")
            if preco_atual <= suporte * 1.03: score += 10; motivos.append("Em Suporte")

            score = min(100, max(0, score))

            if score >= 75: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 35: decisao = "🔴 VENDA"
            else: decisao = "⚪ MANTER"

            txt_motivos = ", ".join(motivos[:3])
            if not txt_motivos: txt_motivos = "Neutro"
            if alertas: txt_motivos += f" | ⚠️ {', '.join(alertas[:2])}"

            return {
                "preco": preco_atual, "rsi": rsi, "volatilidade": volatilidade, "drawdown": drawdown,
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon, "dy": dy,
                "suporte": suporte, "resistencia": resistencia, "stop_loss": stop_loss, "stop_gain": stop_gain,
                "score_ia": score, "decisao_ia": decisao, "motivos": txt_motivos,
                "pl": info.get("trailingPE", 0) or 0, "pvp": info.get("priceToBook", 0) or 0,
                "roe": roe, "margem": margem_liq, "divida_ebitda": divida_ebitda if divida_ebitda else 0
            }
        except Exception: return None

    # MONTE CARLO GBM
    def monte_carlo_carteira(self, retornos_carteira, valor_inicial, aporte_mensal, anos=10, sims=1000):
        if len(retornos_carteira) == 0: return np.array([])
        log_returns = np.log(1 + retornos_carteira)
        mu, sigma = log_returns.mean(), log_returns.std()
        days = anos * 252
        res = []
        drift = mu - (0.5 * sigma**2)
        for _ in range(sims):
            path = np.exp(drift + sigma * np.random.normal(0, 1, days))
            bal = valor_inicial
            for i, r in enumerate(path):
                bal = bal * r
                if (i+1) % 21 == 0: bal += aporte_mensal
            res.append(bal)
        return np.array(res)

    # --- LÓGICA DE DIVIDENDOS (PASSADO + FUTURO) ---
    def consultar_dividendos(self, ticker):
        try:
            t = yf.Ticker(ticker)
            hoje = pd.Timestamp.now().normalize()
            
            resultado = {
                "ultimo_data": "-",
                "ultimo_valor": "-",
                "proximo_data": "-",
                "proximo_valor": "-",
                "status": "NEUTRO"
            }

            # 1. BUSCA O PASSADO (Último Pago)
            try:
                divs = t.dividends
                if not divs.empty:
                    data_ult = divs.index[-1]
                    val_ult = float(divs.iloc[-1])
                    resultado["ultimo_data"] = data_ult.strftime('%d/%m/%Y')
                    resultado["ultimo_valor"] = f"R$ {val_ult:.2f}"
            except: pass

            # 2. BUSCA O FUTURO (Calendário)
            try:
                cal = t.calendar
                data_futura = None
                
                # Tratamento para formatos do Yahoo
                if isinstance(cal, dict):
                    raw_date = cal.get('Dividend Date') or cal.get('Ex-Dividend Date')
                    if raw_date: data_futura = pd.to_datetime(raw_date)
                elif isinstance(cal, pd.DataFrame) and not cal.empty:
                    data_futura = pd.to_datetime(cal.iloc[0, 0])

                # Se existe data futura E ela é maior que hoje
                if data_futura and data_futura > hoje:
                    resultado["proximo_data"] = data_futura.strftime('%d/%m/%Y')
                    resultado["proximo_valor"] = "Aguardando Anúncio" # Yahoo não costuma dar o valor futuro exato
                    resultado["status"] = "AGENDA"
            except: pass

            return resultado

        except:
            return {"ultimo_data": "-", "ultimo_valor": "-", "proximo_data": "-", "proximo_valor": "-", "status": "ERRO"}