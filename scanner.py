import pandas as pd
import yfinance as yf
from motor import MotorAnalise
import streamlit as st

# Lista de Ativos Líquidos para Monitorar (IBOV + SMLL)
TICKERS_ACOES = [
    "VALE3.SA", "PETR4.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA", "PETR3.SA", "ELET3.SA", "RENT3.SA",
    "WEGE3.SA", "ABEV3.SA", "SUZB3.SA", "BPAC11.SA", "EQTL3.SA", "PRIO3.SA", "RADL3.SA", "RDOR3.SA",
    "JBSS3.SA", "LREN3.SA", "GGBR4.SA", "RAIL3.SA", "VIVT3.SA", "ENEV3.SA", "BBSE3.SA", "HYPE3.SA",
    "CMIG4.SA", "SBSP3.SA", "CPLE6.SA", "CSAN3.SA", "UGPA3.SA", "TIMS3.SA", "TOTS3.SA", "EMBR3.SA",
    "VIBRA3.SA", "CCRO3.SA", "EGIE3.SA", "CSNA3.SA", "BRFS3.SA", "MULT3.SA", "GOAU4.SA", "TAEE11.SA",
    "KLBN11.SA", "ALOS3.SA", "FLRY3.SA", "EZTC3.SA", "MRVE3.SA", "CVCB3.SA", "GOLL4.SA", "AZUL4.SA",
    "MGLU3.SA", "VIIA3.SA", "POSI3.SA", "INTB3.SA", "TRPL4.SA", "SAPR11.SA", "SANB11.SA", "CXSE3.SA",
    "PSSA3.SA", "IRBR3.SA", "SLCE3.SA", "SMTO3.SA", "ARZZ3.SA", "SOMA3.SA", "PETZ3.SA"
]

TICKERS_FIIS = [
    "MXRF11.SA", "HGLG11.SA", "XPML11.SA", "KNRI11.SA", "KNCR11.SA", "HGRU11.SA", "IRDM11.SA", "XPLG11.SA",
    "VISC11.SA", "BRCO11.SA", "BTLG11.SA", "CPTS11.SA", "HGBS11.SA", "MALL11.SA", "VILG11.SA", "LVBI11.SA",
    "TGAR11.SA", "KNSC11.SA", "JSRE11.SA", "HGRE11.SA", "RZTR11.SA", "RBRR11.SA", "HECT11.SA", "DEVA11.SA",
    "RECR11.SA", "URPR11.SA", "TRXF11.SA", "ALZR11.SA", "GGRC11.SA", "HABT11.SA", "CVBI11.SA", "VGIR11.SA"
]

def formatar_ticker(t):
    return t if t.endswith(".SA") else f"{t}.SA"

def executar_scanner(tipo="ACOES"):
    motor = MotorAnalise()
    lista = TICKERS_ACOES if tipo == "ACOES" else TICKERS_FIIS
    
    resultados = []
    total = len(lista)
    
    # Barra de progresso na interface
    bar = st.progress(0, text=f"Escaneando {tipo}...")
    
    # Download em lote para ser rápido (Batch Download)
    try:
        dados_batch = yf.download(lista, period="2y", progress=False)
        # Se o download falhar ou vier vazio
        if dados_batch.empty:
            st.error("Erro de conexão com Yahoo Finance.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro no download em lote: {e}")
        return pd.DataFrame()

    for i, ticker in enumerate(lista):
        try:
            # Extrai dados do lote para não chamar API toda hora
            hist = pd.DataFrame()
            if isinstance(dados_batch.columns, pd.MultiIndex):
                # Estrutura complexa do yfinance novo
                try:
                    hist['Close'] = dados_batch['Close'][ticker]
                    hist['Volume'] = dados_batch['Volume'][ticker]
                    # Limpa NaNs
                    hist = hist.dropna()
                except:
                    continue
            else:
                # Fallback
                continue
            
            # Pega Info básica (aqui infelizmente precisa chamar API 1 a 1 para pegar fundamentos)
            # Para otimizar, podemos pular info se o gráfico estiver muito feio, mas vamos pegar tudo por enquanto.
            try:
                info = yf.Ticker(ticker).info
            except:
                info = {}

            analise = motor.analisar(hist, info, ticker)
            
            if analise:
                # Filtro Básico: Só mostra o que tiver Score acima de 50 para não poluir
                if analise['score_ia'] >= 50:
                    resultados.append({
                        "Ticker": ticker.replace(".SA", ""),
                        "Score": analise['score_ia'],
                        "Preço": analise['preco'],
                        "Preço Justo": analise['preco_justo'],
                        "Potencial (%)": ((analise['preco_justo'] / analise['preco']) - 1) * 100 if analise['preco'] > 0 else 0,
                        "Tendência": analise['sinal_tecnico'],
                        "Decisão": analise['decisao_ia'],
                        "Motivos": analise['motivos']
                    })
        except Exception as e:
            # Pula ativo com erro silenciosamente
            pass
            
        bar.progress((i + 1) / total)

    bar.empty()
    
    df = pd.DataFrame(resultados)
    if not df.empty:
        # Ordena pelos melhores Scores
        df = df.sort_values(by="Score", ascending=False)
    
    return df