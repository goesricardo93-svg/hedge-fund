import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import datetime

# ======================================================
# 1. IMPORTAÇÃO DOS MÓDULOS E SEGURANÇA DE ARQUITETURA
# ======================================================
try:
    from motor import MotorAnalise
    from scanner import scanner_fiis_csv
    from rebalance import rebalancear_e_aportar
    from relatorio import RelatorioPrivate
    from options import BlackScholes
    from tax import calcular_darf
    from alerts import disparar_alerta, enviar_relatorio_anexo
except ImportError as e:
    st.error(f"Erro Crítico: Faltam arquivos modulares no diretório. Detalhes: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo | v56.1", layout="wide")

# --- DEFINIÇÃO DA ESTRATÉGIA MESTRE (METAS %) ---
# Baseado na sua solicitação exata
METAS_ESTRATEGIA = {
    "Renda Fixa": 30.0, 
    "Exterior": 20.0, 
    "Ações-Bancos": 7.5,
    "Ações-Elétricas": 7.5, 
    "Ações-Seguridade": 6.0, 
    "Ações-Commodities": 6.0,
    "Ações-Outros": 3.0, 
    "FIIs-Papel": 10.0, 
    "FIIs-Tijolo": 6.0, 
    "FIIs-Outros": 4.0
}

# ======================================================
# 2. CACHE E FUNÇÕES AUXILIARES
# ======================================================
@st.cache_data(ttl=3600)
def obter_dados_v56(ticker):
    """Busca dados e executa análise completa no motor"""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y")
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except:
        return None

@st.cache_data(ttl=86400)
def download_historico_longo(tickers):
    """Download de dados para simulações Monte Carlo"""
    data = yf.download(tickers, period="5y", progress=False)
    if isinstance(data, pd.DataFrame):
        return data["Adj Close"] if "Adj Close" in data else data["Close"]
    return data

def formatar_ticker(ticker):
    """Ajusta sufixos para o padrão Yahoo Finance"""
    t = ticker.strip().upper()
    if t in ["BTC", "ETH", "SOL"]: return f"{t}-USD"
    if any(char.isdigit() for char in t) and "." not in t: return f"{t}.SA"
    return t

def auto_classificar_carteira():
    """Varrer carteira e identificar setores via IA (XPML11 corrigido)"""
    motor = MotorAnalise()
    with st.spinner("🤖 IA analisando balanços e sumários de negócios..."):
        for idx, row in st.session_state.carteira_acoes.iterrows():
            try:
                t = yf.Ticker(row["Ticker"])
                setor_auto = motor.identificar_setor(t.info, row["Ticker"])
                st.session_state.carteira_acoes.at[idx, "Setor"] = setor_auto
            except:
                st.session_state.carteira_acoes.at[idx, "Setor"] = "Ações-Outros"

# ======================================================
# 3. ESTADO DA SESSÃO (PERSISTÊNCIA DE DADOS)
# ======================================================
if "carteira_acoes" not in st.session_state:
    # Dados padrão de exemplo
    dados = [
        ["BBAS3.SA", 1703, 24.48, "Aguardando IA..."],
        ["BBSE3.SA", 55, 35.64, "Aguardando IA..."],
        ["IVVB11.SA", 6, 366.97, "Aguardando IA..."],
        ["XPML11.SA", 10, 106.05, "Aguardando IA..."],
        ["HGLG11.SA", 20, 158.03, "Aguardando IA..."],
        ["KNCR11.SA", 27, 103.11, "Aguardando IA..."]
    ]
    st.session_state.carteira_acoes = pd.DataFrame(dados, columns=["Ticker", "Qtd", "PM", "Setor"])

if "carteira_rf" not in st.session_state:
    st.session_state.carteira_rf = pd.DataFrame([
        ["Tesouro Selic", 10000.0, "Pós-Fixado"],
        ["PGBL BTG", 50000.0, "Previdência"]
    ], columns=["Ativo", "Saldo Atual", "Tipo"])

if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

# ======================================================
# 4. INTERFACE STREAMLIT
# ======================================================
st.sidebar.title("📊 Hedge Fund Ricardo")
if st.sidebar.button("🧹 Limpar Cache do Sistema"):
    st.cache_data.clear()
    st.rerun()

ticker_search = st.sidebar.text_input("🔍 Analisar Ticker:", "BBAS3").upper()
ticker_search = formatar_ticker(ticker_search)

tabs = st.tabs(["🔎 Análise", "💼 Carteira", "🏢 FIIs 360", "🛡️ Renda Fixa", "💰 Futuro", "🦁 Fiscal", "⚡ Opções"])

# --- ABA 1: ANÁLISE ---
with tabs[0]:
    st.header(f"Raio-X: {ticker_search}")
    motor_obj = MotorAnalise()
    r = obter_dados_v56(ticker_search)
    
    if r:
        div_info = motor_obj.consultar_dividendos(ticker_search)
        cor_box = "green" if div_info.get('status') == "AGENDA" else "blue"
        st.markdown(f"""
        <div style="padding:15px; border-radius:10px; background-color:rgba(0,100,0,0.05); border:1px solid {cor_box}; margin-bottom:15px;">
            <h4 style="margin-top:0; color:{cor_box};">💰 Relatório de Proventos</h4>
            <table style="width:100%; border:none;">
                <tr><td style="font-weight:bold;">⏪ Último Pago:</td><td>{div_info.get('ultimo_data')}</td><td><b>{div_info.get('ultimo_valor')}</b></td></tr>
                <tr><td style="font-weight:bold; color:{cor_box};">⏩ Próximo (Prev):</td><td>{div_info.get('proximo_data')}</td><td><b>{div_info.get('proximo_valor')}</b></td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
        k2.metric("Score IA", f"{r['score_ia']}/100")
        k3.metric("RSI (14)", f"{r['rsi']:.0f}")
        k4.metric("Volatilidade", f"{r['volatilidade']*100:.1f}%")
        
        st.subheader("📋 Valuation")
        # Correção KeyError p_gordon e blindagem
        st.table(pd.DataFrame({
            "Modelo": ["Bazin (Dividendos)", "Graham (Patrimônio)", "Gordon (Crescimento)"],
            "Preço Justo": [
                f"R$ {r.get('p_bazin', 0):.2f}", 
                f"R$ {r.get('p_graham', 0):.2f}", 
                f"R$ {r.get('p_gordon', 0):.2f}"
            ]
        }))
        
        # Gráfico TradingView
        components.html(f"""
            <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
            <div id="tv_chart"></div>
            <script type="text/javascript">
            new TradingView.widget({{
              "width": "100%", "height": 450, "symbol": "BMFBOVESPA:{ticker_search.replace(".SA","")}",
              "interval": "D", "timezone": "America/Sao_Paulo", "theme": "light", "style": "1",
              "locale": "br", "toolbar_bg": "#f1f3f6", "container_id": "tv_chart"
            }});
            </script>
        """, height=450)

        st.subheader("🎯 Setup Operacional")
        st.dataframe(pd.DataFrame([
            {"Indicador": "Sinal Técnico", "Valor": r.get('sinal_tecnico')},
            {"Indicador": "Preço Entrada (MME9)", "Valor": f"R$ {r.get('mme9'):.2f}"},
            {"Indicador": "🛑 Stop Loss", "Valor": f"R$ {r.get('stop_loss'):.2f}"},
            {"Indicador": "🎯 Stop Gain", "Valor": f"R$ {r.get('stop_gain'):.2f}"}
        ]), use_container_width=True, hide_index=True)
    else:
        st.warning("Ativo não encontrado. Limpe o cache.")

# --- ABA 2: CARTEIRA ---
with tabs[1]:
    st.subheader("💼 Gestão de Alocação Estratégica")
    
    if st.button("🤖 1. Classificar Carteira via IA"):
        auto_classificar_carteira()
        st.rerun()
    
    df_ed = st.data_editor(
        st.session_state.carteira_acoes,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Setor": st.column_config.SelectboxColumn(
                "Categoria Estratégica", 
                options=list(METAS_ESTRATEGIA.keys()),
                required=True
            )
        }
    )
    st.session_state.carteira_acoes = df_ed
    
    aporte = st.number_input("💰 Aporte Disponível (R$)", min_value=0.0, value=10000.0)
    
    if st.button("🚀 2. Executar Rebalanceamento"):
        if "Aguardando IA..." in df_ed["Setor"].values:
            st.error("Por favor, classifique os ativos via IA primeiro.")
        else:
            analisados = []
            for _, row in df_ed.iterrows():
                d = obter_dados_v56(row["Ticker"])
                if d:
                    analisados.append({
                        **row.to_dict(), "Preço": d["preco"], 
                        "Valor_Atual": row["Qtd"] * d["preco"], "Score": d["score_ia"]
                    })
            if analisados:
                df_final = rebalancear_e_aportar(pd.DataFrame(analisados), aporte, metas_setores=METAS_ESTRATEGIA)
                st.success("Alocação Calculada!")
                st.dataframe(
                    df_final[df_final["Aporte Sugerido (R$)"] > 0][["Ticker", "Setor", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}),
                    use_container_width=True
                )

# --- ABA 3: FIIs 360 ---
with tabs[2]:
    st.subheader("🏢 Scanner FIIs 360º")
    up = st.file_uploader("Upload CSV StatusInvest", type=["csv"])
    if up:
        df_fii = scanner_fiis_csv(up)
        if not df_fii.empty:
            st.dataframe(df_fii.style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True)

# --- ABA 4: RENDA FIXA ---
with tabs[3]:
    st.subheader("🛡️ Renda Fixa")
    df_rf = st.data_editor(st.session_state.carteira_rf, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira_rf = df_rf
    st.metric("Total em RF", f"R$ {df_rf['Saldo Atual'].sum():,.2f}")

# --- ABA 5: FUTURO ---
with tabs[4]:
    st.subheader("🔮 Simulação Monte Carlo (10 Anos)")
    if st.button("Executar Simulação"):
        tickers = st.session_state.carteira_acoes["Ticker"].tolist()
        hist_longo = download_historico_longo(tickers)
        retornos = hist_longo.pct_change().dropna().mean(axis=1)
        simulacao = MotorAnalise().monte_carlo_carteira(retornos, sim_ini=100000, aporte=2000)
        st.line_chart(simulacao)

# --- ABA 6: FISCAL ---
with tabs[5]:
    st.subheader("🦁 DARF e Imposto de Renda")
    if st.button("Calcular DARF"):
        res = calcular_darf(st.session_state.carteira_acoes)
        st.write(res)

# --- ABA 7: OPÇÕES ---
with tabs[6]:
    st.subheader("⚡ Opções (Black-Scholes)")
    # Integração BlackScholes do arquivo options.py