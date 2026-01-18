import pandas as pd
import yfinance as yf
import io

# --- MODO 1: VIA ARQUIVO (PRECISÃO MÁXIMA) ---
def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', thousands='.', decimal=',')
        df.columns = [c.strip() for c in df.columns]
        
        # Filtros Private Bank
        df = df[df['Liquidez Media Diaria'] > 500000] # Liquidez > 500k
        df = df[(df['DY (12M) Media'] > 6.0) & (df['DY (12M) Media'] < 18.0)] # DY Saudável
        df = df[(df['P/VP'] > 0.80) & (df['P/VP'] < 1.15)] # Preço Justo
        
        if 'Vacancia Financeira' in df.columns:
            df = df[df['Vacancia Financeira'] < 10.0]

        cols = ['TICKER', 'PRECO', 'DY (12M) Media', 'P/VP', 'Liquidez Media Diaria', 'SEGMENTO']
        final_cols = [c for c in cols if c in df.columns]
        
        return df[final_cols].sort_values(by='DY (12M) Media', ascending=False).head(20)
    except Exception as e:
        return pd.DataFrame([{"Erro": f"Falha no CSV: {str(e)}"}] )

# --- MODO 2: AUTOMÁTICO (CORREÇÃO DO ERRO) ---
def scanner_auto_yahoo():
    # Top 25 FIIs Líquidos para varredura rápida
    tickers_alvo = [
        "MXRF11.SA", "HGLG11.SA", "XPML11.SA", "KNCR11.SA", "KNRI11.SA", 
        "VISC11.SA", "HGBS11.SA", "CPTS11.SA", "HGRU11.SA", "BTLG11.SA",
        "RECR11.SA", "IRDM11.SA", "ALZR11.SA", "JSRE11.SA", "VILG11.SA",
        "TRXF11.SA", "HGRE11.SA", "XPLG11.SA", "MALL11.SA", "BRCO11.SA",
        "LVBI11.SA", "PVBI11.SA", "RBRR11.SA", "TGAR11.SA", "KNSC11.SA"
    ]
    
    resultados = []
    
    # Download em lote (mais rápido)
    try:
        dados = yf.download(tickers_alvo, period="1d", progress=False)['Close']
        if dados.empty: return pd.DataFrame([{"Status": "Erro de conexão com Yahoo Finance."}])
        
        for t in tickers_alvo:
            try:
                ticker_obj = yf.Ticker(t)
                info = ticker_obj.info
                
                # Pega preço do lote ou direto
                preco = float(dados[t].iloc[-1])
                dy_anual = (info.get('dividendYield', 0) or 0) * 100
                
                # Filtro de Qualidade Básico
                if dy_anual > 6.0 and dy_anual < 20.0:
                    resultados.append({
                        "Ticker": t.replace(".SA", ""),
                        "Preço": f"R$ {preco:.2f}",
                        "DY (Estimado)": f"{dy_anual:.2f}%",
                        "Setor": info.get('industry', 'N/A')
                    })
            except: continue
                
        df = pd.DataFrame(resultados)
        if not df.empty:
            df = df.sort_values(by="DY (Estimado)", ascending=False)
        return df
    except Exception as e:
        return pd.DataFrame([{"Erro": f"Falha na varredura: {str(e)}" }])