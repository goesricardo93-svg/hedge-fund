import yfinance as yf
import pandas_ta as ta

def analisar_ativo(ticker):
    df = yf.download(ticker, period="1y", interval="1d")
    if df.empty or len(df) < 50: return None

    # Limpeza de colunas
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # Indicadores
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['SMA_20'] = ta.sma(df['Close'], length=20)
    df['SMA_200'] = ta.sma(df['Close'], length=200)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df = df.dropna()

    # Suportes e Resistências
    resistencia = float(df['High'].tail(60).max())
    suporte = float(df['Low'].tail(60).min())

    # Fibonacci (Ciclo de 90 dias)
    topo_f = float(df['High'].tail(90).max())
    fundo_f = float(df['Low'].tail(90).min())
    dist = topo_f - fundo_f
    fibo_50 = topo_f - (0.5 * dist)
    fibo_618 = topo_f - (0.618 * dist)

    # Preço e RSI Atual
    preco_atual = float(df['Close'].iloc[-1])
    rsi_atual = float(df['RSI'].iloc[-1])

    # Lógica de Alvo (Expansão 61.8%) e Stop
    stop_gain = topo_f + (0.618 * dist)
    stop_loss = suporte * 0.98

    # Score
    score = 50
    if rsi_atual > 70: score -= 40
    elif rsi_atual < 35: score += 30
    if preco_atual > float(df['SMA_20'].iloc[-1]): score += 10

    return {
        "df": df, "ticker": ticker, "preco": round(preco_atual, 2),
        "score": int(score), "rsi": round(rsi_atual, 2),
        "suporte": round(suporte, 2), "resistencia": round(resistencia, 2),
        "fibo_50": round(fibo_50, 2), "fibo_618": round(fibo_618, 2),
        "stop": round(stop_loss, 2), "alvo": round(stop_gain, 2)
    }