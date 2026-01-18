import pandas as pd
import yfinance as yf

# --- MODO 1: VIA ARQUIVO (PRECISÃO MÁXIMA) ---
def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', thousands='.', decimal=',')
        df.columns = [c.strip() for c in df.columns]
        
        # Filtros de Segurança
        df = df[df['Liquidez Media Diaria'] > 500000] 
        df = df[(df['DY (12M) Media'] > 6.0) & (df['DY (12M) Media'] < 20.0)]
        df = df[(df['P/VP'] > 0.80) & (df['P/VP'] < 1.20)]
        
        cols = ['TICKER', 'PRECO', 'DY (12M) Media', 'P/VP', 'Liquidez Media Diaria', 'SEGMENTO']
        final_cols = [c for c in cols if c in df.columns]
        
        return df[final_cols].sort_values(by='DY (12M) Media', ascending=False).head(20)
    except Exception as e:
        return pd.DataFrame([{"Erro": f"Falha no CSV: {str(e)}"}] )

# --- MODO 2: AUTOMÁTICO (CORRIGIDO PARA NÃO FICAR EM BRANCO) ---
def scanner_auto_yahoo():
    tickers_alvo = [
        "MXRF11.SA", "HGLG11.SA", "XPML11.SA", "KNCR11.SA", "KNRI11.SA", 
        "VISC11.SA", "HGBS11.SA", "CPTS11.SA", "HGRU11.SA", "BTLG11.SA",
        "RECR11.SA", "IRDM11.SA", "ALZR11.SA", "JSRE11.SA", "VILG11.SA",
        "TRXF11.SA", "HGRE11.SA", "XPLG11.SA", "MALL11.SA", "BRCO11.SA",
        "LVBI11.SA", "PVBI11.SA", "RBRR11.SA", "TGAR11.SA", "KNSC11.SA"
    ]
    
    resultados = []
    
    for t in tickers_alvo:
        try:
            # Baixa individualmente para garantir integridade dos dados
            ticker_obj = yf.Ticker(t)
            hist = ticker_obj.history(period="1d")
            
            if not hist.empty:
                preco = float(hist['Close'].iloc[-1])
                info = ticker_obj.info
                
                # Tenta pegar DY de várias formas
                dy = info.get('dividendYield', 0)
                if dy is None: dy = 0
                dy_pct = dy * 100
                
                # Se DY for zero, tenta calcular na mão (soma ultimos 12 meses) - Opcional, mantendo simples
                if dy_pct > 4.0: # Filtra coisas sem yield
                    resultados.append({
                        "Ticker": t.replace(".SA", ""),
                        "Preço": f"R$ {preco:.2f}",
                        "DY (Estimado)": f"{dy_pct:.2f}%",
                        "Setor": info.get('industry', 'FII')
                    })
        except:
            continue
            
    df = pd.DataFrame(resultados)
    if not df.empty:
        df = df.sort_values(by="DY (Estimado)", ascending=False)
    else:
        df = pd.DataFrame([{"Status": "Nenhum dado encontrado. O Yahoo Finance pode estar instável."}])
    
    return df