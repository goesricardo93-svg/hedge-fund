import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import datetime

# ======================================================
# 1. IMPORTAÇÃO DOS MÓDULOS
# ======================================================
try:
    from motor import MotorAnalise
    from scanner import scanner_fiis_csv
    from alerts import disparar_alerta, enviar_relatorio_anexo
    from rebalance import rebalancear_e_aportar
    from tax import calcular_darf
    from relatorio import RelatorioPrivate
    from options import BlackScholes
except ImportError as e:
    st.error(f"Erro Crítico: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 53.0 (Anti-Crash)", layout="wide")

# ======================================================
# 2. CACHE E FUNÇÕES
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados_v53(ticker): 
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_historico_longo(tickers):
    data = yf.download(tickers, period="5y", progress=False)
    if isinstance(data, pd.DataFrame):
        if "Adj Close" in data: return data["Adj Close"]
        elif "Close" in data: return data["Close"]
    return data

def formatar_ticker(ticker):
    t = ticker.strip().upper()
    if t in ["BTC", "ETH", "SOL", "USDT"]: return f"{t}-USD"
    if any(char.isdigit() for char in t) and "." not in t: return f"{t}.SA"
    return t

def renderizar_tradingview_widget(ticker):
    tv_symbol = ticker
    if ".SA" in ticker:
        clean = ticker.replace(".SA", "")
        tv_symbol = f"BMFBOVESPA:{clean}"
    elif "-USD" in ticker:
        clean = ticker.replace("-USD", "")
        tv_symbol = f"BINANCE:{clean}USDT"
    
    html_code = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "width": "100%", "height": 500, "symbol": "{tv_symbol}",
        "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light",
        "style": "1", "locale": "br", "toolbar_bg": "#f1f3f6",
        "enable_publishing": false, "allow_symbol_change": false,
        "container_id": "tradingview_chart"
      }}
      );
      </script>
    </div>
    """
    components.html(html_code, height=500)

# ======================================================
# 3. ESTADO DA SESSÃO (COM AUTOCORREÇÃO)
# ======================================================
# Inicialização Padrão
if "carteira_acoes" not in st.session_state:
    dados = [
        ["BBAS3.SA", 1703, 24.48, "Ações-Bancos"], 
        ["ITSA4.SA", 1174, 9.63,  "Ações-Bancos"],
        ["TAEE4.SA", 1000, 11.36, "Ações-Elétricas"],
        ["CPLE3.SA", 617, 9.64,   "Ações-Elétricas"],
        ["BBSE3.SA", 55, 35.64,   "Ações-Seguridade"],
        ["VALE3.SA", 152, 54.79,  "Ações-Commodities"],
        ["PETR4.SA", 900, 32.07,  "Ações-Commodities"],
        ["IVVB11.SA", 6, 366.97,  "Exterior"],
        ["KNCR11.SA", 27, 103.11, "FIIs-Papel"],
        ["HGLG11.SA", 20, 158.03, "FIIs-Tijolo"]
    ]
    st.session_state.carteira_acoes = pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM", "Setor"])

# --- AUTOCORREÇÃO DE COLUNAS (CORREÇÃO DO ERRO KEYERROR) ---
# Se a carteira existe mas falta a coluna "Setor" (cache antigo), criamos ela agora.
if "Setor" not in st.session_state.carteira_acoes.columns:
    st.session_state.carteira_acoes["Setor"] = "Ações-Outros"
    st.toast("Sistema atualizou a estrutura da tabela automaticamente.", icon="🛠️")
# -----------------------------------------------------------

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000.0, "Pós-Fixado"],
        ["PGBL BTG", 50000.0, "Previdência"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# 4. ROBÔ DE AUTOMAÇÃO
# ======================================================
hoje = datetime.date.today()
mes_str = hoje.strftime("%Y-%m")
forcar_envio = st.query_params.get("run_report") == "true"

if (hoje.day == 1 or forcar_envio) and f"report_{mes_str}" not in st.session_state:
    with st.spinner("🤖 Processando Fechamento..."):
        try:
            res_auto = []
            for _, row in st.session_state.carteira_acoes.iterrows():
                r = obter_dados_v53(row["Ticker"])
                if r:
                    res_auto.append({
                        "Ticker": row["Ticker"], "Preço": r["preco"], "PM": row["PM"],
                        "Valor_Atual": row["Qtd"] * r["preco"], 
                        "Lucro": (r["preco"] - row["PM"]) * row["Qtd"],
                        "Score": r['score_ia']
                    })
            if res_auto:
                df_auto = pd.DataFrame(res_auto)
                pdf_bytes = RelatorioPrivate(df_auto, df_auto["Valor_Atual"].sum()).gerar_pdf()
                enviar_relatorio_anexo(pdf_bytes, f"Relatorio_{mes_str}.pdf")
                st.session_state[f"report_{mes_str}"] = True
                st.toast("Relatório enviado!", icon="🚀")
        except: pass

# ======================================================
# 5. INTERFACE
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")
if st.sidebar.button("🧹 Limpar Cache"):
    st.cache_data.clear()
    st.toast("Memória limpa!", icon="🧹")

ticker_raw = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3").upper()
ticker_input = formatar_ticker(ticker_raw)

if st.sidebar.button("🔄 Restaurar Padrões"):
    st.session_state.clear()
    st.rerun()

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ RF & PGBL", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    motor = MotorAnalise()
    r = obter_dados_v53(ticker_input)
    
    if r:
        div_info = motor.consultar_dividendos(ticker_input)
        cor_box = "green" if div_info['status'] == "AGENDA" else "blue"
        st.markdown(f"""
        <div style="padding:15px; border-radius:10px; background-color:rgba(0,100,0,0.05); border:1px solid {cor_box}; margin-bottom:15px;">
            <h4 style="margin-top:0; color:{cor_box};">💰 Relatório de Proventos</h4>
            <table style="width:100%; border:none;">
                <tr><td style="font-weight:bold;">⏪ Último Pago:</td><td>{div_info['ultimo_data']}</td><td><b>{div_info['ultimo_valor']}</b></td></tr>
                <tr><td style="font-weight:bold; color:{cor_box};">⏩ Próximo (Prev):</td><td>{div_info['proximo_data']}</td><td><b>{div_info['proximo_valor']}</b></td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

        col_ia1, col_ia2 = st.columns([1, 3])
        col_ia1.metric("Score IA (Rigoroso)", f"{r['score_ia']}/100")
        if "COMPRA" in r['decisao_ia']: col_ia2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']: col_ia2.error(f"### {r['decisao_ia']}")
        else: col_ia2.warning(f"### {r['decisao_ia']}")
        
        st.write(f"**Veredito:** {r['motivos']}")
        st.divider()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        k2.metric("Teto (Alvo IA)", f"R$ {r['stop_gain']:.2f}")
        k3.metric("RSI (14)", f"{r['rsi']:.0f}")
        k4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📋 Valuation")
            st.dataframe(pd.DataFrame({
                "Modelo": ["Bazin (Div)", "Graham (Patr)", "Gordon (Cresc)"],
                "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
            }), use_container_width=True)
        with c2:
            st.subheader("📊 Solvência & Qualidade")
            liq_fmt = f"{r['liq_corrente']:.2f}" if r.get('liq_corrente') else "-"
            cresc_fmt = f"{r['cresc_receita']*100:.1f}%" if r.get('cresc_receita') else "-"
            st.dataframe(pd.DataFrame({
                "Indicador": ["Liquidez Corrente", "Cresc. Receita", "Dívida/EBITDA", "ROE"],
                "Valor": [liq_fmt, cresc_fmt, f"{r['divida_ebitda']:.2f}x" if r.get('divida_ebitda') else "-", f"{r['roe']*100:.1f}%"]
            }), use_container_width=True)

        st.divider()
        renderizar_tradingview_widget(ticker_input)
        
        st.subheader("🎯 Setup Operacional")
        sinal = r['sinal_tecnico']
        cor_sinal = "🟢" if "COMPRA" in sinal else "🔴" if "VENDA" in sinal else "⚪"
        vol_txt = f"{r['vol_relativo']:.1f}x Média" if r['vol_relativo'] > 0 else "-"
        macd_s = "↗️ Alta" if r['macd'] > r['macd_signal'] else "↘️ Baixa"
        
        st.dataframe(pd.DataFrame([
            {"Indicador": "🤖 SINAL TÉCNICO", "Valor": f"{cor_sinal} {sinal}"},
            {"Indicador": "Preço Entrada", "Valor": f"R$ {r['preco_alvo_entrada']:.2f}" if r['preco_alvo_entrada'] > 0 else "-"},
            {"Indicador": "Volume Relativo", "Valor": vol_txt},
            {"Indicador": "Tendência MACD", "Valor": macd_s},
            {"Indicador": "Média Curta (9)", "Valor": f"R$ {r['mme9']:.2f}"},
            {"Indicador": "Média Longa (21)", "Valor": f"R$ {r['mme21']:.2f}"},
            {"Indicador": "🛑 Stop Loss", "Valor": f"R$ {r['stop_loss']:.2f}"}
        ]), use_container_width=True, hide_index=True)

    else: st.warning("Ativo não encontrado. Limpe o cache.")

# --- ABA 2: CARTEIRA (ESTRATÉGIA FINA) ---
with tabs[1]:
    st.subheader(f"💼 Gestão de Carteira ({len(st.session_state.carteira_acoes)} Ativos)")
    
    # --- CONFIGURAÇÃO DA ESTRATÉGIA ---
    with st.expander("⚙️ Sua Estratégia de Alocação (%)", expanded=True):
        st.info("Estratégia Personalizada Definida: Exterior 20%, RF 30%, Ações 30% (Subdivididas), FIIs 20% (Subdivididos).")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**🌍 Macro & Renda Fixa**")
            m_rf = st.number_input("Renda Fixa (%)", 0.0, 100.0, 30.0, step=0.5)
            m_ext = st.number_input("Exterior/UCITS (%)", 0.0, 100.0, 20.0, step=0.5)
        
        with c2:
            st.markdown("**📈 Ações (Meta 30% Total)**")
            m_bancos = st.number_input("Ações - Bancos (%)", 0.0, 100.0, 7.5, step=0.5, help="25% de 30%")
            m_eletricas = st.number_input("Ações - Elétricas (%)", 0.0, 100.0, 7.5, step=0.5, help="25% de 30%")
            m_seguridade = st.number_input("Ações - Seguridade (%)", 0.0, 100.0, 6.0, step=0.5, help="20% de 30%")
            m_commod = st.number_input("Ações - Commodities (%)", 0.0, 100.0, 6.0, step=0.5, help="20% de 30%")
            m_acoes_outros = st.number_input("Ações - Outros (%)", 0.0, 100.0, 3.0, step=0.5, help="10% de 30%")
            
        with c3:
            st.markdown("**🏢 FIIs (Meta 20% Total)**")
            m_papel = st.number_input("FIIs - Papel (%)", 0.0, 100.0, 10.0, step=0.5, help="50% de 20%")
            m_tijolo = st.number_input("FIIs - Tijolo (%)", 0.0, 100.0, 6.0, step=0.5, help="30% de 20%")
            m_fii_outros = st.number_input("FIIs - Outros (%)", 0.0, 100.0, 4.0, step=0.5, help="20% de 20%")

        # Checagem de 100%
        total_meta = m_rf + m_ext + m_bancos + m_eletricas + m_seguridade + m_commod + m_acoes_outros + m_papel + m_tijolo + m_fii_outros
        if abs(total_meta - 100.0) > 0.1:
            st.error(f"⚠️ A soma das metas está em {total_meta:.1f}%. Ajuste para 100%.")
        else:
            st.success("✅ Estratégia Validada (100%)")

        metas = {
            "Renda Fixa": m_rf,
            "Exterior": m_ext,
            "Ações-Bancos": m_bancos,
            "Ações-Elétricas": m_eletricas,
            "Ações-Seguridade": m_seguridade,
            "Ações-Commodities": m_commod,
            "Ações-Outros": m_acoes_outros,
            "FIIs-Papel": m_papel,
            "FIIs-Tijolo": m_tijolo,
            "FIIs-Outros": m_fii_outros
        }
    
    # --- EDITOR DE DADOS ---
    st.write("Classifique seus ativos conforme sua estratégia:")
    df_ed = st.data_editor(
        st.session_state.carteira_acoes,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Setor": st.column_config.SelectboxColumn(
                "Categoria Estratégica",
                width="medium",
                options=list(metas.keys()), # Pega as chaves do dicionário acima
                required=True
            )
        }
    )
    st.session_state.carteira_acoes = df_ed
    
    col_inp, col_btn = st.columns([1, 2])
    aporte_user = col_inp.number_input("💰 Aporte Disponível (R$)", 1000.0)
    
    if col_btn.button("🔄 Executar Estratégia"):
        if abs(total_meta - 100.0) > 0.1:
            st.error("Corrija as metas para somar 100%.")
        else:
            res = []
            bar = st.progress(0)
            total = len(df_ed)
            
            for i, row in df_ed.iterrows():
                r = obter_dados_v53(row["Ticker"])
                if r:
                    rec = r['decisao_ia']
                    if "COMPRA" in r['sinal_tecnico']: rec = f"🔥 {r['sinal_tecnico']}"
                    elif r['preco'] < row['PM'] * 0.95 and r['score_ia'] > 60: rec = "🛒 COMPRA (Desc.)"
                    
                    if r['score_ia'] >= 80 and row["Ticker"] not in st.session_state.alertas_enviados:
                        st.session_state.alertas_enviados.add(row["Ticker"])
                    
                    # CORREÇÃO CRÍTICA AQUI: Uso seguro do .get para evitar crash
                    # Se "Setor" não existir na linha (cache velho), usa padrão.
                    try:
                        setor_ativo = row["Setor"] if row["Setor"] else "Ações-Outros"
                    except:
                        setor_ativo = "Ações-Outros"
                    
                    res.append({
                        "Ticker": row["Ticker"], "Preço": r["preco"], "PM": row["PM"],
                        "Qtd": row["Qtd"], "Setor": setor_ativo,
                        "Valor_Atual": row["Qtd"] * r["preco"], 
                        "Lucro": (r["preco"] - row["PM"]) * row["Qtd"],
                        "Veredito IA": rec, "Score": r['score_ia']
                    })
                bar.progress((i+1)/total)
            
            if res:
                df_res = pd.DataFrame(res)
                st.session_state.df_analisado = df_res 
                
                # REBALANCEAMENTO
                df_final = rebalancear_e_aportar(df_res, aporte_user, metas_setores=metas)
                st.session_state.df_final = df_final
                
                st.success("✅ Alocação Calculada com Sucesso!")
                
                c_res1, c_res2 = st.columns(2)
                with c_res1:
                    st.subheader("Distribuição por Categoria")
                    resumo = df_final.groupby("Setor")["Aporte Sugerido (R$)"].sum().reset_index()
                    st.dataframe(resumo.style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)
                
                with c_res2:
                    st.subheader("Aportes nos Ativos (Score IA)")
                    st.dataframe(df_final[df_final["Aporte Sugerido (R$)"] > 0][["Ticker", "Setor", "Score", "Veredito IA", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

    if "df_final" in st.session_state and not st.session_state.df_final.empty:
        st.divider()
        if st.button("📄 Gerar PDF"):
            try:
                total_patr = st.session_state.df_final["Valor_Atual"].sum()
                pdf_bytes = RelatorioPrivate(st.session_state.df_final, total_patr).gerar_pdf()
                st.download_button("📥 Baixar PDF", pdf_bytes, f"Relatorio_{datetime.date.today()}.pdf", "application/pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

# --- ABA 3: FIIs 360 ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs")
    up = st.file_uploader("Upload CSV StatusInvest", type=["csv"])
    if up:
        df_fii = scanner_fiis_csv(up)
        if not df_fii.empty:
            t1, t2, t3, t4, t5 = st.tabs(["Todos", "Papel", "Tijolo", "Agro", "Outros"])
            cols = ["TICKER", "CATEGORIA", "PRECO", "DY", "P/VP", "Score", "Veredito", "Motivos (IA)"]
            t1.dataframe(df_fii[cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            t2.dataframe(df_fii[df_fii["CATEGORIA"]=="PAPEL"][cols], use_container_width=True)
            t3.dataframe(df_fii[df_fii["CATEGORIA"]=="TIJOLO"][cols], use_container_width=True)
            t4.dataframe(df_fii[df_fii["CATEGORIA"]=="AGRO"][cols], use_container_width=True)
            t5.dataframe(df_fii[df_fii["CATEGORIA"]=="OUTROS"][cols], use_container_width=True)

# --- ABA 4: RENDA FIXA ---
with tabs[3]:
    st.subheader("🛡️ Renda Fixa")
    df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_rf = df_rf
    st.metric("Total RF", f"R$ {df_rf['Saldo Atual'].sum():,.2f}")
    st.plotly_chart(go.Figure(data=[go.Pie(labels=df_rf["Ativo"], values=df_rf["Saldo Atual"])]), use_container_width=True)

# --- ABA 5: FUTURO ---
with tabs[4]:
    st.subheader("🔮 Simulação Monte Carlo")
    real_acoes = st.session_state.df_analisado["Valor_Atual"].sum() if "df_analisado" in st.session_state else 0
    real_rf = st.session_state.carteira_rf["Saldo Atual"].sum()
    if real_acoes == 0 and not st.session_state.carteira_acoes.empty: 
        real_acoes = (st.session_state.carteira_acoes['Qtd'] * st.session_state.carteira_acoes['PM']).sum()

    c1, c2 = st.columns(2)
    sim_ini = c1.number_input("Patrimônio Inicial", value=float(real_acoes + real_rf), step=1000.0)
    sim_apt = c2.number_input("Aporte Mensal", value=2000.0, step=100.0)
    
    if st.button("Simular 10 Anos"):
        try:
            tickers = st.session_state.carteira_acoes["Ticker"].tolist()
            hist = download_historico_longo(tickers)
            retornos = hist.pct_change().dropna().mean(axis=1)
            motor = MotorAnalise()
            prop = real_acoes / (real_acoes + real_rf) if (real_acoes + real_rf) > 0 else 1.0
            sim_risco = motor.monte_carlo_carteira(retornos, sim_ini * prop, sim_apt * prop, 10, 1000)
            meses = 120
            taxa_rf = 0.008 
            rf_base = (sim_ini * (1-prop)) * ((1 + taxa_rf) ** meses)
            rf_apts = (sim_apt * (1-prop)) * (((1 + taxa_rf) ** meses - 1) / taxa_rf)
            total = sim_risco + rf_base + rf_apts
            st.plotly_chart(go.Figure(go.Histogram(x=total, marker_color='green')), use_container_width=True)
            k1, k2, k3 = st.columns(3)
            k1.metric("Pessimista", f"R$ {np.percentile(total, 10):,.2f}")
            k2.metric("Provável", f"R$ {np.median(total):,.2f}")
            k3.metric("Otimista", f"R$ {np.percentile(total, 90):,.2f}")
        except Exception as e: st.error(f"Erro simulação: {e}")

# --- ABA 6: FISCAL ---
with tabs[5]:
    st.subheader("🦁 DARF e IR")
    if "df_vendas" not in st.session_state:
        st.session_state.df_vendas = pd.DataFrame(columns=["Ticker", "Qtd", "Preço Venda", "PM"])
    
    df_vendas = st.data_editor(st.session_state.df_vendas, num_rows="dynamic", use_container_width=True)
    st.session_state.df_vendas = df_vendas
    
    if st.button("Calcular DARF"):
        res = calcular_darf(df_vendas)
        st.metric("Pagar", f"R$ {res['darf']:.2f}")
        st.write(res["detalhes"])
        st.table(res["memoria"])

# --- ABA 7: OPÇÕES ---
with tabs[6]:
    st.subheader("⚡ Opções (Black-Scholes)")
    c1, c2 = st.columns([1, 3])
    with c1:
        tk = st.text_input("Ativo", "PETR4.SA").upper()
        try: pr = yf.Ticker(formatar_ticker(tk)).history(period="1d")["Close"].iloc[-1]
        except: pr = 30.0
        spot = st.number_input("Spot", value=float(pr))
        strike = st.number_input("Strike", value=float(pr))
        dt = st.date_input("Vencimento", datetime.date.today() + datetime.timedelta(days=30))
        vol = st.number_input("Vol (%)", 30.0) / 100
        taxa = st.number_input("Juros (%)", 12.25) / 100
        tipo = st.selectbox("Tipo", ["Call", "Put"])
    
    with c2:
        days = np.busday_count(datetime.date.today(), dt)
        if days <= 0: st.error("Data inválida")
        else:
            bs = BlackScholes(spot, strike, days/252, taxa, vol, "call" if "Call" in tipo else "put")
            st.markdown(f"### Preço Justo: R$ {bs.calcular_preco():.2f}")
            g = bs.calcular_gregas()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Delta", f"{g['Delta']:.2f}")
            k2.metric("Gamma", f"{g['Gamma']:.3f}")
            k3.metric("Theta", f"{g['Theta']:.3f}")
            k4.metric("Vega", f"{g['Vega']:.2f}")
            x, y = bs.gerar_payoff(0.2)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines'))
            fig.add_vline(x=spot, line_dash="dash", line_color="orange")
            fig.add_hline(y=0, line_dash="dot")
            st.plotly_chart(fig, use_container_width=True)