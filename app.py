import streamlit as st
from motor import analisar_ativo
import matplotlib.pyplot as plt

st.set_page_config(page_title="Hedge Fund Pro", layout="wide")
st.title("📈 Terminal Quantitativo: Fibonacci & Price Action")

ticker = st.text_input("Digite o Ticker (ex: VALE3.SA):", "VALE3.SA")

if st.button("Executar Análise"):
    res = analisar_ativo(ticker)
    if res:
        # Métricas de Topo
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Preço Atual", f"R$ {res['preco']}")
        col2.metric("Score", f"{res['score']}/100")
        col3.metric("RSI", f"{res['rsi']}")
        col4.metric("ALVO (Gain)", f"R$ {res['alvo']}")

        # Gráfico Profissional
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(res['df']['Close'], label="Preço", color='black', alpha=0.7)
        
        # Linhas de Referência
        ax.axhline(res['resistencia'], color='red', linestyle='--', alpha=0.5, label="Resistência")
        ax.axhline(res['suporte'], color='blue', linestyle='--', alpha=0.5, label="Suporte")
        ax.axhline(res['fibo_50'], color='orange', linestyle=':', label="Fibo 50%")
        
        # LINHAS DE EXECUÇÃO (Stop e Gain)
        ax.axhline(res['alvo'], color='green', linewidth=3, label=f"STOP GAIN (R$ {res['alvo']})")
        ax.axhline(res['stop'], color='darkred', linewidth=3, label=f"STOP LOSS (R$ {res['stop']})")
        
        # Pintar zona de lucro
        ax.fill_between(res['df'].index, res['preco'], res['alvo'], color='green', alpha=0.1)

        ax.legend(loc='upper left', ncol=2)
        ax.set_title(f"Análise de Fibonacci: {ticker}")
        st.pyplot(fig)

        # Tabela Final
        st.subheader("📊 Resumo da Estratégia")
        st.table({
            "Nível Técnico": ["Stop Gain (Projeção 61.8%)", "Resistência Relevante", "Ponto 50% Fibo", "Suporte Relevante", "Stop Loss (Risco)"],
            "Preço (R$)": [res['alvo'], res['resistencia'], res['fibo_50'], res['suporte'], res['stop']]
        })

        if res['rsi'] > 70:
            st.warning("⚠️ Ativo em zona de TOPO (Sobrecomprado). RSI alto.")
    else:
        st.error("Erro ao carregar dados.")