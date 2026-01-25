# ==============================================================================
# HEDGE FUND RICARDO V220 - HYBRID TITAN (TRADINGVIEW + PATTERNS + DATA)
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import time
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="Hedge Fund Ricardo v220", 
    layout="wide", 
    page_icon="🦁",
    initial_sidebar_state="expanded"
)

# --- 2. IMPORTAÇÃO CIENTÍFICA ---
try:
    from scipy.signal import argrelextrema
    from scipy.stats import linregress, norm
    SCIPY_OK = True
except ImportError:
    st.warning("⚠️ Biblioteca SciPy incompleta. Instale 'scipy'.")
    argrelextrema = None; norm = None; linregress = None; SCIPY_OK = False

# --- 3. MOTOR DE INTELIGÊNCIA ---
class MotorAnalise:
    def formatar_ticker(self, ticker):
        t = str(ticker).upper().strip()
        if not t.endswith(".SA") and not any(c.isdigit() for c in t): return t
        if not t.endswith(".SA"): return f"{t}.SA"
        return t

    def detectar_tipo(self, ticker):
        t = ticker.replace(".SA", "")
        fake_fiis = ["TAEE11", "KLBN11", "SAPR11", "SANB11", "ALUP11", "BBSE3", "CXSE3", "ITUB4", "VALE3", "PETR4", "ELET3", "WEGE3", "PRIO3", "RRRP3", "JBSS3", "BBAS3"]
        if t.endswith("11") and t not in fake_fiis: return "FII"
        return "ACAO"

    # [MÓDULO 1] PADRÕES GEOMÉTRICOS (MATEMÁTICA)
    def identificar_padroes_complexos(self, h, l):
        if not SCIPY_OK: return None
        try:
            n = 5
            idx_max = argrelextrema(h.values, np.greater_equal, order=n)[0]
            idx_min = argrelextrema(l.values, np.less_equal, order=n)[0]
            topos = h.iloc[idx_max].values; fundos = l.iloc[idx_min].values
            x_topos = np.arange(len(h))[idx_max]; x_fundos = np.arange(len(l))[idx_min]
            padroes = []

            # Triângulos (Slope)
            if len(topos) >= 3 and len(fundos) >= 3:
                slope_top, _, _, _, _ = linregress(x_topos[-3:], topos[-3:])
                slope_bot, _, _, _, _ = linregress(x_fundos[-3:], fundos[-3:])
                if slope_top < -0.05 and slope_bot > 0.05: padroes.append("⚠️ Triângulo Simétrico")
                elif abs(slope_top) < 0.05 and slope_bot > 0.05: padroes.append("🚀 Triângulo Ascendente")
                elif slope_top < -0.05 and abs(slope_bot) < 0.05: padroes.append("🔻 Triângulo Descendente")

            # Topo/Fundo Duplo
            if len(topos) >= 2:
                if abs(topos[-1] - topos[-2]) / topos[-2] < 0.015: padroes.append("📉 Topo Duplo")
            if len(fundos) >= 2:
                if abs(fundos[-1] - fundos[-2]) / fundos[-2] < 0.015: padroes.append("📈 Fundo Duplo")

            # OCO
            if len(topos) >= 3:
                if topos[-2] > topos[-3] and topos[-2] > topos[-1]:
                    if abs(topos[-3] - topos[-1]) / topos[-3] < 0.05: padroes.append("💀 OCO")

            return " + ".join(padroes) if padroes else None
        except: return None

    # [MÓDULO 2] FUNDAMENTOS & VALUATION (COM P/VP MANUAL)
    def consultar_dividendos_reais(self, ticker_obj):
        try:
            divs = ticker_obj.dividends
            if divs.empty: return 0.0
            corte = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
            return divs[divs.index >= corte].sum()
        except: return 0.0

    def calcular_fundamentos(self, info, preco, ticker, modo_crise, dy_val):
        modelos = {}
        tipo = self.detectar_tipo(ticker)
        
        lpa = info.get('trailingEps', 0) or 0
        vpa = info.get('bookValue', 0)
        roe = info.get('returnOnEquity', 0) or 0
        div = dy_val if dy_val > 0 else (info.get('dividendRate', 0) or 0)
        
        # P/VP MANUAL (BACKUP)
        if vpa is None or vpa == 0:
            pb = info.get('priceToBook')
            vpa = preco / pb if pb else 0.01
            pvp = pb if pb else 0.0
        else:
            pvp = preco / vpa

        rf = 0.135 if modo_crise else 0.115 
        g = 0.01; ke = rf + 0.06

        if tipo == "FII":
            if vpa > 0.1: modelos['VPA'] = vpa
            if div > 0: modelos['Gordon'] = div / (rf - g + 0.02)
            if div > 0: modelos['Bazin'] = div / 0.06
            vals = [v for v in modelos.values() if v > 0]
            p_justo = float(np.median(vals)) if vals else vpa
            p_teto = p_justo * (0.95 if modo_crise else 1.05)
        else:
            if lpa > 0 and vpa > 0.1: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            if div > 0: modelos['Gordon'] = div * (1+g) / (ke-g)
            if roe > 0 and vpa > 0.1: modelos['ROE Justo'] = (roe - g)/(ke - g) * vpa
            vals = [v for v in modelos.values() if v > 0 and v < preco*5]
            p_justo = float(np.median(vals)) if vals else 0
            p_teto = p_justo * (0.75 if modo_crise else 0.85)

        dados = {
            "LPA": lpa, "VPA": vpa, "ROE": roe, "DY 12m": div, "P/VP": pvp, "TIPO": tipo,
            "Margem": info.get('profitMargins', 0), "DividaLiq/Ebitda": info.get('debtToEquity', 0) # Simplificado
        }
        return p_justo, p_teto, modelos, dados

    # [MÓDULO 3] CORE ANALYTICS
    def analisar_macro(self):
        try:
            ibov = yf.download("^BVSP", period="1y", progress=False, threads=False)['Close']
            if ibov.empty: return 0, "Neutro"
            atual = ibov.iloc[-1]; mm200 = ibov.rolling(200).mean().iloc[-1]
            return (5, "🟢 Bull") if atual > mm200 else (-10, "🔴 Bear")
        except: return 0, "⚪ Indefinido"

    def analisar(self, hist, info, ticker, modo_crise, ticker_obj):
        try:
            if hist is None or hist.empty: return None
            c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])
            
            macro_score, macro_txt = self.analisar_macro()
            dy_val = self.consultar_dividendos_reais(ticker_obj)
            p_justo, p_teto, modelos, dados_fund = self.calcular_fundamentos(info, atual, ticker, modo_crise, dy_val)
            padrao_grafico = self.identificar_padroes_complexos(h, l)
            
            # Técnica
            mme9 = c.ewm(span=9).mean().iloc[-1]; mme21 = c.ewm(span=21).mean().iloc[-1]
            mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else atual
            delta = c.diff(); gain = delta.clip(lower=0).rolling(14).mean(); loss = -delta.clip(upper=0).rolling(14).mean()
            rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50
            
            # Score
            score = 50; motivos = []
            pvp = dados_fund["P/VP"]; tipo = dados_fund["TIPO"]

            # Lógica FII/Ação
            if 0.01 < pvp <= 1.00: score += 20; motivos.append("💎 P/VP Descontado")
            elif pvp > 1.50: score -= 20
            
            if tipo == "FII":
                if 0.85 <= pvp <= 1.05: score += 20
                if (dy_val/atual) > 0.10: score += 20; motivos.append("💰 DY > 10%")
            else:
                if p_justo > 0 and atual <= p_teto: score += 30; motivos.append("📉 Barato")
            
            if mme9 > mme21: score += 10
            if rsi < 30: score += 10; motivos.append("📉 Sobrevenda")
            if padrao_grafico: 
                motivos.append(f"👁️ {padrao_grafico}")
                if "Ascendente" in padrao_grafico or "Fundo" in padrao_grafico: score += 15
                if "Descendente" in padrao_grafico or "Topo" in padrao_grafico: score -= 15
            
            score += macro_score
            decisao = "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"
            dy_pct = (dy_val/atual)*100
            
            tec_data = [
                {"Ind": "Padrão", "Val": padrao_grafico or "-", "Sinal": "⚠️" if padrao_grafico else "⚪"},
                {"Ind": "P/VP", "Val": f"{pvp:.2f}x", "Sinal": "🟢" if pvp <= 1.05 else "🔴"},
                {"Ind": "RSI (14)", "Val": f"{rsi:.0f}", "Sinal": "🟢" if rsi < 30 else "⚪"},
                {"Ind": "Macro", "Val": macro_txt, "Sinal": "🟢" if macro_score > 0 else "🔴"}
            ]

            return {
                "score_ia": max(0, min(100, score)), "decisao_ia": decisao, "motivos": ", ".join(motivos),
                "preco": atual, "p_justo": p_justo, "p_teto": p_teto,
                "modelos_val": modelos, "dados_fund": dados_fund, "dy_pct": dy_pct,
                "tabela_tecnica": pd.DataFrame(tec_data), "tipo": tipo, "pvp": pvp, "hist": hist,
                "tecnica_extra": {"MME9": mme9, "MME21": mme21, "MM200": mm200}
            }
        except: return None

    # [MÓDULOS AUXILIARES]
    def rebalancear(self, df):
        tot = df["Valor Atual"].sum()
        if tot == 0: return df
        df["Meta R$"] = (df["Meta %"]/100)*tot; df["Diff R$"] = df["Meta R$"] - df["Valor Atual"]
        df["Sugestão"] = np.where(df["Diff R$"]>0, "🟢 COMPRAR", "🔴 VENDER")
        mask = df["Preço"] > 0; df.loc[mask, "Qtd Ação"] = (abs(df.loc[mask, "Diff R$"])/df.loc[mask, "Preço"]).astype(int)
        return df

    def calcular_stress_test(self, ticker, qtd, preco):
        e = qtd * preco
        return {"📉 Crash (-10%)": e*-0.10, "🔥 Crash (-30%)": e*-0.30}

    def monte_carlo(self, ret, ini, sims=1000):
        days = 252*5; r_m = ret.mean(); r_s = ret.std()
        res = ini * (1 + np.random.normal(r_m, r_s, (days, sims))).cumprod(axis=0)
        df = pd.DataFrame(res)
        return pd.DataFrame({"Média": df.mean(axis=1), "Otimista": df.quantile(0.95, axis=1), "Pessimista": df.quantile(0.05, axis=1)})

# --- 4. CACHE E GRÁFICOS ---
@st.cache_data(ttl=600)
def obter_dados_v220(ticker, modo_crise):
    motor = MotorAnalise(); t = motor.formatar_ticker(ticker)
    try:
        t_obj = yf.Ticker(t); hist = t_obj.history(period="2y")
        if hist.empty: return None
        try: info = t_obj.info
        except: info = {"symbol": t}
        return motor.analisar(hist, info, t, modo_crise, t_obj)
    except: return None

@st.cache_data(ttl=3600)
def calcular_consolidado_v220(df_dict):
    df = pd.DataFrame(df_dict); motor = MotorAnalise(); vals = []; precos = []
    for _, r in df.iterrows():
        try:
            t = motor.formatar_ticker(r["Ticker"]); h = yf.Ticker(t).history(period="1d")
            p = float(h["Close"].iloc[-1]); vals.append(r["Qtd"] * p); precos.append(p)
        except: vals.append(0.0); precos.append(0.0)
    return vals, precos

@st.cache_data(ttl=86400)
def download_longo(tickers):
    motor = MotorAnalise(); l = [motor.formatar_ticker(t) for t in tickers]
    return yf.download(l, period="5y", progress=False, threads=False)['Close']

def plotar_grafico_nativo(hist, ticker, padrao):
    try:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='Preço'))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].ewm(span=9).mean(), line=dict(color='orange'), name='MME 9'))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].ewm(span=21).mean(), line=dict(color='blue'), name='MME 21'))
        
        titulo = f"{ticker} - Padrão Detectado: {padrao}" if padrao else f"{ticker}"
        fig.update_layout(title=titulo, xaxis_rangeslider_visible=False, height=450, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    except: pass

# --- 5. INTERFACE ---
st.title("💰 Hedge Fund Ricardo v220 (Hybrid Titan)")

with st.sidebar:
    st.header("⚙️ Painel"); modo_crise = st.toggle("🔴 MODO CRISE")
    if st.button("🔄 Restaurar Carteira"):
        st.session_state.carteira_acoes = pd.DataFrame([["HGLG11", 20, 20], ["VALE3", 100, 30], ["PETR4", 200, 30], ["ITUB4", 100, 20]], columns=["Ticker", "Qtd", "Meta %"])
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])
        st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([["VALE3", 100, 50], ["HGLG11", 20, 50]], columns=["Ticker", "Qtd", "Meta %"])
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["CDB", 0.0]], columns=["Ativo", "Saldo"])

tabs = st.tabs(["📊 Dash", "⚖️ Rebalance", "🔎 Análise", "🔗 Matriz", "📡 Scanner", "🧪 Stress", "🔮 Futuro", "🛡️ Renda Fixa", "🦁 Fiscal", "⚡ Opções"])

# DASH
with tabs[0]:
    if st.button("🚀 Atualizar"):
        with st.spinner("Atualizando..."):
            vals, precos = calcular_consolidado_v220(st.session_state.carteira_acoes.to_dict())
            st.session_state.carteira_acoes["Valor Atual"] = vals; st.session_state.carteira_acoes["Preço"] = precos; st.session_state.last_update = time.time(); st.rerun()
    if "last_update" in st.session_state:
        df = st.session_state.carteira_acoes; rf = st.session_state.carteira_rf["Saldo"].sum(); rv = df["Valor Atual"].sum()
        c1, c2, c3 = st.columns(3); c1.metric("Total", f"R$ {rf+rv:,.2f}"); c2.metric("Ações/FIIs", f"R$ {rv:,.2f}"); c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
        if rv > 0: st.plotly_chart(px.pie(df, values='Valor Atual', names='Ticker', hole=0.4), use_container_width=True)

# REBALANCE
with tabs[1]:
    st.subheader("⚖️ Rebalanceamento"); st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    if "last_update" in st.session_state:
        motor = MotorAnalise(); df_bal = motor.rebalancear(st.session_state.carteira_acoes.copy())
        st.dataframe(df_bal[["Ticker", "Meta %", "Valor Atual", "Diff R$", "Sugestão", "Qtd Ação"]].style.format({"Valor Atual": "R$ {:.2f}", "Diff R$": "R$ {:.2f}", "Qtd Ação": "{:.0f}"}).applymap(lambda v: 'color: green' if v == '🟢 COMPRAR' else 'color: red' if v == '🔴 VENDER' else '', subset=['Sugestão']), use_container_width=True)

# ANÁLISE
with tabs[2]:
    c_in, c_bt = st.columns([3, 1]); t_in = c_in.text_input("Ticker", "VALE3")
    if c_bt.button("Analisar"):
        with st.spinner("Analisando..."): r = obter_dados_v220(t_in, modo_crise)
        if r:
            c1, c2, c3, c4 = st.columns(4); 
            c1.metric("Score", r['score_ia'], r['decisao_ia'])
            c2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            c3.metric("DY (12m)", f"{r['dy_pct']:.2f}%", f"R$ {r['dados_fund']['DY 12m']:.2f}")
            c4.metric("P/VP", f"{r['pvp']:.2f}x")
            
            st.success(f"**Tese ({r['tipo']}):** {r['motivos']}")
            
            # 1. GRÁFICO NATIVO (COM PADRÕES)
            st.write("#### 📉 Gráfico de Padrões (Nativo)")
            padrao_encontrado = r['tabela_tecnica']['Val'].iloc[0] if "Triângulo" in r['tabela_tecnica']['Val'].iloc[0] or "Duplo" in r['tabela_tecnica']['Val'].iloc[0] else ""
            plotar_grafico_nativo(r['hist'], t_in, padrao_encontrado)
            
            # 2. TRADINGVIEW (RESTAURADO)
            st.write("#### 🌏 TradingView (Interativo)")
            t_fmt = t_in.upper().replace(".SA", "")
            components.html(f"""<div class="tradingview-widget-container"><div id="tradingview_chart"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 500, "symbol": "BMFBOVESPA:{t_fmt}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_chart" }});</script></div>""", height=500)
            
            # 3. DADOS EMBAIXO
            st.divider()
            c_tec, c_fund, c_val = st.columns(3)
            with c_tec: 
                st.subheader("📊 Quadro Técnico")
                st.dataframe(r['tabela_tecnica'], use_container_width=True, hide_index=True)
            with c_fund: 
                st.subheader("🏗️ Fundamentos")
                d = r['dados_fund']
                st.write(f"**LPA:** R$ {d.get('LPA',0):.2f}")
                st.write(f"**VPA:** R$ {d.get('VPA',0):.2f}")
                st.write(f"**ROE:** {d.get('ROE',0)*100:.1f}%")
                st.write(f"**Margem:** {d.get('Margem',0)*100:.1f}%")
                st.write(f"**Dívida/Eq:** {d.get('DividaLiq/Ebitda',0):.2f}")
            with c_val:
                st.subheader("📐 Valuation")
                for k, v in r['modelos_val'].items(): st.metric(k, f"R$ {v:.2f}")

# MATRIZ E OUTROS
with tabs[3]: 
    if st.button("Matriz"): ts = st.session_state.carteira_acoes["Ticker"].tolist(); h = download_longo(ts); st.plotly_chart(px.imshow(h.corr(), text_auto=True), use_container_width=True)
with tabs[4]:
    if st.button("🔍 Ações Top 10"):
        l = ["VALE3", "PETR4", "ITUB4", "BBDC4", "BBAS3", "ELET3", "WEGE3", "RENT3", "SUZB3", "BPAC11"]; res = []; b = st.progress(0)
        for i, t in enumerate(l):
            d = obter_dados_v220(t, modo_crise); 
            if d: res.append({"Ticker": t, "Score": d['score_ia'], "Decisão": d['decisao_ia'], "P/VP": f"{d['pvp']:.2f}"})
            b.progress((i+1)/len(l))
        st.dataframe(pd.DataFrame(res).sort_values("Score", ascending=False), use_container_width=True)
    if st.button("🏢 FIIs Top 10"):
        l = ["HGLG11", "KNCR11", "KNIP11", "MXRF11", "XPLG11", "XPML11", "VISC11", "BTLG11", "IRDM11", "CPTS11"]; res = []; b = st.progress(0)
        for i, t in enumerate(l):
            d = obter_dados_v220(t, modo_crise); 
            if d: res.append({"Ticker": t, "Score": d['score_ia'], "Decisão": d['decisao_ia'], "P/VP": f"{d['pvp']:.2f}"})
            b.progress((i+1)/len(l))
        st.dataframe(pd.DataFrame(res).sort_values("Score", ascending=False), use_container_width=True)
with tabs[5]: 
    if st.button("Stress"): 
        m = MotorAnalise(); tot = {}
        for i, r in st.session_state.carteira_acoes.iterrows():
            d = obter_dados_v220(r["Ticker"], False)
            if d:
                res = m.calcular_stress_test(r["Ticker"], r["Qtd"], d['preco'])
                for k, v in res.items(): tot[k] = tot.get(k, 0) + v
        for k, v in tot.items(): st.metric(k, f"R$ {v:.2f}")
with tabs[6]:
    if st.button("Simular"): ts = st.session_state.carteira_acoes["Ticker"].tolist(); h = download_longo(ts); m = MotorAnalise(); st.line_chart(m.monte_carlo(h.pct_change().dropna().mean(axis=1), 100000))
with tabs[7]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
with tabs[8]:
    st.subheader("🦁 DARF"); l = st.number_input("Lucro", 0.0); v = st.number_input("Vendas", 0.0); t = st.radio("Tipo", ["Swing", "FII/Day"])
    if t == "Swing" and v < 20000: st.success("Isento")
    else: st.error(f"Pagar: {l*(0.15 if t=='Swing' else 0.20):.2f}")
with tabs[9]:
    if norm: 
        S = st.number_input("Preço", 30.0); K = st.number_input("Strike", 32.0)
        if st.button("Calc"): st.metric("Call", f"{S * norm.cdf((np.log(S/K)+0.13*0.08)/(0.3*np.sqrt(0.08))) - K * np.exp(-0.13*0.08) * norm.cdf((np.log(S/K)+0.13*0.08)/(0.3*np.sqrt(0.08)) - 0.3*np.sqrt(0.08)):.2f}")