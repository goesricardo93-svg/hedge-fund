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
st.set_page_config(page_title="Hedge Fund Ricardo v128", layout="wide", page_icon="🏦")

if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v128":
    st.session_state.versao_sistema = "v128"
    st.cache_data.clear()
    st.toast("Sistema Completo v128 Carregado!", icon="💎")

# ======================================================
# 2. IMPORTAÇÃO DOS MÓDULOS
# ======================================================
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
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
# 3. DADOS E CARTEIRA PADRÃO
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

# --- IMPORTADOR B3 V115 COMPLETO ---
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
                        if setor != "Ações-Outros" and posicao_consolidada[ticker]['setor'] == "Ações-Outros": 
                            posicao_consolidada[ticker]['setor'] = setor
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
        return carteira_rv_final, carteira_rf_nova, "\n".join(log_msgs)
    except Exception as e: return None, None, f"Erro: {str(e)}"

# --- ANALYTICS ---
@st.cache_data(ttl=300)
def obter_dados(ticker, modo_crise):
    t = formatar_ticker_global(ticker)
    try: return MotorAnalise().analisar(yf.Ticker(t).history(period="2y"), yf.Ticker(t).info, t, modo_crise)
    except: return None

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
# 4. UI - APLICAÇÃO PRINCIPAL
# ======================================================
st.title("💰 Hedge Fund Ricardo v128 (Full Suite)")

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
    b3_file = st.file_uploader("📂 Importar B3 (Excel)", type=['xlsx', 'xls'])
    if b3_file and st.button("Processar"):
        rv, rf, log = processar_excel_b3(b3_file)
        if rv:
            st.session_state.carteira_acoes = pd.DataFrame(rv, columns=["Ticker", "Qtd", "PM", "Setor"])
            if rf: st.session_state.carteira_rf = pd.DataFrame(rf, columns=["Ativo", "Saldo Atual", "Tipo"])
            st.success("Dados Atualizados!")
            st.rerun()
        else: st.error(log)
    
    st.divider()
    if st.button("🆘 Restaurar 31 Ativos"): 
        st.session_state.carteira_acoes = carregar_carteira_padrao()
        st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

# DEFINIÇÃO DAS ABAS - TODAS ELAS
tabs = st.tabs(["📊 Dash", "🔎 Análise Completa", "🧪 Stress Test", "🔗 Correlação", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# --- ABA 0: DASHBOARD ---
with tabs[0]:
    st.subheader("Patrimônio & Alocação")
    if st.button("Atualizar Preços"): st.rerun()
    rf, rv, df_rv = calcular_consolidado()
    c1, c2, c3 = st.columns(3)
    c1.metric("AUM Total", f"R$ {rf+rv:,.2f}")
    c2.metric("Renda Variável", f"R$ {rv:,.2f}")
    c3.metric("Renda Fixa", f"R$ {rf:,.2f}")
    if not df_rv.empty:
        df_g = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
        if rf > 0: df_g = pd.concat([df_g, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": rf}])])
        st.plotly_chart(px.pie(df_g, values='Valor Atual', names='Setor', title="Alocação Real"), use_container_width=True)

# --- ABA 1: ANÁLISE COMPLETA (Deep Dive) ---
with tabs[1]:
    ticker = st.text_input("Ticker", "VALE3")
    if st.button("Analisar (Dados Brutos)"):
        r = obter_dados(ticker, modo_crise)
        if r:
            # 1. HEADER CIO
            st.markdown("### 1. Painel de Controle (CIO)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Score Final", f"{r['score_ia']}/100", r['decisao_ia'])
            c2.metric("Qualidade", f"{r['score_qualidade']}/100")
            c3.metric("Convicção", f"{r['score_conviccao']}/100")
            c4.metric("Sentimento", f"{r['macro']}", r['news'])
            st.info(f"**Tese:** {r['motivos']}")
            if r['alertas']: st.error(f"**Riscos:** {r['alertas']}")
            st.divider()

            # 2. FUNDAMENTOS DETALHADOS
            st.markdown("### 2. Fundamentos & Valuation (Analista)")
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Preço Tela", f"R$ {r['preco']:.2f}")
            v2.metric("Preço Justo", f"R$ {r['p_justo']:.2f}")
            v3.metric("Preço Teto", f"R$ {r['p_teto']:.2f}")
            v4.metric("Margem Seg.", f"{r['margem']*100:.0f}%")
            
            # Modelos Individuais
            st.write("#### 📐 Detalhamento dos Modelos Matemáticos")
            if r['modelos_val']:
                cols_mod = st.columns(len(r['modelos_val']))
                idx=0
                for k, v in r['modelos_val'].items():
                    cols_mod[idx].metric(k, f"R$ {v:.2f}")
                    idx+=1
            else: st.warning("Sem dados suficientes para modelos (LPA/Div negativos ou nulos).")

            # Dados Brutos
            st.write("#### 🏗️ Indicadores Estruturais")
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("P/VP", f"{r['pvp']:.2f}")
            f2.metric("ROE", f"{r['roe']*100:.1f}%")
            f3.metric("DY (12m)", f"{r['dy_anual']:.2f}%")
            f4.metric("Dívida/EBITDA", f"{r['divida_ebitda']:.2f}")
            f5.metric("Margem Líq.", f"{r['margem_liq']*100:.1f}%")
            
            d_fund = r.get('dados_fund', {})
            if d_fund:
                f6, f7, f8, f9 = st.columns(4)
                f6.metric("LPA (Lucro)", f"R$ {d_fund.get('LPA',0):.2f}")
                f7.metric("VPA (Livro)", f"R$ {d_fund.get('VPA',0):.2f}")
                f8.metric("Div. Anual Est.", f"R$ {d_fund.get('Div. Anual',0):.2f}")
                f9.metric("Ke (Custo Cap.)", f"{d_fund.get('Ke',0)*100:.1f}%")
            st.divider()

            # 3. TÉCNICA
            st.markdown("### 3. Raio-X Técnico (Trader)")
            t1, t2, t3, t4, t5 = st.columns(5)
            t1.metric("RSI (14)", f"{r['rsi']:.0f}", delta="Sobrecompra" if r['rsi']>70 else "Sobrevenda" if r['rsi']<30 else "Neutro")
            t2.metric("MME 9", f"R$ {r['mme9']:.2f}")
            t3.metric("MME 21", f"R$ {r['mme21']:.2f}")
            t4.metric("MM 200", f"R$ {r['mm200']:.2f}")
            t5.metric("Volatilidade", f"{r['probs']['volatilidade_anual']*100:.1f}%")
            
            st.write(f"**Padrão Gráfico:** {r['padrao_grafico'] or 'Nenhum'} | **Candle:** {r['candle'] or 'Normal'}")

            # Probabilidades
            probs = r['probs']
            if probs:
                st.caption("🎲 **Projeção Estatística (21 dias):**")
                p1, p2, p3 = st.columns(3)
                p1.metric("Otimista (+2σ)", f"R$ {probs['otimista']:.2f}")
                p2.metric("Base (±1σ)", f"R$ {probs['base_min']:.2f} - {probs['base_max']:.2f}")
                p3.metric("Pessimista (-2σ)", f"R$ {probs['pessimista']:.2f}")
            
            t_fmt = formatar_ticker_global(ticker)
            symbol = f"BMFBOVESPA:{t_fmt.replace('.SA','')}"
            components.html(f"""<div class="tradingview-widget-container"><div id="tv"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 400, "symbol": "{symbol}", "interval": "D", "theme": "light", "container_id": "tv" }});</script></div>""", height=400)

# --- ABA 2: STRESS TEST ---
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
        
        st.error("📉 Impacto Estimado no Patrimônio")
        cols = st.columns(len(total_perda))
        idx = 0
        for cenario, perda in total_perda.items():
            cols[idx].metric(cenario, f"R$ {perda:,.2f}", delta_color="inverse")
            idx += 1

# --- ABA 3: CORRELAÇÃO ---
with tabs[3]:
    st.subheader("🔗 Matriz de Correlação")
    if st.button("Gerar Matriz"):
        tickers = [formatar_ticker_global(t) for t in st.session_state.carteira_acoes["Ticker"]]
        if tickers:
            corr = yf.download(tickers, period="6mo", progress=False)['Close'].corr()
            st.plotly_chart(px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r"), use_container_width=True)

# --- ABA 4: CARTEIRA ---
with tabs[4]:
    st.subheader("💼 Gestão de Ativos")
    st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        aporte = st.number_input("Aporte", 5000.0)
    with c2:
        if st.button("Calcular Rebalanceamento"):
            m = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
            dados = []
            for i, row in st.session_state.carteira_acoes.iterrows():
                d = obter_dados(row["Ticker"], False)
                p = d.get("preco", 0) if d else 0
                s = d.get("score_ia", 0) if d else 0
                dados.append({**row.to_dict(), "Preço": p, "Valor_Atual": row["Qtd"]*p, "Score": s})
            res = rebalancear_e_aportar(pd.DataFrame(dados), aporte, m)
            st.dataframe(res[res["Aporte Sugerido (R$)"] > 0.01].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# --- ABA 5: SCANNER ---
with tabs[5]:
    st.subheader("🔭 Radar")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Escanear Ações (.SA)"):
            df = executar_scanner("ACOES")
            if not df.empty: st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)
    with c2:
        if st.button("Escanear FIIs (IFIX)"):
            df = executar_scanner("FIIS")
            if not df.empty: st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)

# --- ABA 6: RENDA FIXA ---
with tabs[6]:
    st.subheader("🛡️ Renda Fixa & Tesouro")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)

# --- ABA 7: FUTURO (MONTE CARLO) ---
with tabs[7]:
    st.subheader("🔮 Previsão de Futuro (Monte Carlo)")
    if st.button("Rodar Simulação"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: 
            retornos = h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna()
            val_atual = st.session_state.carteira_acoes["Qtd"].mul(h.iloc[-1].values, fill_value=0).sum() if not h.empty else 100000
            sim = MotorAnalise().monte_carlo_carteira(retornos, val_atual, 2000)
            st.line_chart(sim)
            st.success(f"Simulação concluída!")

# --- ABA 8: FISCAL ---
with tabs[8]:
    st.subheader("🦁 Calculadora de DARF")
    if calcular_darf:
        st.table(calcular_darf(st.session_state.carteira_acoes))
    else: st.warning("Módulo tax.py não encontrado.")

# --- ABA 9: OPÇÕES ---
with tabs[9]:
    st.subheader("⚡ Simulador de Opções (Black & Scholes)")
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1: 
            S = st.number_input("Preço Atual", 30.0)
            K = st.number_input("Strike", 32.0)
        with c2: 
            T_dias = st.number_input("Dias Vencimento", 30)
            sig = st.number_input("Volatilidade %", 30.0) / 100.0
        if st.button("Calcular Gregas"):
            bs = BlackScholes(S, K, T_dias/365, 0.13, sig, "call")
            gregas = bs.calcular_gregas()
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Delta", f"{gregas['Delta']:.3f}")
            g2.metric("Gamma", f"{gregas['Gamma']:.3f}")
            g3.metric("Theta", f"{gregas['Theta']:.3f}")
            g4.metric("Vega", f"{gregas['Vega']:.3f}")
    else: st.warning("Módulo options.py não encontrado.")