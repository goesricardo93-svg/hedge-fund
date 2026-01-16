import yfinance as yf
import pandas_ta as ta
import numpy as np

def analisar_ativo(ticker):
    # 1. Busca de dados ampliada para garantir médias longas
    df = yf.download(ticker, period="1y", interval="1d")
    
    if df.empty or len(df) < 50:
        return None

    # Limpeza de colunas (trata o formato novo do yfinance)
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # 2. Indicadores Técnicos
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['SMA_20'] = ta.sma(df['Close'], length=20)
    df['SMA_200'] = ta.sma(df['Close'], length=200)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    
    # Remove valores iniciais vazios
    df = df.dropna()

    # 3. Cálculo de Suporte e Resistência (Extremos de 3 meses)
    resistencia_relevante = float(df['High'].tail(60).max())
    suporte_relevante = float(df['Low'].tail(60).min())

    # 4. Projeção de Fibonacci (Ciclo Recente)
    topo_fibo = float(df['High'].tail(90).max())
    fundo_fibo = float(df['Low'].tail(90).min())
    distancia = topo_fibo - fundo_fibo
    
    fibo_382 = topo_fibo - (0.382 * distancia)
    fibo_500 = topo_fibo - (0.5 * distancia)
    fibo_618 = topo_fibo - (0.618 * distancia)

    # 5. Lógica do Score (Foco em Risco de Topo)
    atual = df.iloc[-1]
    preco_atual = float(atual['Close'])
    rsi_atual = float(atual['RSI'])
    
    score = 50 # Base Neutra
    
    # Penalidade por Topo/Sobrecompra
    if rsi_atual > 70: 
        score -= 40 # Ativo esticado
    elif rsi_atual < 35: 
        score += 30 # Ativo em zona de oportunidade

    # Tendência de Médias
    if preco_atual > float(atual['SMA_20']): score += 10
    if float(atual['SMA_20']) > float(atual['SMA_200']): score += 10

    # 6. Definição de Gestão de Risco
    # Stop Loss: 2% abaixo do suporte relevante
    stop_loss = suporte_relevante * 0.98
    # Alvo: Projeção de 161.8% do movimento ou Resistência + ATR
    alvo_fibo = topo_fibo + (0.618 * distancia)

    return {
        "df": df,
        "ticker": ticker,
        "preco": round(preco_atual, 2),
        "score": int(max(0, min(100, score))),
        "rsi": round(rsi_atual, 2),
        "suporte": round(suporte_relevante, 2),
        "resistencia": round(resistencia_relevante, 2),
        "fibo_50": round(fibo_500, 2),
        "stop": round(stop_loss, 2),
        "alvo": round(alvo_fibo, 2)
    }