import pandas as pd

def calcular_darf(df_vendas):
    """
    Calcula o imposto devido (DARF) baseado nas regras da B3:
    - FIIs: 20% sobre o lucro (sem isenção).
    - Ações (Swing Trade): 15% sobre o lucro (isento se vendas totais < R$ 20k).
    """
    if df_vendas.empty:
        return {"darf": 0.0, "detalhes": "Sem vendas registradas.", "memoria": pd.DataFrame()}

    # Separação por Tipo
    df = df_vendas.copy()
    
    # Identifica se é FII ou Ação pela terminação ou lista conhecida (simplificação robusta)
    def identificar_tipo(ticker):
        if "11" in ticker: return "FII" # Maioria dos FIIs termina em 11 (Generalização segura p/ MVP)
        return "ACAO"

    df["Tipo"] = df["Ticker"].apply(identificar_tipo)
    df["Valor_Venda"] = df["Qtd"] * df["Preço Venda"]
    df["Custo_Aquisicao"] = df["Qtd"] * df["PM"]
    df["Lucro"] = df["Valor_Venda"] - df["Custo_Aquisicao"]

    # 1. Cálculo FIIs
    vendas_fii = df[df["Tipo"] == "FII"]
    lucro_fii = vendas_fii["Lucro"].sum()
    imposto_fii = max(0, lucro_fii * 0.20) if lucro_fii > 0 else 0

    # 2. Cálculo Ações
    vendas_acao = df[df["Tipo"] == "ACAO"]
    total_venda_acao = vendas_acao["Valor_Venda"].sum()
    lucro_acao = vendas_acao["Lucro"].sum()
    
    # Regra de Isenção 20k
    if total_venda_acao < 20000 and lucro_acao > 0:
        imposto_acao = 0
        msg_acao = "ISENTO (< 20k)"
    else:
        imposto_acao = max(0, lucro_acao * 0.15) if lucro_acao > 0 else 0
        msg_acao = "TRIBUTADO (15%)"

    darf_total = imposto_fii + imposto_acao

    resumo = pd.DataFrame([
        {"Categoria": "FIIs", "Total Venda": vendas_fii["Valor_Venda"].sum(), "Lucro Líquido": lucro_fii, "Imposto": imposto_fii, "Status": "20% Flat"},
        {"Categoria": "Ações", "Total Venda": total_venda_acao, "Lucro Líquido": lucro_acao, "Imposto": imposto_acao, "Status": msg_acao}
    ])

    return {
        "darf": darf_total,
        "detalhes": f"Total a Pagar: R$ {darf_total:.2f}",
        "memoria": resumo
    }