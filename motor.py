import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # --- 1. TRATAMENTO DE DADOS ---
            if isinstance(hist, pd.DataFrame):
                fechamento = hist["Close"] if "Close" in hist.columns else hist.iloc[:, 0]
                volume = hist["Volume"] if "Volume" in hist.columns else pd.Series([0]*len(fechamento))
            else: return None

            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            if isinstance(volume, pd.DataFrame): volume = volume.iloc[:, 0]
            
            if len(fechamento) < 30: return None
            
            preco_atual = float(fechamento.iloc[-1])
            
            # --- 2. TÉCNICA (MACD, MÉDIAS E VOLATILIDADE) ---
            # Médias
            mme9 = fechamento.ewm(span=9, adjust=False).mean()
            mme21 = fechamento.ewm(span=21, adjust=False).mean()
            curta, longa = mme9.iloc[-1], mme21.iloc[-1]
            curta_ant, longa_ant = mme9.iloc[-2], mme21.iloc[-2]

            # MACD
            ema12 = fechamento.ewm(span=12, adjust=False).mean()
            ema26 = fechamento.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_val = macd_line.iloc[-1]
            signal_val = signal_line.iloc[-1]

            # Volume
            vol_media = volume.rolling(20).mean().iloc[-1]
            vol_relativo = (volume.iloc[-1] / vol_media) if vol_media > 0 else 0

            # Volatilidade (Restaurada)
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)

            # Sinal Técnico
            sinal_tecnico = "NEUTRO"
            preco_alvo = 0.0
            
            if curta > longa and curta_ant <= longa_ant:
                sinal_tecnico = "⚡ COMPRA (CRUZAMENTO)"
                preco_alvo = preco_atual
            elif curta > longa:
                sinal_tecnico = "📈 TENDÊNCIA ALTA"
                preco_alvo = curta 
            elif curta < longa and curta_ant >= longa_ant:
                sinal_tecnico = "☠️ VENDA (CRUZAMENTO)"
            elif curta < longa:
                sinal_tecnico = "📉 TENDÊNCIA BAIXA"

            # --- 3. FUNDAMENTOS (BLINDADOS) ---
            def safe_get(key, default=0.0):
                val = info.get(key)
                if val is None: return default
                return float(val)

            div_rate = safe_get("trailingAnnualDividendRate")
            if div_rate == 0: div_rate = safe_get("dividendYield") * preco_atual
            dy = div_rate / preco_atual if preco_atual > 0 else 0

            lpa = safe_get("trailingEps")
            vpa = safe_get("bookValue")
            roe = safe_get("returnOnEquity")
            margem_liq = safe_get("profitMargins")
            divida_ebitda = safe_get("debtToEbitda")
            
            # Novos Indicadores
            liq_corrente = safe_get("currentRatio", 0) 
            cresc_receita = safe_get("revenueGrowth", 0)

            # Valuation
            val_div = div_rate
            p_bazin = val_div / 0.06 if val_div > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin # Gordon simplificado (igual a Bazin para crescimento zero)

            # --- 4. SCORE IA ---
            score = 50
            motivos = []
            alertas = []

            # Critérios
            if "COMPRA" in sinal_tecnico: 
                score += 15; motivos.append("Cruzamento Médias")
                if macd_val > signal_val: score += 5; motivos.append("MACD Compra")
                if vol_relativo > 1.2: score += 5; motivos.append("Volume Forte")
            elif "VENDA" in sinal_tecnico: score -= 15; alertas.append("Tendência Baixa")

            if p_bazin > 0 and preco_atual < p_bazin: score += 10; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 10; motivos.append("Desconto Graham")
            if roe > 0.15: score += 10; motivos.append(f"ROE Alto ({roe*100:.0f}%)")
            
            if cresc_receita > 0.10: score += 10; motivos.append("Crescimento > 10%")
            elif cresc_receita < -0.05: score -= 10; alertas.append("Receita Caindo")

            # Solvência (Ignora se for zero/banco)
            if liq_corrente > 0: 
                if liq_corrente > 1.5: score += 5; motivos.append("Caixa Sólido")
                elif liq_corrente < 1.0: score -= 15; alertas.append("Liquidez Baixa")

            if divida_ebitda > 3.5: score -= 15; alertas.append("Alavancado")
            if dy > 0.06: score += 5; motivos.append("Dividendos")

            # RSI
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            if loss.iloc[-1] == 0: rsi = 50
            else: rsi = 100 - (100 / (1 + (gain.iloc[-1]/loss.iloc[-1])))
            
            if rsi < 30: score += 10; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 10; alertas.append("RSI Esticado")

            score = min(100, max(0, score))
            
            if score >= 80: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 40: decisao = "🔴 VENDA/RISCO"
            else: decisao = "⚪ MANTER"

            txt_resumo = ", ".join(motivos[:3])
            if alertas: txt_resumo += f" | ⚠️ {', '.join(alertas[:2])}"

            window = 60
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())

            return {
                "preco": preco_atual, "rsi": rsi, "volatilidade": volatilidade, 
                "p_bazin": p_bazin, "p_graham": p_graham, "p_gordon": p_gordon, # <--- AQUI ESTAVA O ERRO (Corrigido)
                "dy": dy,
                "suporte": suporte, "resistencia": resistencia, 
                "stop_loss": suporte * 0.97, "stop_gain": resistencia * 1.02,
                "score_ia": score, "decisao_ia": decisao, "motivos": txt_resumo,
                "pl": info.get("trailingPE", 0) or 0, "pvp": info.get("priceToBook", 0) or 0,
                "roe": roe, "margem": margem_liq, "divida_ebitda": divida_ebitda,
                "sinal_tecnico": sinal_tecnico, "preco_alvo_entrada": preco_alvo,
                "vol_relativo": vol_relativo, "mme9": curta, "mme21": longa,
                "macd": macd_val, "macd_signal": signal_val,
                "liq_corrente": liq_corrente, "cresc_receita": cresc_receita
            }
        except Exception as e:
            print(f"❌ Erro MotorAnalise ({ticker}): {e}")
            return None

    # MANTENHA AS FUNÇÕES ABAIXO (Monte Carlo e Dividendos) IGUAIS
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