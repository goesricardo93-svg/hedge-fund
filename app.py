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
# 1. CONFIGURAÇÕES GERAIS
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 9.0", layout="wide")

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
# 2. MOTOR DE ANÁLISE (COMPLETO)
# ======================================================
class MotorAnalise:
    def analisar(self, hist, info, ticker):
        try:
            if hist is None or hist.empty: return None

            # --- DADOS DE PREÇO ---
            # Correção para garantir série unidimensional
            fechamento = hist["Close"]
            if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:, 0]
            preco_atual = fechamento.iloc[-1]
            
            # --- TÉCNICA ---
            # RSI
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

            # Níveis Técnicos (Suporte e Resistência 60d)
            window = 60 
            suporte = fechamento.tail(window).min()
            resistencia = fechamento.tail(window).max()
            stop_loss = suporte * 0.97 # 3% abaixo do suporte
            stop_gain = resistencia * 1.02 # 2% acima da resistência

            # --- FUNDAMENTOS ---
            dy = info.get("dividendYield", 0) or 0
            lpa = info.get("trailingEps", 0) or 0
            vpa = info.get("bookValue", 0) or 0
            roe = info.get("returnOnEquity", 0) or 0
            pl = info.get("trailingPE", 0) or 0
            pvp = info.get("priceToBook", 0) or 0
            margem = info.get("profitMargins", 0) or 0
            divida_ebitda = info.get("debtToEbitda", 0) or 0
            
            # Valuation
            dpa = preco_atual * dy
            p_bazin = dpa / 0.06 if dpa > 0 else 0
            p_graham = np.sqrt(22.5 * lpa * vpa) if (lpa > 0 and vpa > 0) else 0
            
            # Gordon (Proxy via Bazin para simplificação robusta)
            p_gordon = p_bazin

            # --- IA DE DECISÃO (SCORE) ---
            score = 50
            motivos = []

            # Pontos Positivos
            if p_bazin > 0 and preco_atual < p_bazin: score += 20; motivos.append("Desconto Bazin")
            if p_graham > 0 and preco_atual < p_graham: score += 20; motivos.append("Desconto Graham")
            if rsi < 30: score += 20; motivos.append("RSI Sobrevendido")
            if dy > 0.06: score += 10; motivos.append("Dividendos Altos")
            
            # Pontos Negativos
            if rsi > 70: score -= 20; motivos.append("RSI Sobrecomprado")
            if preco_atual > resistencia: score -= 10; motivos.append("Topo Histórico")

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
                "roe": roe,
                "pl": pl,
                "pvp": pvp,
                "margem": margem,
                "divida_ebitda": divida_ebitda,
                "suporte": suporte,
                "resistencia": resistencia,
                "stop_loss": stop_loss,
                "stop_gain": stop_gain,
                "score_ia": score,
                "decisao_ia": decisao,
                "motivos": ", ".join(motivos)
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
# 3. FUNÇÕES AUXILIARES
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
        cols = ["DY", "P/VP", "VACÂNCIA FISICA"]
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace("%","").str.replace(".","").str.replace(",","."), errors='coerce')
        
        df["Score"] = 0
        df.loc[df["DY"] > 8, "Score"] += 40
        df.loc[(df["P/VP"] > 0.8) & (df["P/VP"] < 1.05), "Score"] += 40
        df.loc[df["VACÂNCIA FISICA"] < 5, "Score"] += 20
        return df.sort_values("Score", ascending=False)
    except:
        return pd.DataFrame()

# ======================================================
# 4. SESSION STATE
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
# 5. INTERFACE (O APP)
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")

# --- SIDEBAR: METAS (REINSERIDA AQUI) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Metas por Setor (%)")
# Tabela editável lateral
df_metas = st.sidebar.data_editor(
    st.session_state.metas_setor,
    num_rows="dynamic",
    key="editor_metas_sidebar"
)
st.session_state.metas_setor = df_metas

# Validação visual
soma_metas = df_metas["Meta"].sum()
if abs(soma_metas - 1.0) > 0.01:
    st.sidebar.warning(f"⚠️ Soma: {soma_metas*100:.0f}% (Ideal: 100%)")
else:
    st.sidebar.success("✅ Metas Balanceadas")

st.sidebar.markdown("---")
ticker_input = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3.SA").upper()

tabs = st.tabs(["🔎 Análise Completa", "💼 Carteira & Ranking", "🏢 Scanner FIIs", "💰 Futuro (Monte Carlo)"])

# --- ABA 1: ANÁLISE TÉCNICA E FUNDAMENTALISTA (COMPLETA) ---
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

        # 3. TABELA DE VALUATION COMPLETA
        st.subheader("📋 Valuation: O Preço é Justo?")
        val_data = {
            "Modelo": ["Decio Bazin (Div.)", "Ben. Graham (Patr.)", "Gordon (Cresc.)"],
            "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"],
            "Margem de Segurança": [
                f"{(r['p_bazin']/r['preco'] - 1)*100:.1f}%" if r['p_bazin'] > 0 else "N/A",
                f"{(r['p_graham']/r['preco'] - 1)*100:.1f}%" if r['p_graham'] > 0 else "N/A",
                f"{(r['p_gordon']/r['preco'] - 1)*100:.1f}%" if r['p_gordon'] > 0 else "N/A"
            ]
        }
        st.dataframe(pd.DataFrame(val_data), use_container_width=True)

        # 4. TABELA DE FUNDAMENTOS ADICIONAIS
        st.subheader("📊 Indicadores Fundamentalistas")
        fund_data = {
            "Indicador": ["DY (%)", "P/L", "P/VP", "ROE (%)", "Margem Líquida (%)", "Dívida/EBITDA"],
            "Valor": [
                f"{r['dy']*100:.2f}%", f"{r['pl']:.2f}", f"{r['pvp']:.2f}", 
                f"{r['roe']*100:.1f}%", f"{r['margem']*100:.1f}%", f"{r['divida_ebitda']:.2f}"
            ]
        }
        st.table(pd.DataFrame(fund_data).T)

        # 5. GRÁFICO TÉCNICO COMPLETO
        st.subheader("📈 Análise Gráfica (Setup)")
        try:
            hist_chart = yf.download(ticker_input, period="2y", progress=False)
            if not hist_chart.empty:
                fechamento = hist_chart["Close"]
                if isinstance(fechamento, pd.DataFrame): fechamento = fechamento.iloc[:,0]
                
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

                # Médias
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm20, name="MM20", line=dict(color='orange', width=1)))
                fig.add_trace(go.Scatter(x=hist_chart.index, y=mm50, name="MM50", line=dict(color='blue', width=1)))
                
                # Linhas Técnicas (REINSERIDAS)
                fig.add_hline(y=r['suporte'], line_dash="dot", line_color="green", annotation_text=f"SUPORTE {r['suporte']:.2f}")
                fig.add_hline(y=r['resistencia'], line_dash="dot", line_color="red", annotation_text=f"RESISTÊNCIA {r['resistencia']:.2f}")
                fig.add_hline(y=r['stop_loss'], line_dash="dash", line_color="red", annotation_text=f"STOP LOSS {r['stop_loss']:.2f}")
                fig.add_hline(y=r['stop_gain'], line_dash="dash", line_color="gold", annotation_text=f"ALVO {r['stop_gain']:.2f}")

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_white", title=f"Setup Técnico: {ticker_input}")
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabela de Setup Técnico (REINSERIDA)
                st.info(f"""
                **🎯 Setup Técnico:**
                * **Suporte:** R$ {r['suporte']:.2f}
                * **Resistência:** R$ {r['resistencia']:.2f}
                * **Stop Loss Sugerido:** R$ {r['stop_loss']:.2f}
                * **Stop Gain (Alvo):** R$ {r['stop_gain']:.2f}
                """)
                
        except Exception as e:
            st.error(f"Erro ao gerar gráfico: {e}")

    else:
        st.warning("Ticker não encontrado ou erro na API.")

# --- ABA 2: CARTEIRA E RANKING ---
with tabs[1]:
    st.subheader("🏆 Ranking Automático da Carteira")
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_acoes = df_ed

    if st.button("🔄 Gerar Ranking e Alertas"):
        res = []
        bar = st.progress(0)
        total = len(df_ed)
        for i, row in df_ed.iterrows():
            r = obter_dados(row["Ticker"])
            if r:
                if r['score_ia'] >= 75 and row["Ticker"] not in st.session_state.alertas_enviados:
                    disparar_alerta(f"TOP PICK: {row['Ticker']}", f"Score: {r['score_ia']}\nPreço: {r['preco']:.2f}")
                    st.session_state.alertas_enviados.add(row["Ticker"])
                    st.toast(f"Alerta enviado: {row['Ticker']}")

                res.append({
                    "Ticker": row["Ticker"],
                    "Preço": r["preco"],
                    "Score IA": r['score_ia'],
                    "Decisão": r['decisao_ia'],
                    "Bazin": r["p_bazin"],
                    "Graham": r["p_graham"],
                    "DY": f"{r['dy']*100:.2f}%"
                })
            bar.progress((i+1)/total)
        
        df_rank = pd.DataFrame(res).sort_values("Score IA", ascending=False)
        st.dataframe(df_rank.style.background_gradient(subset=["Score IA"], cmap="Greens"), use_container_width=True)
        
        st.divider()
        st.write("#### 🤖 Sugestão de Aporte Inteligente (Considera Metas da Sidebar)")
        val = st.number_input("Valor do Aporte (R$)", 1000.0)
        if st.button("Calcular Distribuição"):
            sug = sugerir_aportes(df_rank if 'df_rank' in locals() else pd.DataFrame(), val, st.session_state.metas_setor)
            st.dataframe(sug, use_container_width=True)

# --- ABA 3: FIIs ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs (CSV)")
    st.info("Faça upload do arquivo 'statusinvest-busca-avancada.csv'")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        df_fii = scanner_fiis_csv(uploaded)
        if not df_fii.empty:
            st.success(f"{len(df_fii)} FIIs filtrados.")
            st.dataframe(df_fii[["TICKER", "PRECO", "DY", "P/VP", "Score"]].head(20).style.background_gradient(subset=["Score"], cmap="Blues"), use_container_width=True)

# --- ABA 4: FUTURO ---
with tabs[3]:
    st.subheader("🔮 Simulação Monte Carlo")
    val_atual = st.number_input("Patrimônio Atual (R$)", 50000.0)
    aporte = st.number_input("Aporte Mensal (R$)", 2000.0)
    
    if st.button("Simular 10 Anos"):
        motor = MotorAnalise()
        sims = motor.monte_carlo(val_atual, aporte, 10, 1000)
        fig = go.Figure(go.Histogram(x=sims, nbinsx=40, marker_color='green'))
        fig.update_layout(title="Distribuição de Probabilidade de Patrimônio")
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Cenário Provável (Mediana)", f"R$ {np.median(sims):,.2f}")