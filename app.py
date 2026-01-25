# ==============================================================================
# HEDGE FUND RICARDO V173 - GRAND MASTER (ALL FEATURES UNLOCKED)
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import time
import yfinance as yf
import plotly.express as px
import streamlit.components.v1 as components

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="Hedge Fund Ricardo v173", 
    layout="wide", 
    page_icon="🏛️",
    initial_sidebar_state="expanded"
)

# --- 2. IMPORTAÇÃO SEGURA ---
try:
    from scipy.signal import argrelextrema
    from scipy.stats import norm
except ImportError:
    st.warning("⚠️ Biblioteca SciPy não detectada.")
    argrelextrema = None; norm = None

# --- 3. MOTOR DE INTELIGÊNCIA ---
class MotorAnalise:
    def formatar_ticker(self, ticker):
        t = str(ticker).upper().strip()
        if not t.endswith(".SA") and not any(c.isdigit() for c in t): return t
        if not t.endswith(".SA"): return f"{t}.SA"
        return t

    def detectar_tipo(self, ticker):
        t = ticker.replace(".SA", "")
        # Units e Ações terminadas em 11 que não são FIIs
        fake_fiis = ["TAEE11", "KLBN11", "SAPR11", "SANB11", "ALUP11", "BBSE3", "CXSE3", "ITUB4", "VALE3", "PETR4", "ELET3", "WEGE3", "PRIO3", "RRRP3", "JBSS3"]
        if t.endswith("11") and t not in fake_fiis: return "FII"
        return "ACAO"

    # [MÓDULOS DE ANÁLISE]
    def analisar_macro(self):
        try:
            # threads=False para não travar
            ibov = yf.download("^BVSP", period="1y", progress=False, threads=False)['Close']
            if ibov.empty: return 0, "Neutro"
            atual = ibov.iloc[-1]
            mm200 = ibov.rolling(200).mean().iloc[-1]
            if atual > mm200: return 5, "🟢 Bull Market"
            return -10, "🔴 Bear Market"
        except: return 0, "⚪ Indefinido"

    def analisar_sentimento_news(self, ticker_obj):
        try:
            news = ticker_obj.news
            if not news: return "Neutro", 0, ["Sem Notícias"]
            score = 0
            pos = ["lucro", "alta", "dividend", "compra", "recorde", "aprovado", "forte", "bonificação"]
            neg = ["prejuízo", "queda", "fraude", "corrupção", "divida", "risco", "fraco", "investigação"]
            manchetes = []
            for n in news[:5]:
                t = n.get('title', '').lower()
                manchetes.append(n.get('title', ''))
                score += sum(2 for w in pos if w in t)
                score -= sum(2 for w in neg if w in t)
            sentimento = "🟢 Positivo" if score > 2 else "🔴 Negativo" if score < -2 else "⚪ Neutro"
            return sentimento, score, manchetes
        except: return "Neutro", 0, ["Erro News"]

    def consultar_dividendos_reais(self, ticker_obj):
        try:
            divs = ticker_obj.dividends
            if divs.empty: return 0.0
            corte = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
            return divs[divs.index >= corte].sum()
        except: return 0.0

    def calcular_valuation(self, info, preco, ticker, modo_crise, dy_val):
        modelos = {}
        tipo = self.detectar_tipo(ticker)
        
        lpa = info.get('trailingEps', 0) or 0
        vpa = info.get('bookValue', 0) or 0
        roe = info.get('returnOnEquity', 0) or 0
        div = dy_val if dy_val > 0 else (info.get('dividendRate', 0) or 0)
        pvp = preco / vpa if vpa > 0 else 0
        rf = 0.135 if modo_crise else 0.115 
        g = 0.01; ke = rf + 0.06

        if tipo == "FII":
            if vpa > 0: modelos['VPA'] = vpa
            if div > 0: modelos['Gordon'] = div / (rf - g + 0.02)
            if div > 0: modelos['Bazin'] = div / 0.06
            vals = [v for v in modelos.values() if v > 0]
            p_justo = float(np.median(vals)) if vals else vpa
            fator_teto = 0.95 if modo_crise else 1.05
            p_teto = p_justo * fator_teto
        else:
            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div > 0: modelos['Gordon'] = div * (1+g) / (ke-g)
            if roe > 0 and vpa > 0:
                p_roe = (roe - g) / (ke - g) * vpa
                if p_roe > 0: modelos['Justo (ROE)'] = p_roe
            vals = [v for v in modelos.values() if v > 0 and v < preco*5]
            p_justo = float(np.median(vals)) if vals else 0
            margem = 0.25 if modo_crise else 0.15
            p_teto = p_justo * (1 - margem)

        dados = {"LPA": lpa, "VPA": vpa, "ROE": roe, "DY 12m": div, "P/VP": pvp, "TIPO": tipo}
        return p_justo, p_teto, modelos, dados

    def analisar(self, hist, info, ticker, modo_crise, ticker_obj):
        try:
            if hist is None or hist.empty: return None
            c = hist["Close"]
            atual = float(c.iloc[-1])

            macro_score, macro_txt = self.analisar_macro()
            # News: simplificado no scanner, detalhado no individual
            sentimento = "⚪ Neutro" 
            
            dy_val = self.consultar_dividendos_reais(ticker_obj)
            p_justo, p_teto, modelos, dados = self.calcular_valuation(info, atual, ticker, modo_crise, dy_val)
            tipo_ativo = dados["TIPO"]
            pvp = dados["P/VP"]

            mme9 = c.ewm(span=9).mean().iloc[-1]
            mme21 = c.ewm(span=21).mean().iloc[-1]
            
            # Score Inteligente
            score = 50; motivos = []
            if tipo_ativo == "FII":
                if 0.80 <= pvp <= 1.05: score += 30; motivos.append("✅ P/VP Atrativo")
                elif pvp > 1.15: score -= 30; motivos.append("❌ P/VP Caro")
                if (dy_val/atual) > 0.10: score += 20; motivos.append("💰 DY > 10%")
            else:
                if p_justo > 0 and atual <= p_teto: score += 30; motivos.append("💎 Barato")
                elif p_justo > 0 and atual > p_justo: score -= 20; motivos.append("💸 Caro")
                if mme9 > mme21: score += 15; motivos.append("📈 Tend. Alta")

            score += macro_score
            decisao = "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"
            dy_pct = (dy_val/atual)*100 if atual > 0 else 0
            
            tec_data = [
                {"Ind": "P/VP", "Val": f"{pvp:.2f}", "Sinal": "🟢" if pvp <= 1.05 else "🔴"},
                {"Ind": "Macro", "Val": macro_txt, "Sinal": "🟢" if macro_score > 0 else "🔴"},
                {"Ind": "DY 12m", "Val": f"{dy_pct:.1f}%", "Sinal": "ℹ️"}
            ]

            return {
                "score_ia": max(0, min(100, score)), "decisao_ia": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto,
                "modelos_val": modelos, "dados_fund": dados, "dy_pct": dy_pct,
                "tabela_tecnica": pd.DataFrame(tec_data), "manchetes": [], "sentimento": sentimento, "tipo": tipo_ativo
            }
        except: return None

    # [MÓDULO REBALANCEAMENTO]
    def rebalancear(self, df_carteira):
        total = df_carteira["Valor Atual"].sum()
        if total == 0: return df_carteira
        
        df_carteira["Meta R$"] = (df_carteira["Meta %"] / 100) * total
        df_carteira["Diff R$"] = df_carteira["Meta R$"] - df_carteira["Valor Atual"]
        df_carteira["Sugestão"] = np.where(df_carteira["Diff R$"] > 0, "🟢 COMPRAR", "🔴 VENDER")
        
        mask = df_carteira["Preço"] > 0
        df_carteira.loc[mask, "Qtd Ação"] = (abs(df_carteira.loc[mask, "Diff R$"]) / df_carteira.loc[mask, "Preço"]).astype(int)
        
        return df_carteira

    def calcular_stress_test(self, ticker, qtd, preco):
        try:
            exp = qtd * preco
            return {
                "📉 Crash (-10%)": exp * -0.10, "🔥 Crash (-30%)": exp * -0.30,
                "🏦 Juros (+1%)": exp * (-0.15 if "11.SA" in ticker else -0.05)
            }
        except: return {}

# --- 4. CACHE ---
@st.cache_data(ttl=600)
def obter_dados_v173(ticker, modo_crise):
    motor = MotorAnalise()
    t = motor.formatar_ticker(ticker)
    try:
        t_obj = yf.Ticker(t)
        hist = t_obj.history(period="2y") 
        if hist.empty: return None
        try: info = t_obj.info
        except: info = {"symbol": t}
        return motor.analisar(hist, info, t, modo_crise, t_obj)
    except: return None

@st.cache_data(ttl=3600)
def calcular_consolidado_v173(df_dict):
    df = pd.DataFrame(df_dict)
    motor = MotorAnalise()
    tickers = [motor.formatar_ticker(t) for t in df["Ticker"]]
    vals = []; precos = []
    # Sequencial seguro
    for _, r in df.iterrows():
        try:
            t = motor.formatar_ticker(r["Ticker"])
            h = yf.Ticker(t).history(period="1d")
            p = float(h["Close"].iloc[-1])
            vals.append(r["Qtd"] * p)
            precos.append(p)
        except: vals.append(0.0); precos.append(0.0)
    return vals, precos

@st.cache_data(ttl=86400)
def download_longo(tickers):
    motor = MotorAnalise()
    l = [motor.formatar_ticker(t) for t in tickers]
    return yf.download(l, period="5y", progress=False, threads=False)['Close']

# --- 5. INTERFACE ---
st.title("💰 Hedge Fund Ricardo v173 (Grand Master)")

with st.sidebar:
    st.header("⚙️ Painel")
    modo_crise = st.toggle("🔴 MODO CRISE", value=False)
    st.divider()
    if st.button("🔄 Restaurar Carteira"):
        # Restaurado com Meta %
        st.session_state.carteira_acoes = pd.DataFrame([
            ["HGLG11", 20, 15], ["KNCR11", 27, 15],
            ["VALE3", 100, 20], ["PETR4", 200, 20], ["BBAS3", 100, 15], ["ITUB4", 100, 15]
        ], columns=["Ticker", "Qtd", "Meta %"])
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])
        st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([["VALE3", 100, 50], ["PETR4", 100, 50]], columns=["Ticker", "Qtd", "Meta %"])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["CDB", 0.0]], columns=["Ativo", "Saldo"])

tabs = st.tabs(["📊 Dash", "⚖️ Rebalance", "🔎 Análise", "📡 Scanner", "🦁 Fiscal", "🛡️ Renda Fixa", "🧪 Stress"])

# DASHBOARD
with tabs[0]:
    if st.button("🚀 Atualizar Dados", type="primary"):
        with st.spinner("Atualizando preços (Sequencial)..."):
            vals, precos = calcular_consolidado_v173(st.session_state.carteira_acoes.to_dict())
            st.session_state.carteira_acoes["Valor Atual"] = vals
            st.session_state.carteira_acoes["Preço"] = precos
            st.session_state.last_update = time.time()
            st.rerun()

    if "last_update" in st.session_state:
        df = st.session_state.carteira_acoes
        rf = st.session_state.carteira_rf["Saldo"].sum()
        rv = df["Valor Atual"].sum() if "Valor Atual" in df.columns else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", f"R$ {rf+rv:,.2f}")
        c2.metric("Renda Variável", f"R$ {rv:,.2f}")
        c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
        if rv > 0: st.plotly_chart(px.pie(df, values='Valor Atual', names='Ticker', hole=0.4), use_container_width=True)
    else: st.info("Clique no botão acima para carregar.")

# REBALANCE (RESTAURADO)
with tabs[1]:
    st.subheader("⚖️ Alocação Inteligente")
    st.info("Defina a 'Meta %' na tabela abaixo. A soma deve ser 100%.")
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    
    if "last_update" in st.session_state:
        motor = MotorAnalise()
        df_bal = motor.rebalancear(st.session_state.carteira_acoes.copy())
        st.write("#### Plano de Ajuste:")
        cols = ["Ticker", "Valor Atual", "Meta R$", "Diff R$", "Sugestão", "Qtd Ação"]
        st.dataframe(df_bal[cols].style.format({
            "Valor Atual": "R$ {:.2f}", "Meta R$": "R$ {:.2f}", "Diff R$": "R$ {:.2f}", "Qtd Ação": "{:.0f}"
        }).applymap(lambda v: 'color: green' if v == '🟢 COMPRAR' else 'color: red' if v == '🔴 VENDER' else '', subset=['Sugestão']), use_container_width=True)

# ANÁLISE
with tabs[2]:
    c_in, c_bt = st.columns([3, 1])
    t_in = c_in.text_input("Ticker", "VALE3")
    if c_bt.button("Analisar"):
        with st.spinner("Analisando..."):
            r = obter_dados_v173(t_in, modo_crise)
        if r:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Score", r['score_ia'], r['decisao_ia'])
            c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c3.metric("DY (12m)", f"{r['dy_pct']:.2f}%")
            if r['tipo'] == "FII": c4.metric("P/VP", f"{r['dados_fund']['P/VP']:.2f}")
            else: c4.metric("Potencial", f"{((r['p_justo']/r['preco'])-1)*100:.1f}%")
            
            st.success(f"**Tese:** {r['motivos']}")
            t_fmt = t_in.upper().replace(".SA", "")
            components.html(f"""<div class="tradingview-widget-container"><div id="tradingview_chart"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 400, "symbol": "BMFBOVESPA:{t_fmt}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_chart" }});</script></div>""", height=400)
            st.dataframe(r['tabela_tecnica'], use_container_width=True, hide_index=True)
            st.write("#### Valuation:")
            for k, v in r['modelos_val'].items(): st.write(f"- **{k}:** R$ {v:.2f}")

# SCANNER COMPLETO
with tabs[3]:
    st.subheader("📡 Radar de Mercado")
    col_scan1, col_scan2 = st.columns(2)
    with col_scan1:
        if st.button("🔍 Top 30 Ações (IBOV)"):
            acoes = ["VALE3", "PETR4", "ITUB4", "BBDC4", "BBAS3", "ELET3", "WEGE3", "RENT3", "SUZB3", "BPAC11", 
                     "JBSS3", "RADL3", "PRIO3", "RDOR3", "RAIL3", "CSAN3", "CPLE6", "VIVT3", "HYPE3", "EQTL3", 
                     "SABESP3", "CMIG4", "LREN3", "B3SA3", "TIMS3", "TOTS3", "EGIE3", "VBBR3", "CCRO3", "CSNA3"]
            res = []; bar = st.progress(0); status = st.empty()
            for i, t in enumerate(acoes):
                status.text(f"Lendo {t}...")
                d = obter_dados_v173(t, modo_crise)
                if d: res.append({"Ticker": t, "Score": d['score_ia'], "Decisão": d['decisao_ia'], "Preço": d['preco'], "Justo": d['p_justo'], "DY%": f"{d['dy_pct']:.1f}%"})
                bar.progress((i+1)/len(acoes))
            status.empty()
            if res: st.dataframe(pd.DataFrame(res).sort_values("Score", ascending=False).style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)

    with col_scan2:
        if st.button("🏢 Top 30 FIIs (IFIX)"):
            fiis = ["HGLG11", "KNCR11", "KNIP11", "MXRF11", "XPLG11", "XPML11", "VISC11", "BTLG11", "IRDM11", "CPTS11", 
                    "BRCO11", "HGRU11", "MCCI11", "HGBS11", "HFOF11", "BCFF11", "KNSC11", "TRXF11", "VILG11", "VINC11", 
                    "JSRE11", "RBRR11", "TGAR11", "MALL11", "RBRP11", "PVBI11", "LVBI11", "HGRE11", "SARE11", "RECR11"]
            res = []; bar = st.progress(0); status = st.empty()
            for i, t in enumerate(fiis):
                status.text(f"Lendo {t}...")
                d = obter_dados_v173(t, modo_crise)
                if d: res.append({"Ticker": t, "Score": d['score_ia'], "Decisão": d['decisao_ia'], "Preço": d['preco'], "P/VP": f"{d['dados_fund']['P/VP']:.2f}", "DY%": f"{d['dy_pct']:.1f}%"})
                bar.progress((i+1)/len(fiis))
            status.empty()
            if res: st.dataframe(pd.DataFrame(res).sort_values("Score", ascending=False).style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)

# FISCAL
with tabs[4]:
    st.subheader("🦁 Calculadora DARF")
    c1, c2 = st.columns(2)
    with c1: tipo = st.radio("Operação", ["Swing Trade Ações", "FIIs", "Day Trade"])
    with c2: lucro = st.number_input("Lucro Líquido (R$)", 0.0); vendas = st.number_input("Total Vendas (Só Swing)", 0.0)
    
    darf = 0.0
    if tipo == "Swing Trade Ações":
        if vendas > 20000: darf = lucro * 0.15; st.error(f"Pagar: R$ {darf:.2f}")
        else: st.success("ISENTO (< 20k)")
    else:
        darf = lucro * 0.20; st.error(f"Pagar: R$ {darf:.2f}")

# RENDA FIXA & STRESS
with tabs[5]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)
with tabs[6]:
    if st.button("Stress Test"):
        motor = MotorAnalise(); total = {}
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados_v173(row["Ticker"], False)
            if d:
                res = motor.calcular_stress_test(row["Ticker"], row["Qtd"], d['preco'])
                for k, v in res.items(): total[k] = total.get(k, 0) + v
        for k, v in total.items(): st.metric(k, f"R$ {v:,.2f}", delta_color="inverse")