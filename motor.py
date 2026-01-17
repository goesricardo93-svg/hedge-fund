import pandas as pd
import numpy as np

class MotorAnalise:
    def __init__(self):
        self.p_curto = 14
        self.p_longo = 252

    def calcular_rsi(self, serie, window):
        delta = serie.diff()
        ganho = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        perda = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = ganho / (perda + 1e-9)
        return 100 - (100 / (1 + rs))

    def analisar(self, df, info=None):
        if len(df) < 10: return None
        df['close'] = df['close'].ffill()
        
        preco_atual = float(df['close'].iloc[-1])
        ma252 = df['close'].rolling(window=min(len(df), self.p_longo)).mean().iloc[-1]
        rsi14 = self.calcular_rsi(df['close'], self.p_curto).iloc[-1]
        
        # --- 1. ANÁLISE FUNDAMENTALISTA (VALOR) ---
        lpa = info.get('trailingEps', 0) if info else 0
        vpa = info.get('bookValue', 0) if info else 0
        dpa = info.get('dividendRate', 0) if info else 0
        
        p_graham = np.sqrt(max(0, 22.5 * lpa * vpa)) if (lpa > 0 and vpa > 0) else 0
        p_bazin = dpa / 0.06 if dpa > 0 else 0
        p_gordon = dpa / 0.08 if dpa > 0 else 0
        
        vals = [v for v in [p_graham, p_bazin, p_gordon] if v > 0]
        preco_teto = np.mean(vals) if vals else preco_atual
        margem_seguranca = preco_teto > (preco_atual * 1.10) # 10% de margem mínima

        # --- 2. ANÁLISE TÉCNICA (MOMENTO) ---
        tendencia_alta = preco_atual > ma252
        sobrecomprado = rsi14 > 68  # Esticado (Perigo)
        sobrevendido = rsi14 < 35   # Barato tecnicamente (Oportunidade)

        # --- 3. CRUZAMENTO DE SEGURANÇA (MATRIZ DE DECISÃO) ---
        if margem_seguranca and tendencia_alta and not sobrecomprado:
            rec, cor = "COMPRA SEGURA (Valor + Tendência)", "green"
        elif margem_seguranca and sobrevendido:
            rec, cor = "COMPRA OPORTUNISTA (Valor + Reversão)", "green"
        elif sobrecomprado:
            rec, cor = "AGUARDAR (Preço Esticado / RSI Alto)", "yellow"
        elif not margem_seguranca and tendencia_alta:
            rec, cor = "MANTER (Tendência Forte, mas sem Margem)", "blue"
        elif not margem_seguranca and not tendencia_alta:
            rec, cor = "VENDA/FORA (Caro e em Queda)", "red"
        else:
            rec, cor = "AGUARDAR (Sinais Mistos)", "gray"

        # --- SUPORTES E STOPS ---
        max_252 = float(df['close'].tail(252).max())
        min_252 = float(df['close'].tail(252).min())
        diff = max_252 - min_252
        stop_tecnico = min_252 * 0.98

        return {
            "preco": round(preco_atual, 2),
            "ma252": round(ma252, 2),
            "rsi_14": round(rsi14, 2),
            "tendencia": "ALTA" if tendencia_alta else "BAIXA",
            "recomendacao": rec,
            "cor_sinal": cor,
            "val_graham": round(p_graham, 2),
            "val_bazin": round(p_bazin, 2),
            "val_gordon": round(p_gordon, 2),
            "preco_teto": round(preco_teto, 2),
            "upside": round(((preco_teto/preco_atual)-1)*100, 2),
            "suporte": round(min_252, 2),
            "resistencia": round(max_252, 2),
            "stop_loss": round(stop_tecnico, 2),
            "stop_gain": round(preco_teto, 2),
            "fibonacci": {
                "61.8%": round(max_252 - (0.382 * diff), 2),
                "50.0%": round(max_252 - (0.5 * diff), 2),
                "38.2%": round(max_252 - (0.618 * diff), 2)
            }
        }