import pandas as pd
import yfinance as yf
import numpy as np

# --- MODO 1: VIA ARQUIVO (MANTIDO) ---
def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', thousands='.', decimal=',')
        df.columns = [c.strip() for c in df.columns]
        
        # Filtros
        df = df[df['Liquidez Media Diaria'] > 500000] 
        df = df[(df['DY (12M) Media'] > 6.0) & (df['DY (12M) Media'] < 20.0)]
        
        cols = ['TICKER', 'PRECO', 'DY (12M) Media', 'P/VP', 'Liquidez Media Diaria', 'SEGMENTO']
        final_cols = [c for c in cols if c in df.columns]
        
        return df[final_cols].sort_values(by='DY (12M) Media', ascending=False).head(20)
    except Exception as e:
        return pd.DataFrame([{"Erro": f"Falha no CSV: {str(e)}"}] )

# --- MODO 2: AUTOMÁTICO (CORREÇÃO DE P/VP) ---
def scanner_auto_yahoo():
    try:
        from motor import MotorAnalise
    except ImportError:
        return pd.DataFrame([{"Erro": "motor.py não encontrado."}])

    motor = MotorAnalise()
    
    # Lista de FIIs Líquidos
    tickers_alvo = [
        "MXRF11.SA", "HGLG11.SA", "XPML11.SA", "KNCR11.SA", "KNRI11.SA", 
        "VISC11.SA", "HGBS11.SA", "CPTS11.SA", "HGRU11.SA", "BTLG11.SA",
        "RECR11.SA", "IRDM11.SA", "ALZR11.SA", "JSRE11.SA", "VILG11.SA",
        "TRXF11.SA", "HGRE11.SA", "XPLG11.SA", "MALL11.SA", "BRCO11.SA",
        "LVBI11.SA", "PVBI11.SA", "RBRR11.SA", "TGAR11.SA", "KNSC11.SA",
        "GGRC11.SA", "VGHF11.SA", "VGIR11.SA", "CVBI11.SA", "RBRF11.SA"
    ]
    
    resultados = []
    
    for t in tickers_alvo:
        try:
            obj = yf.Ticker(t)
            # Tenta baixar histórico suficiente para o motor
            hist = obj.history(period="2y")
            info = obj.info
            
            # Roda o Motor
            analise = motor.analisar(hist, info, t)
            
            if analise:
                # --- CORREÇÃO P/VP FORÇADA ---
                # Se o motor devolveu 0 (porque o Yahoo falhou), tentamos recalcular aqui
                pvp = analise.get('pvp', 0.0)
                
                if pvp == 0:
                    # Tentativa 2: Cálculo Manual com dados brutos
                    preco = analise['preco']
                    vpa = info.get('bookValue')
                    if vpa and vpa > 0:
                        pvp = preco / vpa
                    else:
                        # Tentativa 3: Se não tem VPA, assume 1.0 (neutro) para não zerar score
                        # ou deixa 0 para indicar falha de dado. Vamos deixar 0 mas avisar.
                        pvp = 0.0

                # Atualiza o P/VP dentro do dicionário de análise para o Score não quebrar
                if pvp > 0: analise['pvp'] = pvp

                # Filtro de Liquidez visual
                if analise['liq_media'] > 300000:
                    
                    # Cálculo de Desconto IA
                    p_justo = analise['preco_justo']
                    desconto = 0.0
                    if p_justo > 0:
                        desconto = ((p_justo - analise['preco']) / p_justo) * 100
                    
                    resultados.append({
                        "Ticker": t.replace(".SA", ""),
                        "Setor": motor.identificar_setor(info, t).replace("FIIs-", ""),
                        "Preço": analise['preco'],
                        "Valor Justo": p_justo,
                        "Upside (%)": desconto,
                        "Score IA": analise['score_ia'],
                        "DY Anual": analise['dy_anual'],
                        "P/VP": pvp,
                        "Tendência": analise['sinal_tecnico']
                    })
        except: continue
            
    df = pd.DataFrame(resultados)
    
    if not df.empty:
        # Ordena por Score e depois por DY
        df = df.sort_values(by=["Score IA", "DY Anual"], ascending=[False, False])
        
    return df