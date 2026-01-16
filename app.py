import streamlit as st
from motor import analisar_ativo
import matplotlib.pyplot as plt

# Configuração da Página
st.set_page_config(page_title="Hedge Fund Pro", layout="wide")
st.title("📈 Terminal Quantitativo: Fibonacci & Price Action")

# Entrada do Usuário
ticker = st.text_input("Digite o Ticker (ex: VALE3.SA):", "VALE3.SA")

if st.button("Executar Análise"):
    res = analisar_ativo(ticker)
    
    if res:
        # 1. Indicadores de Topo (Métricas)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Preço Atual", f"R$ {res['preco']}")
        col2.metric("Score do Algoritmo", f"{res['score']}/100")
        col3.metric("RSI (IFR)", f"{res['rsi']}")
        col4.metric("Alvo (Fibo)", f"R$ {res['alvo']}")

        # 2. Área do Gráfico Profissional
        st.subheader(f"Mapa de Preços: {ticker}")
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Preço de Fechamento
        ax.plot(res['df']['Close'], label="Preço", color='black', alpha=0.7, linewidth=1.5)
        
        # Desenho das Linhas de Suporte e Resistência Relevantes
        ax.axhline(res['resistencia'], color='red', linestyle='--', alpha=0.6, label=f"Resistência (R$ {res['resistencia']})")
        ax.axhline(res['suporte'], color='green', linestyle='--', alpha=0.6, label=f"Suporte (R$ {res['suporte']})")
        
        # Nível de Fibonacci 50% (Equilíbrio)
        ax.axhline(res['fibo_50'], color='orange', linestyle=':', label=f"Fibo 50% (R$ {res['fibo_50']})")
        
        # Stop Loss e Stop Gain (Projeção)
        ax.fill_between(res['df'].index, res['stop'], res['alvo'], color='gray', alpha=0.1, label="Zona de Operação")
        ax.axhline(res['stop'], color='darkred', linewidth=2, label=f"STOP LOSS (R$ {res['stop']})")
        ax.axhline(res['alvo'], color='darkgreen', linewidth=2, label=f"ALVO/GAIN (R$ {res['alvo']})")
        
        ax.set_title(f"Análise Técnica Avançada - {ticker}")
        ax.legend(loc='upper left', fontsize='small', ncol=2)
        ax.grid(axis='y', alpha=0.3)
        st.pyplot(fig)

        # 3. Tabela de Suporte e Resistência Relevantes
        st.subheader("📊 Quadro de Referências Técnicas")
        tabela_dados = {
            "Indicador": ["Resistência Relevante", "Ponto de Equilíbrio (Fibo 50%)", "Suporte Relevante", "Projeção de Alvo (Gain)", "Risco (Stop Loss)"],
            "Valor (R$)": [res['resistencia'], res['fibo_50'], res['suporte'], res['alvo'], res['stop']]
        }
        st.table(tabela_dados)

        # 4. Alerta de Estratégia
        if res['score'] < 40 and res['rsi'] > 65:
            st.error(f"⚠️ ATENÇÃO: Ativo esticado no TOPO. RSI de {res['rsi']} indica exaustão de compra. Risco de correção alto.")
        elif res['score'] >= 70:
            st.success(f"🚀 SINAL DE FORÇA: Ativo com tendência e espaço para atingir R$ {res['alvo']}.")
        else:
            st.info("⚖️ NEUTRO: Aguardando definição de tendência ou retorno aos níveis de Fibonacci.")

    else:
        st.error("Erro: Ticker não encontrado ou dados insuficientes.")