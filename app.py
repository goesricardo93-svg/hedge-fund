import streamlit as st
import streamlit.components.v1 as components  # <--- Faltava esta linha!
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np
import re

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v120", layout="wide", page_icon="🏦")

# ======================================================
# 2. AUTO-RESET E ESTADO
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v120":
    st.session_state.versao_sistema = "v120"
    st.cache_data.clear()
    st.toast("Sistema v120: Gráficos e Imports Corrigidos!", icon="✅")

# ======================================================
# 3. IMPORTAÇÃO DOS MÓDULOS
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
    st.error(f"Erro crítico na importação dos módulos: {e}")
    st.info("Verifique se os arquivos motor.py, rebalance.py, scanner.py estão na pasta.")
    st.stop()

# ======================================================
# 4. CARTEIRA PADRÃO
# ======================================================
def carregar_carteira_padrao():
    dados_reais = [
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
    return pd.DataFrame(dados_reais, columns=["Ticker", "Qtd", "PM", "Setor"])

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

# ======================================================
# 5. HELPERS E FORMATADORES
# ======================================================
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

# ======================================================
# 6. MOTOR DE IMPORTAÇÃO B3 (V115)
# ======================================================
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
            
            # Busca dinâmica do cabeçalho
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

            # Mapeamento Flexível
            col_ticker = encontrar_coluna(df, ["código", "negociação", "ticker"])
            col_produto = encontrar_coluna(df, ["produto", "ativo", "título", "especificação"]) 
            col_qtd = encontrar_coluna(df, ["quantidade", "qtd", "disponível"])
            col_saldo = encontrar_coluna(df, ["valor líquido", "valor atual", "saldo", "valor total", "bruto"])

            # --- PROCESSAMENTO ---
            # CASO A: AÇÕES / FIIs / ETF / EMPRÉSTIMOS
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

            # CASO B: RENDA FIXA / TESOURO
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

        msg_final = f"Total RV: {len(carteira_rv_final)} | Total RF: {len(carteira_rf_nova)}."
        if log_msgs: msg_final += "\n" + "\n".join(log_msgs)

        return carteira_rv_final, carteira_rf_nova, msg_final

    except Exception as e:
        return None, None, f"Erro: {str(e)}"

# --- DEMAIS FUNÇÕES DE SUPORTE ---
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
# 7. UI - BARRA LATERAL
# ======================================================
st.title("💰 Hedge Fund Ricardo v120")

with st.sidebar:
    st.header("Importação B3")
    b3_file = st.file_uploader("📂 Excel da B3", type=['xlsx', 'xls'])
    if b3_file and st.button("Processar B3"):
        rv, rf, log = processar_excel_b3(b3_file)
        if rv is not None:
            st.session_state.carteira_acoes = pd.DataFrame(rv, columns=["Ticker", "Qtd", "PM", "Setor"])
            if rf: 
                st.session_state.carteira_rf = pd.DataFrame(rf, columns=["Ativo", "Saldo Atual", "Tipo"])
            st.success("Carteira Atualizada com Sucesso!")
            st.text_area("Log de Processamento", log, height=150)
            st.rerun()
        else: st.error(f"Erro: {log}")

    st.divider()
    st.download_button("⬇️ Backup CSV", st.session_state.carteira_acoes.to_csv(index=False), "backup.csv", "text/csv")
    up = st.file_uploader("📂 Restaurar CSV", type=['csv'])
    if up:
        st.session_state.carteira_acoes = pd.read_csv(up)
        st.rerun()
    
    st.divider()
    if st.button("🆘 Restaurar 31 Ativos"): 
        st.session_state.carteira_acoes = carregar_carteira_padrao()
        st.rerun()
    if st.button("🧹 Limpar Cache"): st.cache_data.clear(); st.rerun()

# ======================================================
# 8. ABAS PRINCIPAIS (FULL)
# ======================================================
tabs = st.tabs(["📊 Dashboard CEO", "🔎 Análise", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# --- ABA 0: DASHBOARD CEO ---
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

# --- ABA 1: ANÁLISE GLOBAL ---
with tabs[1]:
    c_input, c_btn = st.columns([3, 1])
    with c_input:
        t_input = st.text_input("Ticker", "MXRF11", label_visibility="collapsed", placeholder="Ex: MXRF11, AAPL, BTC...")
    with c_btn:
        btn_analisar = st.button("Analisar", use_container_width=True)

    if btn_analisar:
        t_fmt = formatar_ticker_global(t_input)
        r = obter_dados(t_input)
        
        if r:
            c_score, c_veredito = st.columns([1, 3])
            cor = "normal" if r.get('score_ia', 0) >= 60 else "inverse"
            c_score.metric("Score IA", f"{r.get('score_ia', 0)}/100")
            c_veredito.info(f"**Veredito:** {r.get('decisao_ia', '-')} | **Motivos:** {r.get('motivos', '-')}")
            if r.get('alertas'): c_veredito.error(f"**Atenção:** {r['alertas']}")
            st.divider()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Preço Atual", f"{r.get('preco', 0):.2f}")
            k2.metric("Teto (Stop Gain)", f"{r.get('stop_gain', 0):.2f}")
            rsi_val = r.get('rsi', 50)
            k3.metric("RSI (14)", f"{rsi_val:.0f}", delta="Sobrecomprado" if rsi_val>70 else "Sobrevendido" if rsi_val<30 else "Neutro", delta_color="inverse")
            k4.metric("Volatilidade", f"{r.get('volatilidade', 0)*100:.1f}%")

            st.divider()
            st.subheader("💰 Raio-X de Proventos")
            motor_div = MotorAnalise()
            div_info = motor_div.consultar_dividendos(t_fmt)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Último Pago", div_info.get('ultimo_valor', '-'), div_info.get('ultimo_data', '-'))
            d2.metric("Próximo", div_info.get('proximo_valor', '-'), div_info.get('proximo_data', '-'))
            d3.metric("DY Anual (12m)", f"{r.get('dy_anual', 0):.2f}%")
            d4.metric("Status", div_info.get('status', 'NEUTRO'))
            st.divider()

            col_val, col_rob = st.columns(2)
            with col_val:
                st.subheader("📋 Valuation")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Div.)", "Graham (Patrim.)", "Gordon (Cresc.)"],
                    "Preço Justo": [f"{r.get('p_bazin', 0):.2f}", f"{r.get('p_graham', 0):.2f}", f"{r.get('p_gordon', 0):.2f}"]
                }))

            with col_rob:
                if r.get('tipo_ativo') == 'FII':
                    st.subheader("🏗️ Setup FIIs")
                    pvp = r.get('pvp', 0)
                    alav = r.get('alavancagem', 0)
                    lbl_pvp = "🟢 Barato" if pvp < 1.0 else "🔴 Caro (>1.02)" if pvp > 1.02 else "⚪ Justo"
                    lbl_alav = "⚠️ Alta" if alav > 0.3 else "🟢 OK"
                    
                    df_setup = pd.DataFrame([
                        {"Indicador": "ANÁLISE FII", "Valor": f"{r.get('decisao_ia')}"},
                        {"Indicador": "MM200 (Tendência Longa)", "Valor": f"{r.get('status_mm200')}"},
                        {"Indicador": "Alavancagem (Dívida)", "Valor": f"{alav*100:.1f}% ({lbl_alav})"},
                        {"Indicador": "P/VP (Limite 1.02)", "Valor": f"{pvp:.2f}x ({lbl_pvp})"},
                        {"Indicador": "Preço Teto (Bazin)", "Valor": f"{r.get('p_bazin', 0):.2f}"},
                    ])
                    st.dataframe(df_setup, use_container_width=True, hide_index=True)
                else:
                    st.subheader("🎯 Setup Operacional (Ações)")
                    sinal = r.get('sinal_tecnico', 'NEUTRO')
                    df_setup = pd.DataFrame([
                        {"Indicador": "SINAL TÉCNICO (Curto)", "Valor": sinal},
                        {"Indicador": "TENDÊNCIA LONGA (MM200)", "Valor": f"{r.get('status_mm200')} (R$ {r.get('mm200',0):.2f})"},
                        {"Indicador": "Entrada Sugerida", "Valor": f"{r.get('preco_alvo_entrada', 0):.2f}"},
                        {"Indicador": "Volume Relativo", "Valor": f"{r.get('vol_relativo', 1):.1f}x"},
                        {"Indicador": "Stop Loss", "Valor": f"{r.get('stop_loss', 0):.2f}"}
                    ])
                    st.dataframe(df_setup, use_container_width=True, hide_index=True)

            st.subheader("Gráfico Interativo")
            if ".SA" in t_fmt: symbol_tv = "BMFBOVESPA:" + t_fmt.replace(".SA", "")
            elif "-USD" in t_fmt: symbol_tv = "BINANCE:" + t_fmt.replace("-USD", "USDT")
            else: symbol_tv = "NASDAQ:" + t_fmt
            widget = f"""<div class="tradingview-widget-container"><div id="tradingview_123"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "width": "100%", "height": 500, "symbol": "{symbol_tv}", "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tradingview_123" }});</script></div>"""
            components.html(widget, height=500)
        else: 
            st.error(f"Ativo '{t_input}' não encontrado.")

# --- ABA 2: CARTEIRA ---
with tabs[2]:
    c1, c2 = st.columns([1, 2])
    c1.subheader("Metas %")
    st.session_state.df_metas = c1.data_editor(st.session_state.df_metas, num_rows="dynamic")
    
    c2.subheader(f"Meus Ativos ({len(st.session_state.carteira_acoes)})")
    if c2.button("Auto-Classificar"): auto_classificar()
    
    st.session_state.carteira_acoes = c2.data_editor(
        st.session_state.carteira_acoes, 
        num_rows="dynamic", 
        column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=st.session_state.df_metas["Setor"].tolist())}, 
        use_container_width=True
    )
    
    aporte = c2.number_input("Aporte", 5000.0)
    if c2.button("Calcular Rebalanceamento"):
        m = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        dados = []
        bar = st.progress(0, "Calculando (Global)...")
        for i, row in st.session_state.carteira_acoes.iterrows():
            d = obter_dados(row["Ticker"])
            p = d.get("preco", 0) if d else 0
            s = d.get("score_ia", 0) if d else 0
            dados.append({**row.to_dict(), "Preço": p, "Valor_Atual": row["Qtd"]*p, "Score": s})
            bar.progress((i+1)/len(st.session_state.carteira_acoes))
        bar.empty()
        res = rebalancear_e_aportar(pd.DataFrame(dados), aporte, m)
        st.dataframe(res[res["Aporte Sugerido (R$)"] > 0.01].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# --- ABA 3: SCANNER ---
with tabs[3]:
    st.subheader("🔭 Radar de Oportunidades")
    c1, c2 = st.columns(2)
    with c1:
        st.info("Varre ~70 ações do Ibovespa/Small Caps.")
        if st.button("Escanear Ações (.SA)", use_container_width=True):
            df = executar_scanner("ACOES")
            if not df.empty: st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)
            else: st.warning("Nada encontrado.")
    with c2:
        st.info("Varre os principais FIIs do IFIX.")
        if st.button("Escanear FIIs (IFIX)", use_container_width=True):
            df = executar_scanner("FIIS")
            if not df.empty: st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)
            else: st.warning("Nada encontrado.")

# --- ABA 4: RENDA FIXA ---
with tabs[4]: 
    st.subheader("Renda Fixa & Tesouro")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)

# --- ABA 5: FUTURO (MONTE CARLO) ---
with tabs[5]:
    st.subheader("🔮 Previsão de Futuro (Monte Carlo)")
    if st.button("Rodar Simulação"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: 
            retornos = h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna()
            val_atual = st.session_state.carteira_acoes["Qtd"].mul(h.iloc[-1].values, fill_value=0).sum() if not h.empty else 100000
            sim = MotorAnalise().monte_carlo_carteira(retornos, val_atual, 2000)
            st.line_chart(sim)
            st.success(f"Simulação concluída!")

# --- ABA 6: FISCAL (DARF) ---
with tabs[6]:
    st.subheader("🦁 Calculadora de DARF")
    if calcular_darf:
        st.info("Cálculo estimativo para Swing Trade (Vendas > R$ 20k).")
        st.table(calcular_darf(st.session_state.carteira_acoes))
    else:
        st.warning("Módulo 'tax.py' não encontrado.")

# --- ABA 7: OPÇÕES (BLACK SCHOLES) ---
with tabs[7]:
    st.subheader("⚡ Simulador de Opções (Black & Scholes)")
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1: 
            S = st.number_input("Preço Atual (Spot)", 30.0)
            K = st.number_input("Strike (Exercício)", 32.0)
        with c2: 
            T_dias = st.number_input("Dias até Vencimento", 30)
            sig = st.number_input("Volatilidade (%)", 30.0) / 100.0
        
        if st.button("Calcular Gregas"):
            bs = BlackScholes(S, K, T_dias/365, 0.13, sig, "call")
            gregas = bs.calcular_gregas()
            st.divider()
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Delta (Δ)", f"{gregas['Delta']:.3f}")
            g2.metric("Gamma (Γ)", f"{gregas['Gamma']:.3f}")
            g3.metric("Theta (Θ)", f"{gregas['Theta']:.3f}")
            g4.metric("Vega (ν)", f"{gregas['Vega']:.3f}")
    else:
        st.warning("Módulo 'options.py' não encontrado.")