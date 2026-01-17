import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import requests
import smtplib
from email.mime.text import MIMEText

# ======================================================
# 1. CONFIGURAÇÕES INICIAIS
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | vFinal", layout="wide")

# Tenta ler os segredos. Se não achar (ainda não configurou), usa vazio para não travar.
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
# 2. MOTOR DE ANÁLISE (CLASSE INTERNA)
# ======================================================
class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # Preço
            preco_atual = hist["Close"].iloc[-1]
            
            # RSI
            delta = hist["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # Volatilidade e Drawdown
            retornos = hist["Close"].pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)
            topo = hist["Close"].cummax()
            drawdown = ((hist["Close"] - topo) / topo).min() * 100

            # Valuation
            dy = info.get("dividendYield", 0) or 0
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            
            dpa = preco_atual * dy
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            p_graham = (22.5 * lpa * vpa) ** 0.5 if (lpa > 0 and vpa > 0) else 0
            p_gordon = p_bazin # Proxy

            # Níveis Técnicos (Suporte/Resistência/Stops)
            window = 60 # 3 meses aprox
            suporte = hist["Close"].tail(window).min()
            resistencia = hist["Close"].tail(window).max()
            stop_loss = suporte * 0.95
            stop_gain = resistencia * 1.05

            return {
                "preco": preco_atual,
                "rsi": rsi,
                "volatilidade": volatilidade,
                "drawdown": drawdown,
                "p_bazin": p_bazin,
                "p_graham": p_graham,
                "p_gordon": p_gordon,
                "lpa": lpa,
                "vpa": vpa,
                "dy": dy,
                "suporte": suporte,
                "resistencia": resistencia,
                "stop_loss": stop_loss,
                "stop_gain": stop_gain
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

# --- CORREÇÃO DO ERRO DE CACHE (UnserializableReturnValueError) ---
@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None, None
        
        motor = MotorAnalise()
        r = motor.analisar(hist, t.info, ticker)
        
        # RETORNA APENAS DADOS PUROS (Dicionário), NÃO O OBJETO TICKER
        return r, t.info 
    except:
        return None, None

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
    
    df["Score_IA"] = ((df["Gap"] * 200) + (df["Score"] / 100) + ((df["PM"] - df["Cotação"]) / df["PM"])).clip(lower=0)
    soma = df["Score_IA"].sum()
    if soma > 0: df["Aporte_Sugerido"] = (df["Score_IA"] / soma) * aporte
    else: df["Aporte_Sugerido"] = 0
    return df[df["Aporte_Sugerido"] > 1].sort_values("Aporte_Sugerido", ascending=False)

# ======================================================
# 4. DADOS INICIAIS (SESSION STATE)
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

tabs = st.tabs(["🔎 Análise Técnica", "💼 Ações", "🏢 FIIs & Scanner", "💰 RF & PGBL"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    r, info = obter_dados(ticker_input)
    
    if r:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Preço", f"R$ {r['preco']:.2f}")
        c2.metric("Bazin (Teto)", f"R$ {r['p_bazin']:.2f}", delta=f"{r['p_bazin']-r['preco']:.2f}")
        c3.metric("Graham (Justo)", f"R$ {r['p_graham']:.2f}")
        c4.metric("Gordon (Est.)", f"R$ {r['p_gordon']:.2f}")

        c5, c6, c7, c8 = st.columns(4)
        c5.markdown(f"**{get_rsi_status(r['rsi'])}**")
        c6.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        c7.metric("Drawdown", f"{r['drawdown']:.1f}%", delta_color="inverse")
        c8.metric("DY Anual", f"{r['dy']*100:.2f}%")

        # GRÁFICO TÉCNICO COMPLETO
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                vals = hist_chart["Close"] if "Close" in hist_chart else hist_chart.iloc[:,0]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist_chart.index, y=vals, name="Preço", line_color='blue'))
                
                # Linhas Técnicas
                if r['stop_gain'] > 0: fig.add_hline(y=r['stop_gain'], line_dash="dash", line_color="gold", annotation_text="ALVO")
                if r['stop_loss'] > 0: fig.add_hline(y=r['stop_loss'], line_dash="dash", line_color="red", annotation_text="STOP")
                if r['suporte'] > 0: fig.add_hline(y=r['suporte'], line_dash="dot", line_color="green", annotation_text="SUPORTE")
                if r['p_bazin'] > 0: fig.add_hline(y=r['p_bazin'], line_dash="dash", line_color="purple", annotation_text="BAZIN")
                
                st.plotly_chart(fig, use_container_width=True)
                        except Exception as e: st.warning(f"Gráfico indisponível: {e}")
        
        # TABELA VALUATION
        st.subheader("📋 Valuation Consolidado")
        dados_tabela = {
            "Métrica": ["DY (%)", "P/L", "P/VP", "ROE (%)", "Preço Bazin", "Preço Graham", "Preço Gordon"],
            "Valor": [f"{r['dy']*100:.2f}%", f"{info.get('trailingPE', 0):.2f}", f"{info.get('priceToBook', 0):.2f}", 
                      f"{info.get('returnOnEquity', 0)*100:.1f}%", f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
        }
        st.table(pd.DataFrame(dados_tabela))
    else: st.warning("Ticker não encontrado.")

# --- ABA 2: AÇÕES ---
with tabs[1]:
    st.subheader("Gestão de Ações")
    df_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", key="ed_acoes", use_container_width=True)
    st.session_state.carteira_acoes = df_acoes

    if st.button("🔄 Analisar Ações"):
        res = []
        bar = st.progress(0)
        total = len(df_acoes)
        for i, row in df_acoes.iterrows():
            r, info = obter_dados(row["Ticker"])
            if r:
                score = 0
                if r["preco"] < r["p_bazin"]: score += 30
                if r["preco"] < r["p_graham"]: score += 20
                if r["rsi"] < 40: score += 30
                if row["PM"] > r["preco"]: score += 20
                
                status = "MANTER"
                if score >= 70: status = "🟢 COMPRA"
                elif score <= 30: status = "🔴 VENDA"

                chave = f"{row['Ticker']}_{status}"
                if "COMPRA" in status and chave not in st.session_state.alertas_enviados:
                    disparar_alerta(f"OPORTUNIDADE: {row['Ticker']}", f"Preço: {r['preco']:.2f}\nBazin: {r['p_bazin']:.2f}")
                    st.session_state.alertas_enviados.add(chave)
                    st.toast(f"Alerta enviado: {row['Ticker']}")

                res.append({**row.to_dict(), "Cotação": r["preco"], "Score": score, "Bazin": r["p_bazin"]})
            else: res.append({**row.to_dict(), "Cotação": 0, "Score": 0, "Bazin": 0})
            bar.progress((i+1)/total)
        st.session_state.df_final_acoes = pd.DataFrame(res)
        st.rerun()

    if "df_final_acoes" in st.session_state:
        df_final = st.session_state.df_final_acoes
        st.dataframe(df_final.style.background_gradient(subset=["Score"], cmap="Greens"), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            val = st.number_input("Aporte Disponível (R$)", 1000.0)
            if st.button("Sugerir Alocação"):
                sug = sugerir_aportes(df_final, val, st.session_state.metas_setor)
                st.dataframe(sug[["Ticker", "Setor", "Aporte_Sugerido"]].style.format({"Aporte_Sugerido": "R$ {:.2f}"}))
        with c2:
            pat = (df_final["Cotação"] * df_final["Qtd"]).sum()
            if st.button("Simular Crises (Stress Test)"):
                motor = MotorAnalise()
                res_stress = motor.stress_test(pat)
                fig = go.Figure()
                for k, v in res_stress.items(): fig.add_trace(go.Scatter(y=v, name=k))
                st.plotly_chart(fig, use_container_width=True)

# --- ABA 3: FIIs ---
with tabs[2]:
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
    st.subheader("🔍 Scanner Offline (CSV)")
    st.info("Para usar, faça upload de 'statusinvest-busca-avancada.csv' na raiz do GitHub.")

# --- ABA 4: RF ---
with tabs[3]:
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