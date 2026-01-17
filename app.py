import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import requests
import smtplib
import datetime
from email.mime.text import MIMEText

# ======================================================
# 1. CONFIGURAÇÕES & SEGREDOS
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 4.0", layout="wide")

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

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

# ======================================================
# 2. MOTOR DE ANÁLISE & IA
# ======================================================
class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # 1. Dados Básicos
            preco_atual = hist["Close"].iloc[-1]
            
            # 2. RSI
            delta = hist["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # 3. Volatilidade e Drawdown
            retornos = hist["Close"].pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            topo = hist["Close"].cummax()
            drawdown = ((hist["Close"] - topo) / topo).min() * 100

            # 4. Valuation
            dy = info.get("dividendYield", 0) or 0
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            dpa = preco_atual * dy
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            p_graham = (22.5 * lpa * vpa) ** 0.5 if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin 

            # 5. Níveis Técnicos
            window = 60 
            suporte = hist["Close"].tail(window).min()
            resistencia = hist["Close"].tail(window).max()
            stop_loss = suporte * 0.95
            stop_gain = resistencia * 1.05

            # 6. IA OBJETIVA (SCORING AÇÕES)
            score = 0
            motivos = []

            # Critérios Fundamentalistas
            if p_bazin > 0 and preco_atual < p_bazin: 
                score += 25
                motivos.append("Abaixo do Teto Bazin")
            if p_graham > 0 and preco_atual < p_graham: 
                score += 25
                motivos.append("Desconto Patrimonial (Graham)")
            if dy > 0.06:
                score += 15
                motivos.append("DY Atrativo (>6%)")

            # Critérios Técnicos
            if rsi < 35: 
                score += 20
                motivos.append("Sobrevenda (RSI)")
            elif rsi > 70: 
                score -= 20
                motivos.append("Sobrecompra (RSI)")
            
            if volatilidade > 0.40:
                score -= 20
                motivos.append("Alta Volatilidade")

            # Decisão Final
            if score >= 80: decisao = "🟢🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🟢 COMPRA"
            elif score >= 40: decisao = "🟡 MANTER"
            elif score >= 20: decisao = "🔴 VENDA"
            else: decisao = "🔴🔴 VENDA FORTE"

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
                "stop_loss": stop_loss,
                "stop_gain": stop_gain,
                "score_ia": score,
                "decisao_ia": decisao,
                "motivos": ", ".join(motivos) if motivos else "Neutro"
            }
        except Exception as e:
            print(f"Erro Motor {ticker}: {e}")
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
# 3. FUNÇÕES DE SUPORTE & ALERTAS
# ======================================================
def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
        requests.post(url, data=payload, timeout=5)
    except: pass

def enviar_email(mensagem):
    if not EMAIL_USER: return
    try:
        msg = MIMEText(mensagem)
        msg["Subject"] = "🚨 ALERTA – HEDGE FUND RICARDO"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
    except: pass

def disparar_alerta(titulo, corpo):
    msg = f"🚨 *{titulo}*\n\n{corpo}"
    enviar_telegram(msg)
    enviar_email(msg)

# === ALERTA DIÁRIO INTELIGENTE ===
if "alertas_diarios" not in st.session_state:
    st.session_state.alertas_diarios = {}

def alerta_diario_ia(ticker, score, decisao, preco):
    hoje = datetime.date.today().isoformat()
    chave = f"{ticker}_{hoje}"

    # Se já enviou hoje para este ticker, sai
    if st.session_state.alertas_diarios.get(chave):
        return

    # Dispara apenas para decisões extremas
    if "FORTE" in decisao:
        msg = f"*{ticker}*\nDecisão: {decisao}\nScore IA: {score}/100\nPreço: R$ {preco:.2f}"
        disparar_alerta(f"ALERTA IA: {ticker}", msg)
        st.session_state.alertas_diarios[chave] = True
        st.toast(f"Alerta Diário Enviado: {ticker}", icon="🔔")

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None, None
        
        motor = MotorAnalise()
        r = motor.analisar(hist, t.info, ticker)
        return r, t.info 
    except:
        return None, None

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
    
    # Usa Score se existir, senão 50
    score_val = df["Score"] if "Score" in df.columns else 50
    df["Score_Alocacao"] = ((df["Gap"] * 200) + (score_val / 100)).clip(lower=0)
    
    soma = df["Score_Alocacao"].sum()
    if soma > 0: df["Aporte_Sugerido"] = (df["Score_Alocacao"] / soma) * aporte
    else: df["Aporte_Sugerido"] = 0
    return df[df["Aporte_Sugerido"] > 1].sort_values("Aporte_Sugerido", ascending=False)

def gerar_ranking_acoes(df_acoes):
    ranking = []
    bar = st.progress(0)
    total = len(df_acoes)
    
    for i, row in df_acoes.iterrows():
        r, info = obter_dados(row["Ticker"])
        if r:
            # Chama o alerta diário aqui
            alerta_diario_ia(row["Ticker"], r["score_ia"], r["decisao_ia"], r["preco"])
            
            ranking.append({
                "Ticker": row["Ticker"],
                "Setor": row["Setor"],
                "Preço": r["preco"],
                "Score IA": r["score_ia"],
                "Decisão": r["decisao_ia"],
                "DY (%)": f"{r['dy']*100:.2f}%",
                "RSI": f"{r['rsi']:.0f}"
            })
        bar.progress((i+1)/total)
    
    return pd.DataFrame(ranking).sort_values("Score IA", ascending=False)

# === SCANNER IA DE FIIs ===
def score_fii(row):
    score = 0
    # Tratamento de string para float (CSV brasileiro)
    try:
        dy = float(str(row.get("DY", "0")).replace("%", "").replace(",", "."))
        pvp = float(str(row.get("P/VP", "0")).replace(",", "."))
        vac = float(str(row.get("VACÂNCIA FISICA", "100")).replace("%", "").replace(",", "."))
    except:
        return 0, "ERRO DADOS"

    if dy >= 8: score += 30
    if pvp <= 1.05 and pvp >= 0.8: score += 25
    if vac <= 10: score += 20
    
    # Critério extra: Liquidez (se houver coluna)
    if "LIQUIDEZ MEDIA DIARIA" in row:
        liq = float(str(row.get("LIQUIDEZ MEDIA DIARIA", "0")).replace(".", "").replace(",", "."))
        if liq > 1000000: score += 15

    if score >= 80: decisao = "🟢🟢 COMPRA FORTE"
    elif score >= 60: decisao = "🟢 COMPRA"
    elif score >= 40: decisao = "🟡 MANTER"
    else: decisao = "🔴 EVITAR"

    return score, decisao

# ======================================================
# 4. DADOS INICIAIS
# ======================================================
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 1703, 24.48, "Bancos"], ["VALE3.SA", 152, 54.79, "Mineração"],
        ["ITSA4.SA", 1174, 9.63, "Holding"], ["TAEE11.SA", 500, 35.00, "Elétricas"],
        ["KLBN4.SA", 2323, 3.63, "Papel"], ["PETR4.SA", 900, 32.07, "Petróleo"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_fiis" not in st.session_state:
    st.session_state.carteira_fiis = pd.DataFrame([
        ["HGLG11.SA", 20, 158.03, "Logística"], ["KNCR11.SA", 27, 103.11, "Papel"],
        ["MXRF11.SA", 100, 10.50, "Híbrido"], ["VISC11.SA", 16, 109.70, "Shoppings"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000, "Pós"], ["PGBL BTG", 50000, "Multimercado"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

if "metas_setor" not in st.session_state:
    st.session_state.metas_setor = pd.DataFrame([
        ["Bancos", 0.15], ["Mineração", 0.10], ["Elétricas", 0.15], ["Holding", 0.10],
        ["Logística", 0.10], ["Papel", 0.10], ["Outros", 0.10], ["Petróleo", 0.10],
        ["Shoppings", 0.05], ["Híbrido", 0.05]
    ], columns=["Setor", "Meta"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# 5. INTERFACE DO APP
# ======================================================
st.sidebar.title("📊 Painel de Controle")
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Metas de Alocação")
df_metas = st.sidebar.data_editor(st.session_state.metas_setor, num_rows="dynamic", key="meta_ed")
st.session_state.metas_setor = df_metas
st.sidebar.markdown("---")
ticker_input = st.sidebar.text_input("🔍 Ticker:", "BBAS3.SA").upper()

# NOVAS ABAS INCLUINDO RANKING IA
tabs = st.tabs(["🔎 Análise Técnica", "💼 Ações", "🏆 Ranking IA", "🏢 FIIs & Scanner", "💰 RF & PGBL"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    r, info = obter_dados(ticker_input)
    
    if r:
        # PAINEL IA
        st.divider()
        col_score, col_decisao = st.columns([1, 2])
        col_score.metric("Score IA (0-100)", r['score_ia'])
        
        decisao = r['decisao_ia']
        if "COMPRA" in decisao: st.success(f"### {decisao}")
        elif "VENDA" in decisao: st.error(f"### {decisao}")
        else: st.warning(f"### {decisao}")
        
        st.caption(f"**Motivos:** {r['motivos']}")
        st.divider()

        # Métricas
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        c2.metric("Bazin (Teto)", f"R$ {r['p_bazin']:.2f}", delta=f"{r['p_bazin']-r['preco']:.2f}")
        c3.metric("Graham (Justo)", f"R$ {r['p_graham']:.2f}")
        c4.metric("Gordon (Est.)", f"R$ {r['p_gordon']:.2f}")

        # GRÁFICO CANDLESTICK
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                vals = hist_chart["Close"]
                if isinstance(vals, pd.DataFrame): vals = vals.iloc[:, 0]

                hist_chart["MM20"] = hist_chart["Close"].rolling(20).mean()
                hist_chart["MM50"] = hist_chart["Close"].rolling(50).mean()

                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=hist_chart.index, open=hist_chart["Open"], high=hist_chart["High"],
                    low=hist_chart["Low"], close=hist_chart["Close"], name="Preço"))
                fig.add_trace(go.Scatter(x=hist_chart.index, y=hist_chart["MM20"], name="MM20", line=dict(color='orange')))
                fig.add_trace(go.Scatter(x=hist_chart.index, y=hist_chart["MM50"], name="MM50", line=dict(color='blue')))

                if r['stop_gain'] > 0: fig.add_hline(y=r['stop_gain'], line_dash="dash", line_color="green", annotation_text="ALVO")
                if r['stop_loss'] > 0: fig.add_hline(y=r['stop_loss'], line_dash="dash", line_color="red", annotation_text="STOP")
                if r['suporte'] > 0: fig.add_hline(y=r['suporte'], line_dash="dot", line_color="gray", annotation_text="SUPORTE")

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, title=f"Gráfico Técnico: {ticker_input}", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e: st.warning(f"Gráfico indisponível: {e}")
    else: st.warning("Ticker não encontrado.")

# --- ABA 2: AÇÕES ---
with tabs[1]:
    st.subheader("Gestão de Ações")
    df_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", key="ed_acoes", use_container_width=True)
    st.session_state.carteira_acoes = df_acoes

    if st.button("🔄 Analisar Carteira"):
        res = []
        bar = st.progress(0)
        total = len(df_acoes)
        for i, row in df_acoes.iterrows():
            r, info = obter_dados(row["Ticker"])
            if r:
                # Alerta diário é verificado dentro da Aba 3 (Ranking), 
                # mas podemos verificar aqui também se quiser
                res.append({**row.to_dict(), "Cotação": r["preco"], "Veredito": r['decisao_ia'], "Score": r['score_ia'], "Bazin": r["p_bazin"]})
            else: res.append({**row.to_dict(), "Cotação": 0, "Veredito": "ERRO", "Score": 0, "Bazin": 0})
            bar.progress((i+1)/total)
        st.session_state.df_final_acoes = pd.DataFrame(res)
        st.rerun()

    if "df_final_acoes" in st.session_state:
        df_final = st.session_state.df_final_acoes
        st.dataframe(df_final.style.background_gradient(subset=["Score"], cmap="Greens"), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            val = st.number_input("Aporte Disponível (R$)", 1000.0)
            if st.button("Sugerir Alocação Inteligente"):
                sug = sugerir_aportes(df_final, val, st.session_state.metas_setor)
                st.dataframe(sug[["Ticker", "Setor", "Aporte_Sugerido"]].style.format({"Aporte_Sugerido": "R$ {:.2f}"}))
        with c2:
            pat = (df_final["Cotação"] * df_final["Qtd"]).sum()
            if st.button("Stress Test (Crises)"):
                motor = MotorAnalise()
                res_stress = motor.stress_test(pat)
                fig = go.Figure()
                for k, v in res_stress.items(): fig.add_trace(go.Scatter(y=v, name=k))
                st.plotly_chart(fig, use_container_width=True)

# --- ABA 3: RANKING IA ---
with tabs[2]:
    st.subheader("🏆 Ranking Quantitativo de Ações")
    st.info("Ranking gerado automaticamente com base no Score IA (0-100). Também dispara alertas diários.")

    if st.button("📊 Gerar Ranking IA"):
        df_rank = gerar_ranking_acoes(st.session_state.carteira_acoes)
        st.session_state.df_ranking = df_rank
        st.rerun()

    if "df_ranking" in st.session_state:
        st.dataframe(
            st.session_state.df_ranking.style.background_gradient(subset=["Score IA"], cmap="Greens"),
            use_container_width=True
        )

# --- ABA 4: FIIs & SCANNER ---
with tabs[3]:
    st.subheader("Carteira FIIs")
    df_fiis = st.data_editor(st.session_state.carteira_fiis, num_rows="dynamic", key="ed_fiis", use_container_width=True)
    st.session_state.carteira_fiis = df_fiis
    
    if st.button("🔄 Atualizar FIIs"):
        res = []
        for _, row in df_fiis.iterrows():
            r, info = obter_dados(row["Ticker"])
            if r:
                res.append({"Ticker": row["Ticker"], "Preço": r["preco"], "DY": f"{r['dy']*100:.2f}%", "PVP": f"{(r['preco']/r['p_bazin'])*0.6:.2f}"})
        st.session_state.df_fiis_final = pd.DataFrame(res)
        st.rerun()
    if "df_fiis_final" in st.session_state: st.dataframe(st.session_state.df_fiis_final, use_container_width=True)

    st.divider()
    st.subheader("🤖 Scanner IA de FIIs (Quantitativo)")
    st.caption("Faça upload do CSV de Busca Avançada do StatusInvest para que a IA analise as oportunidades.")
    
    uploaded_file = st.file_uploader("Arraste o arquivo CSV aqui", type=["csv"])
    
    if uploaded_file is not None:
        try:
            # Lê com separador ponto e vírgula (padrão StatusInvest)
            df_scan = pd.read_csv(uploaded_file, sep=";", encoding="latin-1")
            df_scan.columns = df_scan.columns.str.strip().str.upper()
            
            resultados = []
            for _, row in df_scan.iterrows():
                score, decisao = score_fii(row)
                resultados.append({
                    "TICKER": row.get("TICKER", "N/A"),
                    "PRECO": row.get("PRECO", "0"),
                    "DY": row.get("DY", "0"),
                    "P/VP": row.get("P/VP", "0"),
                    "VACANCIA": row.get("VACÂNCIA FISICA", "0"),
                    "SCORE IA": score,
                    "DECISAO": decisao
                })
            
            df_res = pd.DataFrame(resultados).sort_values("SCORE IA", ascending=False)
            
            # Filtra apenas oportunidades reais
            df_oportunidades = df_res[df_res["SCORE IA"] >= 60]
            
            st.success(f"{len(df_oportunidades)} Oportunidades de Compra Encontradas!")
            st.dataframe(df_oportunidades.style.background_gradient(subset=["SCORE IA"], cmap="Greens"), use_container_width=True)
            
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

# --- ABA 5: RF ---
with tabs[4]:
    st.subheader("Renda Fixa & PGBL")
    c1, c2 = st.columns(2)
    with c1:
        df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", key="ed_rf", use_container_width=True)
        st.session_state.carteira_rf = df_rf
        st.metric("Total RF", f"R$ {df_rf['Saldo Atual'].sum():,.2f}")
    with c2:
        renda = st.number_input("Renda Bruta Anual", 100000.0)
        aporte = st.number_input("Aporte PGBL", 12000.0)
        st.metric("Restituição IR Estimada", f"R$ {min(aporte, renda*0.12)*0.275:,.2f}")
    
    if st.button("🔮 Monte Carlo (10 Anos)"):
        pat_ac = (st.session_state.df_final_acoes["Cotação"] * st.session_state.df_final_acoes["Qtd"]).sum() if "df_final_acoes" in st.session_state else 0
        total = df_rf['Saldo Atual'].sum() + pat_ac
        sims = MotorAnalise().monte_carlo(total, 2000)
        fig = go.Figure(go.Histogram(x=sims, nbinsx=30))
        st.plotly_chart(fig, use_container_width=True)