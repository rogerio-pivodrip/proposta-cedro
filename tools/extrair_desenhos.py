#!/usr/bin/env python3
"""Extrai as tabelas dimensionais do caderno de desenhos Netafim.

Cada pagina do caderno traz uma peca com sua tabela parametrica: diametro,
cotas, espessura, tipo das pontas e o codigo Netafim - ou "CADASTRAR", que e
como a propria Netafim marca o que ainda nao tem codigo.

E dai que sai a cota face a face, que a vista lateral precisa e que a descricao
do item nao tem.

Uso: python3 tools/extrair_desenhos.py [pdf] > data/desenhos_netafim.csv
"""
import csv
import re
import sys
import types

sys.modules.setdefault("cryptography", types.ModuleType("cryptography"))
from pypdf import PdfReader  # noqa: E402

PADRAO = "data/fichas/NETAFIM_desenhos_tubos_conexoes_aco_PN16_rev20.pdf"
RX_LINHA = re.compile(r"^(\d{2,3})\s*\[\s*(\d{1,2})\s*\"\s*\]\s*(.*)$")
RX_SAP = re.compile(r"\b(\d{5}-\d{6})\b")
RX_TITULO = re.compile(r"Dimensional padrao p/ construcao de (.+?)(?:\s{2,}|$)",
                       re.I)


# Linha em que a tipografia saiu letra a letra: "1 5 2  [6 " ]  2 5 0".
RX_ESPACADA = re.compile(r'^\d(\s\d)+\s*\[')


def desespacar(linha):
    """So mexe na linha que saiu caractere a caractere.

    Nela, um espaco simples entre alfanumericos e artefato de tipografia e o
    separador de coluna sao dois ou mais espacos. Na linha normal, mexer seria
    grudar colunas - "70 4,75" viraria "704,75".
    """
    linha = re.sub(r'\s*\[\s*', ' [', linha)
    linha = re.sub(r'\s*"\s*\]', '"]', linha)
    if not RX_ESPACADA.match(linha):
        return linha
    partes = re.split(r'\s{2,}', linha)
    return "  ".join(re.sub(r'(?<=[\w,.°])\s(?=[\w,.°])', '', p)
                     for p in partes)


def titulo_da_pagina(texto):
    sem_acento = (texto.replace("ç", "c").replace("ã", "a").replace("ô", "o")
                  .replace("é", "e").replace("ê", "e").replace("í", "i"))
    m = RX_TITULO.search(sem_acento)
    if m:
        return " ".join(m.group(1).split())[:70]
    for linha in texto.splitlines():
        if "Dimensional" in linha:
            return " ".join(linha.split())[:70]
    return ""


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else PADRAO
    leitor = PdfReader(caminho)
    escritor = csv.writer(sys.stdout)
    escritor.writerow(["pagina", "peca", "dn_mm", "dn_pol", "cotas",
                       "sap", "situacao"])
    linhas = faltando = 0
    for numero, pagina in enumerate(leitor.pages, 1):
        texto = pagina.extract_text() or ""
        peca = titulo_da_pagina(texto)
        for bruta in texto.splitlines():
            linha = desespacar(bruta.strip())
            m = RX_LINHA.match(linha)
            if not m:
                continue
            resto = m.group(3)
            sap = RX_SAP.search(resto)
            situacao = "cadastrado"
            if sap:
                codigo = sap.group(1)
                resto = resto[:sap.start()].strip()
            elif re.search(r"CADASTRAR|sem cadastro", resto, re.I):
                codigo, situacao = "", "CADASTRAR"
                resto = re.sub(r"CADASTRAR|sem cadastro", "", resto,
                               flags=re.I).strip()
                faltando += 1
            else:
                codigo, situacao = "", "indefinido"
            escritor.writerow([numero, peca, m.group(1), m.group(2),
                               " ".join(resto.split()), codigo, situacao])
            linhas += 1
    print(f"# {linhas} linhas, {faltando} marcadas CADASTRAR", file=sys.stderr)


if __name__ == "__main__":
    main()
