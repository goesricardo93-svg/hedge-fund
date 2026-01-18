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
                
                if "Volume" in hist.columns: volume = hist["Volume"]
                else: volume = pd.Series([0]*len(fechamento))
            else: return None

            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            if isinstance(volume, pd.DataFrame): volume = volume.iloc[:, 0]
            
            preco_atual = float(fechamento.iloc[-1])
            
            # --- TÉCNICA AVANÇADA (MACD + MÉDIAS) ---
            # Médias
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            curta, longa = mme9.iloc[-1], mme21.iloc[-1]
            curta_ant, longa_ant = mme9.iloc[-2], mme21.iloc[-2]

            # MACD (Novo Indicador de Tendência)
            # MACD Line: MME12 - MME26
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            # Signal Line: MME9 da MACD Line
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histograma = macd_line - signal_line
            
            macd_val = macd_line.iloc[-1]
            signal_val = signal_line.iloc[-1]
            hist_val = histograma.iloc[-1]

            # Volume Relativo
            vol_media = volume.rolling(20).mean().iloc[-1]
            vol_relativo = (volume.iloc[-1] / vol_media) if vol_media > 0 else 0

            # --- SINAL TÉCNICO ---
            sinal_tecnico = "NEUTRO"
            preco_alvo = 0.0
            
            # Setup Cruzamento
            if curta > longa and curta_ant <= longa_ant:
                sinal_tecnico = "⚡ COMPRA (CRUZAMENTO)"
                preco_alvo = preco_atual
            elif curta > longa:
                sinal_tecnico = "📈 TENDÊNCIA ALTA"
                preco_alvo = curta # Pullback
            elif curta < longa and curta_ant >= longa_ant:
                sinal_tecnico = "☠️ VENDA (CRUZAMENTO)"
            elif curta < longa:
                sinal_tecnico = "📉 TENDÊNCIA BAIXA"

            # Confirmação MACD
            status_macd = "Bullish" if macd_val > signal_val else "Bearish"

            # --- FUNDAMENTOS & SEGURANÇA (NOVOS) ---
            div_rate = info.get("trailingAnnualDividendRate", 0) or 0
            if div_rate == 0: div_rate = (info.get("dividendYield", 0) or 0) * preco_atual
            dy = div_rate / preco_atual if preco_atual > 0 else 0

            # Métricas Básicas
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            roe = info.get("returnOnEquity", 0) or 0
            margem_liq = info.get("profitMargins", 0) or 0
            divida_ebitda = info.get("debtToEbitda", 0)

            # Métricas de Segurança (NOVAS)
            # Liquidez Corrente: Capacidade de pagar dívidas curto prazo
            liq_corrente = info.get("currentRatio", 0) 
            # Crescimento de Receita (YoY): A empresa está viva?
            cresc_receita = info.get("revenueGrowth", 0)

            # Valuation
            val_div = div_rate
            p_bazin = val_div / 0.06 if val_div > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin

            # --- SCORE IA 2.0 (MAIS RIGOROSO) ---
            score = 50
            motivos = []
            alertas = []

            # 1. Técnica (Peso 30)
            if "COMPRA" in sinal_tecnico: 
                score += 15; motivos.append("Cruzamento Médias")
                if status_macd == "Bullish": score += 5; motivos.append("MACD Positivo")
                if vol_relativo > 1.2: score += 5; motivos.append("Volume Forte")
            elif "VENDA" in sinal_tecnico: 
                score -= 15; alertas.append("Tendência Baixa")

            # 2. Valuation (Peso 20)
            if p_bazin > 0 and preco_atual < p_bazin: score += 10; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 10; motivos.append("Desconto Graham")

            # 3. Qualidade & Crescimento (Peso 30)
            if roe > 0.15: score += 10; motivos.append(f"ROE Alto ({roe*100:.0f}%)")
            
            # NOVO: Bonifica Crescimento / Pune Estagnação
            if cresc_receita and cresc_receita > 0.10: score += 10; motivos.append("Crescimento > 10%")
            elif cresc_receita and cresc_receita < 0: score -= 10; alertas.append("Receita Caindo")

            # 4. Segurança & Solvência (Peso 20)
            # NOVO: Liquidez Corrente
            if liq_corrente and liq_corrente > 1.5: score += 5; motivos.append("Caixa Sólido")
            elif liq_corrente and liq_corrente < 1.0: score -= 15; alertas.append("Risco Liquidez (Curto Prazo)")

            # Dívida Longa
            if divida_ebitda and divida_ebitda > 3.5: score -= 15; alertas.append("Alavancado")

            # 5. Dividendos
            if dy > 0.06: score += 5; motivos.append("Dividendos")

            # RSI
            rsi = 100 - (100 / (1 + (gain.iloc[-1]/loss.iloc[-1] if loss.iloc[-1]!=0 else 1)))
            if rsi < 30: score += 10; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 10; alertas.append("RSI Esticado")

            score = min(100, max(0, score))

            if score >= 80: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 40: decisao = "🔴 VENDA/RISCO"
            else: decisao = "⚪ MANTER"

            txt_resumo = ", ".join(motivos[:3])
            if alertas: txt_resumo += f" | ⚠️ {', '.join(alertas[:2])}"

            # Indicadores de Suporte
            window = 60
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())

            return {
                "preco": preco_atual, "rsi": rsi, "volatilidade": volatilidade, 
                "p_bazin": p_bazin, "p_graham": p_graham, "dy": dy,
                "suporte": suporte, "resistencia": resistencia, 
                "stop_loss": suporte * 0.97, "stop_gain": resistencia * 1.02,
                "score_ia": score, "decisao_ia": decisao, "motivos": txt_resumo,
                "pl": info.get("trailingPE", 0) or 0, "pvp": info.get("priceToBook", 0) or 0,
                "roe": roe, "margem": margem_liq, "divida_ebitda": divida_ebitda,
                # NOVOS DADOS
                "sinal_tecnico": sinal_tecnico, "preco_alvo_entrada": preco_alvo,
                "vol_relativo": vol_relativo, "mme9": curta, "mme21": longa,
                "macd": macd_val, "macd_signal": signal_val,
                "liq_corrente": liq_corrente, "cresc_receita": cresc_receita
            }
        except Exception as e: 
            print(f"Erro Motor: {e}")
            return None

    # MÉTODOS DE MONTE CARLO E DIVIDENDOS (MANTIDOS IGUAIS - NÃO COPIEI PARA ECONOMIZAR ESPAÇO, MANTENHA-OS)
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

    def consultar_dividendos(self, ticker):
        try:
            t = yf.Ticker(ticker)
            hoje = pd.Timestamp.now().normalize()
            resultado = {"ultimo_data": "-", "ultimo_valor": "-", "proximo_data": "-", "proximo_valor": "-", "status": "NEUTRO"}
            try:
                divs = t.dividends
                if not divs.empty:
                    resultado["ultimo_data"] = divs.index[-1].strftime('%d/%m/%Y')
                    resultado["ultimo_valor"] = f"R$ {float(divs.iloc[-1]):.2f}"
            except: pass
            try:
                cal = t.calendar
                data_fut = None
                if isinstance(cal, dict):
                    dt = cal.get('Dividend Date') or cal.get('Ex-Dividend Date')
                    if dt: data_fut = pd.to_datetime(dt)
                elif isinstance(cal, pd.DataFrame) and not cal.empty:
                    data_fut = pd.to_datetime(cal.iloc[0, 0])
                if data_fut and data_fut > hoje:
                    resultado["proximo_data"] = data_fut.strftime('%d/%m/%Y')
                    resultado["proximo_valor"] = "Aguardando"
                    resultado["status"] = "AGENDA"
            except: pass
            return resultado
        except: return {"status": "ERRO", "ultimo_data":"-", "ultimo_valor":"-", "proximo_data":"-", "proximo_valor":"-"}