import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# Importações dos módulos locais
from motor import MotorAnalise
from rebalance import rebalancear_e_aportar
from alerts import alerta

# Configuração da Página
st.set_page_config(page_title="Hedge Fund Ricardo | Terminal Modular", layout="wide")

# Instancia o motor de análise
motor = MotorAnalise()

# =========================
# CARTEIRA BASE (Estado da Sessão)
# =========================
if "carteira" not in st.session_state:
    # Lista inicial de exemplo (pode ser substituída pela sua lista de 31 ativos)
    dados_iniciais = [
        ["BBAS3.SA", 1703, 24.48],
        ["VALE3.SA", 152, 54.79],
        ["ITSA4.SA", 1174, 9.63],
        ["HGLG11.SA", 20, 158.03],
        ["KNCR11.SA", 27, 103.11],
    ]
    st.session_state.carteira = pd.DataFrame(dados_iniciais, columns=["Ticker", "Qtd", "PM"])

if "df_scores" not in st.session_state:
    st.session_state.df_scores = pd.DataFrame()

# Título Principal
st.title("🏛️ Hedge Fund Ricardo - Terminal de Gestão")

# Abas da Aplicação
tabs = st.tabs(["🔎 Ativo Individual", "💼 Carteira & Análise", "⚖️ Rebalanceamento Inteligente", "📈 Monte Carlo"])

# =========================
# ABA 1 – ATIVO INDIVIDUAL
# =========================
with tabs[0]:
    st.header("Análise Detalhada de Ativo")
    col1, col2 = st.columns([1, 3])
    with col1:
        tk = st.text_input("Digite o Ticker", "BBAS3.SA").upper()
        btn_analisar = st.button("Analisar Ativo")
    
    if btn_analisar or tk:
        with st.spinner(f"Analisando {tk}..."):
            try:
                # Baixa dados
                ticker_obj = yf.Ticker(tk)
                hist = ticker_obj.history(period="2y")
                info = ticker_obj.info

                if not hist.empty:
                    # Executa análise
                    r = motor.analisar_acao(hist, info)
                    
                    if r:
                        # Métricas Principais
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Preço Atual", f"R$ {r['preco']:.2f}")
                        c2.metric("Score IA", f"{r['score']}/100", delta_color="normal")
                        c3.metric("Recomendação", r['decisao'])
                        c4.metric("Dividend Yield", f"{r['dy']*100:.2f}%")

                        # Dados Técnicos e Fundamentalistas
                        st.subheader("Indicadores")
                        col_tec, col_fund = st.columns(2)
                        
                        with col_tec:
                            st.markdown("### 📉 Técnico")
                            st.write(f"**RSI (14):** {r['rsi']:.1f}")
                            st.write(f"**Volatilidade Anual:** {r['vol']*100:.1f}%")
                            st.write(f"**Drawdown Max:** {r['drawdown']*100:.1f}%")
                        
                        with col_fund:
                            st.markdown("### 📊 Fundamentalista")
                            st.write(f"**Preço Bazin:** R$ {r['p_bazin']:.2f}")
                            st.write(f"**Preço Graham:** R$ {r['p_graham']:.2f}")

                        # Gráfico Simples
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='Preço'))
                        fig.update_layout(title=f"Histórico de Preços - {tk}", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error("Erro ao processar indicadores.")
                else:
                    st.warning("Dados não encontrados para este ticker.")
            except Exception as e:
                st.error(f"Ocorreu um erro: {e}")

# =========================
# ABA 2 – CARTEIRA
# =========================
with tabs[1]:
    st.header("Gestão de Carteira")
    st.markdown("Edite sua carteira abaixo e clique em 'Analisar' para atualizar os Scores.")
    
    # Editor da Carteira
    df_editor = st.data_editor(st.session_state.carteira, num_rows="dynamic", use_container_width=True)
    st.session_state.carteira = df_editor

    if st.button("🔄 Analisar Carteira Completa"):
        resultados = []
        bar_progresso = st.progress(0)
        total_ativos = len(df_editor)
        
        for i, row in df_editor.iterrows():
            ticker = row["Ticker"]
            try:
                # Baixa dados para cada ativo
                t_obj = yf.Ticker(ticker)
                h = t_obj.history(period="2y")
                inf = t_obj.info
                
                if not h.empty:
                    anl = motor.analisar_acao(h, inf)
                    if anl:
                        valor_total = row["Qtd"] * anl["preco"]
                        resultados.append([
                            ticker, 
                            anl["score"], 
                            anl["decisao"], 
                            valor_total,
                            f"R$ {anl['preco']:.2f}",
                            f"{anl['dy']*100:.1f}%"
                        ])
                        
                        # Dispara alerta se for oportunidade forte
                        if anl["score"] >= 80:
                            alerta(f"🔥 OPORTUNIDADE NA CARTEIRA: {ticker} | Score {anl['score']}")
            except Exception as e:
                st.warning(f"Erro ao analisar {ticker}: {e}")
            
            # Atualiza barra de progresso
            bar_progresso.progress((i + 1) / total_ativos)
        
        # Salva resultados no estado
        st.session_state.df_scores = pd.DataFrame(
            resultados, 
            columns=["Ticker", "Score", "Decisão", "Valor_Atual", "Preço", "DY"]
        )
        
        st.success("Análise concluída!")

    # Exibição dos Resultados da Carteira
    if not st.session_state.df_scores.empty:
        st.subheader("Resultados da Análise")
        # Formatação condicional simples
        st.dataframe(
            st.session_state.df_scores.style.background_gradient(subset=["Score"], cmap="RdYlGn"),
            use_container_width=True
        )
        
        # Resumo
        valor_total_carteira = st.session_state.df_scores["Valor_Atual"].sum()
        st.metric("Valor Total da Carteira Analisada", f"R$ {valor_total_carteira:,.2f}")

# =========================
# ABA 3 – REBALANCEAMENTO
# =========================
with tabs[2]:
    st.header("⚖️ Rebalanceamento Automático + Aporte IA")
    
    col_input, col_btn = st.columns([1, 2])
    with col_input:
        aporte_val = st.number_input("Aporte disponível (R$)", min_value=0.0, value=1000.0, step=100.0)
    
    if st.button("Calcular Rebalanceamento"):
        if "df_scores" in st.session_state and not st.session_state.df_scores.empty:
            df_base = st.session_state.df_scores.copy()
            
            # Chama a função de rebalanceamento do módulo
            df_rebal = rebalancear_e_aportar(df_base, aporte_val)
            
            if not df_rebal.empty:
                st.subheader("Sugestão de Aportes")
                st.dataframe(
                    df_rebal.style.format({
                        "Peso_Final": "{:.2%}",
                        "Valor_Atual": "R$ {:,.2f}",
                        "Aporte_Sugerido": "R$ {:,.2f}"
                    }).background_gradient(subset=["Aporte_Sugerido"], cmap="Greens"),
                    use_container_width=True
                )
                
                total_sugerido = df_rebal["Aporte_Sugerido"].sum()
                st.info(f"Total alocado: R$ {total_sugerido:,.2f} (baseado nos Scores e pesos)")
            else:
                st.warning("Não foi possível calcular o rebalanceamento. Verifique os dados da carteira.")
        else:
            st.warning("Por favor, execute a análise da carteira na aba anterior primeiro.")

# =========================
# ABA 4 – MONTE CARLO
# =========================
with tabs[3]:
    st.header("📈 Simulação Monte Carlo da Carteira")
    st.write("Simulação de 10 anos baseada na volatilidade histórica composta dos ativos da sua carteira.")

    col_mc1, col_mc2 = st.columns(2)
    with col_mc1:
        aporte_mensal_mc = st.number_input("Aporte Mensal para Simulação (R$)", value=2000.0)
    
    if st.button("Rodar Simulação"):
        if "df_scores" in st.session_state and not st.session_state.df_scores.empty:
            with st.spinner("Baixando histórico longo e simulando..."):
                lista_tickers = st.session_state.df_scores["Ticker"].tolist()
                valor_inicial_mc = st.session_state.df_scores["Valor_Atual"].sum()
                
                try:
                    # Baixa histórico de 5 anos para ter mais dados estatísticos
                    dados_hist = yf.download(lista_tickers, period="5y", progress=False)["Close"]
                    
                    # Calcula retornos diários
                    retornos_diarios = dados_hist.pct_change().dropna()
                    
                    # Cria um "índice" da carteira (média ponderada seria ideal, aqui média simples dos retornos para demonstração)
                    # Para maior precisão, poderíamos ponderar pelos pesos atuais
                    retorno_carteira = retornos_diarios.mean(axis=1)
                    
                    # Executa Monte Carlo
                    simulacoes = motor.monte_carlo_carteira(
                        retorno_carteira, valor_inicial_mc, aporte=aporte_mensal_mc
                    )
                    
                    if len(simulacoes) > 0:
                        # Gráfico de Distribuição
                        fig_mc = go.Figure(data=[go.Histogram(x=simulacoes, nbinsx=50, marker_color='green')])
                        fig_mc.update_layout(
                            title="Distribuição de Patrimônio Provável em 10 Anos",
                            xaxis_title="Patrimônio Final (R$)",
                            yaxis_title="Frequência",
                            bargap=0.1
                        )
                        st.plotly_chart(fig_mc, use_container_width=True)
                        
                        # Estatísticas
                        mediana = np.median(simulacoes)
                        p10 = np.percentile(simulacoes, 10) # Cenário Pessimista
                        p90 = np.percentile(simulacoes, 90) # Cenário Otimista
                        
                        col_res1, col_res2, col_res3 = st.columns(3)
                        col_res1.metric("Cenário Pessimista (10%)", f"R$ {p10:,.2f}")
                        col_res2.metric("Cenário Provável (Mediana)", f"R$ {mediana:,.2f}")
                        col_res3.metric("Cenário Otimista (90%)", f"R$ {p90:,.2f}")
                    else:
                        st.error("Erro na simulação: dados insuficientes.")
                        
                except Exception as e:
                    st.error(f"Erro ao processar simulação: {e}")
        else:
            st.warning("Analise a carteira na aba 'Carteira' antes de rodar a simulação.")