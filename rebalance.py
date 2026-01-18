import pandas as pd
import numpy as np

def rebalancear_e_aportar(df_carteira, aporte_total):
    """
    Calcula o rebalanceamento inteligente.
    Retorna DataFrame com colunas garantidas: 
    ['Ticker', 'Score', 'Valor_Atual', 'Lucro', 'Veredito IA', 'Aporte Sugerido (R$)']
    """
    if df_carteira.empty:
        return pd.DataFrame()

    df = df_carteira.copy()
    
    # Garante que colunas essenciais existem, preenchendo com 0 se faltar
    if "Score" not in df.columns: df["Score"] = 50
    if "Valor_Atual" not in df.columns: df["Valor_Atual"] = 0.0
    
    # 1. Peso Ideal baseado no Score (Exponencial)
    df["Fator_Score"] = df["Score"] ** 1.5 
    
    soma_fatores = df["Fator_Score"].sum()
    if soma_fatores == 0: 
        df["Peso_Alvo_Score"] = 1.0 / len(df) # Distribuição igualitária se scores forem 0
    else:
        df["Peso_Alvo_Score"] = df["Fator_Score"] / soma_fatores
    
    # 2. Patrimônio Meta (Atual + Novo Aporte)
    patrimonio_total_futuro = df["Valor_Atual"].sum() + aporte_total
    df["Valor_Ideal"] = patrimonio_total_futuro * df["Peso_Alvo_Score"]
    
    # 3. Gap (O quanto falta pra chegar no ideal)
    df["Gap"] = df["Valor_Ideal"] - df["Valor_Atual"]
    
    # 4. Distribuição do Aporte
    gaps_positivos = df[df["Gap"] > 0]["Gap"].sum()
    
    if gaps_positivos > 0:
        # Distribui proporcionalmente ao Gap positivo
        df["Aporte Sugerido (R$)"] = np.where(df["Gap"] > 0, (df["Gap"] / gaps_positivos) * aporte_total, 0.0)
    else:
        # Fallback: Se tudo estiver acima da meta (raro), distribui pelo score
        df["Aporte Sugerido (R$)"] = df["Peso_Alvo_Score"] * aporte_total
        
    return df.sort_values("Aporte Sugerido (R$)", ascending=False)