"""Quanto uma peca mede - a unica porta por onde o motor pergunta isso.

A cota nao esta no codigo SAP: esta numa tabela por (fabricante, familia,
variante, bitola). A casa compra dos dois fornecedores e a furacao dos dois
bate, entao qualquer peca de um monta na outra - mas nenhuma tem a mesma cota,
e cota diferente muda o desenho. Por isso o fabricante e parametro, com um
padrao declarado.

  cota("REDUCAO_CONCENTRICA", 8)              -> 150.0   (Irrigafour, o padrao)
  cota("REDUCAO_CONCENTRICA", 8, fonte="NETAFIM") -> 300.0
  cota("CURVA", 8, variante="90", significado="perna_mm") -> 335.0
"""
import csv
import os

PADRAO = "IRRIGAFOUR"
TABELA = os.path.join(os.path.dirname(__file__), "..", "data", "cotas.csv")

_indice = None


def _carregar():
    global _indice
    if _indice is not None:
        return _indice
    _indice = {}
    with open(TABELA, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            chave = (r["fonte"], r["familia"], r["variante"],
                     float(r["dn_pol"]),
                     float(r["dn_menor_pol"]) if r["dn_menor_pol"] else None,
                     r["significado"])
            _indice[chave] = float(r["valor_mm"])
    return _indice


def fontes():
    return sorted({k[0] for k in _carregar()})


def cota_com_fonte(familia, dn_pol, variante="", significado="face_a_face_mm",
                   fonte=None, dn_menor_pol=None):
    """Devolve (valor, fonte_usada). Cai para o outro fabricante se o padrao
    nao tiver a peca - e diz de quem veio, para o desenho poder avisar.

    dn_menor_pol so importa na reducao, onde a cota depende do par: a
    excentrica de 8" mede 200 contra 6" e 300 contra 3".
    """
    indice = _carregar()
    if dn_pol is None:
        return None, None
    preferida = fonte or PADRAO
    ordem = [preferida] + [f for f in fontes() if f != preferida]
    menores = [dn_menor_pol, None] if dn_menor_pol is not None else [None]
    for f in ordem:
        for menor in menores:
            chave = (f, familia, variante, float(dn_pol),
                     float(menor) if menor is not None else None, significado)
            valor = indice.get(chave)
            if valor is not None:
                return valor, f
    return None, None


def cota(familia, dn_pol, variante="", significado="face_a_face_mm", fonte=None,
         dn_menor_pol=None):
    return cota_com_fonte(familia, dn_pol, variante, significado, fonte,
                          dn_menor_pol)[0]
