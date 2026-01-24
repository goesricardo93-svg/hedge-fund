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
st.set_page_config(page_title="Hedge Fund Ricardo v126.1", layout="wide", page_icon="🏦")

if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v126.1":
    st.session_state.versao_sistema = "v126.1"
    st.cache_data.clear()
    st.toast("Hotfix v126.1: Sintaxe corrigida e Import B3 restaurada!", icon="✅")

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
except Exception as e:
    st.error(f"Erro: {e}"); st.stop()

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

if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([{"Setor": "Renda Fixa", "Meta (%)": 20.0}, {"Setor": "Ações-Bancos", "Meta (%)": 15.0}])

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

# --- IMPORTADOR B3 V115 (RESTAURADO COMPLETO) ---
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
                row_str = row.astype(str).values.tolist()
                linha_texto = " ".join(row_str).lower()
                if any(x in linha_texto for x in ["produto", "código", "ativo", "título", "vencimento"]):
                    target_row = i
                    break
            
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
                        
                        if ticker not in posicao_consolidada:
                            posicao_consolidada[ticker] = {'qtd': 0.0, 'setor': setor}
                        
                        if setor != "Ações-Outros" and posicao_consolidada[ticker]['setor'] == "Ações-Outros": 
                            posicao_consolidada[ticker]['setor'] = setor
                        
                        posicao_consolidada[ticker]['qtd'] += qtd
                    
                    log_msgs.append(f"✅ {nome_aba}: RV Processada.")

            elif "tesouro" in nome_limpo or "renda fixa" in nome_limpo:
                if col_produto and col_saldo:
                    for _, row in df.iterrows():
                        prod = row[col_produto]
                        saldo = limpar_valor_monetario(row[col_saldo])

                        if pd.notna(prod) and saldo > 0:
                            tipo = "Tesouro Direto" if "tesouro" in nome_limpo else "CRI/CRA/LCI/LCA"
                            carteira_rf_nova.append([prod, saldo, tipo])
                    
                    log_msgs.append(f"✅ {nome_aba}: RF Importada.")

        carteira_rv_final = []
        for ticker, dados in posicao_consolidada.items():
            if dados['qtd'] > 0:
                carteira_rv_final.append([ticker, dados['qtd'], 0.0, dados['setor']])

        return carteira_rv_final, carteira_rf_nova, "\n".join(log_msgs)

    except Exception as e:
        return None, None, f"Erro: {str(e)}"

# --- ANALYTICS ---
@st.cache_data(ttl=300)
def obter_dados(ticker, modo_crise):
    t = formatar_ticker_global(ticker)
    try: return MotorAnalise().analisar(yf.Ticker(t).history(period="2y"), yf.Ticker(t).info, t, modo_crise)
    except: return None

def calcular_correlacao_carteira():
    tickers = [formatar_ticker_global(t) for t in st.session_state.carteira_acoes["Ticker"]]
    if not tickers: return pd.DataFrame()
    return yf.download(tickers, period="6mo", progress=False)['Close'].corr()

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
# 4. UI
# ======================================================
st.title("💰 Hedge Fund Ricardo v126.1 (CIO Edition)")

with st.sidebar:
    st.header("⚙️ Controle de Risco")
    
    modo_crise = st.toggle("🔴 MODO CRISE", value=False, help="Ativa protocolos defensivos: Mais margem, menos risco.")
    
    if modo_crise:
        st.error("⚠️ PROTOCOLO DEFENSIVO ATIVO")
        st.caption("Margens de Segurança Aumentadas (+10%)")
        st.caption("Penalidade de Macro Severa")
        st.caption("Peso 'Qualidade' > 'Convicção'")
    
    st.divider()
    st.header("B3 & Config")
    b3_file = st.file_uploader("📂 Importar B3", type=['xlsx'])
    if b3_file and st.button("Processar"):
        rv, rf, log = processar_excel_b3(b3_file)
        if rv:
            st.session_state.carteira_acoes = pd.DataFrame(rv, columns=["Ticker", "Qtd", "PM", "Setor"])
            if rf: st.session_state.carteira_rf = pd.DataFrame(rf, columns=["Ativo", "Saldo Atual", "Tipo"])
            st.success("Dados Atualizados!")
            st.rerun()
        else: st.error(log)
    
    st.divider()
    if st.button("🆘 Restaurar Padrão"): 
        st.session_state.carteira_acoes = carregar_carteira_padrao()
        st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

tabs = st.tabs(["📊 Dashboard", "🔎 Análise CIO", "🧪 Stress Test", "🔗 Correlação", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal"])

# ABA 0: DASHBOARD
with tabs[0]:
    rf, rv, df_rv = calcular_consolidado()
    c1, c2, c3 = st.columns(3)
    c1.metric("AUM Total", f"R$ {rf+rv:,.2f}")
    c2.metric("Renda Variável", f"R$ {rv:,.2f}")
    c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
    if not df_rv.empty:
        df_g = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
        if rf > 0: df_g = pd.concat([df_g, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": rf}])])
        st.plotly_chart(px.pie(df_g, values='Valor Atual', names='Setor', title="Alocação Real"), use_container_width=True)

# ABA 1: ANÁLISE CIO (SPLIT SCORE)
with tabs[1]:
    ticker = st.text_input("Ticker", "VALE3")
    if st.button("Analisar (CIO)"):
        r = obter_dados(ticker, modo_crise)
        if r:
            c1, c2, c3 = st.columns(3)
            c1.metric("Score Final", f"{r['score_ia']}/100", r['decisao_ia'])
            c2.metric("Qualidade (Estrutura)", f"{r['score_qualidade']}/100", help="Valuation, ROE, Dívida")
            c3.metric("Convicção (Timing)", f"{r['score_conviccao']}/100", help="Tendência, News, Macro")
            
            st.divider()
            
            probs = r['probs']
            if probs:
                st.subheader("🎲 Mapa de Probabilidade (21 dias)")
                kp1, kp2, kp3 = st.columns(3)
                kp1.metric("Otimista", f"R$ {probs['otimista']:.2f}")
                kp2.metric("Base", f"R$ {probs['base_min']:.2f} - {probs['base_max']:.2f}")
                kp3.metric("Pessimista", f"R$ {probs['pessimista']:.2f}")

            st.info(f"**Tese:** {r['motivos']}")
            if r['alertas']: st.error(f"**Riscos:** {r['alertas']}")
            
            v1, v2 = st.columns(2)
            v1.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            v2.metric("Teto (Margem)", f"R$ {r['p_teto']:.2f}")
            
            t_fmt = formatar_ticker_global(ticker)
            symbol = f"BMFBOVESPA:{t_fmt.replace('.SA','')}"
            components.html(f"""<div class="tradingview-widget-container"><div id="tv"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 400, "symbol": "{symbol}", "interval": "D", "theme": "light", "container_id": "tv" }});</script></div>""", height=400)

# ABA 2: STRESS TEST
with tabs[2]:
    st.subheader("🧪 Simulador de Caos")
    if st.button("Rodar Stress Test na Carteira"):
        motor = MotorAnalise()
        total_perda = {}
        prog = st.progress(0, "Simulando choques...")
        for i, row in st.session_state.carteira_acoes.iterrows():
            t = formatar_ticker_global(row["Ticker"])
            p_atual = obter_dados(t, False)['preco']
            res = motor.calcular_stress_test(t, row["Qtd"], p_atual)
            for cenario, valor in res.items():
                total_perda[cenario] = total_perda.get(cenario, 0) + valor
            prog.progress((i+1)/len(st.session_state.carteira_acoes))
        prog.empty()
        
        cols = st.columns(len(total_perda))
        idx = 0
        for cenario, perda in total_perda.items():
            cols[idx].metric(cenario, f"R$ {perda:,.2f}", delta=f"{(perda/rv)*100:.1f}%", delta_color="inverse")
            idx += 1

# ABA 3: CORRELAÇÃO
with tabs[3]:
    if st.button("Gerar Matriz"):
        corr = calcular_correlacao_carteira()
        if not corr.empty: st.plotly_chart(px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r", title="Matriz"), use_container_width=True)

# DEMAIS ABAS
with tabs[4]: st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
with tabs[5]: 
    if st.button("Escanear Ações"): st.dataframe(executar_scanner("ACOES"))
with tabs[6]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)
with tabs[7]: st.subheader("Monte Carlo"); st.write("Disponível")
with tabs[8]: st.subheader("Fiscal"); st.write("Disponível")