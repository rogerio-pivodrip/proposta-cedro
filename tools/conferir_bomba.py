#!/usr/bin/env python3
"""Confere se as reducoes do desenho casam com os bocais da bomba.

Le a lista de pecas de um projeto, acha a bomba, interpreta a nomenclatura e
compara com as reducoes que o desenho traz.

Uso: python3 tools/conferir_bomba.py [lista.csv ...]
"""
import csv
import glob
import sys

sys.path.insert(0, ".")
from motor.bomba import MM_PARA_POLEGADA, interpretar
from tools.normalizar import normalizar_item


def pol(valor):
    return f"{valor:g}\"" if valor else "?"


def conferir(caminho):
    with open(caminho, encoding="utf-8") as fh:
        itens = list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))

    bomba = nome_bomba = None
    for reg in itens:
        achado = interpretar(reg["nome_peca"])
        if achado:
            bomba, nome_bomba = achado, reg["nome_peca"]
            break

    print(f"\n== {caminho.split('/')[-1]} ==")
    if not bomba:
        print("  bomba nao identificada na lista")
        return
    print(f"  bomba: {nome_bomba}")
    if bomba["grupos"] == 3:
        print(f'  entrada {bomba["entrada_mm"]} mm ({pol(bomba["entrada_pol"])})'
              f'  ·  saida {bomba["saida_mm"]} mm ({pol(bomba["saida_pol"])})'
              f'  ·  rotor {bomba["rotor_mm"]}')
    else:
        print(f'  saida {bomba["saida_mm"]} mm ({pol(bomba["saida_pol"])})'
              f'  ·  rotor {bomba["rotor_mm"]}  ·  entrada nao declarada')

    bocais = {bomba["entrada_pol"], bomba["saida_pol"]} - {None}
    for reg in itens:
        peca = normalizar_item(reg["nome_peca"])
        if peca["familia"] not in ("REDUCAO_CONCENTRICA", "REDUCAO_EXCENTRICA"):
            continue
        dns = set(peca["dn"])
        casa = dns & bocais
        marca = "casa com a bomba" if casa else "nao toca a bomba"
        lado = ""
        if bomba["entrada_pol"] in dns:
            lado = " (entrada)"
        elif bomba["saida_pol"] in dns:
            lado = " (saida)"
        tipo = "exc" if peca["familia"].endswith("EXCENTRICA") else "con"
        print(f'    {reg["nome_peca"][:38]:38s} {tipo}  '
              f'{sorted(dns)}  ->  {marca}{lado}')


def main():
    alvos = sys.argv[1:] or sorted(glob.glob("data/projetos/*.csv"))
    for caminho in alvos:
        conferir(caminho)


if __name__ == "__main__":
    main()
