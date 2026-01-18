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
        col_seg = mapa.get("SEGMENTO")

        if not (col_dy and col_pvp and col_ticker): return pd.DataFrame()

        df["DY_N"] = df[col_dy].apply(limpar_numero)
        df["PVP_N"] = df[col_pvp].apply(limpar_numero)
        df["VAC_N"] = df[col_vac].apply(limpar_numero) if col_vac else 0
        df["LIQ_N"] = df[col_liq].apply(limpar_numero) if col_liq else 0
        
        # Lógica "Análise 360"
        def analise_360_fii(row):
            p_vp = row["PVP_N"]
            vac = row["VAC_N"]
            seg = str(row[col_seg]).upper() if col_seg else ""
            
            if "PAPEL" in seg or "RECEB" in seg:
                if 0.90 <= p_vp <= 1.02: return "🔥 COMPRA (Papel)"
                return "⚪ OBSERVAR"
            
            if vac < 10 and p_vp < 0.95: return "🏢 OPORTUNIDADE (Tijolo)"
            if vac > 15: return "🔴 CUIDADO (Vacância)"
            
            if 0.85 <= p_vp <= 1.0: return "✅ VALOR JUSTO"
            return "⚪ NEUTRO"

        df["Veredito 360"] = df.apply(analise_360_fii, axis=1)

        def calc_score(row):
            s = 50
            if row["DY_N"] > 9: s += 20
            elif row["DY_N"] > 6: s += 10
            
            if 0.85 <= row["PVP_N"] <= 1.0: s += 20
            if row["LIQ_N"] > 1000000: s += 10
            
            if row["VAC_N"] > 10: s -= 20
            if row["PVP_N"] > 1.15: s -= 15
            
            return min(100, max(0, s))

        df["Score"] = df.apply(calc_score, axis=1)
        
        cols_final = [col_ticker, col_preco, col_dy, col_pvp, "Score", "Veredito 360"]
        if col_vac: cols_final.append(col_vac)
        
        return df[cols_final].sort_values("Score", ascending=False)
            
    except:
        return pd.DataFrame()