#!/usr/bin/env python3
"""Quantos codigos do catalogo o desenho ja cobre, e o que falta para o resto.

Tenta desenhar cada item do catalogo. Nao conta familia coberta: conta CODIGO
que sai desenhado, que e a pergunta que importa quando alguem escolhe uma peca
na lista e espera ver o desenho.

A regra de catalogo -> simbolo mora em motor/desenho.py, nao aqui: e a mesma
que o exportador de DXF usa para nomear o bloco com o codigo SAP.

Uso: python3 tools/conferir_cobertura.py
"""
import collections
import json
import sys

sys.path.insert(0, ".")
from motor import desenho  # noqa: E402

CATALOGO = "data/catalogo.json"


def main():
    itens = json.load(open(CATALOGO, encoding="utf-8"))
    ok, motivos = collections.Counter(), collections.Counter()
    for item in itens:
        try:
            desenho.de_item(item)
            ok[item["familia"]] += 1
        except Exception as erro:
            motivos[f'{item["familia"]}: {erro}'] += 1

    print(f"{sum(ok.values())} de {len(itens)} codigos do catalogo saem "
          f"desenhados hoje\n")
    for familia, n in sorted(ok.items(), key=lambda kv: -kv[1]):
        print(f"{n:5d}  {familia}")
    print("\n-- o que ainda nao sai, por motivo --")
    for motivo, n in motivos.most_common(14):
        print(f"{n:5d}  {motivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
