"""Traduz o nome de peca do desenho para o vocabulario do catalogo.

Duas conversoes, ambas em tabela para vocês editarem sem tocar em codigo:
 - de-para de nomes (data/depara_nomes.csv)
 - polegada -> milimetro para PVC/PEAD, que o desenho chama de 6" e o catalogo
   de 160 mm.
"""
import csv
import os
import re
import unicodedata

from .bitola import METRICO, POLEGADA

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPARA = os.path.join(RAIZ, "data", "depara_nomes.csv")

# Equivalencia comercial polegada -> mm usada em PVC/PEAD.
#
# A tabela nao mora mais aqui: ela e uma projecao de motor/bitola.py, que e a
# unica tabela de conversao do programa. Estava copiada em quatro lugares, e
# copia e onde a divergencia mora - ver o cabecalho de bitola.py.
POLEGADA_MM = {POLEGADA[dn]: externo for dn, externo in METRICO.items()
               if dn in POLEGADA}


def sem_acento(txt):
    normal = unicodedata.normalize("NFD", txt)
    return "".join(c for c in normal if not unicodedata.combining(c))


def carregar_regras(caminho=DEPARA):
    with open(caminho, encoding="utf-8") as fh:
        linhas = [ln for ln in fh if not ln.startswith("#")]
    return [(re.compile(r["regex"], re.I), r["destino"])
            for r in csv.DictReader(linhas)]


REGRAS = carregar_regras()


def traduzir(nome):
    """Nome do desenho -> nome no vocabulario do catalogo (ou o proprio nome)."""
    alvo = sem_acento(nome).upper()
    for rx, destino in REGRAS:
        novo, n = rx.subn(destino, alvo)
        if n:
            return novo
    return nome


def polegada_para_mm(dn_pol):
    return POLEGADA_MM.get(dn_pol)
