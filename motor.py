import pandas as pd
import numpy as np

class MotorAnalise:
    def analisar(self, hist, info, ticker):
        """
        Analisa dados históricos e fundamentais para gerar indicadores.
        """
        try:
            # Proteção contra dados vazios
            if hist is None or hist.empty:
                return None

            # 1. Dados de Preço Atual
            preco_atual = hist["Close"].iloc[-1]
            
            # 2. RSI (Relative Strength Index) - 14 períodos
            delta = hist["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # 3. Volatilidade Anualizada (252 dias úteis)
            retornos = hist["Close"].pct_change().dropna()
            volatilidade = retornos.std() * (252 ** 0.5)

            # 4. Preço Justo de Bazin (DPA / 6%)
            # Tenta pegar dividendYield com segurança
            dy = info.get("dividendYield", 0)
            if dy is None: dy = 0
            
            dpa = preco_atual * dy
            p_bazin = dpa / 0.06 if dpa > 0 else 0

            # 5. Indicadores Fundamentais
            pl = info.get("trailingPE", 0)
            roe = info.get("returnOnEquity", 0)
            
            # Garantir que não seja None
            if pl is None: pl = 0
            if roe is None: roe = 0

            return {
                "preco": preco_atual,
                "rsi": rsi,
                "volatilidade": volatilidade,
                "p_bazin": p_bazin,
                "pl": pl,
                "roe": roe
            }
        except Exception as e:
            # Em caso de erro silencioso, imprime no log do servidor
            print(f"Erro ao analisar {ticker}: {e}")
            return None

    def sugerir_alocacao_quantitativa(self, df, valor_aporte, alvos_setor):
        """
        Calcula o IPA (Índice de Prioridade de Aporte) para sugerir compras.
        """
        df = df.copy()
        
        # Dados Financeiros Básicos
        df["Valor Atual"] = df["Qtd"] * df["Cotação"]
        total_carteira = df["Valor Atual"].sum()
        
        # Pesos Atuais e Alvos
        df["Peso Atual"] = df["Valor Atual"] / total_carteira if total_carteira > 0 else 0
        
        # Calcula Peso Alvo Individual (Peso do Setor / Quantidade de ativos naquele setor)
        contagem_setor = df.groupby("Setor")["Ticker"].transform("count")
        df["Peso Setor Alvo"] = df["Setor"].map(alvos_setor).fillna(0.01) # Se setor não existir, alvo é 1%
        df["Peso Alvo"] = df["Peso Setor Alvo"] / contagem_setor
        
        # Fatores do IPA
        desvio = (df["Peso Alvo"] - df["Peso Atual"])
        desconto_pm = (df["PM"] - df["Cotação"]) / df["PM"]
        risco = df["Volatilidade"]
        
        # Fórmula do IPA (Index of Priority Allocation)
        # Prioriza: Desvio do Alvo (4x), Score Alto (1x), Desconto no PM (0.5x)
        # Penaliza: Alta Volatilidade (0.5x)
        df["IPA"] = (
            (desvio * 4) + 
            (df["Score"] / 100) + 
            (desconto_pm * 0.5) - 
            (risco * 0.5)
        )
        
        # Remove valores negativos (não vamos "vender", só deixar de comprar)
        df["IPA"] = df["IPA"].clip(lower=0)
        
        # Distribuição do Dinheiro
        soma_ipa = df["IPA"].sum()
        if soma_ipa > 0:
            df["Aporte R$"] = (df["IPA"] / soma_ipa) * valor_aporte
            
            # Filtra "migalhas" (aportes menores que 1% do total) para focar
            df.loc[df["Aporte R$"] < (valor_aporte * 0.01), "Aporte R$"] = 0
            
            df["Qtd Sugerida"] = (df["Aporte R$"] / df["Cotação"]).astype(int)
        else:
            df["Aporte R$"] = 0
            df["Qtd Sugerida"] = 0

        # Retorna apenas as linhas com sugestão de compra, ordenadas por valor
        return df[df["Aporte R$"] > 0].sort_values("Aporte R$", ascending=False)

    def simular_monte_carlo(self, patrimonio_inicial, aporte_mensal, anos=10, simulacoes=1000):
        """
        Simula 1000 caminhos possíveis para o patrimônio.
        """
        meses = anos * 12
        resultados = []
        
        # Parâmetros de Mercado (Conservador)
        mu = 0.008  # Retorno médio mensal esperado (0.8%)
        sigma = 0.05 # Volatilidade mensal (5%)
        
        for _ in range(simulacoes):
            patrimonio = patrimonio_inicial
            for _ in range(meses):
                retorno = np.random.normal(mu, sigma)
                patrimonio = patrimonio * (1 + retorno) + aporte_mensal
            resultados.append(patrimonio)
            
        return np.array(resultados)

    def simular_stress_historico(self, patrimonio_atual, cenarios):
        """
        Simula o efeito de crises históricas no patrimônio atual ao longo de 6 meses.
        """
        dados_grafico = {}
        for nome_cenario, queda_total in cenarios.items():
            # Dilui a queda total em 6 meses para criar um gráfico de "sangramento"
            meses = 6
            # Fórmula da taxa composta inversa: (1 - Queda)^(1/6) - 1
            fator_queda = 1 - (1 + queda_total) ** (1/meses)
            
            valores = [patrimonio_atual]
            curr = patrimonio_atual
            for _ in range(meses):
                curr = curr * (1 - fator_queda)
                valores.append(curr)
            dados_grafico[nome_cenario] = valores
        return dados_grafico