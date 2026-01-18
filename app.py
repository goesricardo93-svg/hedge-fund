import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# Importação Segura
try:
    from motor import MotorAnalise
    from rebalance import rebalancear_e_aportar
except ImportError as e:
    st.error(f"Erro ao importar módulos: {e}")
    st.stop()

st.set_page_config(page_title="Hedge Fund Ricardo v58.0 (Gestor Risco)", layout="wide")

# --- SUAS METAS ---
METAS = {
    "Renda Fixa": 30.0,
    "Exterior": 20.0,
    "Ações-Bancos": 7.5, "Ações-Elétricas": 7.5, "Ações-Seguridade": 6.0, "Ações-Commodities": 6.0, "Ações-Outros": 3.0,
    "FIIs-Papel": 10.0, "FIIs-Tijolo": 6.0, "FIIs-Outros": 4.0
}

@st.cache_data(ttl=3600)
def obter_dados(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y") 
        if hist.empty: return None
        return MotorAnalise().analisar(hist, t.info, ticker)
    except: return None

def auto_classificar():
    motor = MotorAnalise()
    progress_text = "Classificando ativos via IA..."
    my_bar = st.progress(0, text=progress_text)
    
    total = len(st.session_state.carteira_acoes)
    for idx, row in st.session_state.carteira_acoes.iterrows():
        try:
            t = yf.Ticker(row["Ticker"])
            setor = motor.identificar_setor(t.info, row["Ticker"])
            st.session_state.carteira_acoes.at[idx, "Setor"] = setor
        except:
            st.session_state.carteira_acoes.at[idx, "Setor"] = "Outros"
        my_bar.progress((idx + 1) / total)
    
    my_bar.empty()
    st.success("Classificação Concluída!")

# Inicializa Carteira
if "carteira_acoes" not in st.session_state:
    st.session_state.carteira_acoes = pd.DataFrame([
        ["BBAS3.SA", 100, 24.50, "Aguardando..."],
        ["CPSH11.SA", 50, 10.10, "Aguardando..."],
        ["XPML11.SA", 10, 115.00, "Aguardando..."],
        ["IVVB11.SA", 5, 280.00, "Aguardando..."]
    ], columns=["Ticker", "Qtd", "PM", "Setor"])

# --- INTERFACE ---
st.title("🛡️ Hedge Fund Ricardo (Gestor de Risco)")

tabs = st.tabs(["🔎 Análise Blindada", "💼 Carteira Inteligente"])

with tabs[0]:
    c_input, c_btn = st.columns([3, 1])
    t = c_input.text_input("Ticker", "MXRF11.SA").upper()
    if c_btn.button("Analisar Risco"):
        r = obter_dados(t)
        if r:
            # --- ÁREA DE DESTAQUE ---
            st.subheader("📊 Raio-X & Segurança")
            col1, col2, col3, col4 = st.columns(4)
            
            col1.metric("Preço", f"R$ {r['preco']:.2f}")
            col2.metric("DY Anual", f"{r['dy_anual']:.1f}%")
            
            # Formatação condicional do Score
            if r['score_ia'] == 0:
                col3.error("BLOQUEADO (0/100)")
            else:
                col3.metric("Score IA", f"{r['score_ia']}/100", delta=r['decisao_ia'])
            
            liq_formatada = f"R$ {r['liq_media']/1000:.0f}k"
            col4.metric("Liquidez Média", liq_formatada)
            
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📋 Valuation")
                st.table(pd.DataFrame({
                    "Modelo": ["Bazin", "Graham", "Gordon"], 
                    "Valor": [f"R$ {r['p_bazin']:.2f}", f"R$ {r['p_graham']:.2f}", f"R$ {r['p_gordon']:.2f}"]
                }))
            with c2:
                st.subheader("🧠 Análise de Riscos & Oportunidades")
                if "⚠️" in r['motivos'] or "⛔" in r['motivos']:
                    st.error(r['motivos']) # Mostra em vermelho se tiver perigo
                else:
                    st.info(r['motivos']) # Azul se estiver normal

        else:
            st.error("Ativo não encontrado ou sem dados.")

with tabs[1]:
    st.subheader("Gestão & Rebalanceamento")
    
    if st.button("🔄 1. Atualizar Classificação (IA)"):
        auto_classificar()
        st.rerun()
            
    df_edited = st.data_editor(
        st.session_state.carteira_acoes,
        column_config={
            "Setor": st.column_config.SelectboxColumn("Setor", options=list(METAS.keys()), required=True)
        },
        use_container_width=True,
        num_rows="dynamic"
    )
    st.session_state.carteira_acoes = df_edited
    
    aporte = st.number_input("Quanto quer aportar hoje? (R$)", value=5000.0)
    
    if st.button("🚀 2. Calcular Aportes Seguros"):
        dados_completos = []
        for _, row in df_edited.iterrows():
            d = obter_dados(row["Ticker"])
            if d:
                dados_completos.append({
                    "Ticker": row["Ticker"],
                    "Setor": row["Setor"],
                    "Qtd": row["Qtd"],
                    "Valor_Atual": row["Qtd"] * d["preco"],
                    "Score": d["score_ia"]
                })
            else:
                dados_completos.append({
                    "Ticker": row["Ticker"],
                    "Setor": row["Setor"],
                    "Qtd": row["Qtd"],
                    "Valor_Atual": row["Qtd"] * 10.0,
                    "Score": 50
                })
        
        df_calc = pd.DataFrame(dados_completos)
        df_final = rebalancear_e_aportar(df_calc, aporte, METAS)
        
        st.divider()
        st.subheader("Sugestão de Compra (Filtrada pelo Risco)")
        # Só mostra quem tem aporte sugerido E Score > 0 (Dupla segurança)
        df_show = df_final[(df_final["Aporte Sugerido (R$)"] > 1) & (df_final["Score"] > 0)]
        
        if df_show.empty and df_final["Aporte Sugerido (R$)"].sum() > 0:
            st.warning("O rebalanceador sugeriu compras, mas os ativos foram bloqueados pelas Travas de Segurança (Score 0). Revise a qualidade dos ativos.")
        else:
            st.dataframe(
                df_show[["Ticker", "Setor", "Score", "Aporte Sugerido (R$)"]].style.format({"Aporte Sugerido (R$)": "R$ {:.2f}"}),
                use_container_width=True
            )