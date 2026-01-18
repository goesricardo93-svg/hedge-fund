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
st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 11.0", layout="wide")

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
                # Campos extras para evitar KeyError
                "pl": info.get("trailingPE", 0) or 0,
                "pvp": info.get("priceToBook", 0) or 0,
                "roe": info.get("returnOnEquity", 0) or 0,
                "margem": info.get("profitMargins", 0) or 0,
                "divida_ebitda": info.get("debtToEbitda", 0) or 0
            }
        except Exception as e:
            print(f"Erro Motor ({ticker}): {e}")
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

    def stress_test(self, valor):
        cenarios = {"2008 (-50%)": -0.50, "COVID (-35%)": -0.35, "Juros Altos (-15%)": -0.15}
        dados = {}
        for nome, queda in cenarios.items():
            hist = [valor]
            v = valor * (1 + queda)
            hist.append(v)
            for _ in range(10):
                v = v * 1.005 
                hist.append(v)
            dados[nome] = hist
        return dados

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

@st.cache_data(ttl=3600)
def obter_dados_seguros_v2(ticker):
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

def sugerir_aportes(df, aporte, metas_setor):
    if df.empty: return pd.DataFrame()
    df = df.copy()
    
    df["Valor"] = df["Qtd"] * df["Cotação"]
    total = df["Valor"].sum() or 1
    df["Peso_Atual"] = df["Valor"] / total
    
    dict_metas = dict(zip(metas_setor["Setor"], metas_setor["Meta"]))
    df["Meta_Setorial"] = df["Setor"].map(dict_metas).fillna(0.05)
    qtd_por_setor = df.groupby("Setor")["Ticker"].transform("count")
    df["Peso_Alvo"] = df["Meta_Setorial"] / qtd_por_setor
    df["Gap"] = df["Peso_Alvo"] - df["Peso_Atual"]
    
    score_val = df["Score IA"] if "Score IA" in df.columns else 50
    df["Score_Alocacao"] = ((df["Gap"] * 200) + (score_val / 100)).clip(lower=0)
    
    soma = df["Score_Alocacao"].sum()
    if soma > 0: df["Aporte_Sugerido"] = (df["Score_Alocacao"] / soma) * aporte
    else: df["Aporte_Sugerido"] = 0
    return df[df["Aporte_Sugerido"] > 1].sort_values("Aporte_Sugerido", ascending=False)

def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=";", encoding="latin-1")
        
        # LIMPEZA ROBUSTA PARA CSV BRASILEIRO
        def limpar_numero(x):
            if isinstance(x, str):
                # Remove % e pontos de milhar, troca vírgula por ponto
                x = x.replace('%', '').replace('.', '').replace(',', '.')
                try: return float(x)
                except: return 0.0
            return x

        cols = ["DY", "P/VP", "VACÂNCIA FISICA", "LIQUIDEZ MEDIA DIARIA"]
        
        # Encontra as colunas ignorando maiúsculas/minúsculas
        mapa_cols = {c.upper(): c for c in df.columns}
        
        for c in cols:
            real_col = mapa_cols.get(c)
            if real_col:
                df[c] = df[real_col].apply(limpar_numero)
            else:
                df[c] = 0 # Se não achar a coluna, preenche com 0
        
        # Score FII
        df["Score"] = 0
        df.loc[df["DY"] > 8, "Score"] += 30
        df.loc[(df["P/VP"] > 0.8) & (df["P/VP"] < 1.05), "Score"] += 30
        df.loc[df["VACÂNCIA FISICA"] < 5, "Score"] += 20
        df.loc[df["LIQUIDEZ MEDIA DIARIA"] > 500000, "Score"] += 20
        
        return df.sort_values("Score", ascending=False)
    except Exception as e:
        st.error(f"Erro ao processar CSV: {e}")
        return pd.DataFrame()

# ======================================================
# 4. SESSION STATE (SUA CARTEIRA COMPLETA DE 31 ATIVOS)
# ======================================================
if "carteira_acoes" not in st.session_state:
    # Dados extraídos do seu prompt
    dados_carteira = [
        ["ALZR11.SA", 100, 10.81, "FII"], ["BBAS3.SA", 1703, 24.48, "Bancos"],
        ["BBSE3.SA", 55, 35.64, "Seguros"], ["BTCI11.SA", 502, 10.16, "FII"],
        ["BTLG11.SA", 60, 98.50, "FII"], ["CCME11.SA", 152, 8.55, "FII"],
        ["CMIG4.SA", 1644, 11.12, "Elétricas"], ["CPLE3.SA", 617, 9.64, "Elétricas"],
        ["CPSH11.SA", 169, 10.10, "FII"], ["CPTS11.SA", 276, 8.52, "FII"],
        ["CXSE3.SA", 800, 14.20, "Seguros"], ["EQTL3.SA", 200, 30.21, "Elétricas"],
        ["HGCR11.SA", 20, 95.81, "FII"], ["HGLG11.SA", 20, 158.03, "FII"],
        ["ITSA4.SA", 1174, 9.63, "Holding"], ["IVVB11.SA", 6, 366.97, "ETF Ext."],
        ["KLBN4.SA", 2323, 3.63, "Papel"], ["KNCR11.SA", 27, 103.11, "FII"],
        ["KNHF11.SA", 15, 93.23, "FII"], ["KNRI11.SA", 30, 152.49, "FII"],
        ["KNSC11.SA", 373, 8.78, "FII"], ["KNUQ11.SA", 16, 102.45, "FII"],
        ["PETR4.SA", 900, 32.07, "Petróleo"], ["SAPR11.SA", 300, 37.97, "Saneamento"],
        ["TAEE4.SA", 1000, 11.36, "Elétricas"], ["VALE3.SA", 152, 54.79, "Mineração"],
        ["VGIR11.SA", 296, 9.58, "FII"], ["VISC11.SA", 16, 109.70, "FII"],
        ["XPCA11.SA", 110, 8.77, "FII"], ["XPLG11.SA", 26, 102.31, "FII"],
        ["XPML11.SA", 10, 106.05, "FII"]
    ]
    st.session_state.carteira_acoes = pd.DataFrame(dados_carteira, columns=["Ticker", "Qtd", "PM", "Setor"])

if "metas_setor" not in st.session_state:
    st.session_state.metas_setor = pd.DataFrame([
        ["Bancos", 0.10], ["Mineração", 0.05], ["Elétricas", 0.15], 
        ["Holding", 0.05], ["FII", 0.30], ["Papel", 0.05], 
        ["Seguros", 0.10], ["Petróleo", 0.05], ["Saneamento", 0.05],
        ["ETF Ext.", 0.05], ["Outros", 0.05]
    ], columns=["Setor", "Meta"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# 5. INTERFACE (FRONTEND)
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Metas por Setor (%)")
df_metas = st.sidebar.data_editor(st.session_state.metas_setor, num_rows="dynamic", key="editor_metas_sidebar")
st.session_state.metas_setor = df_metas

st.sidebar.markdown("---")
ticker_input = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3.SA").upper()

tabs = st.tabs(["🔎 Análise Completa", "💼 Carteira & Ranking", "🏢 Scanner FIIs", "💰 Futuro (Monte Carlo)"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    r = obter_dados_seguros_v2(ticker_input)
    
    if r:
        # PAINEL IA
        col_ia1, col_ia2 = st.columns([1, 3])
        col_ia1.metric("Score IA", f"{r['score_ia']}/100")
        
        if "COMPRA" in r['decisao_ia']: col_ia2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']: col_ia2.error(f"### {r['decisao_ia']}")
        else: col_ia2.warning(f"### {r['decisao_ia']}")
        
        st.write(f"**Gatilhos:** {r['motivos']}")
        st.divider()

        # MÉTRICAS
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        c2.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        c3.metric("Drawdown Max", f"{r['drawdown']:.1f}%", delta_color="inverse")
        c4.markdown(f"**{get_rsi_status(r['rsi'])}**")

        # TABELAS
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

        # GRÁFICO
        st.subheader("📈 Análise Gráfica")
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                close_data = hist_chart["Close"]
                if isinstance(close_data, pd.DataFrame): close_data = close_data.iloc[:,0]

                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=hist_chart.index, open=hist_chart["Open"] if "Open" in hist_chart else hist_chart.iloc[:,0],
                    high=hist_chart["High"] if "High" in hist_chart else hist_chart.iloc[:,1],
                    low=hist_chart["Low"] if "Low" in hist_chart else hist_chart.iloc[:,2],
                    close=close_data, name="Preço"))
                
                # Médias
                mm50 = close_data.rolling(50).mean()
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm50, name="MM50", line=dict(color='blue')))
                
                # Linhas
                fig.add_hline(y=r['suporte'], line_dash="dot", line_color="green", annotation_text="SUPORTE")
                fig.add_hline(y=r['resistencia'], line_dash="dot", line_color="red", annotation_text="RESISTÊNCIA")
                fig.add_hline(y=r['stop_loss'], line_dash="dash", line_color="red", annotation_text="STOP LOSS")
                fig.add_hline(y=r['stop_gain'], line_dash="dash", line_color="gold", annotation_text="ALVO")

                fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
                
                st.info(f"**Setup:** Suporte {r['suporte']:.2f} | Resist {r['resistencia']:.2f} | Stop {r['stop_loss']:.2f} | Alvo {r['stop_gain']:.2f}")

        except Exception as e: st.error(f"Erro gráfico: {e}")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    st.subheader("🏆 Ranking & Carteira")
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_acoes = df_ed

    if st.button("🔄 Analisar Carteira"):
        res = []
        bar = st.progress(0)
        total = len(df_ed)
        for i, row in df_ed.iterrows():
            r_rank = obter_dados_seguros_v2(row["Ticker"])
            if r_rank:
                if r_rank['score_ia'] >= 80 and row["Ticker"] not in st.session_state.alertas_enviados:
                    disparar_alerta(f"TOP PICK: {row['Ticker']}", f"Score: {r_rank['score_ia']}\nPreço: {r_rank['preco']:.2f}")
                    st.session_state.alertas_enviados.add(row["Ticker"])
                    st.toast(f"Alerta enviado: {row['Ticker']}")

                res.append({
                    "Ticker": row["Ticker"],
                    "Preço": f"R$ {r_rank['preco']:.2f}",
                    "Score IA": r_rank['score_ia'],
                    "Decisão": r_rank['decisao_ia'],
                    "DY": f"{r_rank['dy']*100:.1f}%",
                    "Bazin": f"R$ {r_rank['p_bazin']:.2f}"
                })
            bar.progress((i+1)/total)
        
        st.dataframe(pd.DataFrame(res).sort_values("Score IA", ascending=False).style.background_gradient(subset=["Score IA"], cmap="Greens"), use_container_width=True)
        
        st.divider()
        val = st.number_input("Aporte (R$)", 1000.0)
        if st.button("Sugerir Aporte"):
            sug = sugerir_aportes(pd.DataFrame(res) if res else pd.DataFrame(), val, st.session_state.metas_setor)
            st.dataframe(sug, use_container_width=True)

# --- ABA 3: FIIs ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs")
    st.info("Faça upload do CSV 'statusinvest-busca-avancada.csv'")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        df_fii = scanner_fiis_csv(uploaded)
        if not df_fii.empty:
            st.success(f"{len(df_fii)} FIIs analisados e pontuados!")
            st.dataframe(df_fii[["TICKER", "PRECO", "DY", "P/VP", "Score"]].head(20).style.background_gradient(subset=["Score"], cmap="Blues"), use_container_width=True)

# --- ABA 4: FUTURO ---
with tabs[3]:
    st.subheader("🔮 Simulação Monte Carlo")
    val_atual = st.number_input("Patrimônio Atual (R$)", 150000.0)
    aporte = st.number_input("Aporte Mensal (R$)", 2000.0)
    
    if st.button("Simular 10 Anos"):
        motor = MotorAnalise()
        sims = motor.monte_carlo(val_atual, aporte, 10, 1000)
        fig = go.Figure(go.Histogram(x=sims, nbinsx=40, marker_color='green'))
        fig.update_layout(title="Distribuição de Patrimônio Futuro")
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Mediana Esperada", f"R$ {np.median(sims):,.2f}")