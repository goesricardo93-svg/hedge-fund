import numpy as np
from scipy.stats import norm
import pandas as pd
import datetime

class BlackScholes:
    def __init__(self, S, K, T, r, sigma, tipo="call"):
        """
        S: Preço do Ativo Objeto (Spot)
        K: Strike (Exercício)
        T: Tempo até vencimento (em anos)
        r: Taxa livre de risco (Selic anual / 100)
        sigma: Volatilidade Implícita (anual)
        tipo: 'call' ou 'put'
        """
        self.S = float(S)
        self.K = float(K)
        self.T = float(T)
        self.r = float(r)
        self.sigma = float(sigma)
        self.tipo = tipo.lower()

    def _d1_d2(self):
        d1 = (np.log(self.S / self.K) + (self.r + 0.5 * self.sigma ** 2) * self.T) / (self.sigma * np.sqrt(self.T))
        d2 = d1 - self.sigma * np.sqrt(self.T)
        return d1, d2

    def calcular_preco(self):
        d1, d2 = self._d1_d2()
        if self.tipo == "call":
            price = self.S * norm.cdf(d1) - self.K * np.exp(-self.r * self.T) * norm.cdf(d2)
        else:
            price = self.K * np.exp(-self.r * self.T) * norm.cdf(-d2) - self.S * norm.cdf(-d1)
        return price

    def calcular_gregas(self):
        d1, d2 = self._d1_d2()
        
        # Delta
        if self.tipo == "call":
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
            
        # Gamma (Igual para Call e Put)
        gamma = norm.pdf(d1) / (self.S * self.sigma * np.sqrt(self.T))
        
        # Vega (Sensibilidade à Volatilidade - Igual para Call e Put)
        # Dividido por 100 para representar mudança de 1% na Vol
        vega = (self.S * norm.pdf(d1) * np.sqrt(self.T)) / 100
        
        # Theta (Decaimento temporal)
        if self.tipo == "call":
            theta = (- (self.S * norm.pdf(d1) * self.sigma) / (2 * np.sqrt(self.T)) 
                     - self.r * self.K * np.exp(-self.r * self.T) * norm.cdf(d2))
        else:
            theta = (- (self.S * norm.pdf(d1) * self.sigma) / (2 * np.sqrt(self.T)) 
                     + self.r * self.K * np.exp(-self.r * self.T) * norm.cdf(-d2))
        # Theta por dia (aprox)
        theta = theta / 365 

        return {
            "Delta": delta,
            "Gamma": gamma,
            "Vega": vega,
            "Theta": theta
        }

    def gerar_payoff(self, range_pct=0.2):
        """Gera dados para gráfico de Lucro/Prejuízo no vencimento"""
        precos = np.linspace(self.S * (1 - range_pct), self.S * (1 + range_pct), 100)
        payoffs = []
        custo = self.calcular_preco()
        
        for p in precos:
            if self.tipo == "call":
                valor_intrinsico = max(0, p - self.K)
            else:
                valor_intrinsico = max(0, self.K - p)
            
            # Lucro = Valor no Vencimento - Custo Inicial
            payoffs.append(valor_intrinsico - custo)
            
        return precos, np.array(payoffs)