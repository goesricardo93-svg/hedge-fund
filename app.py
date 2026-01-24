import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np
import re

# ======================================================
# 1. CONFIGURAÇÃO E CACHE RESET
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v132", layout="wide", page_icon="🏦")

if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v132":
    st.session_state.versao_sistema = "v132"
    st.cache_data.clear() # Limpa cache antigo para evitar conflitos de versão
    st.toast("Sistema v132 Full Stack Carregado!", icon="🚀")

# ======================================================
# 2. IMPORTAÇÃO SEGURA
# ======================================================
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    from scanner import executar_scanner
    # Tenta importar módulos opcionais, mas não quebra se faltar
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
except Exception as e:
    st.error(f"Erro ao carregar módulos: {e}")
    st.stop()

# ======================================================
# 3. FUNÇÕES DE DADOS E CARTEIRA
# ======================================================
def carregar_carteira_padrao():
    # Sua lista completa original
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
if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([
        {"Setor": "Renda Fixa", "Meta (%)": 20.0}, {"Setor": "Exterior", "Meta (%)": 15.0},
        {"Setor": "Ações-Bancos", "Meta (%)": 10.0}, {"Setor": "Ações-Elétricas", "Meta (%)": 10.0},
        {"Setor": "Ações-Seguridade", "Meta (%)": 5.0}, {"Setor": "Ações-Commodities", "Meta (%)": 5.0},
        {"Setor": "Ações-Outros", "Meta (%)": 5.0}, {"Setor": "FIIs-Papel", "Meta (%)": 15.0},
        {"Setor": "FIIs-Tijolo", "Meta (%)": 10.0}, {"Setor": "FIIs-Outros", "Meta (%)": 5.0}
    ])

# --- HELPERS ---
def formatar_ticker_global(t):
    t = str(t).upper().strip()
    if any(char.isdigit() for char in t) and "." not in t: return f"{t}.SA"
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

# --- IMPORTADOR B3 V115 (Completo) ---
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
                        if pd.isna(row[col_ref]): continue
                        t = formatar_ticker_b3(row[col_ref])
                        q = limpar_valor_monetario(row[col_qtd])
                        if q > 0:
                            s = "Ações-Outros"
                            if "fundo" in nome_limpo: s = "FIIs-Indefinido"
                            if t not in posicao_consolidada: posicao_consolidada[t] = {'qtd': 0.0, 'setor': s}
                            posicao_consolidada[t]['qtd'] += q
                    log_msgs.append(f"✅ RV: {nome_aba}")
            elif "renda fixa" in nome_limpo or "tesouro" in nome_limpo:
                if col_produto and col_saldo:
                    for _, row in df.iterrows():
                        p = row[col_produto]
                        s = limpar_valor_monetario(row[col_saldo])
                        if s > 0: carteira_rf_nova.append([p, s, "Renda Fixa"])
                    log_msgs.append(f"✅ RF: {nome_aba}")
        
        rv_final = [[k, v['qtd'], 0.0, v['setor']] for k, v in posicao_consolidada.items()]
        return rv_final, carteira_rf_nova, "\n".join(log_msgs)
    except Exception as e: return None, None, f"Erro: {str(e)}"

# --- ANALYTICS BLINDADO (v132) ---
# 'show_spinner=False' evita o erro de Threading em loops
@st.cache_data(ttl=300, show_spinner=False)
def obter_dados(ticker, modo_crise):
    t = formatar_ticker_global(ticker)
    
    # 1. Histórico
    try:
        ticker_obj = yf.Ticker(t)
        hist = ticker_obj.history(period="2y")
        if hist.empty: return None
    except: return None

    # 2. Fundamentos (Com proteção contra bloqueio do Yahoo)
    try:
        info = ticker_obj.info
    except Exception:
        # Se bloquear, cria um info falso para não quebrar o código
        info = {"symbol": t, "longName": t, "quoteType": "EQUITY"}
    
    # 3. Chama o Motor
    return MotorAnalise().analisar(hist, info, t, modo_crise)

@st.cache_data(ttl=86400, show_spinner=False)
def download_longo(tickers):
    l = [formatar_ticker_global(t) for t in tickers]
    try: return yf.download(l, period="5y", progress=False)['Close']
    except: return pd.DataFrame()

def calcular_consolidado():
    trf = st.session_state.carteira_rf["Saldo Atual"].sum()
    df = st.session_state.carteira_acoes.copy()
    tickers = [formatar_ticker_global(t) for t in df["Ticker"]]
    
    # Download em lote para performance
    prices = pd.Series()
    try: 
        data = yf.download(tickers, period="1d", progress=False)['Close']
        if not data.empty: prices = data.iloc[-1]
    except: pass
    
    vals = []
    for _, r in df.iterrows():
        t = formatar_ticker_global(r["Ticker"])
        try: 
            if t in prices: p = float(prices[t])
            else: 
                d = obter_dados(t, False)
                p = d.get('preco', 0) if d else 0.0
        except: p = 0.0
        vals.append(r["Qtd"] * p)
    
    df["Valor Atual"] = vals
    return trf, sum(vals), df

# ======================================================
# UI - DASHBOARD PRINCIPAL
# ======================================================
st.title("💰 Hedge Fund Ricardo v132 (Ultimate)")

with st.sidebar:
    st.header("⚙️ Risco")
    modo_crise = st.toggle("🔴 MODO CRISE", value=False)
    if modo_crise: st.error("⚠️ PROTOCOLO DEFENSIVO ATIVO")
    
    st.divider()
    b3_file = st.file_uploader("📂 Importar B3 (Excel)", type=['xlsx'])
    if b3_file and st.button("Processar"):
        rv, rf, log = processar_excel_b3(b3_file)
        if rv: 
            st.session_state.carteira_acoes = pd.DataFrame(rv, columns=["Ticker", "Qtd", "PM", "Setor"])
            if rf: st.session_state.carteira_rf = pd.DataFrame(rf, columns=["Ativo", "Saldo Atual", "Tipo"])
            st.success("Dados Atualizados!")
        else: st.error(log)
    
    st.divider()
    if st.button("🆘 Restaurar Padrão"): 
        st.session_state.carteira_acoes = carregar_carteira_padrao(); st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

# LISTA COMPLETA DE ABAS
tabs = st.tabs([
    "📊 Dash", 
    "🔎 Análise", 
    "🧪 Stress", 
    "🔗 Correlação", 
    "💼 Carteira", 
    "🏢 Scanner", 
    "🛡️ Renda Fixa", 
    "💰 Futuro", 
    "🦁 Fiscal", 
    "⚡ Opções"
])

# --- ABA 0: DASH ---
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

# --- ABA 1: ANÁLISE DEEP DIVE ---
with tabs[1]:
    ticker = st.text_input("Ticker", "VALE3")
    if st.button("Analisar (Full Data)"):
        r = obter_dados(ticker, modo_crise)
        if r:
            # 1. Score
            st.markdown("### 1. Visão do Gestor (CIO)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Score Final", f"{r.get('score_ia')}/100", r.get('decisao_ia'))
            c2.metric("Qualidade", f"{r.get('score_qualidade')}/100", "Fundamentos")
            c3.metric("Convicção", f"{r.get('score_conviccao')}/100", "Técnica")
            c4.metric("Sentimento", f"{r.get('macro')}", r.get('news'))
            st.info(f"**Tese:** {r.get('motivos')}")
            if r.get('alertas'): st.error(f"**Riscos:** {r.get('alertas')}")
            st.divider()

            # 2. Valuation
            st.markdown("### 2. Visão Fundamentalista")
            if not r.get('modelos_val'): st.warning("⚠️ Yahoo bloqueou fundamentos.")
            
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Preço Tela", f"R$ {r.get('preco',0):.2f}")
            v2.metric("Preço Justo", f"R$ {r.get('p_justo',0):.2f}")
            v3.metric("Preço Teto", f"R$ {r.get('p_teto',0):.2f}")
            v4.metric("Margem Seg.", f"{r.get('margem',0)*100:.0f}%")
            
            # Modelos Individuais
            modelos = r.get('modelos_val', {})
            if modelos:
                st.caption("Detalhamento dos Modelos:")
                cols_mod = st.columns(len(modelos))
                idx=0
                for k, v in modelos.items():
                    cols_mod[idx].metric(k, f"R$ {v:.2f}")
                    idx+=1
            
            # Brutos
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("P/VP", f"{r.get('pvp',0):.2f}")
            f2.metric("ROE", f"{r.get('roe',0)*100:.1f}%")
            f3.metric("DY (12m)", f"{r.get('dy_anual',0):.2f}%")
            f4.metric("Dívida/EBITDA", f"{r.get('divida_ebitda',0):.2f}")
            
            d_fund = r.get('dados_fund', {})
            if d_fund:
                f5, f6, f7, f8 = st.columns(4)
                f5.metric("LPA", f"R$ {d_fund.get('LPA',0):.2f}")
                f6.metric("VPA", f"R$ {d_fund.get('VPA',0):.2f}")
                f7.metric("Div. Rate", f"R$ {d_fund.get('Div. Anual',0):.2f}")
                f8.metric("Ke (Custo)", f"{d_fund.get('Ke',0)*100:.1f}%")
            st.divider()

            # 3. Técnica
            st.markdown("### 3. Visão de Trading")
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("RSI (14)", f"{r.get('rsi',50):.0f}")
            t2.metric("MME 9 vs 21", "Alta" if r.get('mme9',0)>r.get('mme21',0) else "Baixa")
            t3.metric("Padrão", r.get('padrao_grafico') or "-")
            t4.metric("Candle", r.get('candle') or "-")
            
            # Gráfico
            t_fmt = formatar_ticker_global(ticker)
            symbol = f"BMFBOVESPA:{t_fmt.replace('.SA','')}"
            components.html(f"""<div class="tradingview-widget-container"><div id="tv"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 400, "symbol": "{symbol}", "interval": "D", "theme": "light", "container_id": "tv" }});</script></div>""", height=400)

# --- ABA 2: STRESS ---
with tabs[2]:
    st.subheader("🧪 Simulador de Choques")
    if st.button("Rodar Stress Test"):
        motor = MotorAnalise(); total = {}; prog = st.progress(0)
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"], False)
            p = d.get('preco', 0) if d else 0
            res = motor.calcular_stress_test(row["Ticker"], row["Qtd"], p)
            for k, v in res.items(): total[k] = total.get(k, 0) + v
            prog.progress((i+1)/len(st.session_state.carteira_acoes))
        prog.empty()
        for k, v in total.items(): st.metric(k, f"R$ {v:,.2f}", delta_color="inverse")

# --- ABA 3: CORRELAÇÃO ---
with tabs[3]:
    if st.button("Gerar Matriz"):
        tickers = [formatar_ticker_global(t) for t in st.session_state.carteira_acoes["Ticker"]]
        corr = yf.download(tickers, period="6mo", progress=False)['Close'].corr()
        st.plotly_chart(px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r"), use_container_width=True)

# --- DEMAIS ABAS ---
with tabs[4]: st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
with tabs[5]: 
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("Escanear Ações"): st.dataframe(executar_scanner("ACOES"))
    with c2: 
        if st.button("Escanear FIIs"): st.dataframe(executar_scanner("FIIS"))

with tabs[6]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)

with tabs[7]:
    st.subheader("🔮 Monte Carlo")
    if st.button("Simular"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: 
            ret = h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna()
            v_atual = st.session_state.carteira_acoes["Qtd"].mul(h.iloc[-1].values, fill_value=0).sum() if not h.empty else 10000
            sim = MotorAnalise().monte_carlo_carteira(ret, v_atual, 2000)
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
            S = st.number_input("Preço", 30.0); K = st.number_input("Strike", 32.0)
        with c2: 
            D = st.number_input("Dias", 30); V = st.number_input("Vol %", 30.0)/100
        if st.button("Calc Gregas"):
            g = BlackScholes(S, K, D/365, 0.13, V, "call").calcular_gregas()
            st.write(g)
    else: st.warning("Módulo options.py ausente")