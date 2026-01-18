import pandas as pd

def rebalancear_e_aportar(df, aporte_total, metas_setores):
    """
    Distribui o aporte total para atingir as metas percentuais,
    priorizando ativos com maior Score IA dentro de cada setor.
    """
    df = df.copy()
    if "Aporte Sugerido (R$)" not in df.columns:
        df["Aporte Sugerido (R$)"] = 0.0
    
    patrimonio_atual = df["Valor_Atual"].sum()
    patrimonio_final_estimado = patrimonio_atual + aporte_total
    
    # 1. Calcula quanto cada setor DEVERIA ter no final
    alvos_reais = {}
    deficit_setor = {}
    
    for setor, pct in metas_setores.items():
        alvo = patrimonio_final_estimado * (pct / 100)
        alvos_reais[setor] = alvo
        
        # Quanto tem hoje?
        atual = df[df["Setor"] == setor]["Valor_Atual"].sum()
        
        # Quanto falta para chegar no alvo? (Deficit)
        deficit = max(0, alvo - atual)
        deficit_setor[setor] = deficit
    
    total_deficit = sum(deficit_setor.values())
    
    # 2. Distribui o aporte proporcionalmente ao "buraco" (deficit) de cada setor
    # Se o buraco for maior que o aporte, enchemos o proporcional.
    # Se for menor, a lógica garante que usamos tudo baseando no peso relativo.
    
    if total_deficit == 0: return df # Carteira já perfeita ou vazia
    
    sobra_aporte = aporte_total
    
    for setor, falta in deficit_setor.items():
        if falta > 0:
            # Regra de 3: Se faltam 10k no total de setores, e 2k nesse setor,
            # ele recebe 20% do aporte disponível.
            pct_do_aporte = falta / total_deficit
            dinheiro_para_setor = aporte_total * pct_do_aporte
            
            # Agora distribui esse dinheiro DENTRO do setor
            ativos = df[df["Setor"] == setor]
            
            if not ativos.empty:
                # Usa o Score IA para ponderar. Quem tem score maior, recebe mais.
                total_score = ativos["Score"].sum()
                
                if total_score > 0:
                    for idx, row in ativos.iterrows():
                        peso_ativo = row["Score"] / total_score
                        valor_compra = dinheiro_para_setor * peso_ativo
                        df.at[idx, "Aporte Sugerido (R$)"] = valor_compra
                else:
                    # Se ninguém tem score (tudo zero), divide igual
                    divisao_igual = dinheiro_para_setor / len(ativos)
                    for idx in ativos.index:
                        df.at[idx, "Aporte Sugerido (R$)"] = divisao_igual

    return df