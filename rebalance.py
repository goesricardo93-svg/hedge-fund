import pandas as pd

def rebalancear_e_aportar(df, aporte_total, metas_setores):
    df = df.copy()
    if "Aporte Sugerido (R$)" not in df.columns: df["Aporte Sugerido (R$)"] = 0.0
    
    patrimonio_atual = df["Valor_Atual"].sum()
    patrimonio_estimado = patrimonio_atual + aporte_total
    
    deficit_setor = {}
    for setor, pct in metas_setores.items():
        alvo = patrimonio_estimado * (pct / 100)
        atual = df[df["Setor"] == setor]["Valor_Atual"].sum()
        deficit_setor[setor] = max(0, alvo - atual)
    
    total_deficit = sum(deficit_setor.values())
    
    if total_deficit == 0:
        if df["Score"].sum() > 0:
            df["Aporte Sugerido (R$)"] = (df["Score"] / df["Score"].sum()) * aporte_total
        return df

    for setor, falta in deficit_setor.items():
        if falta > 0:
            verba = aporte_total * (falta / total_deficit)
            ativos = df[df["Setor"] == setor]
            if not ativos.empty:
                t_score = ativos["Score"].sum()
                if t_score > 0:
                    for i, r in ativos.iterrows():
                        df.at[i, "Aporte Sugerido (R$)"] = verba * (r["Score"] / t_score)
                else:
                    for i in ativos.index:
                        df.at[i, "Aporte Sugerido (R$)"] = verba / len(ativos)
    return df