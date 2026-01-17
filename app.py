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
# 1. CONFIGURAÇÕES & SEGREDOS (BLINDAGEM)
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 7.0", layout="wide")

# Tenta ler segredos, mas não trava se falhar
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
# 2. MOTOR DE ANÁLISE (CÉREBRO MATEMÁTICO)
# ======================================================
class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # --- PREPARAÇÃO DE DADOS ---
            # Garante que temos séries unidimensionais (corrige bug do yfinance novo)
            fechamento = hist["Close"]
            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            
            preco_atual = fechamento.iloc[-1]

            # --- TÉCNICA ---
            # RSI (14)
            delta = fechamento.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            # Volatilidade & Drawdown
            retornos = fechamento.pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            topo = fechamento.cummax()
            drawdown = ((fechamento - topo) / topo).min() * 100

            # Suporte e Resistência (Janela 60 dias)
            suporte = fechamento.tail(60).min()
            resistencia = fechamento.tail(60).max()
            stop_loss = suporte * 0.95
            stop_gain = resistencia * 1.05

            # --- FUNDAMENTOS (VALUATION) ---
            dy = info.get("dividendYield", 0) or 0
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            # 1. Bazin (Focado em Dividendos)
            # Preço Teto = DPA / 6%
            dpa = preco_atual * dy
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            
            # 2. Graham (Valor Intrínseco)
            # VI = Raiz(22.5 * LPA * VPA)
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            
            # 3. Gordon (Crescimento Perpétuo)
            # Simplificação: Usamos Bazin como proxy conservador ou projeção de g=2%
            k = 0.08 # Custo de oportunidade exigido
            g = 0.02 # Crescimento perene
            p_gordon = (dpa * (1+g)) / (k - g) if (dpa > 0 and k > g) else 0

            # --- IA DE DECISÃO (SCORE 0-100) ---
            score = 50 # Começa neutro
            motivos = []

            # Pontuação Fundamentalista
            if p_bazin > 0 and preco_atual < p_bazin:
                score += 20
                motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham:
                score += 20
                motivos.append("Desconto Graham")
            if dy > 0.06:
                score += 10
                motivos.append("DY > 6%")

            # Pontuação Técnica
            if rsi < 30:
                score += 20
                motivos.append("RSI Sobrevendido")
            elif rsi > 70:
                score -= 20
                motivos.append("RSI Sobrecomprado")
            
            if preco_atual <= suporte * 1.02:
                score += 10
                motivos.append("Em Suporte")

            score = min(100, max(0, score))

            # Classificação
            if score >= 75: decisao = "🟢 COMPRA FORTE"
            elif score >= 60: decisao = "🔵 COMPRA"
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
                "lpa": lpa,
                "vpa": vpa
            }
        except Exception as e:
            print(f"Erro Motor: {e}")
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
# 3. FUNÇÕES AUXILIARES E ALERTAS
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
def obter_dados(ticker):
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

def scanner_fiis_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=";", encoding="latin-1")
        cols = ["DY", "P/VP", "VACÂNCIA FISICA"]
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace("%","").str.replace(".","").str.replace(",","."), errors='coerce')
        
        # Lógica de Score FII
        df["Score"] = 0
        df.loc[df["DY"] > 8, "Score"] += 40
        df.loc[(df["P/VP"] > 0.8) & (df["P/VP"] < 1.05), "Score"] += 40
        df.loc[df["VACÂNCIA FISICA"] < 5, "Score"] += 20
        return df.sort_values("Score", ascending=False)
    except:
        return pd.DataFrame()

# ======================================================
# 4. SESSION STATE (DADOS)
# ======================================================
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 1703, 24.48, "Bancos"], ["VALE3.SA", 152, 54.79, "Mineração"],
        ["ITSA4.SA", 1174, 9.63, "Holding"], ["TAEE11.SA", 500, 35.00, "Elétricas"],
        ["KLBN4.SA", 2323, 3.63, "Papel"], ["PETR4.SA", 900, 32.07, "Petróleo"]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# 5. INTERFACE (O APP)
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")
st.sidebar.markdown("---")
ticker_input = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3.SA").upper()

tabs = st.tabs(["🔎 Análise Completa", "💼 Carteira & Ranking", "🏢 Scanner FIIs", "💰 Futuro (Monte Carlo)"])

# --- ABA 1: ANÁLISE TÉCNICA E FUNDAMENTALISTA ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    r = obter_dados(ticker_input)
    
    if r:
        # 1. PAINEL DE INTELIGÊNCIA ARTIFICIAL
        st.info("🧠 **Análise da Inteligência Artificial**")
        col_ia1, col_ia2 = st.columns([1, 3])
        col_ia1.metric("Score IA", f"{r['score_ia']}/100")
        
        if "COMPRA" in r['decisao_ia']:
            col_ia2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']:
            col_ia2.error(f"### {r['decisao_ia']}")
        else:
            col_ia2.warning(f"### {r['decisao_ia']}")
        
        st.write(f"**Gatilhos:** {r['motivos']}")
        st.divider()

        # 2. MÉTRICAS DE PREÇO E RISCO
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        c2.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        c3.metric("Drawdown Max", f"{r['drawdown']:.1f}%", delta_color="inverse")
        c4.markdown(f"**{get_rsi_status(r['rsi'])}**")

        # 3. TABELA DE VALUATION (A QUE TINHA SUMIDO)
        st.subheader("📋 Valuation: O Preço é Justo?")
        val_data = {
            "Modelo": ["Decio Bazin (Div.)", "Ben. Graham (Patr.)", "Gordon (Cresc.)"],
            "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"],
            "Margem de Segurança": [
                f"{(r['p_bazin']/r['preco'] - 1)*100:.1f}%",
                f"{(r['p_graham']/r['preco'] - 1)*100:.1f}%",
                f"{(r['p_gordon']/r['preco'] - 1)*100:.1f}%"
            ]
        }
        st.dataframe(pd.DataFrame(val_data), use_container_width=True)

        # 4. GRÁFICO TÉCNICO COMPLETO (COM SUPORTE/RESISTÊNCIA)
        st.subheader("📈 Análise Gráfica")
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                # Tratamento de dados para gráfico
                fechamento = hist_chart["Close"]
                if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:,0]
                
                # Médias
                mm20 = fechamento.rolling(20).mean()
                mm50 = fechamento.rolling(50).mean()

                fig = go.Figure()
                
                # Candlestick
                fig.add_trace(go.Candlestick(
                    x=hist_chart.index,
                    open=hist_chart["Open"] if "Open" in hist_chart else hist_chart.iloc[:,0],
                    high=hist_chart["High"] if "High" in hist_chart else hist_chart.iloc[:,1],
                    low=hist_chart["Low"] if "Low" in hist_chart else hist_chart.iloc[:,2],
                    close=fechamento,
                    name="Preço"
                ))

                # Médias e Linhas
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm20, name="MM20", line=dict(color='orange', width=1)))
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm50, name="