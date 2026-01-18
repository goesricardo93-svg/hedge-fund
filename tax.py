import pandas as pd
import yfinance as yf

def calcular_darf(df_carteira):
    if df_carteira.empty: return pd.DataFrame([{"Status": "Carteira Vazia"}])
    df = df_carteira.copy()
    
    # Baixa preço atual se não tiver
    if "Valor_Atual" not in df.columns:
        try:
            tickers = df["Ticker"].tolist()
            data = yf.download(tickers, period="1d", progress=False)['Close'].iloc[-1]
            def get_p(t): 
                try: return float(data[t]) if isinstance(data, pd.Series) else float(data)
                except: return 0.0
            df["Preço Venda"] = df["Ticker"].apply(get_p)
        except: return pd.DataFrame([{"Erro": "Falha cotação online"}])
    else:
        df["Preço Venda"] = df["Valor_Atual"] / df["Qtd"]

    df["Total Venda"] = df["Qtd"] * df["Preço Venda"]
    df["Lucro"] = df["Total Venda"] - (df["Qtd"] * df["PM"])

    def get_aliquota(row):
        t = row["Ticker"].upper()
        # FIIs = 20%
        if "11" in t and not any(x in t for x in ["IVVB", "BOVA", "XINA", "BDR"]): return 0.20
        return 0.15 # Ações e ETFs de Ações

    df["Aliq"] = df.apply(get_aliquota, axis=1)
    
    # Resumo
    res = []
    # FIIs
    fiis = df[df["Aliq"] == 0.20]
    lucro_fii = fiis["Lucro"].sum()
    res.append({"Tipo": "FIIs (20%)", "Lucro": f"R$ {lucro_fii:.2f}", "Imposto": f"R$ {max(0, lucro_fii*0.2):.2f}"})
    
    # Ações
    acoes = df[df["Aliq"] == 0.15]
    lucro_acao = acoes["Lucro"].sum()
    venda_acao = acoes["Total Venda"].sum()
    imposto_acao = 0.0
    obs = "Tributado"
    
    if lucro_acao > 0:
        if venda_acao < 20000 and "IVVB" not in str(acoes["Ticker"].values): 
            obs = "Isento (<20k)"
        else: 
            imposto_acao = lucro_acao * 0.15
            
    res.append({"Tipo": f"Ações/ETF (15%) - {obs}", "Lucro": f"R$ {lucro_acao:.2f}", "Imposto": f"R$ {imposto_acao:.2f}"})
    
    return pd.DataFrame(res)