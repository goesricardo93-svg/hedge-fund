import pandas as pd

def processar_ranking_acoes(motor, lista_tickers, cache_func):
    """Gera ranking usando o motor e cache do app."""
    dados = []
    for t in lista_tickers:
        # Aqui usamos uma função de callback para pegar dados cacheados do app.py
        # Se não for possível, teria que chamar yfinance aqui, o que seria lento sem cache.
        # Vamos assumir que o app.py passará os dados já processados ou faremos download aqui.
        pass 
    return pd.DataFrame()

def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=";", encoding="latin-1")
        
        cols = ["DY", "P/VP", "VACÂNCIA FISICA", "LIQUIDEZ MEDIA DIARIA"]
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace("%","").str.replace(".","").str.replace(",","."), errors='coerce')

        # Score IA para FIIs
        df["Score"] = 0
        df.loc[df["DY"] > 8, "Score"] += 30
        df.loc[(df["P/VP"] > 0.8) & (df["P/VP"] < 1.05), "Score"] += 30
        df.loc[df["VACÂNCIA FISICA"] < 5, "Score"] += 20
        df.loc[df["LIQUIDEZ MEDIA DIARIA"] > 1000000, "Score"] += 20
        
        df = df.sort_values("Score", ascending=False)
        return df
    except:
        return pd.DataFrame()