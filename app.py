import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import smtplib
from email.mime.text import MIMEText
from motor import MotorAnalise

# ======================================================
# 1. CONFIGURAÇÕES GERAIS
# ======================================================
st.set_page_config(page_title="Hedge Fund Ricardo | Terminal v4.0", layout="wide")

# Credenciais (Edite aqui ou use Secrets do Streamlit)
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"
EMAIL_USER = "goes.ricardo93@gmail.com"
EMAIL_PASS = "SENHA_APP_GOOGLE"

# Configuração de Estratégia
ALVOS_SETOR = {
    "FII": 0.40, 
    "Elétricas": 0.25, 
    "Bancos": 0.10, 
    "Seguros": 0.10, 
    "Holding": 0.05,
    "Exterior": 0.05,
    "Outros": 0.05
}

# Configuração de Stress Test
CENARIOS_STRESS_PERDA_TOTAL = {
    "Crise 2008 (-50%)": -0.50,
    "Joesley Day (-15%)": -0.15,
    "Pandemia (-45%)": -0.45,
    "Bear Market Lento (-30%)": -0.30
}

# ======================================================
# 2. ESTILO E ESTADO DA SESSÃO
# ======================================================
def aplicar_estilo():
    st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #f0f2f6; }
    div[data-testid="metric-container"] { 
        background-color: #1f2937; border: 1px solid #374151; 
        padding: 15px; border-radius: 8px; 
    }
    .stDataFrame { border: 1px solid #374151; }
    </style>
    """, unsafe_allow_html=True)

aplicar_estilo()

# Inicializa variáveis de sessão se não existirem
if "alertas_enviados" not in st.session_state:
    st.session_state.alertas_enviados = set()

if "meus_ativos" not in st.session_state:
    # Dados iniciais da carteira
    data = [
        ["ALZR11.SA",100,10.81,"FII"],["BBAS3.SA",1703,24.48,"Bancos"],
        ["BBSE3.SA",55,35.64,"Seguros"],["BTCI11.SA",502,10.16,"FII"],
        ["BTLG11.SA",60,98.50,"FII"],["CMIG4.SA",1644,11.12,"Elétricas"],
        ["CPLE3.SA",617,9.64,"Elétricas"],["CPTS11.SA",276,8.52,"FII"],
        ["CXSE3.SA",800,14.20,"Seguros"],["EQTL3.SA",200,30.21,"Elétricas"],
        ["ITSA4.SA",1174,9.63,"Holding"],["IVVB11.SA",6,366.97,"Exterior"],
        ["PETR4.SA",900,32.07,"Outros"],["TAEE4.SA",1000,11.36,"Elétricas"],
        ["VALE3.SA",152,54.79,"Outros"]
    ]
    st.session_state.meus_ativos = pd.DataFrame(data, columns=["Ticker","Qtd","PM","Setor"])

# ======================================================
# 3. FUNÇÕES DE SUPORTE
# ======================================================
def enviar_telegram(msg):
    try:
        if "SEU_TOKEN" not in TELEGRAM_TOKEN: # Só envia se tiver configurado
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except: pass

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        # Tenta pegar histórico recente
        hist = t.history(period="2y")
        
        if hist.empty: 
            return None, None, None
            
        motor = MotorAnalise()
        # Passa o ticker também para logs de erro
        r = motor.analisar(hist, t.info, ticker)
        return t, r, t.info
    except Exception as e:
        print(f"Erro no Yahoo Finance para {ticker}: {e}")
        return None, None, None

def calcular_score(r, info):
    s = 0
    if not r: return 0
    
    # Regras do Score (0 a 100)
    if r["rsi"] < 40: s += 20          # Está descontado tecnicamente?
    if r["preco"] < r["p_bazin"]: s += 30 # Está barato pelos dividendos?
    if (info.get("dividendYield",0) or 0) > 0.06: s += 20 # Paga bem?
    if r["roe"] > 0.15: s += 15        # É rentável?
    if r["volatilidade"] < 0.30: s += 15 # É segura?
    
    return min(s, 100)

# ======================================================
# 4. INTERFACE DO USUÁRIO
# ======================================================
st.title("💼 Terminal Quantitativo Ricardo")
tabs = st.tabs(["🔎 Carteira & Sincronização", "🤖 IA de Alocação (IPA)", "🎲 Risco & Monte Carlo"])

# --- ABA 1: CARTEIRA ---
with tabs[0]:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("Sua Carteira")
        # Editor interativo para mudar Qtd ou PM
        df_ed = st.data_editor(st.session_state.meus_ativos, num_rows="dynamic", use_container_width=True, key="editor_carteira")
        # Atualiza a sessão com o que for editado
        st.session_state.meus_ativos = df_ed 
    
    with col2:
        st.subheader("Ações")
        if st.button("🔄 Sincronizar Agora", type="primary"):
            res = []
            progress = st.progress(0)
            total = len(df_ed)
            
            for i, row in df_ed.iterrows():
                # Busca dados
                t, r, info = obter_dados(row["Ticker"])
                
                if r:
                    sc = calcular_score(r, info)
                    
                    status = "MANTER"
                    if sc > 75: status = "🟢 COMPRAR"
                    if sc < 40: status = "🔴 REVISAR"
                    
                    # Sistema de Alertas (Telegram)
                    chave_alerta = f"{row['Ticker']}_{status}"
                    if "COMPRAR" in status and chave_alerta not in st.session_state.alertas_enviados:
                        enviar_telegram(f"💰 OPORTUNIDADE: {row['Ticker']} | Score {sc} | Preço: {r['preco']:.2f}")
                        st.session_state.alertas_enviados.add(chave_alerta)

                    res.append({
                        **row.to_dict(),
                        "Cotação": r["preco"],
                        "Volatilidade": r["volatilidade"],
                        "Score": sc,
                        "Status": status
                    })
                else:
                    # Caso o Yahoo Finance falhe ou ticker esteja errado
                    res.append({**row.to_dict(), "Cotação": 0, "Volatilidade": 0, "Score": 0, "Status": "❌ ERRO"})
                
                progress.progress((i+1)/total)
            
            # Salva o resultado processado
            st.session_state.df_final = pd.DataFrame(res)
            st.success("Sincronização concluída!")

    # Exibe Tabela Final Processada
    if "df_final" in st.session_state:
        st.divider()
        st.dataframe(st.session_state.df_final, use_container_width=True)
        
        # Totalizador de Patrimônio
        if not st.session_state.df_final.empty:
            total_patrimonio = (st.session_state.df_final["Cotação"] * st.session_state.df_final["Qtd"]).sum()
            st.metric("Patrimônio Total Atualizado", f"R$ {total_patrimonio:,.2f}")

# --- ABA 2: IA DE ALOCAÇÃO ---
with tabs[1]:
    st.header("🤖 Alocação Inteligente (IPA)")
    st.info("A IA calcula o 'Índice de Prioridade de Aporte' cruzando: Desvio do Alvo, Valuation (Score) e Risco.")
    
    if "df_final" in st.session_state and not st.session_state.df_final.empty:
        col_input, col_res = st.columns([1, 2])
        
        with col_input:
            valor_aporte = st.number_input("Quanto quer aportar hoje?", value=5000.0, step=500.0)
            st.write("A IA vai distribuir esse valor respeitando os pesos dos setores e buscando as melhores oportunidades.")
            calc_btn = st.button("🧠 Calcular Distribuição")

        with col_res:
            if calc_btn:
                motor = MotorAnalise()
                df_sugestao = motor.sugerir_alocacao_quantitativa(
                    st.session_state.df_final, 
                    valor_aporte, 
                    ALVOS_SETOR
                )
                
                if not df_sugestao.empty:
                    st.subheader("🎯 Sugestão de Compra")
                    
                    # Prepara tabela bonita para exibição
                    df_show = df_sugestao[["Ticker", "Setor", "Score", "IPA", "Qtd Sugerida", "Aporte R$"]].copy()
                    
                    st.dataframe(
                        df_show.style.format({
                            "Aporte R$": "R$ {:.2f}", 
                            "IPA": "{:.2f}",
                            "Score": "{:.0f}"
                        }).background_gradient(subset=["IPA"], cmap="Greens"),
                        use_container_width=True
                    )
                    
                    # Gráfico Pizza da Sugestão
                    fig = go.Figure(data=[go.Pie(labels=df_show["Ticker"], values=df_show["Aporte R$"], hole=.4)])
                    fig.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("A IA não encontrou oportunidades claras (Carteira balanceada ou Score baixo).")
    else:
        st.warning("⚠️ Vá na aba 'Carteira' e clique em Sincronizar primeiro.")

# --- ABA 3: RISCO & MONTE CARLO ---
with tabs[2]:
    st.header("🛡️ Gestão de Risco")
    
    if "df_final" in st.session_state and not st.session_state.df_final.empty:
        patrimonio_atual = (st.session_state.df_final["Cotação"] * st.session_state.df_final["Qtd"]).sum()
        motor = MotorAnalise()
        
        c1, c2 = st.columns(2)
        
        # --- STRESS TEST ---
        with c1:
            st.subheader("🔥 Stress Test (6 Meses)")
            st.write(f"Patrimônio Base: **R$ {patrimonio_atual:,.2f}**")
            
            if st.button("💥 Rodar Stress Test"):
                dados_stress = motor.simular_stress_historico(patrimonio_atual, CENARIOS_STRESS_PERDA_TOTAL)
                
                fig_stress = go.Figure()
                for cenario, valores in dados_stress.items():
                    fig_stress.add_trace(go.Scatter(y=valores, mode='lines', name=cenario))
                
                fig_stress.update_layout(yaxis_tickprefix="R$ ", template="plotly_dark", title="Queda Patrimonial Simulada")
                st.plotly_chart(fig_stress, use_container_width=True)

        # --- MONTE CARLO ---
        with c2:
            st.subheader("🎲 Monte Carlo (10 Anos)")
            aporte_mensal = st.number_input("Aporte Mensal Recorrente", value=2000.0)
            
            if st.button("🔮 Rodar 1.000 Simulações"):
                simulacoes = motor.simular_monte_carlo(patrimonio_atual, aporte_mensal)
                
                mediana = np.median(simulacoes)
                pior = np.percentile(simulacoes, 5)   # Pior caso (5% azar)
                melhor = np.percentile(simulacoes, 95) # Melhor caso (95% sorte)
                
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Pessimista (5%)", f"R$ {pior:,.2f}", delta="-Risco", delta_color="inverse")
                col_m2.metric("Otimista (95%)", f"R$ {melhor:,.2f}", delta="+Retorno")
                st.metric("Cenário Provável (Mediana)", f"R$ {mediana:,.2f}")
                
                fig_mc = go.Figure()
                fig_mc.add_trace(go.Histogram(x=simulacoes, nbinsx=40, marker_color='#00CC96'))
                fig_mc.update_layout(xaxis_tickprefix="R$ ", template="plotly_dark", showlegend=False, title="Distribuição de Resultados")
                st.plotly_chart(fig_mc, use_container_width=True)
    else:
        st.warning("⚠️ Sincronize a carteira na Aba 1.")

