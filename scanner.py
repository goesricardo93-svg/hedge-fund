import pandas as pd
import yfinance as yf

# MODO 1: CSV
def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', thousands='.', decimal=',')
        df.columns = [c.strip() for c in df.columns]
        cols = ['TICKER', 'PRECO', 'DY (12M) Media', 'P/VP', 'Liquidez Media Diaria']
        final = [c for c in cols if c in df.columns]
        return df[final].head(20)
    except: return pd.DataFrame()

# MODO 2: AUTO
def scanner_auto_yahoo():
    try: from motor import MotorAnalise
    except: return pd.DataFrame([{"Erro": "Motor não encontrado"}])
    
    motor = MotorAnalise()
    
    # Lista Curta e Eficiente para Teste
    tickers = [
        "MXRF11.SA", "HGLG11.SA", "XPML11.SA", "KNCR11.SA", "KNRI11.SA", 
        "VISC11.SA", "HGBS11.SA", "CPTS11.SA", "HGRU11.SA", "BTLG11.SA"
    ]
    
    res = []
    for t in tickers:
        try:
            # Baixa só 6 meses para ser rápido
            hist = yf.Ticker(t).history(period="6mo")
            info = yf.Ticker(t).info
            
            an = motor.analisar(hist, info, t)
            
            if an:
                res.append({
                    "Ticker": t.replace(".SA", ""),
                    "Score": an['score_ia'],
                    "Preço": an['preco'],
                    "Valor Justo": an['preco_justo'],
                    "P/VP": an['pvp'],
                    "DY %": an['dy_anual'],
                    "Decisão": an['decisao_ia']
                })
        except: continue
            
    df = pd.DataFrame(res)
    if not df.empty:
        df = df.sort_values(by="Score", ascending=False)
    return df