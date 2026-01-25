# ==============================================================================
# HEDGE FUND RICARDO V251 - THE PENTAGON (FULL 10 TABS EDITION)
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import time
import yfinance as yf
import streamlit.components.v1 as components
from scipy.stats import norm, linregress
from scipy.signal import argrelextrema

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="Hedge Fund Ricardo v251", 
    layout="wide", 
    page_icon="🦁",
    initial_sidebar_state="expanded"
)

# --- 2. MOTOR DE INTELIGÊNCIA (OS 5 CÉREBROS) ---
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

    # 🧠 CÉREBRO 1: GEOMETRIA & PADRÕES
    def cerebro_grafico(self, h, l):
        try:
            n = 5
            idx_max = argrelextrema(h.values, np.greater_equal, order=n)[0]
            idx_min = argrelextrema(l.values, np.less_equal, order=n)[0]
            topos = h.iloc[idx_max].values; fundos = l.iloc[idx_min].values
            
            padroes = []
            # Triângulos
            if len(topos) >= 3 and len(fundos) >= 3:
                x_t = np.arange(len(topos)); x_f = np.arange(len(fundos))
                s_top = linregress(x_t[-3:], topos[-3:]).slope
                s_bot = linregress(x_f[-3:], fundos[-3:]).slope
                
                if s_top < -0.05 and s_bot > 0.05: padroes.append("⚠️ Triângulo Simétrico")
                elif abs(s_top) < 0.05 and s_bot > 0.05: padroes.append("🚀 Triângulo Ascendente")
                elif s_top < -0.05 and abs(s_bot) < 0.05: padroes.append("🔻 Triângulo Descendente")

            # Topo/Fundo Duplo
            if len(topos) >= 2:
                if abs(topos[-1] - topos[-2])/topos[-2] < 0.015: padroes.append("📉 Topo Duplo")
            if len(fundos) >= 2:
                if abs(fundos[-1] - fundos[-2])/fundos[-2] < 0.015: padroes.append("📈 Fundo Duplo")

            # OCO
            if len(topos) >= 3:
                if topos[-2] > topos[-3] and topos[-2] > topos[-1]:
                    if abs(topos[-3] - topos[-1])/topos[-3] < 0.05: padroes.append("💀 OCO")

            return padroes
        except: return []

    # 🧠 CÉREBRO 2: FUNDAMENTOS & VALUATION (ATUALIZADO)
    def cerebro_fundamentos(self, info, preco, ticker, modo_crise, dy_val):
        modelos = {}
        tipo = self.detectar_tipo(ticker)
        
        lpa = info.get('trailingEps', 0) or 0
        roe = info.get('returnOnEquity', 0) or 0
        div = dy_val if dy_val > 0 else (info.get('dividendRate', 0) or 0)
        
        pvp = info.get('priceToBook')
        vpa = info.get('bookValue')
        
        # Tratamento de erros de dados nulos
        if pvp is None:
            pvp = (preco / vpa) if (vpa and vpa > 0) else 0.0
        if (vpa is None or vpa == 0) and (pvp is not None and pvp > 0):
            vpa = preco / pvp
        if tipo == "FII" and (vpa is None or vpa == 0): vpa = preco; pvp = 1.0

        rf = 0.135 if modo_crise else 0.115; g = 0.03; ke = rf + 0.06

        # --- Lógica de Valuation ---
        if tipo == "FII":
            if vpa > 0: modelos['VPA'] = vpa
            if div > 0: modelos['Gordon'] = div / (rf - g + 0.02)
            if div > 0: modelos['Bazin'] = div / 0.06
            vals = [v for v in modelos.values() if v > 0]
            p_justo = float(np.median(vals)) if vals else vpa
            p_teto = p_justo * (0.95 if modo_crise else 1.05)
        else:
            # Graham
            if lpa > 0 and vpa > 0: modelos['Graham'] = (22.5 * lpa * vpa)**0.5
            # Gordon (usa dy_val que é o dividendo em reais)
            if div > 0: modelos['Gordon'] = div * (1+g) / (ke-g)
            # Bazin
            if div > 0: modelos['Bazin'] = div / 0.06
            
            # Consenso
            vals = [v for v in modelos.values() if v > 0 and v < preco*5]
            p_justo = float(np.median(vals)) if vals else 0
            p_teto = p_justo * (0.75 if modo_crise else 0.85)

        status_val = "Justo"
        if preco <= p_teto: status_val = "💎 Barato"
        elif preco > p_justo * 1.15: status_val = "💸 Caro"
        
        return {
            "p_justo": p_justo, "p_teto": p_teto, "modelos": modelos, "status": status_val,
            "dados": {"LPA": lpa, "VPA": vpa, "ROE": roe, "DY": div, "P/VP": pvp, "TIPO": tipo}
        }

    # 🧠 CÉREBRO 3: NOTÍCIAS
    def cerebro_news(self, ticker_obj):
        try:
            news = ticker_obj.news
            if not news: return "⚪ Neutro (Sem dados)", []
            score = 0
            pos = ["lucro", "alta", "dividend", "compra", "aprovado", "forte", "bonificação"]
            neg = ["prejuízo", "queda", "fraude", "divida", "risco", "fraco", "investigação"]
            manchetes = []
            for n in news[:3]:
                t = n.get('title', ''); manchetes.append(t)
                tl = t.lower()
                score += sum(1 for w in pos if w in tl)
                score -= sum(1 for w in neg if w in tl)
            sent = "🟢 Otimista" if score > 0 else "🔴 Pessimista" if score < 0 else "⚪ Neutro"
            return sent, manchetes
        except: return "⚪ Neutro", []

    # 🧠 CÉREBRO 4: TÉCNICA
    def cerebro_tecnico(self, c):
        atual = c.iloc[-1]
        mme9 = c.ewm(span=9).mean().iloc[-1]
        mme21 = c.ewm(span=21).mean().iloc[-1]
        mm200 = c.rolling(200).mean().iloc[-1] if len(c)>200 else atual
        
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rsi = 100 - (100/(1 + gain.iloc[-1]/loss.iloc[-1])) if loss.iloc[-1]!=0 else 50
        
        cruzamento = "Alta" if mme9 > mme21 else "Baixa"
        tendencia_longa = "Bull" if atual > mm200 else "Bear"
        
        return {"MME9": mme9, "MME21": mme21, "MM200": mm200, "RSI": rsi, "Cruzamento": cruzamento, "Longa": tendencia_longa}

    # 🧠 CÉREBRO 5: CENÁRIOS FUTUROS
    def cerebro_futuro(self, hist, atual):
        try:
            retornos = hist['Close'].pct_change().dropna()
            media = retornos.mean(); std = retornos.std()
            sims = 100; projecoes = []
            for _ in range(sims):
                caminho = np.random.normal(media, std, 252)
                projecoes.append(atual * (1 + caminho).cumprod()[-1])
            return {
                "Pessimista": np.percentile(projecoes, 5),
                "Realista": np.percentile(projecoes, 50),
                "Otimista": np.percentile(projecoes, 95)
            }
        except: return {"Pessimista": atual, "Realista": atual, "Otimista": atual}

    # --- SÍNTESE FINAL ---
    def analisar_completo(self, ticker, modo_crise):
        try:
            t = self.formatar_ticker(ticker)
            t_obj = yf.Ticker(t)
            hist = t_obj.history(period="2y")
            if hist.empty: return None
            
            info = t_obj.info; c = hist["Close"]; h = hist["High"]; l = hist["Low"]
            atual = float(c.iloc[-1])
            dy_val = self.consultar_dividendos_reais(t_obj) if hasattr(self, 'consultar_dividendos_reais') else 0

            res_grafico = self.cerebro_grafico(h, l)
            res_fund = self.cerebro_fundamentos(info, atual, ticker, modo_crise, self.consultar_dividendos_reais(t_obj))
            res_news, manchetes = self.cerebro_news(t_obj)
            res_tec = self.cerebro_tecnico(c)
            res_futuro = self.cerebro_futuro(hist, atual)
            
            score = 50; motivos = []
            
            # Valuation Logic for Score
            if "Barato" in res_fund["status"]: score += 25; motivos.append("💎 Valuation Barato")
            elif "Caro" in res_fund["status"]: score -= 15
            
            pvp = res_fund["dados"]["P/VP"]
            if res_fund["dados"]["TIPO"] == "FII":
                if 0.85 <= pvp <= 1.05: score += 15; motivos.append("✅ P/VP Justo")
                dy_pct = (res_fund["dados"]["DY"]/atual)*100
                if dy_pct > 10: score += 15; motivos.append(f"💰 DY Atrativo ({dy_pct:.1f}%)")
            else:
                if res_fund["p_justo"] > atual: score += 15
            
            # Técnica
            if res_tec["Cruzamento"] == "Alta": score += 15; motivos.append("📈 Cruzamento Alta (9x21)")
            else: score -= 10
            if res_tec["RSI"] < 30: score += 10; motivos.append("📉 RSI Sobrevendido")
            
            # Padrões
            if res_grafico:
                txt_padrao = ", ".join(res_grafico)
                motivos.append(f"👁️ Padrão: {txt_padrao}")
                if "Fundo" in txt_padrao or "Ascendente" in txt_padrao: score += 15
                if "Topo" in txt_padrao or "OCO" in txt_padrao: score -= 15
                
            # News
            if "Otimista" in res_news: score += 10
            elif "Pessimista" in res_news: score -= 10
            
            decisao = "🟢 COMPRA FORTE" if score >= 75 else "🟢 COMPRA" if score >= 60 else "🔴 VENDA" if score <= 40 else "⚪ NEUTRO"

            relatorio = f"""
            **1. 🏗️ Fundamentos & Valuation:** O ativo é considerado **{res_fund['status']}**. 
            O Preço Justo médio é R$ {res_fund['p_justo']:.2f}. O P/VP está em {pvp:.2f}x.
            
            **2. 📊 Técnica (Tendência):** O curto prazo indica **{res_tec['Cruzamento']}** (Médias 9x21). 
            O RSI está em {res_tec['RSI']:.0f}. No longo prazo (MM200), a tendência é **{res_tec['Longa']}**.
            
            **3. 👁️ Padrões Gráficos:** {'Nenhum padrão crítico detectado.' if not res_grafico else f'ATENÇÃO: Detectado {", ".join(res_grafico)}.'}
            
            **4. 🔮 Cenários (12 Meses):**
            - Pessimista: R$ {res_futuro['Pessimista']:.2f}
            - Realista: R$ {res_futuro['Realista']:.2f}
            - Otimista: R$ {res_futuro['Otimista']:.2f}
            
            **5. 📰 Sentimento Notícias:** {res_news}.
            """

            return {
                "ticker": ticker.upper(), "preco": atual, "score": max(0, min(100, score)), "decisao": decisao,
                "relatorio": relatorio, "motivos_curtos": motivos, "fundamentos": res_fund,
                "tecnica": res_tec, "futuro": res_futuro, "news": manchetes,
                "dy_pct": (res_fund["dados"]["DY"]/atual)*100
            }
            
        except Exception as e: return None

    def consultar_dividendos_reais(self, t_obj):
        try:
            divs = t_obj.dividends
            if divs.empty: return 0.0
            corte = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
            return divs[divs.index >= corte].sum()
        except: return 0.0

# --- 4. CACHE ---
@st.cache_data(ttl=600)
def analisar_ticker_v251(ticker, modo_crise):
    motor = MotorAnalise()
    return motor.analisar_completo(ticker, modo_crise)

@st.cache_data(ttl=3600)
def carteira_consolidada_v251(df_dict):
    df = pd.DataFrame(df_dict); motor = MotorAnalise()
    vals = []; precos = []
    for _, r in df.iterrows():
        try:
            t = motor.formatar_ticker(r["Ticker"]); h = yf.Ticker(t).history(period="1d")
            p = float(h["Close"].iloc[-1]); vals.append(r["Qtd"] * p); precos.append(p)
        except: vals.append(0.0); precos.append(0.0)
    return vals, precos

# --- 5. INTERFACE ---
st.title("💰 Hedge Fund Ricardo v251 (Full 10-Tabs)")

with st.sidebar:
    st.header("⚙️ Painel"); modo_crise = st.toggle("🔴 MODO CRISE")
    if st.button("🔄 Restaurar Carteira"):
        st.session_state.carteira_acoes = pd.DataFrame([["HGLG11", 20, 20], ["VALE3", 100, 30], ["PETR4", 200, 30], ["ITUB4", 100, 20]], columns=["Ticker", "Qtd", "Meta %"])
        st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0]], columns=["Ativo", "Saldo"])
        st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

if "carteira_acoes" not in st.session_state: st.session_state.carteira_acoes = pd.DataFrame([["VALE3", 100, 50], ["HGLG11", 20, 50]], columns=["Ticker", "Qtd", "Meta %"])
if "carteira_rf" not in st.session_state: st.session_state.carteira_rf = pd.DataFrame([["CDB", 0.0]], columns=["Ativo", "Saldo"])

# === DEFINIÇÃO DAS 10 ABAS ===
tabs = st.tabs([
    "📊 Dash", 
    "🔎 War Room", 
    "📡 Scanner", 
    "⚖️ Rebalance", 
    "🧪 Stress", 
    "🛡️ Renda Fixa", 
    "🦁 Fiscal", 
    "🌍 Macro",
    "🎰 Opções",
    "₿ Cripto"
])

# 1. DASH
with tabs[0]:
    if st.button("🚀 Atualizar"):
        with st.spinner("Atualizando..."):
            vals, precos = carteira_consolidada_v251(st.session_state.carteira_acoes.to_dict())
            st.session_state.carteira_acoes["Valor Atual"] = vals; st.session_state.carteira_acoes["Preço"] = precos; st.session_state.last_update = time.time(); st.rerun()
    if "last_update" in st.session_state:
        df = st.session_state.carteira_acoes; rf = st.session_state.carteira_rf["Saldo"].sum(); rv = df["Valor Atual"].sum()
        c1, c2, c3 = st.columns(3); c1.metric("Total", f"R$ {rf+rv:,.2f}"); c2.metric("Renda Variável", f"R$ {rv:,.2f}"); c3.metric("Renda Fixa", f"R$ {rf:,.2f}")

# 2. ANÁLISE (WAR ROOM)
with tabs[1]:
    c_in, c_bt = st.columns([3, 1]); t_in = c_in.text_input("Ticker", "VALE3")
    if c_bt.button("Analisar"):
        with st.spinner(f"Ativando os 5 Cérebros para {t_in}..."):
            r = analisar_ticker_v251(t_in, modo_crise)
        if r:
            # Metrics Top Row
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Score IA", r['score'], r['decisao'])
            c2.metric("Preço Atual", f"R$ {r['preco']:.2f}")
            c3.metric("Preço Justo (Médio)", f"R$ {r['fundamentos']['p_justo']:.2f}")
            c4.metric("DY (12m)", f"{r['dy_pct']:.2f}%")
            c5.metric("P/VP", f"{r['fundamentos']['dados']['P/VP']:.2f}x")
            
            st.info(r['relatorio'])
            
            # TradingView Chart
            t_fmt = t_in.upper().replace(".SA", "")
            components.html(f"""<div class="tradingview-widget-container"><div id="tradingview_chart"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 500, "symbol": "BMFBOVESPA:{t_fmt}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_chart" }});</script></div>""", height=500)
            
            st.divider()
            c_tec, c_fund, c_cen = st.columns(3)
            
            with c_tec: 
                st.subheader("📊 Técnica")
                st.write(f"**Tendência Curta:** {r['tecnica']['Cruzamento']}")
                st.write(f"**Tendência Longa:** {r['tecnica']['Longa']}")
                st.write(f"**RSI (14):** {r['tecnica']['RSI']:.0f}")
                st.write(f"**MME 9:** {r['tecnica']['MME9']:.2f}")
                st.write(f"**MME 21:** {r['tecnica']['MME21']:.2f}")

            with c_fund: 
                st.subheader("🏗️ Fundamentos")
                d = r['fundamentos']['dados']
                st.write(f"**LPA:** R$ {d.get('LPA',0):.2f}")
                st.write(f"**VPA:** R$ {d.get('VPA',0):.2f}")
                st.write(f"**ROE:** {d.get('ROE',0)*100:.1f}%")
                st.write(f"**Status:** {r['fundamentos']['status']}")

                # --- NOVO BLOCO DE VALUATION VISUAL ---
                mods = r['fundamentos']['modelos']
                
                # Prepara variáveis para exibição (evita erro se chave não existir)
                v_graham = f"R$ {mods['Graham']:.2f}" if 'Graham' in mods else "N/A"
                v_bazin = f"R$ {mods['Bazin']:.2f}" if 'Bazin' in mods else "N/A"
                v_gordon = f"R$ {mods['Gordon']:.2f}" if 'Gordon' in mods else "N/A"
                v_vpa_fii = f"R$ {mods['VPA']:.2f}" if 'VPA' in mods else None

                if r['fundamentos']['dados']['TIPO'] == 'FII' and v_vpa_fii:
                     st.markdown(f"""
                    <div style="margin-top: 15px; padding: 15px; background-color: white; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                        <h5 style="margin: 0 0 10px 0; border-bottom: 2px solid #FF9800; display: inline-block; color: #333;">🏢 Valuation FII</h5>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;"><span style="color:#555">VP (Justo):</span><span style="font-weight:bold; color:#E65100">{v_vpa_fii}</span></div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;"><span style="color:#555">Bazin (6%):</span><span style="font-weight:bold; color:#1565C0">{v_bazin}</span></div>
                        <div style="display: flex; justify-content: space-between;"><span style="color:#555">Gordon:</span><span style="font-weight:bold; color:#6A1B9A">{v_gordon}</span></div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="margin-top: 15px; padding: 15px; background-color: white; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                        <h5 style="margin: 0 0 10px 0; border-bottom: 2px solid #4CAF50; display: inline-block; color: #333;">💎 Valuation Ação</h5>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;"><span style="color:#555">Graham:</span><span style="font-weight:bold; color:#2E7D32">{v_graham}</span></div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;"><span style="color:#555">Bazin (6%):</span><span style="font-weight:bold; color:#1565C0">{v_bazin}</span></div>
                        <div style="display: flex; justify-content: space-between;"><span style="color:#555">Gordon:</span><span style="font-weight:bold; color:#6A1B9A">{v_gordon}</span></div>
                        <div style="margin-top: 8px; font-size: 0.75em; color: #999; text-align: center;">*Gordon c/ g=3% e ke=12%</div>
                    </div>
                    """, unsafe_allow_html=True)
                # ---------------------------------------

            with c_cen:
                st.subheader("🔮 Cenários (12m)")
                st.metric("Otimista", f"R$ {r['futuro']['Otimista']:.2f}", delta="Céu de Brigadeiro")
                st.metric("Realista", f"R$ {r['futuro']['Realista']:.2f}")
                st.metric("Pessimista", f"R$ {r['futuro']['Pessimista']:.2f}", delta="-Apertem os cintos", delta_color="inverse")
                
            st.subheader("📰 Manchetes Recentes")
            for m in r['news']: st.text(f"• {m}")

# 3. SCANNER
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("🔍 Ações (IBOV)"):
            l = ["VALE3", "PETR4", "ITUB4", "BBDC4", "BBAS3", "ELET3", "WEGE3", "RENT3", "SUZB3", "BPAC11"]; res = []; b = st.progress(0)
            for i, t in enumerate(l):
                d = analisar_ticker_v251(t, modo_crise); 
                if d: res.append({"Ticker": t, "Score": d['score'], "Decisão": d['decisao'], "P/VP": f"{d['fundamentos']['dados']['P/VP']:.2f}"})
                b.progress((i+1)/len(l))
            st.dataframe(pd.DataFrame(res).sort_values("Score", ascending=False), use_container_width=True)
    with c2:
        if st.button("🏢 FIIs (IFIX)"):
            l = ["HGLG11", "KNCR11", "KNIP11", "MXRF11", "XPLG11", "XPML11", "VISC11", "BTLG11", "IRDM11", "CPTS11"]; res = []; b = st.progress(0)
            for i, t in enumerate(l):
                d = analisar_ticker_v251(t, modo_crise); 
                if d: res.append({"Ticker": t, "Score": d['score'], "Decisão": d['decisao'], "P/VP": f"{d['fundamentos']['dados']['P/VP']:.2f}"})
                b.progress((i+1)/len(l))
            st.dataframe(pd.DataFrame(res).sort_values("Score", ascending=False), use_container_width=True)

# 4. REBALANCE
with tabs[3]:
    st.subheader("⚖️ Rebalanceamento"); st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    if "last_update" in st.session_state:
        df = st.session_state.carteira_acoes.copy(); tot = df["Valor Atual"].sum()
        if tot > 0:
            df["Meta R$"] = (df["Meta %"]/100)*tot; df["Diff R$"] = df["Meta R$"] - df["Valor Atual"]
            df["Sugestão"] = np.where(df["Diff R$"]>0, "🟢 COMPRAR", "🔴 VENDER")
            st.dataframe(df[["Ticker", "Valor Atual", "Meta R$", "Sugestão"]], use_container_width=True)

# 5. STRESS
with tabs[4]: 
    if st.button("Simular Stress"): 
        tot = {}
        for i, r in st.session_state.carteira_acoes.iterrows():
            d = analisar_ticker_v251(r["Ticker"], False)
            if d:
                e = r["Qtd"] * d['preco']
                res = {"📉 Crash (-10%)": e*-0.10, "🔥 Crash (-30%)": e*-0.30}
                for k, v in res.items(): tot[k] = tot.get(k, 0) + v
        for k, v in tot.items(): st.metric(k, f"R$ {v:.2f}")

# 6. RENDA FIXA
with tabs[5]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")

# 7. FISCAL
with tabs[6]:
    st.subheader("🦁 DARF"); l = st.number_input("Lucro", 0.0); v = st.number_input("Vendas", 0.0); t = st.radio("Tipo", ["Swing", "FII/Day"])
    if t == "Swing" and v < 20000: st.success("Isento")
    else: st.error(f"Pagar: {l*(0.15 if t=='Swing' else 0.20):.2f}")

# 8. MACROECONOMIA
with tabs[7]:
    st.subheader("🌍 Painel Macro")
    c1, c2, c3 = st.columns(3)
    c1.metric("Dólar (USD/BRL)", "5.85", "0.5%")
    c2.metric("S&P 500", "5,200", "-0.2%")
    c3.metric("Selic Meta", "11.25%", "Neutro")
    st.write("---")
    st.info("Aqui você pode conectar APIs do Banco Central (SGS) para puxar IPCA, PIB, etc.")

# 9. OPÇÕES (DERIVATIVOS)
with tabs[8]:
    st.subheader("🎰 Estratégias de Opções")
    st.write("Monitoramento de Volatilidade Implícita e Gregas.")
    st.warning("🚧 Módulo em desenvolvimento. Conecte dados da B3 para exibir a grade de opções.")

# 10. CRIPTOATIVOS
with tabs[9]:
    st.subheader("₿ Mercado Cripto")
    if st.button("Atualizar Cripto"):
        tickers_cripto = ["BTC-USD", "ETH-USD", "SOL-USD"]
        c_cols = st.columns(len(tickers_cripto))
        for i, tick in enumerate(tickers_cripto):
            try:
                p = yf.Ticker(tick).history(period="1d")['Close'].iloc[-1]
                c_cols[i].metric(tick, f"$ {p:,.2f}")
            except:
                c_cols[i].metric(tick, "Erro")