import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import yfinance as yf
import plotly.express as px

# ======================================================
# 1. CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v109", layout="wide", page_icon="🏦")

# ======================================================
# 2. AUTO-RESET
# ======================================================
if "versao_sistema" not in st.session_state or st.session_state.versao_sistema != "v109":
    st.session_state.versao_sistema = "v109"
    st.cache_data.clear()
    st.toast("Módulo B3 Ativado! Importação de Excel disponível.", icon="📂")

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
# 4. FUNÇÕES DE DADOS E IMPORTAÇÃO B3
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

# --- FORMATADORES ---
def formatar_ticker_global(t):
    t = str(t).upper().strip()
    if t in ["BTC", "ETH", "SOL", "USDT", "ADA", "DOGE"]: return f"{t}-USD"
    if "." in t or "-" in t or "=" in t: return t
    if any(char.isdigit() for char in t): return f"{t}.SA"
    return t

def formatar_ticker_b3(cod):
    # O Excel da B3 às vezes traz o código sem o .SA
    cod = str(cod).upper().strip()
    if cod.endswith("F"): cod = cod[:-1] # Remove Fracionário (PETR4F -> PETR4)
    if not cod.endswith(".SA") and len(cod) <= 6: return f"{cod}.SA"
    return cod

# --- PROCESSADOR DE EXCEL B3 (NOVO!) ---
def processar_excel_b3(arquivo):
    try:
        # Lê o Excel tentando encontrar o cabeçalho correto
        # A B3 costuma colocar logotipos nas primeiras linhas, então procuramos a linha que tem "Código de Negociação"
        df_raw = pd.read_excel(arquivo)
        
        # Procura a linha de cabeçalho
        header_row = -1
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).values
            if "Código de Negociação" in row_str or "Produto" in row_str:
                header_row = i + 1 # +1 pois o pandas indexa do 0 mas o header seria a próxima
                break
        
        if header_row != -1:
            # Recarrega com o cabeçalho certo
            df = pd.read_excel(arquivo, header=header_row)
        else:
            df = df_raw # Tenta sorte

        # Normaliza colunas
        cols_map = {
            "Código de Negociação": "Ticker",
            "Produto": "Produto",
            "Quantidade": "Qtd",
            "Quantidade Total": "Qtd"
        }
        df = df.rename(columns=cols_map)
        
        # Filtra apenas o necessário
        if "Ticker" not in df.columns:
            # Tenta extrair do Produto se não tiver coluna Ticker (Raro, mas acontece)
            return None, "Coluna 'Código de Negociação' não encontrada."
            
        carteira_nova = []
        motor_aux = MotorAnalise() # Para classificar setores automaticamente
        
        for _, row in df.iterrows():
            ticker_bruto = row["Ticker"]
            qtd = row["Qtd"]
            
            # Pula linhas vazias ou totais
            if pd.isna(ticker_bruto) or pd.isna(qtd): continue
            
            ticker_fmt = formatar_ticker_b3(ticker_bruto)
            
            # Tenta identificar setor na hora
            setor = "Ações-Outros"
            try: 
                # Busca rápida de info (pode demorar se for muitos, então deixamos genérico e o usuário classifica depois)
                # Otimização: Apenas inferir pelo nome
                if "11.SA" in ticker_fmt: setor = "FIIs-Indefinido"
            except: pass
            
            carteira_nova.append([ticker_fmt, float(qtd), 0.0, setor])
            
        return pd.DataFrame(carteira_nova, columns=["Ticker", "Qtd", "PM", "Setor"]), "Sucesso"

    except Exception as e:
        return None, f"Erro ao ler arquivo: {str(e)}"

# --- DADOS ---
@st.cache_data(ttl=300)
def obter_dados(ticker_raw):
    ticker = formatar_ticker_global(ticker_raw)
    try: 
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="5y") 
        if hist is None or hist.empty: return None
        try: info = ticker_obj.info
        except: info = {}
        return MotorAnalise().analisar(hist, info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_longo(tickers_raw):
    lista_formatada = [formatar_ticker_global(t) for t in tickers_raw]
    try:
        d = yf.download(lista_formatada, period="5y", progress=False)
        return d["Adj Close"] if "Adj Close" in d else d["Close"]
    except: return pd.DataFrame()

def auto_classificar():
    motor = MotorAnalise()
    prog = st.progress(0, "Classificando...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        try: st.session_state.carteira_acoes.at[i, "Setor"] = motor.identificar_setor(yf.Ticker(formatar_ticker_global(row["Ticker"])).info, row["Ticker"])
        except: st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    prog.empty(); st.success("Ok!")

def calcular_consolidado():
    total_rf = st.session_state.carteira_rf["Saldo Atual"].sum()
    df = st.session_state.carteira_acoes.copy()
    tickers = [formatar_ticker_global(t) for t in df["Ticker"]]
    try:
        dados = yf.download(tickers, period="1d", progress=False)['Close'].iloc[-1]
    except:
        dados = pd.Series(dtype=float)

    patrimonio_acoes = 0
    lista_valores = []

    for i, row in df.iterrows():
        t_fmt = formatar_ticker_global(row["Ticker"])
        try: preco = float(dados[t_fmt])
        except: 
            d_ind = obter_dados(t_fmt)
            preco = d_ind['preco'] if d_ind else 0.0
        
        val_posicao = row["Qtd"] * preco
        patrimonio_acoes += val_posicao
        lista_valores.append(val_posicao)
    
    df["Valor Atual"] = lista_valores
    return total_rf, patrimonio_acoes, df

# ======================================================
# 6. UI
# ======================================================
st.title("💰 Hedge Fund Ricardo v109")

with st.sidebar:
    st.header("Importação B3 (Novo)")
    b3_file = st.file_uploader("📂 Arraste o Excel da B3", type=['xlsx', 'xls'])
    if b3_file:
        if st.button("Processar Arquivo B3"):
            df_b3, msg = processar_excel_b3(b3_file)
            if df_b3 is not None and not df_b3.empty:
                st.session_state.carteira_acoes = df_b3
                st.success(f"Sucesso! {len(df_b3)} ativos carregados da B3.")
                st.rerun()
            else:
                st.error(f"Erro: {msg}")

    st.divider()
    st.header("Backup")
    csv = st.session_state.carteira_acoes.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Salvar Backup", csv, "backup_v109.csv", "text/csv")
    up = st.file_uploader("📂 Restaurar Backup", type=['csv'])
    if up:
        try:
            st.session_state.carteira_acoes = pd.read_csv(up)
            st.success("Restaurado!"); st.rerun()
        except: st.error("Erro no arquivo")
    
    st.divider()
    if st.button("🆘 Restaurar Padrão"): 
        st.session_state.carteira_acoes = carregar_carteira_padrao()
        st.rerun()
    if st.button("🧹 Limpeza de Cache"): 
        st.cache_data.clear()
        st.rerun()

tabs = st.tabs(["📊 Dashboard CEO", "🔎 Análise Global", "💼 Carteira", "🏢 Scanner", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# ABA 1: DASHBOARD
with tabs[0]:
    st.subheader("Visão Geral do Patrimônio")
    if st.button("🔄 Atualizar (Real-Time)"):
        st.cache_data.clear()
        st.rerun()

    tot_rf, tot_rv, df_rv = calcular_consolidado()
    tot_geral = tot_rf + tot_rv
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Patrimônio Total (AUM)", f"R$ {tot_geral:,.2f}")
    k2.metric("Renda Variável", f"R$ {tot_rv:,.2f}", f"{(tot_rv/tot_geral)*100:.1f}%" if tot_geral>0 else "0%")
    k3.metric("Renda Fixa / Caixa", f"R$ {tot_rf:,.2f}", f"{(tot_rf/tot_geral)*100:.1f}%" if tot_geral>0 else "0%")
    
    st.divider()

    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.subheader("🍕 Alocação por Setor")
        if not df_rv.empty:
            df_sector = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
            if tot_rf > 0:
                df_sector = pd.concat([df_sector, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": tot_rf}])], ignore_index=True)
            fig = px.pie(df_sector, values='Valor Atual', names='Setor', hole=0.4, title="Distribuição do Portfólio")
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Carteira vazia.")

    with c_chart2:
        st.subheader("🎯 Metas vs Realidade")
        if not df_rv.empty and tot_geral > 0:
            df_atual = df_rv.groupby("Setor")["Valor Atual"].sum().reset_index()
            if tot_rf > 0:
                df_atual = pd.concat([df_atual, pd.DataFrame([{"Setor": "Renda Fixa", "Valor Atual": tot_rf}])], ignore_index=True)
            df_atual["% Atual"] = (df_atual["Valor Atual"] / tot_geral) * 100
            
            df_comparacao = pd.merge(st.session_state.df_metas, df_atual, on="Setor", how="outer").fillna(0)
            fig_bar = px.bar(df_comparacao, x="Setor", y=["% Atual", "Meta (%)"], barmode="group", title="Aderência ao Mandato")
            st.plotly_chart(fig_bar, use_container_width=True)

# ABA 2: ANÁLISE GLOBAL
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
            cor_prox = "normal" if div_info.get('status') == 'AGENDA' else "off"
            d2.metric("Próximo", div_info.get('proximo_valor', '-'), div_info.get('proximo_data', '-'), delta_color=cor_prox)
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

# ABA 3: CARTEIRA
with tabs[2]:
    c1, c2 = st.columns([1, 2])
    c1.subheader("Metas %")
    st.session_state.df_metas = c1.data_editor(st.session_state.df_metas, num_rows="dynamic")
    
    c2.subheader(f"Meus Ativos ({len(st.session_state.carteira_acoes)})")
    if c2.button("Classificar (Global)"): auto_classificar()
    
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

# DEMAIS ABAS
with tabs[3]:
    st.subheader("Scanner")
    if st.button("Auto Scanner") and scanner_auto_yahoo: st.dataframe(scanner_auto_yahoo())
    up = st.file_uploader("CSV", type=["csv"])
    if up and scanner_fiis_csv: st.dataframe(scanner_fiis_csv(up))

with tabs[4]:
    st.subheader("Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Total", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

with tabs[5]:
    if st.button("Monte Carlo"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: st.line_chart(MotorAnalise().monte_carlo_carteira(h.pct_change().dropna().mean(axis=1) if isinstance(h, pd.DataFrame) else h.pct_change().dropna(), 100000, 2000))

with tabs[6]:
    if st.button("DARF") and calcular_darf: st.table(calcular_darf(st.session_state.carteira_acoes))

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
            g1.metric("Delta (Δ)", f"{gregas['Delta']:.3f}", help="Sensibilidade ao Preço")
            g2.metric("Gamma (Γ)", f"{gregas['Gamma']:.3f}", help="Aceleração do Delta")
            g3.metric("Theta (Θ)", f"{gregas['Theta']:.3f}", help="Perda de valor por dia (Time Decay)")
            g4.metric("Vega (ν)", f"{gregas['Vega']:.3f}", help="Sensibilidade à Volatilidade")