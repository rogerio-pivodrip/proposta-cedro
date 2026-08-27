#!/usr/bin/env python3
"""Confere a leitura da Meganorm - dentro do manual e contra a lista da casa.

Tres conferencias:

1. A tabela 06 (medidas da bomba) contra a secao 15 (conjunto com motor e
   base). As quatro cotas a, f, h1 e h2 aparecem nas duas, e sao a mesma
   folha lida de dois lugares - divergir ali seria erro de leitura.

2. A Meganorm e normalizada pela EN 733 / ISO 2858, entao o nome tem que
   reproduzir o DN de recalque e o rotor sem consultar nada: 125-400 e
   recalque DN125 com rotor de 400.

3. Quantos codigos METN da lista tem cota, e quais tamanhos faltam.

Uso: python3 tools/conferir_meganorm.py
"""
import collections
import csv
import json
import re
import sys

TABELA = "data/bombas_ksb_meganorm.csv"
CONJUNTO = "data/bombas_ksb_meganorm_conjunto.csv"
CATALOGO = "data/catalogo.json"
COTAS = ("a_mm", "f_mm", "h1_mm", "h2_mm")


def ler(caminho):
    return list(csv.DictReader(open(caminho, encoding="utf-8")))


def tabela_x_conjunto(medidas, conjunto):
    print("== tabela 06 (bomba) x secao 15 (conjunto)")
    ref = {r["tamanho"]: r for r in medidas}
    conferidas = divergentes = orfas = 0
    for linha in conjunto:
        alvo = ref.get(linha["tamanho"])
        if not alvo:
            orfas += 1
            continue
        for cota in COTAS:
            if linha[cota] == alvo[cota]:
                conferidas += 1
            else:
                divergentes += 1
                print(f"  {linha['tamanho']} {cota}: secao 15 diz "
                      f"{linha[cota]}, tabela 06 diz {alvo[cota]}")
    print(f"  {conferidas} cotas conferem, {divergentes} divergem, "
          f"{orfas} linhas do conjunto sem tamanho na tabela 06")
    faltam = sorted(set(ref) - {c["tamanho"] for c in conjunto})
    if faltam:
        print(f"  tamanhos com medida mas sem conjunto: {', '.join(faltam)}")


def nome_x_norma(medidas):
    print("\n== nome do tamanho x DN de recalque e rotor (EN 733)")
    bate = erra = 0
    for r in medidas:
        recalque, rotor = r["tamanho"].split("-")
        ok = (float(recalque) == float(r["dn2_mm"])
              and rotor.split(".")[0] == r["rotor_mm"])
        bate += ok
        erra += not ok
        if not ok:
            print(f"  {r['tamanho']}: folha diz DN2 {r['dn2_mm']}, "
                  f"rotor {r['rotor_mm']}")
    print(f"  {bate} de {bate + erra} tamanhos: o nome E (DN2, rotor)")
    fora = [r["tamanho"] for r in medidas if r["iso_2858"] != "1"]
    if fora:
        print(f"  fora da ISO 2858, pela nota da folha: {', '.join(fora)}")


def lista_x_folha(medidas):
    tabela = {r["tamanho"] for r in medidas}
    itens = json.load(open(CATALOGO, encoding="utf-8"))
    metn = [i for i in itens if re.search(r"\bMETN\b", i["descricao"])]
    achou = collections.Counter()
    faltam = set()
    for item in metn:
        m = re.search(r"(\d{2,3})-(\d{2,3})-(\d{2,4})", item["descricao"])
        if m:
            chave = f"{int(m.group(2))}-{int(m.group(3))}"
        else:
            m2 = re.search(r"(\d{2,3})-(\d{2,4})(?!\d)", item["descricao"])
            chave = f"{int(m2.group(1))}-{int(m2.group(2))}" if m2 else None
        if chave in tabela:
            achou[chave] += 1
        else:
            faltam.add(chave)
    print(f"\n== lista x folha: {len(metn)} codigos METN")
    print(f"  {sum(achou.values())} tem cota na tabela de medidas, "
          f"{len(metn) - sum(achou.values())} nao")
    if faltam:
        print(f"  tamanhos citados na lista e ausentes da folha: "
              f"{', '.join(sorted(x for x in faltam if x))}")


def main():
    medidas, conjunto = ler(TABELA), ler(CONJUNTO)
    tabela_x_conjunto(medidas, conjunto)
    nome_x_norma(medidas)
    lista_x_folha(medidas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
