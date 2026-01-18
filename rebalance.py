import pandas as pd
import numpy as np

def rebalancear_e_aportar(df, aporte_total):
    """
    df precisa ter as colunas: 'Ticker', 'Score', 'Valor_Atual'
    Retorna um DataFrame com as sugestões de aporte.
    """
    if df.empty or aporte_total <= 0:
        return pd.DataFrame()

    df = df.copy()

    # Evita divisão por zero se a soma dos scores for 0
    total_score = df["Score"].sum()
    if total_score == 0:
        df["Peso_Score"] = 1.0 / len(df)
    else:
        df["Peso_Score"] = df["Score"] / total_score

    # Penalizações e Bonificações (Ajuste Fino)
    # Reduz peso de ativos com score baixo
    df.loc[df["Score"] < 50, "Peso_Score"] *= 0.5
    # Aumenta peso de ativos com score alto
    df.loc[df["Score"] >= 80, "Peso_Score"] *= 1.2

    # Normalização dos pesos para somarem 1 (100%)
    df["Peso_Final"] = df["Peso_Score"] / df["Peso_Score"].sum()

    # Cálculo do Aporte em R$
    # A lógica aqui distribui o aporte novo proporcionalmente ao peso ideal calculado
    # Uma abordagem mais sofisticada consideraria o rebalanceamento para atingir o peso ideal
    # considerando o valor atual, mas esta versão foca na alocação do fluxo novo.
    
    # Vamos implementar a lógica que considera o patrimônio total alvo para ser mais preciso
    patrimonio_atual_total = df["Valor_Atual"].sum()
    patrimonio_futuro = patrimonio_atual_total + aporte_total
    
    df["Valor_Ideal"] = patrimonio_futuro * df["Peso_Final"]
    df["Diferenca"] = df["Valor_Ideal"] - df["Valor_Atual"]
    
    # Se a diferença for positiva, sugere aporte. Se negativa, seria venda (mas focamos em aporte aqui)
    # Para simplificar e garantir que o aporte total seja usado, vamos distribuir
    # proporcionalmente aos que estão abaixo do ideal.
    
    ativos_para_aporte = df[df["Diferenca"] > 0].copy()
    if not ativos_para_aporte.empty:
        total_dif_positiva = ativos_para_aporte["Diferenca"].sum()
        df["Aporte_Sugerido"] = np.where(
            df["Diferenca"] > 0, 
            (df["Diferenca"] / total_dif_positiva) * aporte_total, 
            0.0
        )
    else:
        # Se nenhum precisa de aporte tecnicamente (todos acima do ideal relativo? Raro no aporte),
        # distribui pelo peso final direto.
        df["Aporte_Sugerido"] = df["Peso_Final"] * aporte_total

    return df[["Ticker", "Score", "Peso_Final", "Valor_Atual", "Aporte_Sugerido"]].sort_values("Aporte_Sugerido", ascending=False)