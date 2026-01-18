import pandas as pd

def rebalancear_e_aportar(df, aporte_total, metas_setores=None):
    """
    df: DataFrame com colunas [Ticker, Preço, Qtd, Valor_Atual, Score, Setor]
    aporte_total: Valor em R$ para aportar
    metas_setores: Dict com {Setor: %_Alvo} ex: {'Ações': 40, 'Exterior': 20...}
    """
    df = df.copy()
    
    # 1. Prepara colunas básicas
    if "Aporte Sugerido (R$)" not in df.columns:
        df["Aporte Sugerido (R$)"] = 0.0
    
    patrimonio_atual = df["Valor_Atual"].sum()
    patrimonio_final = patrimonio_atual + aporte_total
    
    # Se não tiver metas definidas, usa a lógica antiga (Score Puro)
    if not metas_setores:
        df["Peso_Score"] = df["Score"] / df["Score"].sum()
        df["Alocacao_Ideal"] = patrimonio_final * df["Peso_Score"]
        df["Diferenca"] = df["Alocacao_Ideal"] - df["Valor_Atual"]
        
        saldo_restante = aporte_total
        df = df.sort_values(by="Diferenca", ascending=False)
        
        for idx, row in df.iterrows():
            if saldo_restante <= 0: break
            if row["Diferenca"] > 0:
                compra = min(row["Diferenca"], saldo_restante)
                df.at[idx, "Aporte Sugerido (R$)"] = compra
                saldo_restante -= compra
                
        return df

    # 2. Lógica Setorial (Nova)
    # Calcula quanto $$ deveria ter em cada setor
    distribuicao_setor = {}
    for setor, pct in metas_setores.items():
        alvo_reais = patrimonio_final * (pct / 100)
        atual_reais = df[df["Setor"] == setor]["Valor_Atual"].sum()
        falta = alvo_reais - atual_reais
        distribuicao_setor[setor] = max(0, falta) # Só considera se precisa comprar

    # Normaliza para caber no aporte
    total_necessario = sum(distribuicao_setor.values())
    if total_necessario == 0: total_necessario = 1 # Evita div zero

    # Distribui o aporte entre os SETORES primeiro
    for setor, falta in distribuicao_setor.items():
        # Quanto deste aporte vai para este setor?
        grana_setor = (falta / total_necessario) * aporte_total
        
        if grana_setor > 0:
            # Agora distribui DENTRO do setor baseado no Score IA
            ativos_setor = df[df["Setor"] == setor].copy()
            if not ativos_setor.empty:
                total_score = ativos_setor["Score"].sum()
                if total_score > 0:
                    for idx, row in ativos_setor.iterrows():
                        peso = row["Score"] / total_score
                        valor_compra = grana_setor * peso
                        df.at[idx, "Aporte Sugerido (R$)"] += valor_compra

    return df