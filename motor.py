import pandas as pd
import numpy as np

class MotorAnalise:
    def __init__(self):
        self.p_curto = 14
        self.p_longo = 252

    def calcular_rsi(self, serie, window):
        delta = serie.diff()
        ganho = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        perda = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = ganho / perda
        return 100 - (100 / (1 + rs))

    def processar_df(self, df):
        # Garante que os dados estão em ordem cronológica
        df = df.sort_index()
        
        # Médias Móveis
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma252'] = df['close'].rolling(window=self.p_longo).mean()

        # RSIs
        df['rsi_14'] = self.calcular_rsi(df['close'], self.p_curto)
        df['rsi_252'] = self.calcular_rsi(df['close'], self.p_longo)
        
        # Identificação de Topos e Fundos para Divergência
        df['topo'] = (df['close'] > df['close'].shift(1)) & (df['close'] > df['close'].shift(-1))
        df['fundo'] = (df['close'] < df['close'].shift(1)) & (df['close'] < df['close'].shift(-1))
        
        return df

    def detectar_divergencia(self, df):
        indices_topos = df.index[df['topo']].tolist()
        if len(indices_topos) < 2: return "NEUTRO"

        # Últimos dois topos para análise macro (252p)
        t1, t2 = indices_topos[-2], indices_topos[-1]
        
        preco_subiu = df['close'].iloc[t2] > df['close'].iloc[t1]
        rsi_caiu = df['rsi_252'].iloc[t2] < df['rsi_252'].iloc[t1]

        if preco_subiu and rsi_caiu and df['rsi_252'].iloc[t2] > 50:
            return "BAIXA MACRO (Divergência)"
        
        # Tendência simples por Média
        if df['close'].iloc[-1] > df['ma252'].iloc[-1]:
            return "ALTA (Acima da MA252)"
        
        return "TENDÊNCIA DE BAIXA"

    def analisar(self, dados_brutos):
        df = self.processar_df(dados_brutos)
        if len(df) < self.p_longo:
            return {"status": "Dados Insuficientes (Mín. 252 dias)"}
        
        return {
            "preco": round(df['close'].iloc[-1], 2),
            "rsi_252": round(df['rsi_252'].iloc[-1], 2),
            "ma252": round(df['ma252'].iloc[-1], 2),
            "sinal": self.detectar_divergencia(df)
        }