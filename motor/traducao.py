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

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPARA = os.path.join(RAIZ, "data", "depara_nomes.csv")

# Equivalencia comercial polegada -> mm usada em PVC/PEAD.
POLEGADA_MM = {2: 63, 2.5: 75, 3: 90, 4: 110, 5: 140, 6: 160, 8: 225,
               10: 280, 12: 315, 14: 355}


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
