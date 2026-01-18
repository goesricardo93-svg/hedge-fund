import streamlit as st
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
except ImportError as e:
    st.error(f"Erro Crítico de Arquitetura: Faltam arquivos modulares. Detalhes: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | vFinal 41.0", layout="wide")

# ======================================================
# 2. CACHE E FUNÇÕES UTILITÁRIAS
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados_v41(ticker): 
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

# ======================================================
# 3. ESTADO DA SESSÃO
# ======================================================
if "carteira_acoes" not in st.session_state:
    dados = [
        ["ALZR11.SA", 100, 10.81], ["BBAS3.SA", 1703, 24.48], ["BBSE3.SA", 55, 35.64],
        ["BTCI11.SA", 502, 10.16], ["BTLG11.SA", 60, 98.50], ["CCME11.SA", 152, 8.55],
        ["CMIG4.SA", 1644, 11.12], ["CPLE3.SA", 617, 9.64], ["CPSH11.SA", 169, 10.10],
        ["CPTS11.SA", 276, 8.52], ["CXSE3.SA", 800, 14.20], ["EQTL3.SA", 200, 30.21],
        ["HGCR11.SA", 20, 95.81], ["HGLG11.SA", 20, 158.03], ["ITSA4.SA", 1174, 9.63],
        ["IVVB11.SA", 6, 366.97], ["KLBN4.SA", 2323, 3.63], ["KNCR11.SA", 27, 103.11],
        ["KNHF11.SA", 15, 93.23], ["KNRI11.SA", 30, 152.49], ["KNSC11.SA", 373, 8.78],
        ["KNUQ11.SA", 16, 102.45], ["PETR4.SA", 900, 32.07], ["SAPR11.SA", 300, 37.97],
        ["TAEE4.SA", 1000, 11.36], ["VALE3.SA", 152, 54.79], ["VGIR11.SA", 296, 9.58],
        ["VISC11.SA", 16, 109.70], ["XPCA11.SA", 110, 8.77], ["XPLG11.SA", 26, 102.31],
        ["XPML11.SA", 10, 106.05]
    ]
    st.session_state.carteira_acoes = pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000.0, "Pós-Fixado"],
        ["PGBL BTG Pactual", 50000.0, "Previdência"],
        ["LCI CDI 90%", 20000.0, "Isento"]
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
    with st.spinner("🤖 Processando Fechamento Mensal..."):
        try:
            res_auto = []
            for _, row in st.session_state.carteira_acoes.iterrows():
                r = obter_dados_v41(row["Ticker"])
                if r:
                    res_auto.append({
                        "Ticker": row["Ticker"],
                        "Preço": r["preco"],
                        "PM": row["PM"],
                        "Valor_Atual": row["Qtd"] * r["preco"],
                        "Lucro": (r["preco"] - row["PM"]) * row["Qtd"],
                        "Score": r['score_ia']
                    })
            if res_auto:
                df_auto = pd.DataFrame(res_auto)
                pdf_bytes = RelatorioPrivate(df_auto, df_auto["Valor_Atual"].sum()).gerar_pdf()
                enviar_relatorio_anexo(pdf_bytes, f"Relatorio_{mes_str}.pdf")
                st.session_state[f"report_{mes_str}"] = True
                st.toast("✅ Relatório enviado!", icon="🚀")
        except: pass

# ======================================================
# 5. INTERFACE
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")
ticker_raw = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3").upper()
ticker_input = formatar_ticker(ticker_raw)

if st.sidebar.button("🔄 Restaurar Padrões"):
    st.session_state.clear()
    st.rerun()

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ RF & PGBL", "💰 Futuro", "🦁 Fiscal"])

# --- ABA 1: ANÁLISE (CORRIGIDA - GRÁFICO) ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_input}")
    motor = MotorAnalise()
    r = obter_dados_v41(ticker_input)
    
    if r:
        div_info = motor.consultar_dividendos(ticker_input)
        if div_info['status'] != "SEM DADOS":
            cor = "green" if div_info['status'] == "CONFIRMADO" else "blue"
            st.markdown(f"""
            <div style="padding:10px; border-radius:5px; background-color:rgba(0,100,0,0.1); border:1px solid {cor}; margin-bottom:10px;">
                💰 <b>PROVENTOS ({div_info['status']}):</b> Data: <b>{div_info['data']}</b> | Valor: <b>{div_info['valor']}</b>
            </div>""", unsafe_allow_html=True)

        col_ia1, col_ia2 = st.columns([1, 3])
        col_ia1.metric("Score IA", f"{r['score_ia']}/100")
        if "COMPRA" in r['decisao_ia']: col_ia2.success(f"### {r['decisao_ia']}")
        elif "VENDA" in r['decisao_ia']: col_ia2.error(f"### {r['decisao_ia']}")
        else: col_ia2.warning(f"### {r['decisao_ia']}")
        
        st.write(f"**Análise Cruzada:** {r['motivos']}")
        st.divider()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        k2.metric("Teto (Alvo IA)", f"R$ {r['stop_gain']:.2f}")
        k3.metric("RSI (14)", f"{r['rsi']:.0f}")
        k4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")

        col_val, col_fund = st.columns(2)
        with col_val:
            st.subheader("📋 Valuation")
            st.dataframe(pd.DataFrame({
                "Modelo": ["Bazin (Div)", "Graham (Patr)", "Gordon (Cresc)"],
                "Preço Justo": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
            }), use_container_width=True)
        with col_fund:
            st.subheader("📊 Qualidade")
            st.dataframe(pd.DataFrame({
                "Indicador": ["DY", "P/L", "P/VP", "ROE", "Dívida/EBITDA"],
                "Valor": [f"{r['dy']*100:.2f}%", f"{r['pl']:.2f}", f"{r['pvp']:.2f}", f"{r['roe']*100:.1f}%", f"{r['divida_ebitda']:.2f}x"]
            }), use_container_width=True)

        # --- CORREÇÃO DO GRÁFICO ---
        st.subheader("📈 Gráfico Técnico")
        try:
            hist = yf.download(ticker_input, period="2y", progress=False)
            if not hist.empty:
                # Função para garantir que os dados sejam Series (1D) e não DataFrame (2D)
                def fix_data(col_name):
                    if col_name in hist.columns:
                        d = hist[col_name]
                        if isinstance(d, pd.DataFrame): return d.iloc[:, 0]
                        return d
                    return hist.iloc[:, 0] # Fallback

                open_p = fix_data("Open")
                high_p = fix_data("High")
                low_p = fix_data("Low")
                close_p = fix_data("Close")
                
                mm50 = close_p.rolling(50).mean()
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=hist.index,
                    open=open_p, high=high_p, low=low_p, close=close_p,
                    name="Preço"
                ))
                fig.add_trace(go.Scatter(x=hist.index, y=mm50, name="MM50", line=dict(color='blue')))
                fig.add_hline(y=r['suporte'], line_dash="dot", line_color="green", annotation_text="SUPORTE")
                fig.add_hline(y=r['resistencia'], line_dash="dot", line_color="red", annotation_text="RESISTÊNCIA")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e: st.error(f"Erro ao carregar gráfico: {e}")
    else: st.warning("Ativo não encontrado.")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    st.subheader(f"💼 Gestão de Carteira ({len(st.session_state.carteira_acoes)} Ativos)")
    df_ed = st.data_editor(st.session_state.carteira_acoes, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_acoes = df_ed
    
    col_inp, col_btn = st.columns([1, 2])
    aporte_user = col_inp.number_input("💰 Aporte Disponível (R$)", 1000.0)
    
    if col_btn.button("🔄 Analisar e Rebalancear"):
        res = []
        bar = st.progress(0)
        total = len(df_ed)
        for i, row in df_ed.iterrows():
            r = obter_dados_v41(row["Ticker"])
            if r:
                rec = r['decisao_ia']
                if r['preco'] < row['PM'] * 0.95 and r['score_ia'] > 60: rec = "🔥 COMPRA (Abaixo PM)"
                if r['score_ia'] >= 80 and row["Ticker"] not in st.session_state.alertas_enviados:
                    disparar_alerta(f"OPORTUNIDADE: {row['Ticker']}", f"Score: {r['score_ia']}")
                    st.session_state.alertas_enviados.add(row["Ticker"])
                res.append({
                    "Ticker": row["Ticker"], "Preço": r["preco"], "PM": row["PM"],
                    "Valor_Atual": row["Qtd"] * r["preco"], "Lucro": (r["preco"] - row["PM"]) * row["Qtd"],
                    "Veredito IA": rec, "Score": r['score_ia']
                })
            bar.progress((i+1)/total)
        
        if res:
            df_res = pd.DataFrame(res)
            st.session_state.df_analisado = df_res 
            df_final = rebalancear_e_aportar(df_res, aporte_user)
            st.session_state.df_final = df_final
            
            st.success("✅ Rebalanceamento Calculado!")
            st.dataframe(df_final[["Ticker", "Score", "Valor_Atual", "Lucro", "Veredito IA", "Aporte Sugerido (R$)"]].style.format({"Valor_Atual": "R$ {:.2f}", "Lucro": "R$ {:.2f}", "Aporte Sugerido (R$)": "R$ {:.2f}"}).background_gradient(subset=["Aporte Sugerido (R$)"], cmap="Greens"), use_container_width=True)

    if "df_final" in st.session_state and not st.session_state.df_final.empty:
        st.divider()
        if st.button("📄 Gerar Relatório Private (PDF)"):
            try:
                total_patr = st.session_state.df_final["Valor_Atual"].sum()
                pdf_bytes = RelatorioPrivate(st.session_state.df_final, total_patr).gerar_pdf()
                st.download_button("📥 Baixar PDF", pdf_bytes, f"Relatorio_{datetime.date.today()}.pdf", "application/pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

# --- ABA 3: FIIs 360 ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360º")
    up = st.file_uploader("Upload CSV StatusInvest", type=["csv"])
    if up:
        df_fii = scanner_fiis_csv(up)
        if not df_fii.empty:
            st.success(f"{len(df_fii)} FIIs processados!")
            t1, t2, t3, t4, t5 = st.tabs(["🌎 Todos", "📄 Papel", "🧱 Tijolo", "🌱 Agro", "⚙️ Outros"])
            cols = ["TICKER", "CATEGORIA", "PRECO", "DY", "P/VP", "Score", "Veredito", "Motivos (IA)"]
            
            t1.dataframe(df_fii[cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            t2.dataframe(df_fii[df_fii["CATEGORIA"]=="PAPEL"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            t3.dataframe(df_fii[df_fii["CATEGORIA"]=="TIJOLO"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            t4.dataframe(df_fii[df_fii["CATEGORIA"]=="AGRO"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)
            t5.dataframe(df_fii[df_fii["CATEGORIA"]=="OUTROS"][cols].style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)

# --- ABA 4: RENDA FIXA ---
with tabs[3]:
    st.subheader("🛡️ Renda Fixa e PGBL")
    df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_rf = df_rf
    st.metric("Total em Renda Fixa", f"R$ {df_rf['Saldo Atual'].sum():,.2f}")
    st.plotly_chart(go.Figure(data=[go.Pie(labels=df_rf["Ativo"], values=df_rf["Saldo Atual"], hole=.4)]), use_container_width=True)

# --- ABA 5: FUTURO ---
with tabs[4]:
    st.subheader("🔮 Simulação Patrimonial (Monte Carlo Real)")
    real_acoes = st.session_state.df_analisado["Valor_Atual"].sum() if "df_analisado" in st.session_state else 0
    real_rf = st.session_state.carteira_rf["Saldo Atual"].sum()
    if real_acoes == 0 and not df_ed.empty: real_acoes = (df_ed['Qtd'] * df_ed['PM']).sum()
    
    ci1, ci2 = st.columns(2)
    sim_ini = ci1.number_input("💰 Patrimônio Inicial", value=float(real_acoes + real_rf), step=1000.0)
    sim_apt = ci2.number_input("➕ Aporte Mensal", value=2000.0, step=100.0)
    
    if st.button("Simular 10 Anos"):
        try:
            hist = download_historico_longo(df_ed["Ticker"].tolist())
            retornos = hist.pct_change().dropna().mean(axis=1)
            motor = MotorAnalise()
            
            prop = real_acoes / (real_acoes + real_rf) if (real_acoes + real_rf) > 0 else 1.0
            sim_risco = motor.monte_carlo_carteira(retornos, sim_ini * prop, sim_apt * prop, 10, 1000)
            
            meses = 120
            taxa_rf = 0.008
            rf_base = (sim_ini * (1-prop)) * ((1 + taxa_rf) ** meses)
            rf_apts = (sim_apt * (1-prop)) * (((1 + taxa_rf) ** meses - 1) / taxa_rf)
            
            total = sim_risco + rf_base + rf_apts
            st.plotly_chart(go.Figure(go.Histogram(x=total, nbinsx=50, marker_color='green')), use_container_width=True)
            k1, k2, k3 = st.columns(3)
            k1.metric("Pessimista (10%)", f"R$ {np.percentile(total, 10):,.2f}")
            k2.metric("Provável (Mediana)", f"R$ {np.median(total):,.2f}")
            k3.metric("Otimista (90%)", f"R$ {np.percentile(total, 90):,.2f}")
        except Exception as e: st.error(f"Erro na simulação: {e}")

# --- ABA 6: FISCAL ---
with tabs[5]:
    st.subheader("🦁 Calculadora de IR (DARF)")
    if "df_vendas" not in st.session_state:
        st.session_state.df_vendas = pd.DataFrame(columns=["Ticker", "Qtd", "Preço Venda", "PM"])
    
    df_vendas = st.data_editor(st.session_state.df_vendas, num_rows="dynamic", use_container_width=True)
    st.session_state.df_vendas = df_vendas
    
    if st.button("Calcular Imposto"):
        res = calcular_darf(df_vendas)
        st.divider()
        c1, c2 = st.columns([1, 2])
        c1.metric("DARF a Pagar", f"R$ {res['darf']:.2f}")
        c2.write(res["detalhes"])
        st.table(res["memoria"])