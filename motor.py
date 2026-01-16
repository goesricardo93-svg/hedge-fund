import yfinance as yf
import pandas_ta as ta
import numpy as np

def analisar_ativo(ticker):
    df = yf.download(ticker, period="1y", interval="1d")
    if df.empty or len(df) < 50: return None

    # Limpeza de colunas
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # 1. Indicadores Básicos
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['SMA_20'] = ta.sma(df['Close'], length=20)
    df['SMA_200'] = ta.sma(df['Close'], length=200)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

    # 2. Suportes e Resistências (Mínimas e Máximas de 52 semanas)
    suporte_relevante = float(df['Low'].rolling(window=60).min().iloc[-1])
    resistencia_relevante = float(df['High'].rolling(window=60).max().iloc[-1])

    # 3. Projeção de Fibonacci (Baseado no último ciclo de 3 meses)
    topo_fibo = float(df['High'].rolling(window=90).max().iloc[-1])
    fundo_fibo = float(df['Low'].rolling(window=90).min().iloc[-1])
    distancia = topo_fibo - fundo_fibo
    
    fibo_382 = topo_fibo - (0.382 * distancia)
    fibo_500 = topo_fibo - (0.5 * distancia)
    fibo_618 = topo_fibo - (0.618 * distancia)

    # 4. Lógica de Score e Análise de "Topo"
    atual = df.iloc[-1]
    preco_atual = float(atual['Close'])
    rsi_atual = float(atual['RSI'])
    
    score = 50 # Começa neutro
    
    # Penaliza se estiver muito caro (RSI > 70)
    if rsi_atual > 70: score -= 40 
    elif rsi_atual < 30: score += 30
    
    # Tendência (Preço vs Médias)
    if preco_atual > float(atual['SMA_20']): score += 10
    if float(atual['SMA_20']) > float(atual['SMA_200']): score += 10

    # Definição de Stop e Alvo (Fibonacci + Volatilidade)
    # Stop Loss logo abaixo do suporte ou do Fibo 38.2
    stop_loss = min(suporte_relevante, fibo_382) * 0.98 
    # Alvo de Gain na próxima expansão de Fibonacci (1.618)
    stop_gain = topo_fibo + (0.618 * distancia)

    return {
        "df": df,
        "ticker": ticker,
        "preco": round(preco_atual, 2),
        "score": max(0, min(100, score)), # Garante score entre 0 e 100
        "rsi": round(rsi_atual, 2),
        "suporte": round(suporte_relevante, 2),
        "resistencia": round(resistencia_relevante, 2),
        "fibo_50": round(fibo_500, 2),
        "stop": round(stop_loss, 2),
        "alvo": round(stop_gain, 2)
    }