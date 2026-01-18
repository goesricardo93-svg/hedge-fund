import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import requests
import smtplib
from email.mime.text import MIMEText

# ======================================================
# 1. CONFIGURAÇÕES & SEGREDOS
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 17.0", layout="wide")

try:
    TELEGRAM_TOKEN = st.secrets["telegram"]["token"]
    TELEGRAM_CHAT_ID = st.secrets["telegram"]["chat_id"]
    EMAIL_USER = st.secrets["email"]["user"]
    EMAIL_PASS = st.secrets["email"]["password"]
except:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    EMAIL_USER = ""
    EMAIL_PASS = ""

# ======================================================
# 2. MOTOR DE ANÁLISE (CÉREBRO)
# ======================================================
class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # DADOS
            fechamento = hist["Close"]
            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            preco_atual = float(fechamento.iloc[-1])
            
            # TÉCNICA
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            topo = fechamento.cummax()
            drawdown = ((fechamento - topo) / topo).min() * 100

            window = 60 
            suporte = float(fechamento.tail(window).min())
            resistencia = float(fechamento.tail(window).max())
            stop_loss = suporte * 0.97
            stop_gain = resistencia * 1.02

            # FUNDAMENTOS
            dy = info.get("dividendYield", 0) or 0
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            # Preços Justos
            dpa = preco_atual * dy
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin # Proxy

            # SCORE IA
            score = 50
            motivos = []

            if p_bazin > 0 and preco_atual < p_bazin: score += 20; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 20; motivos.append("Desconto Graham")
            if dy > 0.06: score += 10; motivos.append("Dividendos > 6%")

            if rsi < 30: score += 20; motivos.append("RSI Sobrevendido")
            elif rsi > 70: score -= 20; motivos.append("RSI Sobrecomprado")
            
            score = min(100, max(0, score))

            if score >= 75: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score <= 30: decisao = "🔴 VENDA"
            else: decisao = "⚪ MANTER"

            return {
                "preco": preco_atual,
                "rsi": rsi,
                "volatilidade": volatilidade,
                "drawdown": drawdown,
                "p_bazin": p_bazin,
                "p_graham": p_graham,
                "p_gordon": p_gordon,
                "dy": dy,
                "suporte": suporte,
                "resistencia": resistencia,
                "stop_loss": stop_loss,
                "stop_gain": stop_gain,
                "score_ia": score,
                "decisao_ia": decisao,
                "motivos": ", ".join(motivos),
                "pl": info.get("trailingPE", 0) or 0,
                "pvp": info.get("priceToBook", 0) or 0,
                "roe": info.get("returnOnEquity", 0) or 0,
                "margem": info.get("profitMargins", 0) or 0,
                "divida_ebitda": info.get("debtToEbitda", 0) or 0
            }
        except Exception:
            return None

    def monte_carlo(self, patrimonio_atual, aporte_mensal, anos=10, sims=1000):
        meses = anos * 12
        resultados = []
        mu, sigma = 0.008, 0.05
        for _ in range(sims):
            pat = patrimonio_atual
            for _ in range(meses):
                pat = pat * (1 + np.random.normal(mu, sigma)) + aporte_mensal
            resultados.append(pat)
        return np.array(resultados)

# ======================================================
# 3. FUNÇÕES DE SUPORTE
# ======================================================
def disparar_alerta(titulo, corpo):
    if not TELEGRAM_TOKEN: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 *{titulo}*\n\n{corpo}", "parse_mode": "Markdown"}
        )
    except: pass

# --- FUNÇÃO RENOMEADA E PADRONIZADA ---
@st.cache_data(ttl=3600)
def obter_dados_final(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None
        motor = MotorAnalise()
        return motor.analisar(hist, t.info, ticker)
    except: return None

def get_rsi_status(val):
    if val < 30: return f"🟢 SOBREVENDA ({val:.0f})"
    if val > 70: return f"🔴 SOBRECOMPRA ({val:.0f})"
    return f"⚪ NEUTRO ({val:.0f})"

# === SCANNER FII INTEIGENTE ===
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
            
    except Exception as e:
        st.error(f"Erro no Scanner: {e}")
        return pd.DataFrame()

# ======================================================
# 4. SESSION STATE (SUA CARTEIRA OFICIAL)
# ======================================================
if "carteira_acoes" not in st.session_state:
    dados = [
        ["ALZR11.SA", 100, 10.81], ["BBAS3.SA", 1703, 24.48], ["BBSE3.SA", 55, 35.64],
        ["BTCI11.SA", 502, 10.16], ["BTLG11.SA", 60, 98.50], ["CCME11.SA", 152, 8.55],
        ["CMIG4.SA", 1644, 11.12], ["CPLE3.SA", 617, 9.64], ["CPSH11.SA", 169, 10.10],
        ["CPTS11.SA", 276, 8.52], ["CXSE3.SA", 800, 14.20], ["EQTL3.SA", 200, 30.21],
        ["HGCR11.SA", 20, 95.81], ["HGLG11.SA", 20, 158.03], ["ITSA4.SA", 1174, 9.63],
        ["IVVB11.SA", 6, 366.97], ["KLBN4.SA", 2323, 3.63], ["KNCR11.SA", 27, 103.11],
        ["KNHF11.SA", 15, 93.23], ["KNRI11.SA", 30, 152.49], ["KNSC11.SA", 373, 8.78],
        ["KNUQ11.SA", 16, 102.45], ["PETR4.SA", 900, 32.07], ["SAPR11.SA", 300, 37.97],
        ["TAEE4.SA", 1000, 11.36], ["VALE3.SA", 152, 54.79], ["VGIR11.SA", 296, 9.58],
        ["VISC11.SA", 16, 109.70], ["XPCA11.SA", 110, 8.77], ["XPLG11.SA", 26, 102.31],
        ["XPML11.SA", 10, 106.05]
    ]
    st.session_state.carteira_acoes = pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# 5. INTERFACE
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")
ticker_input = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3.SA").upper()

if st.sidebar.button("🔄 Restaurar Carteira Padrão"):
    dados = [
        ["ALZR11.SA", 100, 10.81], ["BBAS3.SA", 1703, 24.48], ["BBSE3.SA", 55, 35.64],
        ["BTCI11.SA", 502, 10.16], ["BTLG11.SA", 60, 98.50], ["CCME11.SA", 152, 8.55],
        ["CMIG4.SA", 1644, 11.12], ["CPLE3.SA", 617, 9.64], ["CPSH11.SA", 169, 10.10],
        ["CPTS11.SA", 276, 8.52], ["CXSE3.SA", 800, 14.20], ["EQTL3.SA", 200, 30.21],
        ["HGCR11.SA", 20, 95.81], ["HGLG11.SA", 20, 158.03], ["ITSA4.SA", 1174, 9.63],
        ["IVVB11.SA", 6, 366.97], ["KLBN4.SA", 2323, 3.63], ["KNCR11.SA", 27, 103.11],
        ["KNHF11.SA", 15, 93.23], ["KNRI11.SA", 30, 152.49], ["KNSC11.SA", 373, 8.78],
        ["KNUQ11.SA", 16, 102.45], ["PETR4.SA", 900, 32.07], ["SAPR11.SA", 300, 37.97],
        ["TAEE4.SA", 1000, 11.36], ["VALE3.SA", 152, 54.79], ["VGIR11.SA", 296, 9.58],
        ["VISC11.SA", 16, 109.70], ["XPCA11.SA", 110, 8.77], ["XPLG11.SA", 26, 102.31],
        ["XPML11.SA", 10, 106.05]
    ]
    st.session_state.carteira_acoes = pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM"])
    st.rerun()

tabs = st.tabs(["🔎 Análise Técnica", "💼 Carteira Geral", "🏢 Scanner FIIs 360", "💰 Futuro"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    # CHAMADA CORRIGIDA AQUI:
    r = obter_dados_final(ticker_input)
    
    if r:
        col_ia1, col_ia2 = st.columns([1, 3])
        col_ia1.metric("Score IA", f"{r['score_ia']}/100")
        
        if "COMPRA" in r['decisao_ia']: col_ia2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']: col_ia2.error(f"### {r['decisao_ia']}")
        else: col_ia2.warning(f"### {r['decisao_ia']}")
        
        st.write(f"**Gatilhos:** {r['motivos']}")
        st.divider()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        c2.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        c3.metric("Drawdown Max", f"{r['drawdown']:.1f}%")
        c4.markdown(f"**{get_rsi_status(r['rsi'])}**")

        c_val, c_fund = st.columns(2)
        with c_val:
            st.subheader("📋 Valuation")
            val_data = {
                "Modelo": ["Bazin", "Graham", "Gordon"],
                "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
            }
            st.dataframe(pd.DataFrame(val_data), use_container_width=True)
        
        with c_fund:
            st.subheader("📊 Fundamentos")
            fund_data = {"Indicador": ["DY", "P/L", "P/VP", "ROE"], "Valor": [f"{r['dy']*100:.1f}%", f"{r['pl']:.1f}", f"{r['pvp']:.2f}", f"{r['roe']*100:.1f}%"]}
            st.dataframe(pd.DataFrame(fund_data), use_container_width=True)

        st.subheader("📈 Gráfico Técnico")
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                close = hist_chart["Close"]
                if isinstance(close, pd.DataFrame): close = close.iloc[:,0]
                
                # Média Móvel 50
                mm50 = close.rolling(window=50).mean()

                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=hist_chart.index, open=hist_chart["Open"].iloc[:,0] if isinstance(hist_chart["Open"], pd.DataFrame) else hist_chart["Open"],
                                            high=hist_chart["High"].iloc[:,0] if isinstance(hist_chart["High"], pd.DataFrame) else hist_chart["High"],
                                            low=hist_chart["Low"].iloc[:,0] if isinstance(hist_chart["Low"], pd.DataFrame) else hist_chart["Low"],
                                            close=close, name="Preço"))
                
                # LINHA CORRIGIDA:
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm50, name="MM50", line=dict(color='blue', width=1)))

                fig.add_hline(y=r['suporte'], line_dash="dot", line_color="green", annotation_text="SUPORTE")
                fig.add_hline(y=r['resistencia'], line_dash="dot", line_color="red", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=r['stop_loss'], line_dash="dash", line_color="red", annotation_text="STOP LOSS")
                
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e: st.error(f"Erro gráfico: {e}")

    else: st.warning("Ticker não encontrado.")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    st.subheader(f"💼 Gestão de Carteira ({len(st.session_state.carteira_acoes)} Ativos)")
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_acoes = df_ed

    if st.button("🔄 Analisar Carteira Completa"):
        res = []
        bar = st.progress(0)
        total = len(df_ed)
        for i, row in df_ed.iterrows():
            # CHAMADA CORRIGIDA AQUI TAMBÉM:
            r = obter_dados_final(row["Ticker"])
            if r:
                rec = r['decisao_ia']
                if r['preco'] < row['PM'] * 0.95 and "COMPRA" in rec: rec = "🔥 COMPRA FORTE (Abaixo PM)"
                
                res.append({
                    "Ticker": row["Ticker"],
                    "Preço": r["preco"],
                    "PM": row["PM"],
                    "Lucro": (r["preco"] - row["PM"]) * row["Qtd"],
                    "Veredito IA": rec,
                    "Score": r['score_ia'],
                    "Bazin": r["p_bazin"]
                })
            bar.progress((i+1)/total)
        
        if res:
            df_res = pd.DataFrame(res).sort_values("Score", ascending=False)
            st.dataframe(df_res.style.background_gradient(subset=["Score"], cmap="Greens").map(lambda x: "color: red" if x < 0 else "color: green", subset=["Lucro"]), use_container_width=True)

# --- ABA 3: FIIs 360 ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360º")
    st.info("Faça upload do CSV do StatusInvest. O sistema usará sua lógica de Papel vs Tijolo.")
    
    uploaded = st.file_uploader("Arraste o arquivo aqui", type=["csv"])
    if uploaded:
        df_fii = scanner_fiis_csv(uploaded)
        if not df_fii.empty:
            st.success(f"{len(df_fii)} FIIs processados!")
            st.dataframe(df_fii.head(30).style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
        else:
            st.warning("Erro ao ler CSV.")

# --- ABA 4: FUTURO ---
with tabs[3]:
    st.subheader("🔮 Simulação Patrimonial")
    if not df_ed.empty:
        patrimonio_atual = 0
        for _, row in df_ed.iterrows():
            patrimonio_atual += row['Qtd'] * row['PM']
        
        st.metric("Patrimônio Base (Custo)", f"R$ {patrimonio_atual:,.2f}")
        aporte = st.number_input("Aporte Mensal", 2000.0)
        
        if st.button("Simular 10 Anos"):
            motor = MotorAnalise()
            sims = motor.monte_carlo(patrimonio_atual, aporte, 10, 1000)
            fig = go.Figure(go.Histogram(x=sims, nbinsx=40, marker_color='green'))
            st.plotly_chart(fig, use_container_width=True)
            st.metric("Mediana Esperada", f"R$ {np.median(sims):,.2f}")