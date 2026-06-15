# -*- coding: utf-8 -*-
"""
Padronizador de Numeracao de Pecas  ->  PREFIXO-NUMERO-METODO  (ex.: ALM-1234567-USI)

Regras:
  - O numero (7 digitos) e aleatorio e irrepetivel.
  - A numeracao so pode se repetir se PREFIXO ou METODO mudar.
    => A unicidade e verificada sobre o CODIGO COMPLETO (string inteira).
  - Antes de liberar um codigo, a ferramenta confirma que ele ainda nao existe.

Fonte de verdade da unicidade (funcao `numero_existe`):
  - Por padrao usa um REGISTRO LOCAL em SQLite (confiavel para o que esta ferramenta emite).
  - Ha um gancho pronto (CHECAR_NO_PDM) para consultar o banco do Alibre PDM diretamente.
    Ajuste a conexao/consulta conforme o engine do seu Safe (ver funcao `existe_no_pdm`).

Requisitos: Python 3.8+  (tkinter e sqlite3 ja vem na instalacao padrao).
"""

import os
import random
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

# ============================================================
#  CONFIGURACAO  -- ajuste estas listas/valores ao seu padrao
# ============================================================

PREFIXOS = ["ALM", "FAB", "MON", "COM"]          # prefixos disponiveis (editavel pelo usuario)
METODOS  = ["MAC", "CUT", "CST", "INJ", "PRT", "OEM", "ASM", "WLD", "BND"]  # metodos de manufatura
N_DIGITOS = 7                                    # quantidade de digitos do numero
MAX_TENTATIVAS = 1000                            # tentativas para achar numero livre

# Caminho do registro local. Coloque em um local COMPARTILHADO (rede do PDM)
# para que todos os usuarios validem contra o mesmo registro.
REGISTRO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "numeracao_pecas.db")

# Ligue para tambem consultar o banco do Alibre PDM (ver existe_no_pdm()).
CHECAR_NO_PDM = False


# ============================================================
#  CAMADA DE UNICIDADE
# ============================================================

def _init_registro():
    con = sqlite3.connect(REGISTRO_DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS pecas ("
        "  codigo  TEXT PRIMARY KEY,"
        "  prefixo TEXT,"
        "  numero  TEXT,"
        "  metodo  TEXT,"
        "  criado_em TEXT DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    con.commit()
    return con


def existe_no_registro(con, codigo):
    cur = con.execute("SELECT 1 FROM pecas WHERE codigo = ? LIMIT 1", (codigo,))
    return cur.fetchone() is not None


def existe_no_pdm(codigo):
    """
    GANCHO PARA O ALIBRE PDM.
    Retorne True se `codigo` ja existir como propriedade de alguma peca no PDM.

    O Alibre PDM nao expoe publicamente o esquema do Safe, entao confirme no seu
    ambiente QUAL engine e usado e ONDE o numero da peca fica gravado (uma
    propriedade/Class do PDM). Dois exemplos de implementacao:

    --- Exemplo A: backend Microsoft SQL Server (via pyodbc) ---
    # import pyodbc
    # cn = pyodbc.connect(
    #     "DRIVER={ODBC Driver 17 for SQL Server};"
    #     "SERVER=NOME_DO_SERVIDOR;DATABASE=NOME_DO_VAULT;Trusted_Connection=yes;"
    # )
    # cur = cn.cursor()
    # cur.execute("SELECT TOP 1 1 FROM <tabela_propriedades> "
    #             "WHERE <coluna_valor> = ?", codigo)
    # achou = cur.fetchone() is not None
    # cn.close()
    # return achou

    --- Exemplo B: backend Firebird (via fdb) ---
    # import fdb
    # cn = fdb.connect(dsn="servidor:/caminho/vault.fdb", user="...", password="...")
    # cur = cn.cursor()
    # cur.execute("SELECT FIRST 1 1 FROM <tabela> WHERE <coluna> = ?", (codigo,))
    # achou = cur.fetchone() is not None
    # cn.close()
    # return achou

    Enquanto nao configurado, retorna False (sem bloquear o fluxo).
    """
    return False


def numero_existe(con, codigo):
    """Ponto unico de verificacao de unicidade."""
    if existe_no_registro(con, codigo):
        return True
    if CHECAR_NO_PDM and existe_no_pdm(codigo):
        return True
    return False


def gerar_codigo_unico(con, prefixo, metodo):
    """Gera PREFIXO-NUMERO-METODO garantindo que o codigo completo seja inedito."""
    for _ in range(MAX_TENTATIVAS):
        numero = "".join(str(random.randint(0, 9)) for _ in range(N_DIGITOS))
        codigo = "{}-{}-{}".format(prefixo, numero, metodo)
        if not numero_existe(con, codigo):
            return codigo, numero
    raise RuntimeError("Nao foi possivel achar um numero livre apos varias tentativas.")


def registrar(con, codigo, prefixo, numero, metodo):
    con.execute(
        "INSERT INTO pecas (codigo, prefixo, numero, metodo) VALUES (?,?,?,?)",
        (codigo, prefixo, numero, metodo),
    )
    con.commit()


# ============================================================
#  GUI MINIMA
# ============================================================

class App(tk.Tk):
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.codigo_atual = None
        self.partes = None

        self.title("Numeracao de Pecas")
        self.resizable(False, False)
        pad = {"padx": 8, "pady": 6}

        ttk.Label(self, text="Prefixo").grid(row=0, column=0, sticky="w", **pad)
        self.cb_prefixo = ttk.Combobox(self, values=PREFIXOS, state="readonly", width=10)
        self.cb_prefixo.current(0)
        self.cb_prefixo.grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(self, text="Metodo").grid(row=1, column=0, sticky="w", **pad)
        self.cb_metodo = ttk.Combobox(self, values=METODOS, state="readonly", width=10)
        self.cb_metodo.current(0)
        self.cb_metodo.grid(row=1, column=1, sticky="w", **pad)

        ttk.Button(self, text="Gerar codigo", command=self.gerar).grid(
            row=2, column=0, columnspan=2, sticky="ew", **pad
        )

        self.var_codigo = tk.StringVar(value="")
        ent = ttk.Entry(self, textvariable=self.var_codigo, state="readonly",
                        justify="center", font=("Consolas", 14), width=22)
        ent.grid(row=3, column=0, columnspan=2, **pad)

        botoes = ttk.Frame(self)
        botoes.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Button(botoes, text="Copiar", command=self.copiar).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(botoes, text="Reservar", command=self.reservar).pack(side="left", expand=True, fill="x", padx=2)

        self.var_status = tk.StringVar(value="Pronto.")
        ttk.Label(self, textvariable=self.var_status, foreground="#555").grid(
            row=5, column=0, columnspan=2, sticky="w", **pad
        )

    def gerar(self):
        prefixo = self.cb_prefixo.get()
        metodo = self.cb_metodo.get()
        try:
            codigo, numero = gerar_codigo_unico(self.con, prefixo, metodo)
        except RuntimeError as e:
            messagebox.showerror("Erro", str(e))
            return
        self.codigo_atual = codigo
        self.partes = (prefixo, numero, metodo)
        self.var_codigo.set(codigo)
        self.var_status.set("Codigo gerado (ainda nao reservado).")

    def copiar(self):
        if not self.codigo_atual:
            return
        self.clipboard_clear()
        self.clipboard_append(self.codigo_atual)
        self.var_status.set("Copiado para a area de transferencia.")

    def reservar(self):
        if not self.codigo_atual:
            return
        # Re-checa no momento de gravar (evita corrida entre usuarios)
        if numero_existe(self.con, self.codigo_atual):
            self.var_status.set("Ja existe! Gere um novo codigo.")
            messagebox.showwarning("Conflito", "Esse codigo passou a existir. Gere outro.")
            return
        prefixo, numero, metodo = self.partes
        registrar(self.con, self.codigo_atual, prefixo, numero, metodo)
        self.var_status.set("Reservado: {}".format(self.codigo_atual))


def main():
    con = _init_registro()
    App(con).mainloop()
    con.close()


if __name__ == "__main__":
    main()