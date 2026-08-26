#!/usr/bin/env python3
"""Confronta a regra da casa com a norma, e mostra onde a norma muda na linha.

Duas perguntas que o relatorio responde:
 1. a bitola que a casa usa bate com a que a norma pede naquele DN?
 2. contra o que a linha NBR PN16 se conecta, na pratica? (a resposta esta nas
    reducoes e adaptadores que a Netafim ja estoca)
"""
import collections
import json
import sys

sys.path.insert(0, ".")
from motor import regras

NORMA_LINHA = "NBR PN16"


def comparar_bitola():
    print("== bitola: regra da casa x norma ==")
    print(f'{"DN":>6} {"DN mm":>6} {"furos":>6} {"norma pede":>12} '
          f'{"casa usa":>10}  situacao')
    for pol in (2, 2.5, 3, 4, 5, 6, 8, 10, 12, 14):
        dn_mm = regras.POLEGADA_PARA_DN[pol]
        reg = regras.FUROS.get((NORMA_LINHA, dn_mm))
        if not reg:
            continue
        casa = regras.especificacao_parafuso(pol, "AZ_AZ")["bitola_pol"]
        norma = reg["bitola_unc_pol"]
        situacao = "ok" if casa == norma else (
            f'norma pede {reg["parafuso_norma"]}, furo de {reg["furo_mm"]:.0f}mm'
        )
        print(f'{pol:>5.4g}" {dn_mm:>6} {reg["furos"]:>6} '
              f'{norma + chr(34):>12} {casa + chr(34):>10}  {situacao}')


def onde_a_norma_muda():
    catalogo = json.load(open("data/catalogo.json", encoding="utf-8"))
    print("\n== contra o que a linha NBR PN16 se conecta ==")
    for familia, titulo in (("REDUCAO_CONCENTRICA", "reducao concentrica"),
                            ("REDUCAO_EXCENTRICA", "reducao excentrica"),
                            ("ADAPTADOR", "adaptador")):
        contagem = collections.Counter()
        for item in catalogo:
            if item["familia"] != familia:
                continue
            normas = [c["norma"] for c in item["conexoes"] if c["norma"]]
            if not normas or NORMA_LINHA not in normas:
                continue
            for outra in normas:
                if outra != NORMA_LINHA:
                    contagem[outra] += 1
        total = sum(contagem.values())
        print(f'  {titulo} ({total} peças):')
        for norma, n in contagem.most_common(8):
            print(f'      {n:4d}  {norma}')


if __name__ == "__main__":
    comparar_bitola()
    onde_a_norma_muda()
