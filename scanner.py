import pandas as pd
import yfinance as yf

# ======================================================
# MODO 1: VIA ARQUIVO (ANÁLISE PROFUNDA RESTAURADA)
# ======================================================
def scanner_fiis_csv(uploaded_file):
    try:
        # Lê o CSV padrão do StatusInvest (separador ponto-e-vírgula, encoding latin-1)
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', thousands='.', decimal=',')
        
        # Limpa espaços nos nomes das colunas
        df.columns = [c.strip() for c in df.columns]
        
        # --- APLICAÇÃO DOS FILTROS (AQUI ESTAVA O ERRO) ---
        
        # 1. Filtro de Liquidez (FIIs negociáveis)
        if 'Liquidez Media Diaria' in df.columns:
            df = df[df['Liquidez Media Diaria'] > 500000] 
            
        # 2. Filtro de Dividendos (Evita DY falso/gigante ou zerado)
        if 'DY (12M) Media' in df.columns:
            df = df[(df['DY (12M) Media'] > 6.0) & (df['DY (12M) Media'] < 20.0)]
            
        # 3. Filtro de Preço Justo (P/VP)
        if 'P/VP' in df.columns:
            df = df[(df['P/VP'] > 0.80) & (df['P/VP'] < 1.20)]
            
        # 4. Filtro de Vacância (Segurança para Tijolo)
        # Verifica se a coluna existe antes de filtrar
        if 'Vacancia Financeira' in df.columns:
             df = df[df['Vacancia Financeira'] < 10.0]
        
        # Seleção e Ordenação das Colunas Finais
        cols_desejadas = ['TICKER', 'PRECO', 'DY (12M) Media', 'P/VP', 'Liquidez Media Diaria', 'SEGMENTO', 'Vacancia Financeira']
        
        # Garante que só pegamos colunas que realmente existem no arquivo
        cols_finais = [c for c in cols_desejadas if c in df.columns]
        
        # Retorna o Top 20 ordenado por DY
        return df[cols_finais].sort_values(by='DY (12M) Media', ascending=False).head(20)
        
    except Exception as e:
        return pd.DataFrame([{"Erro na Leitura": f"Verifique se o CSV é do StatusInvest. Detalhe: {str(e)}"}])

# ======================================================
# MODO 2: AUTOMÁTICO (COM INTEGRAÇÃO AO MOTOR)
# ======================================================
def scanner_auto_yahoo():
    try: 
        from motor import MotorAnalise
    except ImportError: 
        return pd.DataFrame([{"Erro": "Arquivo motor.py não encontrado."}])
    
    motor = MotorAnalise()
    
    # Lista Selecionada de FIIs Líquidos
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
            # Baixa histórico curto para performance (suficiente para indicadores técnicos)
            ticker_obj = yf.Ticker(t)
            hist = ticker_obj.history(period="6mo")
            info = ticker_obj.info
            
            # Chama o MotorAnalise para processar este ativo
            analise = motor.analisar(hist, info, t)
            
            if analise:
                # Se passou pelo motor, adiciona na lista
                resultados.append({
                    "Ticker": t.replace(".SA", ""),
                    "Score IA": analise['score_ia'],
                    "Preço": analise['preco'],
                    "Valor Justo": analise['preco_justo'],
                    "P/VP": analise['pvp'],
                    "DY (12m)": analise['dy_anual'],
                    "Decisão": analise['decisao_ia']
                })
        except: 
            continue
            
    df = pd.DataFrame(resultados)
    
    if not df.empty:
        # Ordena: Primeiro os melhores Scores, depois o maior DY
        df = df.sort_values(by=["Score IA", "DY (12m)"], ascending=[False, False])
        
    return df