import pandas as pd
from datetime import datetime
import io

# Tenta importar FPDF, se não tiver, cria uma classe dummy para não quebrar
try:
    from fpdf import FPDF
except ImportError:
    class FPDF: 
        def __init__(self, orientation='P', unit='mm', format='A4'): pass
        def add_page(self): pass
        def set_font(self, family, style, size): pass
        def cell(self, w, h, txt, ln, align): pass
        def output(self, dest='S'): return b"Instale a biblioteca 'fpdf' para gerar PDFs."

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Hedge Fund Ricardo - Relatorio Gerencial', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(5)

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 10, body)
        self.ln()

def gerar_pdf_carteira(df_acoes, df_rf, total_patrimonio, metas):
    pdf = PDFReport()
    pdf.add_page()

    # 1. Resumo Patrimonial
    pdf.chapter_title('1. Resumo Patrimonial')
    total_acoes = df_acoes["Valor_Atual"].sum() if "Valor_Atual" in df_acoes.columns else 0
    total_rf = df_rf["Saldo Atual"].sum() if not df_rf.empty else 0
    
    texto_resumo = (
        f"Patrimonio Total: R$ {total_patrimonio:,.2f}\n"
        f"Renda Variavel: R$ {total_acoes:,.2f} ({(total_acoes/total_patrimonio)*100:.1f}%)\n"
        f"Renda Fixa: R$ {total_rf:,.2f} ({(total_rf/total_patrimonio)*100:.1f}%)"
    )
    pdf.chapter_body(texto_resumo)

    # 2. Alocação Setorial vs Metas
    pdf.chapter_title('2. Alocacao Setorial & Desvios')
    
    # Agrupa carteira por setor
    if "Valor_Atual" in df_acoes.columns:
        alocacao_atual = df_acoes.groupby("Setor")["Valor_Atual"].sum()
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(50, 10, 'Setor', 1)
        pdf.cell(40, 10, 'Atual (R$)', 1)
        pdf.cell(30, 10, 'Atual (%)', 1)
        pdf.cell(30, 10, 'Meta (%)', 1)
        pdf.ln()
        
        pdf.set_font('Arial', '', 10)
        for setor, meta in metas.items():
            valor = alocacao_atual.get(setor, 0.0)
            pct_atual = (valor / total_patrimonio) * 100 if total_patrimonio > 0 else 0
            
            pdf.cell(50, 10, setor[:20], 1)
            pdf.cell(40, 10, f"{valor:,.2f}", 1)
            pdf.cell(30, 10, f"{pct_atual:.1f}%", 1)
            pdf.cell(30, 10, f"{meta:.1f}%", 1)
            pdf.ln()
    else:
        pdf.chapter_body("Dados de carteira insuficientes para calculo setorial.")

    pdf.ln(5)

    # 3. Riscos Identificados (Ativos Bloqueados)
    pdf.chapter_title('3. Radar de Riscos (Compliance)')
    if "Score" in df_acoes.columns:
        riscos = df_acoes[df_acoes["Score"] == 0]
        if not riscos.empty:
            pdf.set_text_color(200, 0, 0) # Vermelho
            pdf.chapter_body(f"ATENCAO: Foram identificados {len(riscos)} ativos com Score 0 (Bloqueados):")
            for _, row in riscos.iterrows():
                pdf.cell(0, 10, f"- {row['Ticker']} ({row['Setor']})", 0, 1)
            pdf.set_text_color(0, 0, 0)
        else:
            pdf.chapter_body("Nenhum risco critico (Score 0) identificado na carteira atual.")
    
    # 4. Sugestões de Aporte
    pdf.chapter_title('4. Sugestoes de Rebalanceamento')
    if "Aporte Sugerido (R$)" in df_acoes.columns:
        sugestoes = df_acoes[df_acoes["Aporte Sugerido (R$)"] > 1].sort_values(by="Aporte Sugerido (R$)", ascending=False)
        if not sugestoes.empty:
            for _, row in sugestoes.iterrows():
                pdf.cell(0, 10, f"COMPRA: {row['Ticker']} - R$ {row['Aporte Sugerido (R$)']:,.2f} (Score: {row['Score']})", 0, 1)
        else:
            pdf.chapter_body("Sem sugestoes de compra no momento.")

    return pdf.output(dest='S').encode('latin-1')