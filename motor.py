import yfinance as yf
import pandas_ta as ta

def analisar_ativo(ticker):
    # Baixamos um pouco mais de dados para garantir que os indicadores calculem
    df = yf.download(ticker, period="1y", interval="1d")
    
    if df.empty or len(df) < 20:
        return None

    # Limpeza: Remove colunas multi-index se houver e garante dados limpos
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # Indicadores técnicos
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['SMA_20'] = ta.sma(df['Close'], length=20)
    df['SMA_200'] = ta.sma(df['Close'], length=200)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

    # Remove linhas com valores vazios (NaN) gerados pelos indicadores iniciais
    df = df.dropna()

    if df.empty:
        return None

    # Pegando os valores da última linha disponível
    atual = df.iloc[-1]
    anterior = df.iloc[-2]

    # Conversão segura para números reais
    preco_atual = float(atual['Close'])
    preco_anterior = float(anterior['Close'])
    rsi_atual = float(atual['RSI'])
    sma20_atual = float(atual['SMA_20'])
    sma200_atual = float(atual['SMA_200'])
    sma20_anterior = float(anterior['SMA_20'])
    atr_atual = float(atual['ATR'])

    score = 0
    if rsi_atual < 35: score += 30
    if preco_atual > sma20_atual: score += 20
    if sma20_atual > sma200_atual: score += 20
    if preco_anterior < sma20_anterior and preco_atual > sma20_atual:
        score += 30 

    stop_loss = preco_atual - (2 * atr_atual)
    alvo = preco_atual + (3 * (preco_atual - stop_loss))

    return {
        "df": df,
        "ticker": ticker,
        "preco": round(preco_atual, 2),
        "score": score,
        "stop": round(stop_loss, 2),
        "alvo": round(alvo, 2),
        "rsi": round(rsi_atual, 2)
    }