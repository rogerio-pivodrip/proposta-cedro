#!/usr/bin/env python3
"""Compatibiliza a bomba com a norma da reducao.

O motor ja sabe o DN dos bocais pela nomenclatura. Falta a norma: a reducao tem
uma ponta em NBR PN16, do lado da linha, e a outra na norma do equipamento.
Enquanto data/bombas_norma.csv nao estiver preenchida, este relatorio mostra o
cardapio - que reducoes existem em cada bocal, em cada norma.

Uso: python3 tools/compatibilizar_bomba.py ["MODELO DA BOMBA"]
"""
import collections
import csv
import json
import os
import sys

sys.path.insert(0, ".")
from motor.bomba import MM_PARA_POLEGADA, RX_FAMILIA, entrada_presumida, interpretar

CATALOGO = "data/catalogo.json"
NORMAS_BOMBA = "data/bombas_norma.csv"
NORMA_LINHA = "NBR PN16"


def carregar_normas():
    if not os.path.exists(NORMAS_BOMBA):
        return {}
    with open(NORMAS_BOMBA, encoding="utf-8") as fh:
        linhas = [ln for ln in fh if not ln.startswith("#")]
    tabela = {}
    for reg in csv.DictReader(linhas):
        if reg["norma_entrada"] or reg["norma_saida"]:
            chave = (reg["familia"].upper(), reg["dn_mm"] or None)
            tabela[chave] = (reg["norma_entrada"], reg["norma_saida"])
    return tabela


def cardapio(catalogo):
    """DN em polegada -> normas de reducao disponiveis do lado do equipamento."""
    menu = collections.defaultdict(collections.Counter)
    for item in catalogo:
        if item["familia"] not in ("REDUCAO_CONCENTRICA", "REDUCAO_EXCENTRICA"):
            continue
        normas = {c["norma"] for c in item["conexoes"] if c["norma"]}
        if NORMA_LINHA not in normas:
            continue
        for con in item["conexoes"]:
            if con["norma"] and con["norma"] != NORMA_LINHA and con["dn"]:
                menu[con["dn"]][con["norma"]] += 1
    return menu


def relatar(modelo, catalogo, menu, normas):
    bomba = interpretar(modelo)
    if not bomba:
        print(f"nao reconheci a nomenclatura de {modelo}")
        return
    familia = RX_FAMILIA.search(modelo.upper()).group(1).upper()
    entrada = bomba["entrada_mm"] or entrada_presumida(bomba["saida_mm"])[0]
    declarado = normas.get((familia, None))

    print(f"\n== {modelo} ==")
    presumida = "" if bomba["entrada_mm"] else "  (presumida)"
    for rotulo, mm, idx in (("entrada", entrada, 0), ("saida", bomba["saida_mm"], 1)):
        pol = MM_PARA_POLEGADA.get(mm)
        norma = declarado[idx] if declarado and declarado[idx] else None
        cab = f'  {rotulo:8s} {mm} mm ({pol}")' + (presumida if rotulo == "entrada" else "")
        if norma:
            print(f"{cab}  ->  {norma}, pela tabela da familia {familia}")
            continue
        opcoes = menu.get(pol)
        if not opcoes:
            print(f"{cab}  ->  nao ha reducao nesse DN fora da NBR PN16")
            continue
        lista = ", ".join(f"{n} ({q})" for n, q in opcoes.most_common(6))
        print(f"{cab}  ->  {lista}")
    if not declarado:
        print(f"  ! familia {familia} sem norma cadastrada em {NORMAS_BOMBA}")


def main():
    catalogo = json.load(open(CATALOGO, encoding="utf-8"))
    menu = cardapio(catalogo)
    normas = carregar_normas()
    modelos = sys.argv[1:] or ["METB 050-32-200 - 15cv - MONO",
                               "METB 125-80-315 - 40cv",
                               "IMBIL INIB 150-250 40CV"]
    for modelo in modelos:
        relatar(modelo, catalogo, menu, normas)


if __name__ == "__main__":
    main()
