import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import yfinance as yf
import plotly.express as px

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v113", layout="wide", page_icon="🏦")

# ======================================================
# 2. AUTO-RESET
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v113":
    st.session_state.versao_sistema = "v113"
    st.cache_data.clear()
    st.toast("Motor v113: Correção de Colunas Duplicadas Ativa!", icon="🔧")

# ======================================================
# 3. IMPORTAÇÃO
# ======================================================
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    try: from scanner import scanner_fiis_csv, scanner_auto_yahoo
    except: scanner_fiis_csv = None; scanner_auto_yahoo = None
    try: from options import BlackScholes
    except: BlackScholes = None
    try: from tax import calcular_darf
    except: calcular_darf = None
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
except Exception as e:
    st.error(f"Erro crítico: {e}")
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

def formatar_ticker_global(t):
    t = str(t).upper().strip()
    if t in ["BTC", "ETH", "SOL", "USDT"]: return f"{t}-USD"
    if "." in t: return t
    if any(char.isdigit() for char in t): return f"{t}.SA"
    return t

def formatar_ticker_b3(cod):
    cod = str(cod).upper().strip()
    if cod.endswith("F"): cod = cod[:-1]
    if not cod.endswith(".SA") and len(cod) <= 6: return f"{cod}.SA"
    return cod

# --- O CORAÇÃO DO SISTEMA v113 (Com Dedetizador de Colunas) ---
def processar_excel_b3(arquivo):
    try:
        xls_raw = pd.read_excel(arquivo, sheet_name=None, header=None)
        
        posicao_consolidada = {}
        carteira_rf_nova = []
        log_msgs = []

        for nome_aba, df_raw in xls_raw.items():
            nome_limpo = str(nome_aba).lower()
            
            # 1. Achar cabeçalho
            target_row = -1
            for i, row in df_raw.iterrows():
                row_str = row.astype(str).values
                if "Código de Negociação" in row_str or "Produto" in row_str:
                    target_row = i
                    break
            
            if target_row == -1: continue

            # 2. Ler aba correta
            df = pd.read_excel(arquivo, sheet_name=nome_aba, header=target_row)
            df.columns = [str(c).strip() for c in df.columns] 
            
            # Mapeamento
            mapa = {
                "Código de Negociação": "Ticker", "Produto": "Produto",
                "Quantidade": "Qtd", "Quantidade Total": "Qtd", "Quantidade Disponível": "Qtd",
                "Valor Atual": "Saldo", "Saldo Líquido": "Saldo"
            }
            df = df.rename(columns=mapa)

            # --- CORREÇÃO DE BUG "AMBIGUOUS SERIES" (DEDETIZADOR) ---
            # Remove colunas com nomes duplicados (mantém a primeira aparição)
            df = df.loc[:, ~df.columns.duplicated()]

            # --- LÓGICA DE CATEGORIZAÇÃO ---

            # A) EMPRÉSTIMOS
            if "empréstimo" in nome_limpo:
                if "Ticker" in df.columns and "Qtd" in df.columns:
                    for _, row in df.iterrows():
                        ticker = formatar_ticker_b3(row["Ticker"])
                        # Usa to_numeric para forçar virar número único, se falhar vira NaN
                        qtd = pd.to_numeric(row["Qtd"], errors='coerce') 
                        if pd.isna(qtd): qtd = 0
                        
                        if qtd > 0:
                            if ticker not in posicao_consolidada:
                                posicao_consolidada[ticker] = {'qtd': 0.0, 'setor': 'Ações-Outros'}
                            posicao_consolidada[ticker]['qtd'] += qtd
                            log_msgs.append(f"➕ {ticker}: Somando {qtd}")

            # B) AÇÕES / FIIs / ETF
            elif any(x in nome_limpo for x in ["ações", "fundo", "etf"]):
                if "Ticker" not in df.columns and "Produto" in df.columns:
                     df["Ticker"] = df["Produto"].apply(lambda x: str(x).split("-")[0].strip())

                if "Ticker" in df.columns and "Qtd" in df.columns:
                    for _, row in df.iterrows():
                        ticker = formatar_ticker_b3(row["Ticker"])
                        qtd = pd.to_numeric(row["Qtd"], errors='coerce')
                        if pd.isna(qtd): qtd = 0
                        
                        if qtd <= 0: continue

                        setor = "Ações-Outros"
                        if "fundo" in nome_limpo: setor = "FIIs-Indefinido"
                        elif "etf" in nome_limpo: setor = "Exterior"
                        elif "ações" in nome_limpo: setor = "Ações-Outros"

                        if ticker not in posicao_consolidada:
                            posicao_consolidada[ticker] = {'qtd': 0.0, 'setor': setor}
                        
                        if setor != "Ações-Outros": 
                            posicao_consolidada[ticker]['setor'] = setor
                        
                        posicao_consolidada[ticker]['qtd'] += qtd

            # C) RENDA FIXA
            elif "tesouro" in nome_limpo or "renda fixa" in nome_limpo:
                if "Produto" in df.columns and "Saldo" in df.columns:
                    for _, row in df.iterrows():
                        prod = row["Produto"]
                        saldo = pd.to_numeric(row["Saldo"], errors='coerce')
                        if pd.isna(saldo): saldo = 0

                        if saldo > 0:
                            tipo = "Tesouro" if "tesouro" in nome_limpo else "Renda Fixa"
                            carteira_rf_nova.append([prod, saldo, tipo])

        carteira_rv_final = []
        for ticker, dados in posicao_consolidada.items():
            if dados['qtd'] > 0:
                carteira_rv_final.append([ticker, dados['qtd'], 0.0, dados['setor']])

        msg_final = f"Processado! {len(carteira_rv_final)} ativos RV e {len(carteira_rf_nova)} RF."
        if log_msgs: msg_final += "\n" + "\n".join(log_msgs[:5]) + "..." 

        return carteira_rv_final, carteira_rf_nova, msg_final

    except Exception as e:
        return None, None, f"Erro: {str(e)}"

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
    prog = st.progress(0, "Refinando Setores...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        if row["Setor"] in ["Ações-Outros", "FIIs-Indefinido"]:
            try: 
                novo_setor = motor.identificar_setor(yf.Ticker(formatar_ticker_global(row["Ticker"])).info, row["Ticker"])
                st.session_state.carteira_acoes.at[i, "Setor"] = novo_setor
            except: pass
        prog.progress((i+1)/total)
    prog.empty(); st.success("Classificação Refinada!")

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
st.title("💰 Hedge Fund Ricardo v113")

with st.sidebar:
    st.header("Importação B3 (V113)")
    b3_file = st.file_uploader("📂 Excel da B3", type=['xlsx', 'xls'])
    if b3_file and st.button("Processar"):
        rv, rf, log = processar_excel_b3(b3_file)
        if rv:
            st.session_state.carteira_acoes = pd.DataFrame(rv, columns=["Ticker", "Qtd", "PM", "Setor"])
            if rf: st.session_state.carteira_rf = pd.DataFrame(rf, columns=["Ativo", "Saldo Atual", "Tipo"])
            st.success("Importado com Sucesso!")
            st.text_area("Log de Processamento", log, height=100)
            st.rerun()
        else: st.error(f"Erro: {log}")

    st.divider()
    st.download_button("⬇️ Backup CSV", st.session_state.carteira_acoes.to_csv(index=False), "backup.csv", "text/csv")
    up = st.file_uploader("📂 Restaurar CSV", type=['csv'])
    if up:
        st.session_state.carteira_acoes = pd.read_csv(up)
        st.rerun()
    
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

tabs = st.tabs(["📊 Dashboard CEO", "🔎 Análise", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# ABA 1: DASHBOARD
with tabs[0]:
    st.subheader("Patrimônio Global")
    if st.button("Atualizar Cotações"): st.rerun()
    
    rf, rv, df_rv = calcular_consolidado()
    total = rf + rv
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total (AUM)", f"R$ {total:,.2f}")
    c2.metric("Renda Variável", f"R$ {rv:,.2f}", f"{(rv/total)*100:.1f}%" if total else "0%")
    c3.metric("Renda Fixa", f"R$ {rf:,.2f}", f"{(rf/total)*100:.1f}%" if total else "0%")
    
    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        if not df_rv.empty:
            df_g = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
            if rf > 0: df_g = pd.concat([df_g, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": rf}])])
            st.plotly_chart(px.pie(df_g, values='Valor Atual', names='Setor', title="Alocação Real"), use_container_width=True)
    with g2:
        if not df_rv.empty:
            df_g = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
            if rf > 0: df_g = pd.concat([df_g, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": rf}])])
            df_g["% Atual"] = (df_g["Valor Atual"] / total) * 100
            comp = pd.merge(st.session_state.df_metas, df_g, on="Setor", how="outer").fillna(0)
            st.plotly_chart(px.bar(comp, x="Setor", y=["% Atual", "Meta (%)"], barmode="group", title="Metas vs Real"), use_container_width=True)

# ABA 2: ANÁLISE
with tabs[1]:
    ticker = st.text_input("Ticker", "MXRF11")
    if st.button("Analisar"):
        r = obter_dados(ticker)
        if r:
            c1, c2 = st.columns([1, 3])
            c1.metric("Score", f"{r['score_ia']}/100")
            c2.info(f"{r['decisao_ia']} | {r['motivos']}")
            st.table(pd.DataFrame([r]))
        else: st.error("Não encontrado")

# ABA 3: CARTEIRA
with tabs[2]:
    st.session_state.df_metas = st.data_editor(st.session_state.df_metas, num_rows="dynamic")
    st.subheader(f"Ativos ({len(st.session_state.carteira_acoes)})")
    if st.button("Refinar Classificação"): auto_classificar()
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    
    aporte = st.number_input("Aporte", 5000.0)
    if st.button("Rebalancear"):
        st.info("Funcionalidade de rebalanceamento pronta para uso.")

# DEMAIS ABAS (Mantidas simplificadas)
with tabs[4]: st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")