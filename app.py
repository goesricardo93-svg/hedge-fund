import streamlit as st
from motor import analisar_ativo
import matplotlib.pyplot as plt

# Configuração da Página
st.set_page_config(page_title="Hedge Fund Pessoal", layout="wide")
st.title("📈 Terminal de Inteligência Quantitativa")

# Entrada do Usuário
ticker = st.text_input("Digite o Ticker (ex: PETR4.SA):", "BBAS3.SA")

if st.button("Analisar"):
    res = analisar_ativo(ticker)
    
    if res:
        # Criação das colunas de indicadores
        col1, col2, col3 = st.columns(3)
        col1.metric("Preço", f"R$ {res['preco']}")
        col2.metric("Score Técnico", f"{res['score']}/100")
        col3.metric("RSI (IFR)", res['rsi'])

        # Criação do Gráfico
        st.subheader(f"Análise Gráfica: {ticker}")
        fig, ax = plt.subplots(figsize=(10, 4))
        
        # Plotando o fechamento
        ax.plot(res['df']['Close'], label="Preço de Fechamento", color='blue')
        
        # Linhas de Gestão de Risco
        ax.axhline(res['stop'], color='red', linestyle='--', label=f"Stop Loss (R$ {res['stop']})")
        ax.axhline(res['alvo'], color='green', linestyle='--', label=f"Alvo (R$ {res['alvo']})")
        
        ax.set_title(f"Histórico de Preços e Projeções")
        ax.legend()
        st.pyplot(fig)
        
        # Alerta de Sinal
        if res['score'] >= 70:
            st.success("🔥 SINAL FORTE DE COMPRA DETECTADO PELO ALGORITMO")
        elif res['score'] >= 50:
            st.warning("⚖️ SINAL NEUTRO - AGUARDAR CONFIRMAÇÃO")
        else:
            st.error("❄️ SEM SINAL DE ENTRADA (MOMENTUM BAIXO)")
    else:
        st.error("Erro ao buscar dados. Verifique se o ticker está correto (ex: PETR4.SA).")