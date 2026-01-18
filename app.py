import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np

# ======================================================
# 1. IMPORTAÇÃO SEGURA DE MÓDULOS (BLINDAGEM)
# ======================================================
try:
    # Módulos Essenciais
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    
    # Módulos Utilitários (Opcionais, mas recomendados)
    try: from report import gerar_pdf_carteira
    except: gerar_pdf_carteira = None
    
    try: from scanner import scanner_fiis_csv, scanner_auto_yahoo
    except: 
        scanner_fiis_csv = None
        scanner_auto_yahoo = None
        
    try: from tax import calcular_darf
    except: calcular_darf = None
    
    try: from options import BlackScholes
    except: BlackScholes = None

except ImportError as e:
    st.error(f"❌ Erro Crítico de Importação: {e}. Verifique se todos os arquivos (.py) estão na pasta.")
    st.stop()

# Configuração da Página (Deve ser a primeira chamada Streamlit)
st.set_page_config(page_title="Hedge Fund Ricardo v70.0", layout="wide", page_icon="💰")

# ======================================================
# 2. FUNÇÕES DE CACHE E DADOS (MOTOR)
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados(ticker):
    """Baixa dados e passa pelo Cérebro (MotorAnalise)"""
    try:
        t = yf.Ticker(ticker)
        # Baixa 2 anos para garantir médias longas (MME200, etc)
        hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_historico_longo(tickers):
    """Baixa histórico de 5 anos para Monte Carlo"""
    try:
        data = yf.download(tickers, period="5y", progress=False)
        if isinstance(data, pd.DataFrame):
            if "Adj Close" in data: return data["Adj Close"]
            if "Close" in data: return data["Close"]
        return data
    except: return pd.DataFrame()

def auto_classificar():
    """Função Auxiliar para Classificar Ativos em Lote"""
    motor = MotorAnalise()
    prog = st.progress(0, text="🤖 A IA está classificando seus ativos...")
    total = len(st.session_state.carteira_acoes)
    
    for i, row in st.session_state.carteira_acoes.iterrows():
        try:
            t = yf.Ticker(row["Ticker"])
            setor = motor.identificar_setor(t.info, row["Ticker"])
            st.session_state.carteira_acoes.at[i, "Setor"] = setor
        except: 
            st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    
    prog.empty()
    st.toast("✅ Classificação Concluída!", icon="🧠")

# ======================================================
# 3. INICIALIZAÇÃO DE ESTADO (SESSION STATE)
# ======================================================

# A) Metas da Estratégia (Editáveis)
if "df_metas" not in st.session_state:
    dados_metas = [
        {"Setor": "Renda Fixa", "Meta (%)": 30.0},
        {"Setor": "Exterior", "Meta (%)": 20.0},
        {"Setor": "Ações-Bancos", "Meta (%)": 7.5},
        {"Setor": "Ações-Elétricas", "Meta (%)": 7.5},
        {"Setor": "Ações-Seguridade", "Meta (%)": 6.0},
        {"Setor": "Ações-Commodities", "Meta (%)": 6.0},
        {"Setor": "Ações-Outros", "Meta (%)": 3.0},
        {"Setor": "FIIs-Papel", "Meta (%)": 10.0},
        {"Setor": "FIIs-Tijolo", "Meta (%)": 6.0},
        {"Setor": "FIIs-Outros", "Meta (%)": 4.0}
    ]
    st.session_state.df_metas = pd.DataFrame(dados_metas)

# B) Carteira de Ativos
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Aguardando..."],
        ["CPSH11.SA", 50, 10.10, "Aguardando..."],
        ["XPML11.SA", 10, 115.00, "Aguardando..."],
        ["IVVB11.SA", 5, 280.00, "Aguardando..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

# C) Carteira de Renda Fixa
if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000.0, "Pós-Fixado"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

# ======================================================
# 4. INTERFACE GRÁFICA (UI)
# ======================================================
st.title("💰 Hedge Fund Ricardo")

# --- BARRA LATERAL (Sidebar) ---
with st.sidebar:
    st.header("🎮 Painel de Controle")
    
    if st.button("🧹 Limpar Cache / Atualizar"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    st.header("📄 Private Bank Docs")
    if gerar_pdf_carteira:
        # Lógica para preparar os dados do PDF
        total_rf = st.session_state.carteira_rf["Saldo Atual"].sum()
        
        # Cria cópia para não alterar o original
        df_rep = st.session_state.carteira_acoes.copy()
        
        # Se ainda não rodou análise, estima valor pelo PM (fallback)
        if "Valor_Atual" not in df_rep.columns: 
            df_rep["Valor_Atual"] = df_rep["Qtd"] * df_rep["PM"]
        
        total_patrimonio = total_rf + df_rep["Valor_Atual"].sum()
        
        # Dicionário de metas para o PDF
        dict_metas = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
        
        if st.button("🖨️ Gerar Relatório Mensal"):
            try:
                pdf_bytes = gerar_pdf_carteira(df_rep, st.session_state.carteira_rf, total_patrimonio, dict_metas)
                st.download_button(
                    label="📥 Baixar PDF Agora",
                    data=pdf_bytes,
                    file_name="Relatorio_Hedge_Fund_Ricardo.pdf",
                    mime="application/pdf"
                )
                st.success("Relatório Gerado!")
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
    else:
        st.info("⚠️ Biblioteca 'fpdf' não detectada. Instale para gerar relatórios.")

# --- NAVEGAÇÃO POR ABAS ---
tabs = st.tabs([
    "🔎 Análise Completa", 
    "💼 Carteira & Estratégia", 
    "🏢 FIIs 360", 
    "🛡️ Renda Fixa", 
    "💰 Futuro (Monte Carlo)", 
    "🦁 Fiscal (DARF)", 
    "⚡ Opções (Black-Scholes)"
])

# ======================================================
# ABA 1: ANÁLISE (O Hub Central de Inteligência)
# ======================================================
with tabs[0]:
    col_input, col_btn = st.columns([4, 1])
    t = col_input.text_input("Digite o Ticker para Analisar:", "MXRF11.SA").upper()
    if col_btn.button("🔍 Analisar Ativo"):
        r = obter_dados(t)
        if r:
            # --- 1. CABEÇALHO: PREÇO, DY E RISCO ---
            st.subheader("📊 Raio-X & Segurança")
            c1, c2, c3, c4 = st.columns(4)
            
            c1.metric("Preço Atual", f"R$ {r.get('preco', 0):.2f}")
            c2.metric("DY Anual (Real)", f"{r.get('dy_anual', 0):.2f}%")
            
            # Score com Tratamento de Erro (Score 0 = Bloqueio)
            score_val = r.get('score_ia', 0)
            if score_val == 0:
                c3.error("⛔ BLOQUEADO (Risco)")
            else:
                c3.metric("Score IA", f"{score_val}/100", delta=r.get('decisao_ia', 'Neutro'))
            
            liq = r.get('liq_media', 0)
            c4.metric("Liquidez Média", f"R$ {liq/1000:.0f}k")
            
            # --- 2. VALOR JUSTO & ENTRADA (O Robô) ---
            st.divider()
            col_v1, col_v2 = st.columns(2)
            
            with col_v1:
                st.markdown("### 💎 Valuation (Preço Justo)")
                
                # Exibe o Valor Justo calculado pela IA
                justo_ia = r.get('preco_justo', 0)
                if justo_ia > 0:
                    delta_justo = (r['preco'] - justo_ia) / justo_ia * 100
                    label_delta = f"{delta_justo:+.1f}% ({'Ágio' if delta_justo > 0 else 'Desconto'})"
                    cor_delta = "inverse" if delta_justo > 0 else "normal" # Verde se desconto
                    st.metric("Preço Teto Sugerido (IA)", f"R$ {justo_ia:.2f}", delta=label_delta, delta_color=cor_delta)
                else:
                    st.info("Valuation inconclusivo (LPA/VPA negativos ou sem dividendos).")

                # Tabela de Modelos
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin (Foco Dividendos)", "Graham (Foco Patrimônio)", "Gordon (Crescimento)"], 
                    "Valor Teto": [f"R$ {r.get('p_bazin',0):.2f}", f"R$ {r.get('p_graham',0):.2f}", f"R$ {r.get('p_gordon',0):.2f}"]
                }))

            with col_v2:
                st.markdown("### 🧠 Parecer da Inteligência")
                motivos = r.get('motivos', '')
                if "⚠️" in motivos or "⛔" in motivos:
                    st.error(f"🚨 ALERTAS: {motivos}")
                else:
                    st.success(f"✅ PONTOS FORTES: {motivos}")

            # --- 3. PAINEL ALGO-TRADING (TÉCNICO) ---
            st.subheader("📈 Painel Algo-Trading (Timing)")
            
            # Cards Técnicos
            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("Tendência (9x21)", r.get('sinal_tecnico', 'Neutro'))
            
            # Lógica MACD para exibição
            macd = r.get('macd', 0)
            sinal = r.get('macd_signal', 0)
            status_macd = "COMPRA" if macd > sinal else "VENDA"
            tc2.metric("Momentum (MACD)", status_macd, delta=f"{macd:.2f}")
            
            tc3.metric("🛑 Stop Loss", f"R$ {r.get('stop_loss', 0):.2f}")
            tc4.metric("✅ Stop Gain", f"R$ {r.get('stop_gain', 0):.2f}")

            # Tabela Detalhada de Indicadores
            rsi = r.get('rsi', 50)
            vol = r.get('volatilidade', 0)
            vrel = r.get('vol_relativo', 1.0)
            
            df_tec = pd.DataFrame([
                {"Indicador": "RSI (14)", "Leitura": f"{rsi:.0f}", "Status": "Sobrecomprado" if rsi>70 else "Sobrevendido" if rsi<30 else "Neutro"},
                {"Indicador": "Volatilidade (Anual)", "Leitura": f"{vol*100:.1f}%", "Status": "Risco de Mercado"},
                {"Indicador": "Volume Relativo", "Leitura": f"{vrel:.2f}x", "Status": "Alto Interesse" if vrel > 1.2 else "Normal"},
                {"Indicador": "Suporte (Piso)", "Leitura": f"R$ {r.get('suporte', 0):.2f}", "Status": "Mínima 60d"},
                {"Indicador": "Resistência (Teto)", "Leitura": f"R$ {r.get('resistencia', 0):.2f}", "Status": "Máxima 60d"}
            ])
            st.dataframe(df_tec, use_container_width=True)

            # --- 4. GRÁFICO TRADINGVIEW ---
            st.markdown("---")
            st.caption("Gráfico Interativo (TradingView)")
            symbol_tv = f"BMFBOVESPA:{t.replace('.SA','')}"
            components.html(f"""
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <div id="tv_chart"></div>
                <script type="text/javascript">
                new TradingView.widget({{
                  "width": "100%", "height": 500, "symbol": "{symbol_tv}",
                  "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light",
                  "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6",
                  "enable_publishing": false, "container_id": "tv_chart"
                }});
                </script>
            """, height=500)
            
        else:
            st.warning("Ativo não encontrado ou sem dados históricos suficientes. Tente limpar o cache.")

# ======================================================
# ABA 2: CARTEIRA & ESTRATÉGIA (O Coração da Gestão)
# ======================================================
with tabs[1]:
    col_ativos, col_metas = st.columns([2, 1])
    
    # --- COLUNA DIREITA: METAS ---
    with col_metas:
        st.subheader("🎯 Sua Estratégia")
        st.info("Defina aqui o % ideal para cada setor.")
        
        # Editor de Metas
        df_metas_edit = st.data_editor(
            st.session_state.df_metas,
            column_config={
                "Meta (%)": st.column_config.NumberColumn("Alvo %", min_value=0, max_value=100, format="%.1f%%")
            },
            num_rows="dynamic",
            use_container_width=True,
            key="editor_metas"
        )
        st.session_state.df_metas = df_metas_edit
        
        # Validação de Soma 100%
        total_metas = df_metas_edit["Meta (%)"].sum()
        if abs(total_metas - 100.0) > 0.1:
            st.warning(f"⚠️ A soma das metas é {total_metas:.1f}%. Ajuste para 100%.")
        else:
            st.success("✅ Estratégia Balanceada (100%)")

    # --- COLUNA ESQUERDA: ATIVOS ---
    with col_ativos:
        st.subheader("💼 Seus Ativos")
        
        col_btns_1, col_btns_2 = st.columns(2)
        with col_btns_1:
            if st.button("🤖 Auto-Classificar Setores"):
                auto_classificar()
                st.rerun()
        
        # Pega as opções de setor das metas para o dropdown
        opcoes_setor = df_metas_edit["Setor"].tolist()
        
        # Editor da Carteira
        df_editor_carteira = st.data_editor(
            st.session_state.carteira_acoes,
            column_config={
                "Setor": st.column_config.SelectboxColumn("Setor", options=opcoes_setor, required=True),
                "Qtd": st.column_config.NumberColumn("Qtd", min_value=0, format="%d"),
                "PM": st.column_config.NumberColumn("Preço Médio", format="R$ %.2f")
            },
            num_rows="dynamic",
            use_container_width=True,
            key="editor_carteira"
        )
        st.session_state.carteira_acoes = df_editor_carteira
        
        st.divider()
        
        # --- ÁREA DE REBALANCEAMENTO ---
        st.subheader("🚀 Gerador de Aportes")
        valor_aporte = st.number_input("Quanto você vai investir hoje? (R$)", value=5000.0, step=100.0)
        
        if st.button("Calcular Rebalanceamento Inteligente"):
            if abs(total_metas - 100.0) > 0.1:
                st.error("Corrija as metas para 100% antes de calcular.")
            else:
                with st.spinner("O Robô está analisando os melhores ativos..."):
                    # 1. Prepara Dicionário de Metas
                    dict_metas = dict(zip(df_metas_edit["Setor"], df_metas_edit["Meta (%)"]))
                    
                    # 2. Enriquece a carteira com dados atuais (Preço e Score)
                    dados_para_algoritmo = []
                    for _, row in df_editor_carteira.iterrows():
                        d = obter_dados(row["Ticker"])
                        if d:
                            dados_para_algoritmo.append({
                                "Ticker": row["Ticker"],
                                "Setor": row["Setor"],
                                "Qtd": row["Qtd"],
                                "Valor_Atual": row["Qtd"] * d["preco"],
                                "Preço": d["preco"],
                                "Score": d["score_ia"] # Usa o Score IA para desempatar
                            })
                        else:
                            # Fallback se falhar download
                            dados_para_algoritmo.append({
                                "Ticker": row["Ticker"],
                                "Setor": row["Setor"],
                                "Qtd": row["Qtd"],
                                "Valor_Atual": row["Qtd"] * 10.0,
                                "Preço": 10.0,
                                "Score": 50
                            })
                    
                    # 3. Executa o Rebalanceamento
                    df_calc = pd.DataFrame(dados_para_algoritmo)
                    df_resultado = rebalancear_e_aportar(df_calc, valor_aporte, dict_metas)
                    
                    # 4. Filtra e Exibe
                    sugestoes = df_resultado[df_resultado["Aporte Sugerido (R$)"] > 1].copy()
                    
                    if sugestoes.empty and df_resultado["Aporte Sugerido (R$)"].sum() > 0:
                        st.warning("O algoritmo detectou que os ativos sugeridos possuem Risco Elevado (Score 0) e bloqueou a compra.")
                    else:
                        st.balloons()
                        st.success("✅ Plano de Compra Gerado:")
                        st.dataframe(
                            sugestoes[["Ticker", "Setor", "Score", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}),
                            use_container_width=True
                        )

# ======================================================
# ABA 3: SCANNER HÍBRIDO (CSV + AUTO)
# ======================================================
with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360")
    
    modo_scan = st.radio("Modo de Operação:", 
                         ["🤖 Modo Automático (Yahoo - Rápido)", "📂 Modo Preciso (CSV StatusInvest - Completo)"], 
                         horizontal=True)
    
    if "Automático" in modo_scan:
        st.info("O Modo Automático varre os principais FIIs do IFIX em busca de oportunidades de Dividendos.")
        if st.button("🚀 Iniciar Varredura Automática"):
            if scanner_auto_yahoo:
                with st.spinner("Analisando mercado..."):
                    df_auto = scanner_auto_yahoo()
                    st.dataframe(df_auto, use_container_width=True)
            else:
                st.error("Função 'scanner_auto_yahoo' não encontrada no arquivo scanner.py.")
    
    else:
        st.info("Faça o upload do CSV da 'Busca Avançada' do StatusInvest para analisar Vacância, P/VP Real e Liquidez.")
        uploaded_file = st.file_uploader("Arraste o arquivo aqui (.csv)", type=["csv"])
        if uploaded_file and scanner_fiis_csv:
            df_csv = scanner_fiis_csv(uploaded_file)
            st.dataframe(df_csv, use_container_width=True)

# ======================================================
# ABA 4: RENDA FIXA
# ======================================================
with tabs[3]:
    st.subheader("🛡️ Controle de Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(
        st.session_state.carteira_rf, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Saldo Atual": st.column_config.NumberColumn(format="R$ %.2f")
        }
    )
    total_rf = st.session_state.carteira_rf["Saldo Atual"].sum()
    st.metric("Total em Renda Fixa", f"R$ {total_rf:,.2f}")

# ======================================================
# ABA 5: FUTURO (MONTE CARLO)
# ======================================================
with tabs[4]:
    st.subheader("🔮 Simulação de Futuro (Monte Carlo)")
    st.write("Projeta 1000 cenários possíveis para sua carteira atual nos próximos 10 anos.")
    
    if st.button("🎲 Rodar Simulação"):
        tickers_mc = st.session_state.carteira_acoes["Ticker"].tolist()
        if not tickers_mc:
            st.warning("Adicione ativos na carteira primeiro.")
        else:
            with st.spinner("Simulando cenários..."):
                hist_mc = download_historico_longo(tickers_mc)
                if not hist_mc.empty:
                    # Calcula retornos diários
                    retornos = hist_mc.pct_change().dropna()
                    # Se for DataFrame, tira a média dos ativos (portfolio equiponderado simples para simulação)
                    if isinstance(retornos, pd.DataFrame):
                        retornos_carteira = retornos.mean(axis=1)
                    else:
                        retornos_carteira = retornos
                    
                    motor_mc = MotorAnalise()
                    # Simula: 100k inicial, aporte 2k/mês, 10 anos
                    projecao = motor_mc.monte_carlo_carteira(retornos_carteira, 100000, 2000)
                    
                    if len(projecao) > 0:
                        st.line_chart(projecao)
                        st.caption("Eixo Y: Patrimônio Acumulado | Eixo X: Simulações")
                    else:
                        st.error("Erro matemático na simulação.")
                else:
                    st.error("Não foi possível baixar dados históricos suficientes.")

# ======================================================
# ABA 6: FISCAL (DARF)
# ======================================================
with tabs[5]:
    st.subheader("🦁 Calculadora Fiscal (Simulação)")
    st.info("Calcula o imposto devido caso você vendesse toda sua posição hoje (Lucro Latente).")
    
    if st.button("🧮 Calcular DARF Estimado"):
        if calcular_darf:
            with st.spinner("Consultando preços atuais e calculando impostos..."):
                # Prepara DataFrame com Qtd e PM
                df_fiscal = st.session_state.carteira_acoes.copy()
                resultado_fiscal = calcular_darf(df_fiscal)
                st.table(resultado_fiscal)
        else:
            st.error("Módulo 'tax.py' não encontrado.")

# ======================================================
# ABA 7: OPÇÕES (BLACK-SCHOLES)
# ======================================================
with tabs[6]:
    st.subheader("⚡ Simulador de Opções (Black-Scholes)")
    
    if BlackScholes:
        col_params_1, col_params_2 = st.columns(2)
        
        with col_params_1:
            opt_type = st.radio("Tipo de Opção", ["Call (Compra)", "Put (Venda)"], horizontal=True)
            spot_price = st.number_input("Preço do Ativo (Spot)", value=30.00, step=0.10)
            strike_price = st.number_input("Strike (Exercício)", value=32.00, step=0.10)
        
        with col_params_2:
            days_to_expire = st.number_input("Dias até Vencimento", value=30, step=1)
            volatility = st.number_input("Volatilidade Implícita (%)", value=30.0, step=1.0)
            risk_free = st.number_input("Taxa de Juros Livre de Risco (%)", value=13.75, step=0.25)

        # Cálculo
        tipo_simples = "call" if "Call" in opt_type else "put"
        bs = BlackScholes(spot_price, strike_price, days_to_expire/365, risk_free/100, volatility/100, tipo_simples)
        
        preco_justo = bs.calcular_preco()
        gregas = bs.calcular_gregas()
        
        st.divider()
        
        c_result, c_gregas = st.columns([1, 2])
        
        with c_result:
            st.metric("Prêmio Teórico", f"R$ {preco_justo:.3f}")
        
        with c_gregas:
            st.markdown("**Gregas (Sensibilidade):**")
            g1, g2, g3, g4, g5 = st.columns(5)
            g1.metric("Delta", f"{gregas['Delta']:.2f}", help="Variação preço/ativo")
            g2.metric("Gamma", f"{gregas['Gamma']:.3f}", help="Aceleração do Delta")
            g3.metric("Theta", f"{gregas['Theta']:.3f}", help="Perda de valor por dia (Time Decay)")
            g4.metric("Vega", f"{gregas['Vega']:.3f}", help="Sensibilidade à Volatilidade")
            g5.metric("Rho", f"{gregas['Rho']:.3f}", help="Sensibilidade aos Juros")
            
    else:
        st.error("Módulo 'options.py' não encontrado.")