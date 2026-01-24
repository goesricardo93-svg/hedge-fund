import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np
import re

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v128.2", layout="wide", page_icon="🏦")

# Auto-Limpeza de Cache na atualização de versão para evitar KeyError
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v128.2":
    st.session_state.versao_sistema = "v128.2"
    st.cache_data.clear() # <--- FORÇA A LIMPEZA DO CACHE ANTIGO
    st.toast("Sistema Atualizado v128.2: Cache Limpo e Estável!", icon="🛡️")

# ======================================================
# 2. IMPORTAÇÃO
# ======================================================
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    from scanner import executar_scanner
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
except Exception as e: st.error(f"Erro: {e}"); st.stop()

# ======================================================
# 3. DADOS
# ======================================================
def carregar_carteira_padrao():
    dados = [
        ["ALZR11.SA", 100, 10.81, "FIIs-Tijolo"], ["BBAS3.SA", 1703, 24.48, "Ações-Bancos"], 
        ["BBSE3.SA", 55, 35.64, "Ações-Seguridade"], ["BTCI11.SA", 502, 10.16, "FIIs-Papel"], 
        ["BTLG11.SA", 60, 98.50, "FIIs-Tijolo"], ["CCME11.SA", 152, 8.55, "FIIs-Outros"],
        ["CMIG4.SA", 1644, 11.12, "Ações-Elétricas"], ["CPLE3.SA", 617, 9.64, "Ações-Elétricas"], 
        ["CPSH11.SA", 169, 10.10, "FIIs-Tijolo"], ["CPTS11.SA", 276, 8.52, "FIIs-Papel"], 
        ["CXSE3.SA", 800, 14.20, "Ações-Seguridade"], ["EQTL3.SA", 200, 30.21, "Ações-Elétricas"],
        ["HGCR11.SA", 20, 95.81, "FIIs-Papel"], ["HGLG11.SA", 20, 158.03, "FIIs-Tijolo"], 
        ["ITSA4.SA", 1174, 9.63, "Ações-Bancos"], ["IVVB11.SA", 6, 366.97, "Exterior"], 
        ["KLBN4.SA", 2323, 3.63, "Ações-Commodities"], ["KNCR11.SA", 27, 103.11, "FIIs-Papel"],
        ["KNHF11.SA", 15, 93.23, "FIIs-Papel"], ["KNRI11.SA", 30, 152.49, "FIIs-Tijolo"], 
        ["KNSC11.SA", 373, 8.78, "FIIs-Papel"], ["KNUQ11.SA", 16, 102.45, "FIIs-Outros"], 
        ["PETR4.SA", 900, 32.07, "Ações-Commodities"], ["SAPR11.SA", 300, 37.97, "Ações-Outros"],
        ["TAEE4.SA", 1000, 11.36, "Ações-Elétricas"], ["VALE3.SA", 152, 54.79, "Ações-Commodities"], 
        ["VGIR11.SA", 296, 9.58, "FIIs-Papel"], ["VISC11.SA", 16, 109.70, "FIIs-Tijolo"], 
        ["XPCA11.SA", 110, 8.77, "FIIs-Outros"], ["XPLG11.SA", 26, 102.31, "FIIs-Tijolo"],
        ["XPML11.SA", 10, 106.05, "FIIs-Tijolo"]
    ]
    return pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_acoes" not in st.session_state or st.session_state.carteira_acoes.empty:
    st.session_state.carteira_acoes = carregar_carteira_padrao()
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós-Fixado"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# --- HELPERS ---
def formatar_ticker_global(t):
    t = str(t).upper().strip()
    if t in ["BTC", "ETH", "SOL", "USDT"]: return f"{t}-USD"
    if "." in t: return t
    if any(char.isdigit() for char in t): return f"{t}.SA"
    return t

def formatar_ticker_b3(cod):
    cod = str(cod).upper().strip()
    if " - " in cod: cod = cod.split(" - ")[0].strip()
    elif "-" in cod: cod = cod.split("-")[0].strip()
    if cod.endswith("F"): cod = cod[:-1]
    if not cod.endswith(".SA") and len(cod) <= 6: return f"{cod}.SA"
    return cod

def limpar_valor_monetario(valor):
    try:
        if isinstance(valor, (int, float)): return float(valor)
        v = str(valor).replace("R$", "").strip()
        v = v.replace(".", "").replace(",", ".")
        return float(v)
    except: return 0.0

# --- IMPORTADOR B3 ---
def encontrar_coluna(df, palavras_chave):
    colunas_lower = [str(c).lower() for c in df.columns]
    for chave in palavras_chave:
        for i, col in enumerate(colunas_lower):
            if chave in col: return df.columns[i]
    return None

def processar_excel_b3(arquivo):
    try:
        xls_raw = pd.read_excel(arquivo, sheet_name=None, header=None)
        posicao_consolidada = {}
        carteira_rf_nova = []
        log_msgs = []
        for nome_aba, df_raw in xls_raw.items():
            nome_limpo = str(nome_aba).lower()
            target_row = -1
            for i, row in df_raw.head(20).iterrows():
                linha = " ".join(row.astype(str).values.tolist()).lower()
                if any(x in linha for x in ["produto", "código", "ativo", "título", "vencimento"]):
                    target_row = i; break
            if target_row == -1: continue
            df = pd.read_excel(arquivo, sheet_name=nome_aba, header=target_row)
            df = df.loc[:, ~df.columns.duplicated()]
            col_ticker = encontrar_coluna(df, ["código", "negociação", "ticker"])
            col_produto = encontrar_coluna(df, ["produto", "ativo", "título", "especificação"]) 
            col_qtd = encontrar_coluna(df, ["quantidade", "qtd", "disponível"])
            col_saldo = encontrar_coluna(df, ["valor líquido", "valor atual", "saldo", "valor total", "bruto"])
            if any(x in nome_limpo for x in ["empréstimo", "ações", "fundo", "etf"]):
                col_ref = col_ticker if col_ticker else col_produto
                if col_ref and col_qtd:
                    for _, row in df.iterrows():
                        valor_ref = row[col_ref]
                        if pd.isna(valor_ref): continue
                        ticker = formatar_ticker_b3(valor_ref)
                        qtd = limpar_valor_monetario(row[col_qtd])
                        if qtd <= 0: continue
                        setor = "Ações-Outros"
                        if "fundo" in nome_limpo: setor = "FIIs-Indefinido"
                        elif "etf" in nome_limpo: setor = "Exterior"
                        elif "ações" in nome_limpo: setor = "Ações-Outros"
                        if ticker not in posicao_consolidada: posicao_consolidada[ticker] = {'qtd': 0.0, 'setor': setor}
                        if setor != "Ações-Outros": posicao_consolidada[ticker]['setor'] = setor
                        posicao_consolidada[ticker]['qtd'] += qtd
                    log_msgs.append(f"✅ {nome_aba}: RV OK")
            elif "tesouro" in nome_limpo or "renda fixa" in nome_limpo:
                if col_produto and col_saldo:
                    for _, row in df.iterrows():
                        prod = row[col_produto]
                        saldo = limpar_valor_monetario(row[col_saldo])
                        if pd.notna(prod) and saldo > 0:
                            tipo = "Tesouro Direto" if "tesouro" in nome_limpo else "CRI/CRA/LCI/LCA"
                            carteira_rf_nova.append([prod, saldo, tipo])
                    log_msgs.append(f"✅ {nome_aba}: RF OK")
        carteira_rv_final = []
        for ticker, dados in posicao_consolidada.items():
            if dados['qtd'] > 0: carteira_rv_final.append([ticker, dados['qtd'], 0.0, dados['setor']])
        return carteira_rv_final, carteira_rf_nova, "\n".join(log_msgs)
    except Exception as e: return None, None, f"Erro: {str(e)}"

# --- ANALYTICS ---
@st.cache_data(ttl=300)
def obter_dados(ticker, modo_crise):
    t = formatar_ticker_global(ticker)
    return MotorAnalise().analisar(yf.Ticker(t).history(period="2y"), yf.Ticker(t).info, t, modo_crise)

@st.cache_data(ttl=86400)
def download_longo(tickers):
    l = [formatar_ticker_global(t) for t in tickers]
    try: return yf.download(l, period="5y", progress=False)['Close']
    except: return pd.DataFrame()

def calcular_consolidado():
    trf = st.session_state.carteira_rf["Saldo Atual"].sum()
    df = st.session_state.carteira_acoes.copy()
    tickers = [formatar_ticker_global(t) for t in df["Ticker"]]
    try: prices = yf.download(tickers, period="1d", progress=False)['Close'].iloc[-1]
    except: prices = pd.Series()
    vals = []
    for _, r in df.iterrows():
        t = formatar_ticker_global(r["Ticker"])
        try: p = float(prices[t])
        except: 
            d = obter_dados(t, False)
            p = d['preco'] if d else 0.0
        vals.append(r["Qtd"] * p)
    df["Valor Atual"] = vals
    return trf, sum(vals), df

# ======================================================
# UI - DASHBOARD
# ======================================================
st.title("💰 Hedge Fund Ricardo v128 (Robust)")

with st.sidebar:
    st.header("⚙️ Risco")
    modo_crise = st.toggle("🔴 MODO CRISE", value=False)
    if modo_crise: st.error("⚠️ DEFESA ATIVA")
    
    st.divider()
    b3_file = st.file_uploader("📂 Importar B3", type=['xlsx'])
    if b3_file and st.button("Processar B3"):
        rv, rf, log = processar_excel_b3(b3_file)
        if rv: 
            st.session_state.carteira_acoes = pd.DataFrame(rv, columns=["Ticker", "Qtd", "PM", "Setor"])
            if rf: st.session_state.carteira_rf = pd.DataFrame(rf, columns=["Ativo", "Saldo Atual", "Tipo"])
            st.success("Dados B3 Importados!")
        else: st.error(log)
    
    st.divider()
    if st.button("🆘 Restaurar Padrão"): 
        st.session_state.carteira_acoes = carregar_carteira_padrao(); st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

tabs = st.tabs(["📊 Dash", "🔎 Análise Completa", "🧪 Stress", "🔗 Correlação", "💼 Carteira", "🏢 Scanner", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

with tabs[0]:
    rf, rv, df_rv = calcular_consolidado()
    c1, c2, c3 = st.columns(3)
    c1.metric("AUM Total", f"R$ {rf+rv:,.2f}")
    c2.metric("Renda Variável", f"R$ {rv:,.2f}")
    c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
    if not df_rv.empty:
        df_g = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
        if rf > 0: df_g = pd.concat([df_g, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": rf}])])
        st.plotly_chart(px.pie(df_g, values='Valor Atual', names='Setor', title="Alocação"), use_container_width=True)

# ABA 1: ANÁLISE COMPLETA (CORRIGIDA COM .get())
with tabs[1]:
    ticker = st.text_input("Ticker", "VALE3")
    if st.button("Analisar (Dados Brutos)"):
        r = obter_dados(ticker, modo_crise)
        if r:
            # 1. SCOREBOARD
            st.markdown("### 1. Painel de Controle")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Score Final", f"{r.get('score_ia', 0)}/100", r.get('decisao_ia','-'))
            c2.metric("Qualidade", f"{r.get('score_qualidade',0)}/100")
            c3.metric("Convicção", f"{r.get('score_conviccao',0)}/100")
            c4.metric("Sentimento", f"{r.get('macro','-')}", r.get('news','-'))
            st.info(f"**Tese:** {r.get('motivos','')}")
            if r.get('alertas'): st.error(f"**Alertas:** {r.get('alertas')}")
            st.divider()

            # 2. VALUATION
            st.markdown("### 2. Fundamentos (Deep Dive)")
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Preço Tela", f"R$ {r.get('preco',0):.2f}")
            v2.metric("Preço Justo", f"R$ {r.get('p_justo',0):.2f}")
            v3.metric("Preço Teto", f"R$ {r.get('p_teto',0):.2f}")
            v4.metric("Margem Seg.", f"{r.get('margem',0)*100:.0f}%")
            
            # Modelos Individuais (Safe Access)
            modelos = r.get('modelos_val', {})
            if models := modelos:
                st.write("#### 📐 Modelos Matemáticos")
                cols_mod = st.columns(len(models))
                idx=0
                for k, v in models.items():
                    cols_mod[idx].metric(k, f"R$ {v:.2f}")
                    idx+=1
            else: st.warning("Dados insuficientes para Valuation.")

            # Dados Brutos Fundamentais
            st.write("#### 🏗️ Indicadores Estruturais")
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("P/VP", f"{r.get('pvp',0):.2f}")
            f2.metric("ROE", f"{r.get('roe',0)*100:.1f}%")
            f3.metric("DY (12m)", f"{r.get('dy_anual',0):.2f}%")
            f4.metric("Dívida/EBITDA", f"{r.get('divida_ebitda',0):.2f}")
            f5.metric("Margem Líq.", f"{r.get('margem_liq',0)*100:.1f}%")
            
            d_fund = r.get('dados_fund', {})
            if d_fund:
                f6, f7, f8, f9 = st.columns(4)
                f6.metric("LPA (Lucro)", f"R$ {d_fund.get('LPA',0):.2f}")
                f7.metric("VPA (Livro)", f"R$ {d_fund.get('VPA',0):.2f}")
                f8.metric("Div. Anual Est.", f"R$ {d_fund.get('Div. Anual',0):.2f}")
                f9.metric("Ke (Custo Cap.)", f"{d_fund.get('Ke',0)*100:.1f}%")

            st.divider()

            # 3. TÉCNICA
            st.markdown("### 3. Raio-X Técnico")
            t1, t2, t3, t4, t5 = st.columns(5)
            rsi = r.get('rsi', 50)
            t1.metric("RSI (14)", f"{rsi:.0f}", delta="Sobrecompra" if rsi>70 else "Sobrevenda" if rsi<30 else "Neutro")
            t2.metric("MME 9", f"R$ {r.get('mme9',0):.2f}")
            t3.metric("MME 21", f"R$ {r.get('mme21',0):.2f}")
            t4.metric("MM 200", f"R$ {r.get('mm200',0):.2f}")
            
            probs = r.get('probs', {})
            vol_anual = probs.get('volatilidade_anual', 0) if probs else 0
            t5.metric("Volatilidade", f"{vol_anual*100:.1f}%")
            
            st.write(f"**Padrão Gráfico:** {r.get('padrao_grafico') or 'Nenhum'} | **Candle:** {r.get('candle') or 'Normal'}")

            if probs:
                st.caption("🎲 **Projeção Estatística (21 dias):**")
                p1, p2, p3 = st.columns(3)
                p1.metric("Otimista (+2σ)", f"R$ {probs.get('otimista',0):.2f}")
                p2.metric("Base (±1σ)", f"R$ {probs.get('base_min',0):.2f} - {probs.get('base_max',0):.2f}")
                p3.metric("Pessimista (-2σ)", f"R$ {probs.get('pessimista',0):.2f}")
            
            t_fmt = formatar_ticker_global(ticker)
            symbol = f"BMFBOVESPA:{t_fmt.replace('.SA','')}"
            components.html(f"""<div class="tradingview-widget-container"><div id="tv"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 400, "symbol": "{symbol}", "interval": "D", "theme": "light", "container_id": "tv" }});</script></div>""", height=400)

with tabs[2]: # Stress
    if st.button("Stress Test"):
        motor = MotorAnalise(); total_perda = {}; prog = st.progress(0)
        for i, row in st.session_state.carteira_acoes.iterrows():
            t = formatar_ticker_global(row["Ticker"])
            res = motor.calcular_stress_test(t, row["Qtd"], obter_dados(t, False)['preco'])
            for c, v in res.items(): total_perda[c] = total_perda.get(c, 0) + v
            prog.progress((i+1)/len(st.session_state.carteira_acoes))
        prog.empty()
        for c, p in total_perda.items(): st.metric(c, f"R$ {p:,.2f}", delta_color="inverse")

with tabs[3]: # Correlação
    if st.button("Matriz"): 
        tickers = [formatar_ticker_global(t) for t in st.session_state.carteira_acoes["Ticker"]]
        corr = yf.download(tickers, period="6mo", progress=False)['Close'].corr()
        st.plotly_chart(px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r"))

# DEMAIS ABAS
with tabs[4]: st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
with tabs[5]: 
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Escanear Ações"): st.dataframe(executar_scanner("ACOES"))
    with c2:
        if st.button("Escanear FIIs"): st.dataframe(executar_scanner("FIIS"))

with tabs[6]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)

with tabs[7]:
    st.subheader("🔮 Previsão de Futuro")
    if st.button("Rodar Monte Carlo"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: 
            retornos = h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna()
            val_atual = st.session_state.carteira_acoes["Qtd"].mul(h.iloc[-1].values, fill_value=0).sum() if not h.empty else 100000
            sim = MotorAnalise().monte_carlo_carteira(retornos, val_atual, 2000)
            st.line_chart(sim)

with tabs[8]:
    st.subheader("🦁 Fiscal")
    if calcular_darf: st.table(calcular_darf(st.session_state.carteira_acoes))
    else: st.warning("Módulo tax.py ausente")

with tabs[9]:
    st.subheader("⚡ Opções")
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1: 
            S = st.number_input("Preço Atual", 30.0)
            K = st.number_input("Strike", 32.0)
        with c2: 
            T_dias = st.number_input("Dias Vencimento", 30)
            sig = st.number_input("Volatilidade %", 30.0) / 100.0
        if st.button("Calcular"):
            bs = BlackScholes(S, K, T_dias/365, 0.13, sig, "call")
            g = bs.calcular_gregas()
            st.write(g)
    else: st.warning("Módulo options.py ausente")