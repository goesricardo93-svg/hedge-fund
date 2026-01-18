from fpdf import FPDF
import datetime

class RelatorioPrivate:
    def __init__(self, df_carteira, patr_total):
        self.df = df_carteira
        self.patr = patr_total
        self.data = datetime.datetime.now().strftime("%d/%m/%Y")

    def gerar_pdf(self):
        pdf = FPDF()
        pdf.add_page()
        
        # --- CABEÇALHO ---
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(44, 62, 80) # Azul escuro profissional
        pdf.cell(0, 10, "RELATORIO DE PERFORMANCE PATRIMONIAL", 0, 1, 'C')
        
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f"Hedge Fund Ricardo | Data Base: {self.data}", 0, 1, 'C')
        pdf.ln(10)

        # --- RESUMO EXECUTIVO ---
        pdf.set_fill_color(240, 240, 240) # Cinza claro
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "  1. RESUMO EXECUTIVO", 0, 1, 'L', True)
        pdf.ln(2)
        
        pdf.set_font("Arial", '', 11)
        # Tenta formatar R$ com tratamento de erro básico
        try:
            str_patr = f"R$ {self.patr:,.2f}"
        except:
            str_patr = str(self.patr)
            
        pdf.cell(0, 7, f"Patrimonio Liquido Total: {str_patr}", 0, 1)
        
        # Lucro Total
        if 'Lucro' in self.df.columns:
            lucro_total = self.df['Lucro'].sum()
            cor_lucro = (0, 100, 0) if lucro_total >= 0 else (200, 0, 0)
            pdf.set_text_color(*cor_lucro)
            pdf.cell(0, 7, f"Resultado Acumulado (PnL): R$ {lucro_total:,.2f}", 0, 1)
        
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        # --- DETALHAMENTO ---
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "  2. ALOCACAO ATIVA", 0, 1, 'L', True)
        pdf.ln(2)
        
        # Cabeçalho da Tabela
        pdf.set_font("Arial", 'B', 9)
        # Ajuste de colunas (Ticker, Preço, PM, Lucro, Score)
        cols = ["Ativo", "Preco Atual", "Preco Medio", "Lucro/Preju", "Score IA"]
        larguras = [30, 35, 35, 35, 25]
        
        for i, col in enumerate(cols):
            pdf.cell(larguras[i], 8, col, 1, 0, 'C')
        pdf.ln()

        # Linhas da Tabela
        pdf.set_font("Arial", '', 9)
        for _, row in self.df.iterrows():
            try:
                ticker = str(row.get('Ticker', '-'))
                preco = f"R$ {row.get('Preço', 0):.2f}"
                pm = f"R$ {row.get('PM', 0):.2f}"
                lucro = f"R$ {row.get('Lucro', 0):.2f}"
                score = str(int(row.get('Score', 0)))
                
                pdf.cell(larguras[0], 7, ticker, 1, 0, 'C')
                pdf.cell(larguras[1], 7, preco, 1, 0, 'C')
                pdf.cell(larguras[2], 7, pm, 1, 0, 'C')
                
                # Cor do lucro na tabela (Opcional, aqui mantendo simples para evitar erro de PDF)
                pdf.cell(larguras[3], 7, lucro, 1, 0, 'C')
                pdf.cell(larguras[4], 7, score, 1, 0, 'C')
                pdf.ln()
            except:
                continue

        # --- RODAPÉ ---
        pdf.set_y(-30)
        pdf.set_font("Arial", 'I', 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, "Relatorio gerado automaticamente pelo Terminal Hedge Fund.", 0, 1, 'C')
        pdf.cell(0, 5, "Este documento nao constitui recomendacao de investimento.", 0, 1, 'C')

        # Retorna os bytes do PDF (compatível com Streamlit)
        return pdf.output(dest='S').encode('latin-1', 'replace')