import pandas as pd

def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=";", encoding="latin-1")
        
        def limpar_numero(x):
            if isinstance(x, str):
                x = x.replace('%', '').replace('.', '').replace(',', '.')
                try: return float(x)
                except: return 0.0
            return x

        mapa = {c.upper().strip(): c for c in df.columns}
        
        col_dy = mapa.get("DY") or mapa.get("DIVIDEND YIELD")
        col_pvp = mapa.get("P/VP")
        col_vac = mapa.get("VACANCIA FISICA") or mapa.get("VACÂNCIA FÍSICA")
        col_liq = mapa.get("LIQUIDEZ MEDIA DIARIA")
        col_ticker = mapa.get("TICKER") or mapa.get("ATIVO")
        col_preco = mapa.get("PRECO") or mapa.get("PREÇO") or mapa.get("COTACAO")
        col_seg = mapa.get("SEGMENTO") or mapa.get("SETOR")

        if not (col_dy and col_pvp and col_ticker): return pd.DataFrame()

        df["DY_N"] = df[col_dy].apply(limpar_numero)
        df["PVP_N"] = df[col_pvp].apply(limpar_numero)
        df["VAC_N"] = df[col_vac].apply(limpar_numero) if col_vac else 0
        df["LIQ_N"] = df[col_liq].apply(limpar_numero) if col_liq else 0
        df["SEGMENTO_N"] = df[col_seg].astype(str).str.upper().fillna("OUTROS") if col_seg else "OUTROS"

        # --- CLASSIFICAÇÃO INTELIGENTE ---
        def classificar_segmento(s):
            if any(x in s for x in ["PAPEL", "RECEB", "CRI", "CRA", "TÍTULO", "TITULO", "VAL. MOB", "FINANCEIRO"]): return "PAPEL"
            if any(x in s for x in ["TIJOLO", "LAJE", "LOG", "SHOP", "VAR", "HIBRIDO", "HÍBRIDO", "INDUSTRIAL", "EDUCACIONAL", "HOSPITAL"]): return "TIJOLO"
            if any(x in s for x in ["AGRO", "RURAL", "TERRA", "FIAGRO"]): return "AGRO"
            return "OUTROS"

        df["CATEGORIA"] = df["SEGMENTO_N"].apply(classificar_segmento)

        # --- SCORE RIGOROSO (Evita notas 100 excessivas) ---
        def analisar_fii(row):
            score = 50 
            motivos = []
            
            # DY
            if row["DY_N"] > 14: score += 5; motivos.append("DY Explosivo (Risco?)")
            elif row["DY_N"] > 9: score += 20; motivos.append("DY Alto")
            elif row["DY_N"] < 6: score -= 15; motivos.append("DY Baixo")

            # P/VP
            if 0.85 <= row["PVP_N"] <= 1.05: score += 20; motivos.append("Preço Justo")
            elif row["PVP_N"] < 0.80: score += 15; motivos.append("Desconto Patrimonial") 
            elif row["PVP_N"] > 1.15: score -= 20; motivos.append("Caro (Ágio)")

            # Vacância (Só penaliza tijolo)
            if row["CATEGORIA"] == "TIJOLO":
                if row["VAC_N"] > 15: score -= 30; motivos.append("Vacância Alta")
                elif row["VAC_N"] < 5: score += 10; motivos.append("Ocupação Alta")

            # Liquidez
            if row["LIQ_N"] < 200000: score -= 10; motivos.append("Baixa Liquidez")
            
            score = min(100, max(0, score))
            
            if score >= 75: veredito = "🔥 COMPRA FORTE"
            elif score >= 60: veredito = "🟢 COMPRA"
            elif score <= 40: veredito = "🔴 EVITAR"
            else: veredito = "⚪ MANTER"

            return pd.Series([score, ", ".join(motivos), veredito])

        df[["Score", "Motivos (IA)", "Veredito"]] = df.apply(analisar_fii, axis=1)
        
        cols_final = [col_ticker, "CATEGORIA", col_preco, col_dy, col_pvp, "Score", "Veredito", "Motivos (IA)"]
        if col_vac: cols_final.append(col_vac)
        
        return df[cols_final].sort_values("Score", ascending=False)
            
    except:
        return pd.DataFrame()