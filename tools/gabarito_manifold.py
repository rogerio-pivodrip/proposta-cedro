#!/usr/bin/env python3
"""Levanta o gabarito do manifold a partir do proprio catalogo.

O manifold nao tem cota nova - todos sao um tubo reto. O que muda e a
TOPOLOGIA: quantos bocais sobem do corpo, de que tamanho, e quantas luvas de
ventosa. E o codigo D do nome e o desenho do barrilete, ou seja: o codigo
deveria fixar a topologia.

Este script pergunta se fixa mesmo. Le a topologia de cada descricao
(motor/manifold.py), agrupa por codigo D, e mostra a moda de cada um com quem
discorda dela. Onde o codigo manda, ele vira reserva para o item cuja descricao
veio truncada - e a lista tem descricao truncada, como
`MNFD AZ D09 20"X4,75X2050MM FL FL12"FL8"`, que perde o comeco da conta.

O que ele mostrou na primeira rodada:

  D03 D04 D05 D06 D07 D11 D12   zero bocal, em 100% dos itens
  D08                           um bocal, em 100%
  D09                           dois, em 34 de 43
  D10 D13 D20                   variam de verdade - a descricao e que manda

E foi por causa disto que o desenho parou de por dois bocais por padrao.

Uso: python3 tools/gabarito_manifold.py [> data/gabarito_manifold.csv]
"""
import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor import manifold  # noqa: E402

CATALOGO = "data/catalogo.json"


def carregar():
    with open(CATALOGO, encoding="utf-8") as fh:
        dados = json.load(fh)
    itens = dados["itens"] if isinstance(dados, dict) else dados
    return [i for i in itens if i.get("familia") == "MANIFOLD"]


def main():
    itens = carregar()
    por = collections.defaultdict(list)
    for item in itens:
        bocais, luvas = manifold.topologia(item["descricao"])
        por[item.get("manifold") or "?"].append(
            (manifold.quantos(bocais), manifold.quantos(luvas), item))

    escritor = csv.DictWriter(sys.stdout,
                              ["codigo", "bocais", "luvas", "itens",
                               "concordam", "exemplo", "fonte"])
    escritor.writeheader()
    duvidosos = []
    for codigo in sorted(por):
        linhas = por[codigo]
        contagem = collections.Counter((b, l) for b, l, _ in linhas)
        (bocais, luvas), quantos = contagem.most_common(1)[0]
        escritor.writerow({
            "codigo": codigo, "bocais": bocais, "luvas": luvas,
            "itens": len(linhas), "concordam": quantos,
            "exemplo": linhas[0][2]["descricao"],
            "fonte": "moda das descricoes do proprio catalogo"})
        for b, l, item in linhas:
            if (b, l) != (bocais, luvas):
                duvidosos.append((codigo, bocais, luvas, b, l, item))

    print(f"# {len(itens)} manifolds em {len(por)} codigos", file=sys.stderr)
    firmes = [c for c in por
              if len({(b, l) for b, l, _ in por[c]}) == 1]
    print(f"# {len(firmes)} codigos com topologia unica: {' '.join(sorted(firmes))}",
          file=sys.stderr)
    print(f"# {len(duvidosos)} itens discordam da moda do proprio codigo:",
          file=sys.stderr)
    for codigo, bm, lm, b, l, item in duvidosos:
        print(f"#   {codigo} diz {bm}b/{lm}lv, este diz {b}b/{l}lv: "
              f'{item["descricao"]}', file=sys.stderr)


if __name__ == "__main__":
    main()
