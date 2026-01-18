import streamlit as st

# ======================================================
# 1. CONFIGURAÇÃO (PRIMEIRA LINHA ABSOLUTA)
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo v83", layout="wide", page_icon="💰")

# ======================================================
# 2. IMPORTAÇÃO BLINDADA
# ======================================================
import pandas as pd
import yfinance as yf
import streamlit.components.v1 as components # <--- A LINHA QUE FALTAVA

try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
    
    # Módulos Utilitários
    try: from scanner import scanner_fiis_csv, scanner_auto_yahoo
    except ImportError: scanner_fiis_csv = None; scanner_auto_yahoo = None
    
    try: from options import BlackScholes
    except ImportError: BlackScholes = None
    
    try: from tax import calcular_darf
    except ImportError: calcular_darf = None
    
    try: from report import gerar_pdf_carteira
    except ImportError: gerar_pdf_carteira = None

except Exception as e:
    st.error(f"❌ Erro Crítico: {e}")
    st.info("Verifique se os arquivos motor.py, scanner.py, options.py etc. estão na pasta.")
    st.stop()

# ======================================================
# 3. CACHE E MOTOR
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try: 
        return MotorAnalise().analisar(yf.Ticker(ticker).history(period="2y"), yf.Ticker(ticker).info, ticker)
    except: return None

@st.cache_data(ttl=86400)
def download_longo(tickers):
    try: 
        d = yf.download(tickers, period="5y", progress=False)
        return d["Adj Close"] if "Adj Close" in d else d["Close"]
    except: return pd.DataFrame()

def auto_classificar():
    motor = MotorAnalise()
    prog = st.progress(0, "Classificando...")
    total = len(st.session_state.carteira_acoes)
    for i, row in st.session_state.carteira_acoes.iterrows():
        try: st.session_state.carteira_acoes.at[i, "Setor"] = motor.identificar_setor(yf.Ticker(row["Ticker"]).info, row["Ticker"])
        except: st.session_state.carteira_acoes.at[i, "Setor"] = "Outros"
        prog.progress((i+1)/total)
    prog.empty(); st.success("Classificação Concluída!")

# ======================================================
# 4. ESTADO INICIAL
# ======================================================
if "df_metas" not in st.session_state:
    st.session_state.df_metas = pd.DataFrame([
        {"Setor": "Renda Fixa", "Meta (%)": 30.0}, {"Setor": "Exterior", "Meta (%)": 20.0},
        {"Setor": "Ações-Bancos", "Meta (%)": 7.5}, {"Setor": "Ações-Elétricas", "Meta (%)": 7.5},
        {"Setor": "Ações-Seguridade", "Meta (%)": 6.0}, {"Setor": "Ações-Commodities", "Meta (%)": 6.0},
        {"Setor": "Ações-Outros", "Meta (%)": 3.0}, {"Setor": "FIIs-Papel", "Meta (%)": 10.0},
        {"Setor": "FIIs-Tijolo", "Meta (%)": 6.0}, {"Setor": "FIIs-Outros", "Meta (%)": 4.0}
    ])

if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Aguardando..."], ["CPSH11.SA", 50, 10.10, "Aguardando..."],
        ["XPML11.SA", 10, 115.00, "Aguardando..."], ["IVVB11.SA", 5, 280.00, "Aguardando..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([["Tesouro Selic", 10000.0, "Pós"]], columns=["Ativo", "Saldo Atual", "Tipo"])

# ======================================================
# 5. INTERFACE
# ======================================================
st.title("💰 Hedge Fund Ricardo v83")

with st.sidebar:
    st.header("🎮 Painel")
    if st.button("🧹 Limpar Cache"): 
        st.cache_data.clear()
        st.rerun()
    st.divider()
    if gerar_pdf_carteira:
        if st.button("📄 Gerar Relatório PDF"):
            df_r = st.session_state.carteira_acoes.copy()
            if "Valor_Atual" not in df_r: df_r["Valor_Atual"] = df_r["Qtd"] * df_r["PM"]
            total = st.session_state.carteira_rf["Saldo Atual"].sum() + df_r["Valor_Atual"].sum()
            metas = dict(zip(st.session_state.df_metas["Setor"], st.session_state.df_metas["Meta (%)"]))
            try:
                st.download_button("📥 Baixar", gerar_pdf_carteira(df_r, st.session_state.carteira_rf, total, metas), "Relatorio.pdf", "application/pdf")
            except Exception as e: st.error(f"Erro PDF: {e}")

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ RF", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# ABA 1: ANÁLISE DETALHADA
with tabs[0]:
    t = st.text_input("Ticker", "MXRF11.SA").upper()
    if st.button("Analisar"):
        r = obter_dados(t)
        if r:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço", f"R$ {r.get('preco',0):.2f}")
            c2.metric("DY Anual", f"{r.get('dy_anual',0):.2f}%")
            
            # Score
            if r.get('score_ia',0)==0: c3.error("BLOQUEADO (Risco)")
            else: c3.metric("Score IA", f"{r.get('score_ia',0)}/100", delta=r.get('decisao_ia',''))
            
            # Valuation
            justo = r.get('preco_justo', 0)
            if justo > 0:
                delta_j = (r['preco'] - justo)/justo*100
                lbl = "Ágio" if delta_j > 0 else "Desconto"
                clr = "inverse" if delta_j > 0 else "normal"
                c4.metric("Valor Justo (IA)", f"R$ {justo:.2f}", delta=f"{delta_j:+.1f}% ({lbl})", delta_color=clr)
            else: c4.metric("Valor Justo", "N/A")
            
            st.divider()
            
            k1, k2 = st.columns(2)
            k1.table(pd.DataFrame({"Modelo": ["Bazin (Teto)", "Graham (Patrim)", "Gordon (Cresc)"], "Valor": [f"R$ {r.get('p_bazin',0):.2f}", f"R$ {r.get('p_graham',0):.2f}", f"R$ {r.get('p_gordon',0):.2f}"]}))
            
            motivos = r.get('motivos','')
            if "⚠️" in motivos or "⛔" in motivos: k2.error(motivos)
            else: k2.info(motivos)
            
            st.subheader("📈 Algo-Trading")
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Tendência", r.get('sinal_tecnico','-'))
            t2.metric("MACD", r.get('status_macd','-'))
            t3.metric("Stop Loss", f"R$ {r.get('stop_loss',0):.2f}")
            t4.metric("Stop Gain", f"R$ {r.get('stop_gain',0):.2f}")
            
            st.dataframe(pd.DataFrame([
                {"Ind": "RSI(14)", "Val": f"{r.get('rsi',50):.0f}"},
                {"Ind": "Volatilidade", "Val": f"{r.get('volatilidade',0)*100:.1f}%"},
                {"Ind": "Vol. Relativo", "Val": f"{r.get('vol_relativo',1):.2f}x"},
                {"Ind": "Suporte", "Val": f"R$ {r.get('suporte',0):.2f}"},
                {"Ind": "Resistência", "Val": f"R$ {r.get('resistencia',0):.2f}"}
            ]), use_container_width=True)
            
            # GRÁFICO (Aqui estava o erro antes, agora corrigido com o import lá em cima)
            components.html(f"""<script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"width":"100%","height":500,"symbol":"BMFBOVESPA:{t.replace('.SA','')}","interval":"D","theme":"light"}});</script>""", height=500)
        else: st.error("Ativo não encontrado. Tente limpar o cache.")

# ABA 2: CARTEIRA
with tabs[1]:
    c_a, c_b = st.columns([2,1])
    with c_b:
        st.subheader("🎯 Metas")
        df_m = st.data_editor(st.session_state.df_metas, num_rows="dynamic")
        st.session_state.df_metas = df_m
        if abs(df_m["Meta (%)"].sum()-100)>0.1: st.warning("Soma != 100%")
    with c_a:
        st.subheader("💼 Ativos")
        if st.button("🤖 Classificar Setores"): auto_classificar(); st.rerun()
        
        st.session_state.carteira_acoes = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", column_config={"Setor": st.column_config.SelectboxColumn("Setor", options=df_m["Setor"].tolist())}, use_container_width=True)
        
        aporte = st.number_input("Aporte Disponível (R$)", 5000.0)
        if st.button("🚀 Gerar Rebalanceamento"):
            d_metas = dict(zip(df_m["Setor"], df_m["Meta (%)"]))
            dados = []
            for _, r in st.session_state.carteira_acoes.iterrows():
                d = obter_dados(r["Ticker"])
                if d: dados.append({**r.to_dict(), "Preço": d["preco"], "Valor_Atual": r["Qtd"]*d["preco"], "Score": d["score_ia"]})
                else: dados.append({**r.to_dict(), "Preço": 10, "Valor_Atual": r["Qtd"]*10, "Score": 50})
            
            final = rebalancear_e_aportar(pd.DataFrame(dados), aporte, d_metas)
            st.dataframe(final[final["Aporte Sugerido (R$)"]>1].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}), use_container_width=True)

# ABA 3: SCANNER 360 (FORMATADO)
with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360")
    modo = st.radio("Fonte de Dados", ["🤖 Automático (Yahoo - Análise IA)", "📂 Planilha (CSV StatusInvest)"], horizontal=True)
    
    if "Automático" in modo:
        st.info("O Modo Automático roda o Motor de IA em cada FII. Isso leva cerca de 10 a 20 segundos.")
        if st.button("🚀 Rodar Varredura"):
            if scanner_auto_yahoo: 
                with st.spinner("Analisando mercado (Baixando dados e calculando Score)..."):
                    df_s = scanner_auto_yahoo()
                    if not df_s.empty and "Score IA" in df_s.columns:
                        # Exibição Rica com Barras de Progresso e Formatação
                        st.dataframe(df_s, use_container_width=True, column_config={
                            "Score IA": st.column_config.ProgressColumn("Score IA", min_value=0, max_value=100, format="%d"),
                            "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Valor Justo": st.column_config.NumberColumn(format="R$ %.2f"),
                            "P/VP": st.column_config.NumberColumn(format="%.2f"),
                            "DY (12m)": st.column_config.NumberColumn(format="%.2f%%")
                        })
                    else:
                        st.dataframe(df_s) # Fallback
            else: st.error("Erro: Função scanner_auto_yahoo não encontrada em scanner.py")
    else:
        st.info("Modo Planilha: Utilize o arquivo da Busca Avançada do StatusInvest.")
        up = st.file_uploader("Arquivo CSV", type=["csv"])
        if up and scanner_fiis_csv: 
            st.dataframe(scanner_fiis_csv(up), use_container_width=True)

# ABA 4: RF
with tabs[3]:
    st.subheader("🛡️ Renda Fixa")
    st.session_state.carteira_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic")
    st.metric("Saldo Total RF", f"R$ {st.session_state.carteira_rf['Saldo Atual'].sum():,.2f}")

# ABA 5: FUTURO
with tabs[4]:
    st.subheader("🔮 Simulação Monte Carlo")
    if st.button("Simular 10 Anos"):
        h = download_longo(st.session_state.carteira_acoes["Ticker"].tolist())
        if not h.empty: 
            ret = h.pct_change().dropna()
            # Se for Series (1 ativo) ou DataFrame (vários)
            r_carteira = ret.mean(axis=1) if isinstance(ret, pd.DataFrame) else ret
            st.line_chart(MotorAnalise().monte_carlo_carteira(r_carteira, 100000, 2000))

# ABA 6: FISCAL
with tabs[5]:
    st.subheader("🦁 Calculadora de DARF")
    if st.button("Calcular Impostos") and calcular_darf:
        st.table(calcular_darf(st.session_state.carteira_acoes))

# ABA 7: OPÇÕES
with tabs[6]:
    st.subheader("⚡ Simulador de Opções")
    if BlackScholes:
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.radio("Tipo", ["Call", "Put"], horizontal=True)
            S = st.number_input("Spot (Ativo)", 30.0)
            K = st.number_input("Strike (Exercício)", 32.0)
        with c2:
            T = st.number_input("Dias Vencimento", 30)/365
            sigma = st.number_input("Volatilidade %", 30.0)/100
            r = st.number_input("Juros %", 13.75)/100
        
        bs = BlackScholes(S, K, T, r, sigma, tipo)
        try:
            gr = bs.calcular_gregas()
            pr = bs.calcular_preco()
            st.divider()
            cc1, cc2 = st.columns([1,3])
            cc1.metric(f"Prêmio {tipo}", f"R$ {pr:.2f}")
            cc2.write(pd.DataFrame([gr]))
        except Exception as e: st.error(f"Erro: {e}")
    else: st.error("Módulo options.py faltando.")