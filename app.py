import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import yfinance as yf
import plotly.express as px
import re

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v116", layout="wide", page_icon="🏦")

# ======================================================
# 2. AUTO-RESET
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v116":
    st.session_state.versao_sistema = "v116"
    st.cache_data.clear()
    st.toast("Scanner de Ações Habilitado v116!", icon="🔭")

# ======================================================
# 3. IMPORTAÇÃO
# ======================================================
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    # AGORA IMPORTAMOS O SCANNER NOVO
    from scanner import executar_scanner
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
except Exception as e:
    st.error(f"Erro crítico na importação: {e}")
    st.stop()

# ======================================================
# 4. FUNÇÕES BASE
# ======================================================
def carregar_carteira_padrao():
    dados = [["MXRF11.SA", 100, 10.50, "FIIs-Papel"], ["PETR4.SA", 200, 35.00, "Ações-Commodities"]]
    return pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_acoes" not in st.session_state or st.session_state.carteira_acoes.empty:
    st.session_state.carteira_acoes = carregar_carteira_padrao()

if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([
        {"Setor": "Renda Fixa", "Meta (%)": 20.0}, {"Setor": "Exterior", "Meta (%)": 15.0},
        {"Setor": "Ações-Bancos", "Meta (%)": 10.0}, {"Setor": "Ações-Elétricas", "Meta (%)": 10.0},
        {"Setor": "Ações-Seguridade", "Meta (%)": 5.0}, {"Setor": "Ações-Commodities", "Meta (%)": 5.0},
        {"Setor": "Ações-Outros", "Meta (%)": 5.0}, {"Setor": "FIIs-Papel", "Meta (%)": 15.0},
        {"Setor": "FIIs-Tijolo", "Meta (%)": 10.0}, {"Setor": "FIIs-Outros", "Meta (%)": 5.0}
    ])

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

# --- LEITOR B3 V115 MANTIDO ---
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
                        
                        if ticker not in posicao_consolidada: posicao_consolidada[ticker] = {'qtd': 0.0, 'setor': setor}
                        if setor != "Ações-Outros" and posicao_consolidada[ticker]['setor'] == "Ações-Outros": posicao_consolidada[ticker]['setor'] = setor
                        posicao_consolidada[ticker]['qtd'] += qtd
                    log_msgs.append(f"✅ {nome_aba}: RV OK.")

            elif "tesouro" in nome_limpo or "renda fixa" in nome_limpo:
                if col_produto and col_saldo:
                    for _, row in df.iterrows():
                        prod = row[col_produto]
                        saldo = limpar_valor_monetario(row[col_saldo])
                        if pd.notna(prod) and saldo > 0:
                            tipo = "Tesouro Direto" if "tesouro" in nome_limpo else "CRI/CRA/LCI/LCA"
                            carteira_rf_nova.append([prod, saldo, tipo])
                    log_msgs.append(f"✅ {nome_aba}: RF OK.")

        carteira_rv_final = []
        for ticker, dados in posicao_consolidada.items():
            if dados['qtd'] > 0: carteira_rv_final.append([ticker, dados['qtd'], 0.0, dados['setor']])

        msg = f"RV: {len(carteira_rv_final)} | RF: {len(carteira_rf_nova)}."
        if log_msgs: msg += "\n" + "\n".join(log_msgs)
        return carteira_rv_final, carteira_rf_nova, msg
    except Exception as e: return None, None, f"Erro: {str(e)}"

# --- DEMAIS FUNÇÕES ---
@st.cache_data(ttl=300)
def obter_dados(ticker_raw):
    ticker = formatar_ticker_global(ticker_raw)
    try: 
        t = yf.Ticker(ticker)
        h = t.history(period="5y") 
        if h.empty: return None
        return MotorAnalise().analisar(h, t.info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_longo(tickers):
    l = [formatar_ticker_global(t) for t in tickers]
    try: return yf.download(l, period="5y", progress=False)['Close']
    except: return pd.DataFrame()

def auto_classificar():
    motor = MotorAnalise()
    prog = st.progress(0, "Refinando...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        if row["Setor"] in ["Ações-Outros", "FIIs-Indefinido"]:
            try: 
                novo_setor = motor.identificar_setor(yf.Ticker(formatar_ticker_global(row["Ticker"])).info, row["Ticker"])
                st.session_state.carteira_acoes.at[i, "Setor"] = novo_setor
            except: pass
        prog.progress((i+1)/total)
    prog.empty(); st.success("Ok!")

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
            d = obter_dados(t)
            p = d['preco'] if d else 0.0
        vals.append(r["Qtd"] * p)
    df["Valor Atual"] = vals
    return trf, sum(vals), df

# ======================================================
# 6. UI
# ======================================================
st.title("💰 Hedge Fund Ricardo v116")

with st.sidebar:
    st.header("Importação B3")
    b3_file = st.file_uploader("📂 Excel da B3", type=['xlsx', 'xls'])
    if b3_file and st.button("Processar"):
        rv, rf, log = processar_excel_b3(b3_file)
        if rv is not None:
            st.session_state.carteira_acoes = pd.DataFrame(rv, columns=["Ticker", "Qtd", "PM", "Setor"])
            if rf: st.session_state.carteira_rf = pd.DataFrame(rf, columns=["Ativo", "Saldo Atual", "Tipo"])
            st.success("Importado!")
            st.text_area("Log", log, height=100)
            st.rerun()
        else: st.error(f"Erro: {log}")
    
    st.divider()
    st.download_button("⬇️ Backup", st.session_state.carteira_acoes.to_csv(index=False), "backup.csv", "text/csv")
    up = st.file_uploader("📂 Restaurar", type=['csv'])
    if up: st.session_state.carteira_acoes = pd.read_csv(up); st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

tabs = st.tabs(["📊 Dashboard CEO", "🔎 Análise", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

with tabs[0]:
    st.subheader("Patrimônio Global")
    if st.button("Atualizar Cotações"): st.rerun()
    rf, rv, df_rv = calcular_consolidado()
    tot = rf + rv
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", f"R$ {tot:,.2f}")
    c2.metric("Renda Variável", f"R$ {rv:,.2f}", f"{(rv/tot)*100:.1f}%" if tot else "0%")
    c3.metric("Renda Fixa", f"R$ {rf:,.2f}", f"{(rf/tot)*100:.1f}%" if tot else "0%")
    st.divider()
    if not df_rv.empty:
        df_g = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
        if rf > 0: df_g = pd.concat([df_g, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": rf}])])
        st.plotly_chart(px.pie(df_g, values='Valor Atual', names='Setor', title="Alocação"), use_container_width=True)

with tabs[1]:
    t = st.text_input("Ticker", "MXRF11")
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            st.metric("Score IA", f"{r['score_ia']}/100", r['decisao_ia'])
            st.info(r['motivos'])
            st.dataframe(pd.DataFrame([r]).T)

with tabs[2]:
    st.subheader(f"Meus Ativos ({len(st.session_state.carteira_acoes)})")
    if st.button("Auto-Classificar"): auto_classificar()
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)

# ABA 3: SCANNER (ATUALIZADA)
with tabs[3]:
    st.subheader("🔭 Radar de Oportunidades")
    
    col_scan1, col_scan2 = st.columns(2)
    
    with col_scan1:
        st.info("Varre ~70 ações do Ibovespa/Small Caps.")
        if st.button("Escanear Ações (.SA)", use_container_width=True):
            df_scan = executar_scanner("ACOES")
            if not df_scan.empty:
                st.success(f"{len(df_scan)} Oportunidades Encontradas!")
                # Formatação condicional bonita
                st.dataframe(
                    df_scan.style.background_gradient(subset=['Score'], cmap='RdYlGn'),
                    use_container_width=True
                )
            else:
                st.warning("Nenhuma ação atendeu aos critérios mínimos ou erro na conexão.")

    with col_scan2:
        st.info("Varre os principais FIIs do IFIX.")
        if st.button("Escanear FIIs (IFIX)", use_container_width=True):
            df_scan = executar_scanner("FIIS")
            if not df_scan.empty:
                st.success(f"{len(df_scan)} FIIs Encontrados!")
                st.dataframe(
                    df_scan.style.background_gradient(subset=['Score'], cmap='RdYlGn'),
                    use_container_width=True
                )
            else:
                st.warning("Nenhum FII encontrado.")

with tabs[4]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)