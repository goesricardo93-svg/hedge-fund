import streamlit as st
import yfinance as yf
import pandas as pd
from motor import MotorAnalise
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(page_title="Terminal Hedge Fund", layout="wide")

# Inicializa o Motor
motor = MotorAnalise()

# --- TÍTULO E CABEÇALHO ---
st.title("🏛️ Terminal Hedge Fund - Inteligência Visual")
st.markdown("Monitoramento de Ciclos de 252 Períodos e Gestão de Risco")

# --- CONSULTA DE ATIVO ---
ticker_raw = st.text_input("Consultar Ativo (Ex: PETR4, BBAS3, BTC-USD, NVDA):", value="PETR4").upper().strip()

# Lógica de Auto-Correção para B3 (Adiciona .SA se for ação brasileira)
ticker = ticker_raw
if "-" not in ticker_raw and "." not in ticker_raw and any(c.isdigit() for c in ticker_raw):
    ticker = f"{ticker_raw}.SA"

if ticker:
    try:
        with st.spinner(f'Processando inteligência de {ticker}...'):
            # Busca dados de 4 anos para garantir cálculo da média de 252p
            df_raw = yf.download(ticker, period="4y", progress=False)
            
            if not df_raw.empty:
                # Padronização de Colunas (Trata MultiIndex e nomes)
                if isinstance(df_raw.columns, pd.MultiIndex):
                    df_raw.columns = df_raw.columns.get_level_values(0)
                df_raw.columns = [str(c).lower() for c in df_raw.columns]
                df_proc = df_raw.reset_index()
                df_proc.columns = [str(c).lower() for c in df_proc.columns]
                
                # Roda a análise no Motor
                res = motor.analisar(df_proc)
                
                if res:
                    # --- PAINEL DE RECOMENDAÇÃO OBJETIVA ---
                    st.markdown("---")
                    # Define a cor do alerta baseado na recomendação
                    color_map = {"green": "green", "red": "red", "yellow": "orange", "blue": "blue", "gray": "gray"}
                    st.subheader(f"🎯 Veredito do Motor: :{color_map.get(res['cor_sinal'], 'white')}[{res['recomendacao']}]")
                    
                    # --- MÉTRICAS DE TOPO ---
                    c1, c2, c3, c4 = st.columns(4)
                    moeda = "R$" if ".SA" in ticker else "$"
                    c1.metric("Preço Atual", f"{moeda} {res['preco']:,.2f}")
                    c2.metric("Tendência (252p)", res['tendencia'])
                    c3.metric("RSI Tático (14p)", res['rsi_14'])
                    c4.metric("RSI Macro (252p)", res['rsi_252'])

                    st.markdown("---")

                    # --- GRÁFICO OPERACIONAL (PLOTLY) ---
                    st.subheader(f"📈 Gráfico Operacional: {ticker}")
                    
                    fig = go.Figure()
                    # Linha de Preço
                    fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['close'], name="Preço", line=dict(color='#ffffff', width=2)))
                    # Média 252 (Calculada no gráfico para visualização)
                    ma_plot = df_proc['close'].rolling(window=252).mean()
                    fig.add_trace(go.Scatter(x=df_proc['date'], y=ma_plot, name="Média 252", line=dict(color='orange', dash='dot')))
                    
                    # LINHAS HORIZONTAIS DE SINAL
                    # Resistência e Suporte Anuais
                    fig.add_hline(y=res['resistencia'], line_dash="dash", line_color="yellow", annotation_text="RESISTÊNCIA ANUAL")
                    fig.add_hline(y=res['suporte'], line_dash="dash", line_color="cyan", annotation_text="SUPORTE ANUAL")
                    
                    # Níveis de Stop
                    fig.add_hline(y=res['stop_loss'], line_color="#FF4B4B", line_width=2, annotation_text="STOP LOSS")
                    fig.add_hline(y=res['stop_gain'], line_color="#00CC96", line_width=2, annotation_text="STOP GAIN")
                    
                    # Ajustes de Layout
                    fig.update_layout(template="plotly_dark", height=600, margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig, use_container_width=True)

                    # --- DETALHAMENTO TÉCNICO (CARDS) ---
                    st.markdown("---")
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        st.subheader("🛡️ Gestão de Risco")
                        st.error(f"🔴 STOP LOSS: {moeda} {res['stop_loss']:,.2f}")
                        st.success(f"🟢 STOP GAIN: {moeda} {res['stop_gain']:,.2f}")
                        st.info(f"🎯 ALVO MÉDIA (252p): {moeda} {res['ma252']:,.2f}")
                    
                    with col_b:
                        st.subheader("🚧 Barreiras de Preço")
                        st.warning(f"RESISTÊNCIA: {moeda} {res['resistencia']:,.2f}")
                        st.info(f"SUPORTE: {moeda} {res['suporte']:,.2f}")
                    
                    with col_c:
                        st.subheader("📐 Fibonacci (Ciclo 252p)")
                        for nivel, valor in res['fibonacci'].items():
                            st.write(f"**{nivel}:** {moeda} {valor:,.2f}")

            else:
                st.warning("Dados insuficientes para este ativo no período de 252 dias.")
        else:
            st.error("Ativo não encontrado. Verifique o ticker (ex: para PETR4 use apenas PETR4 ou PETR4.SA).")
            
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")

# --- MONITOR GLOBAL (WATCHLIST) ---
st.markdown("---")
with st.expander("📊 Monitor Global (Lista de Observação rápidos)"):
    if st.button("Recarregar Monitor Macro"):
        watchlist = ["BTC-USD", "ETH-USD", "PETR4.SA", "VALE3.SA", "BBAS3.SA", "AAPL", "NVDA"]
        dados_monitor = []
        for t in watchlist:
            try:
                d = yf.download(t, period="3y", progress=False)
                if not d.empty:
                    d.columns = [str(c).lower() for c in (d.columns.get_level_values(0) if isinstance(d.columns, pd.MultiIndex) else d.columns)]
                    r = motor.analisar(d.reset_index())
                    if r:
                        dados_monitor.append({
                            "Ativo": t, 
                            "Preço": r['preco'], 
                            "Tendência": r['tendencia'], 
                            "RSI 252p": r['rsi_252'],
                            "Veredito": r['recomendacao']
                        })
            except: continue
        if dados_monitor:
            st.table(pd.DataFrame(dados_monitor))