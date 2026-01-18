import pandas as pd
import yfinance as yf
import numpy as np

# --- MODO 1: VIA ARQUIVO (MANTIDO) ---
def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', thousands='.', decimal=',')
        df.columns = [c.strip() for c in df.columns]
        
        # Filtros Private Bank
        df = df[df['Liquidez Media Diaria'] > 500000] 
        df = df[(df['DY (12M) Media'] > 6.0) & (df['DY (12M) Media'] < 20.0)]
        df = df[(df['P/VP'] > 0.80) & (df['P/VP'] < 1.20)]
        
        cols = ['TICKER', 'PRECO', 'DY (12M) Media', 'P/VP', 'Liquidez Media Diaria', 'SEGMENTO']
        final_cols = [c for c in cols if c in df.columns]
        
        return df[final_cols].sort_values(by='DY (12M) Media', ascending=False).head(20)
    except Exception as e:
        return pd.DataFrame([{"Erro": f"Falha no CSV: {str(e)}"}] )

# --- MODO 2: AUTOMÁTICO 360 (AGORA COM SCORE E VALUATION) ---
def scanner_auto_yahoo():
    # Importação tardia para evitar ciclo, mas usando o motor principal
    try:
        from motor import MotorAnalise
    except ImportError:
        return pd.DataFrame([{"Erro": "Arquivo motor.py não encontrado para realizar análise 360."}])

    motor = MotorAnalise()
    
    # Lista Selecionada (Liquidez + Relevância)
    tickers_alvo = [
        "MXRF11.SA", "HGLG11.SA", "XPML11.SA", "KNCR11.SA", "KNRI11.SA", 
        "VISC11.SA", "HGBS11.SA", "CPTS11.SA", "HGRU11.SA", "BTLG11.SA",
        "RECR11.SA", "IRDM11.SA", "ALZR11.SA", "JSRE11.SA", "VILG11.SA",
        "TRXF11.SA", "HGRE11.SA", "XPLG11.SA", "MALL11.SA", "BRCO11.SA",
        "LVBI11.SA", "PVBI11.SA", "RBRR11.SA", "TGAR11.SA", "KNSC11.SA",
        "GGRC11.SA", "VGHF11.SA", "VGIR11.SA", "CVBI11.SA", "RBRF11.SA"
    ]
    
    resultados = []
    
    # Baixa dados em lote para ser rápido (apenas o histórico curto necessário)
    try:
        # Precisamos de histórico suficiente para calcular indicadores técnicos
        print("Iniciando varredura 360...")
        
        for t in tickers_alvo:
            try:
                # Instancia Ticker individualmente para pegar infos detalhadas
                obj = yf.Ticker(t)
                hist = obj.history(period="2y") # Necessário para o MotorAnalise funcionar full
                info = obj.info
                
                # RODA O MOTOR COMPLETO NO ATIVO
                analise = motor.analisar(hist, info, t)
                
                if analise:
                    # Filtro Básico de Qualidade para não poluir a tela
                    # Só mostra se tiver liquidez mínima e não estiver "quebrado"
                    if analise['liq_media'] > 300000:
                        
                        # Calcula Desconto em relação ao Preço Justo IA
                        p_justo = analise['preco_justo']
                        p_atual = analise['preco']
                        desconto = 0.0
                        if p_justo > 0:
                            desconto = ((p_justo - p_atual) / p_justo) * 100
                        
                        resultados.append({
                            "Ticker": t.replace(".SA", ""),
                            "Setor": motor.identificar_setor(info, t).replace("FIIs-", ""),
                            "Preço": p_atual,
                            "Valor Justo": p_justo,
                            "Desconto (%)": desconto,
                            "Score IA": analise['score_ia'],
                            "Decisão": analise['decisao_ia'].replace("🟢 ", "").replace("🔴 ", ""),
                            "DY Anual": analise['dy_anual'],
                            "P/VP": analise.get('pvp', 0.0),
                            "Tendência": analise['sinal_tecnico']
                        })
            except Exception as e:
                # Pula ativo se der erro, não para o scanner
                continue
                
        df = pd.DataFrame(resultados)
        
        if not df.empty:
            # Ordena pelos Melhores Scores primeiro
            df = df.sort_values(by=["Score IA", "DY Anual"], ascending=[False, False])
            
        return df

    except Exception as e:
        return pd.DataFrame([{"Erro Crítico": f"Falha na varredura: {str(e)}" }])