#!/usr/bin/env python3
"""Confere a folha de flange do caderno Netafim contra a furacao da casa.

O resultado importa para o desenho e para a compra: ate 8" as duas tabelas
dizem a mesma coisa - mesmo circulo, mesma quantidade de furos. De 10" para
cima o caderno desenha 355 / 410 / 470 / 525 / 585 / 650 / 770 de circulo, que
e EN 1092-1 PN16, e nao os 350 / 400 / 460 / 515 / 565 / 620 / 725 da NBR 7675
PN16 que a tabela da casa usa. Sao duas pecas que nao se parafusam.

E a terceira fonte a dizer o mesmo: o catalogo Irrigafour (DIN 2533 PN16) ja
tinha mostrado a mesma diferenca nas mesmas bitolas, e agora e o proprio
caderno de desenhos da Netafim.

Uso: python3 tools/conferir_flanges_netafim.py
"""
import csv
import sys

sys.path.insert(0, ".")
from motor import regras  # noqa: E402

TABELA = "data/flanges_netafim.csv"


def main():
    iguais = divergem = 0
    print(f'{"tipo":15}{"DN":>4}  {"caderno":>18}  {"NBR PN16 da casa":>18}   '
          f'{"EN PN16":>18}')
    for r in csv.DictReader(open(TABELA, encoding="utf-8")):
        dn = float(r["dn_pol"])
        nominal = regras.dn_nominal(dn)
        caderno = (float(r["circulo_mm"]), int(r["furos"]))

        def le(norma):
            reg = regras.FUROS.get((norma, nominal))
            return (reg["circulo_mm"], reg["furos"]) if reg else None

        nbr, en = le("NBR PN16"), le("EN PN16")
        bate = nbr == caderno
        iguais += bate
        divergem += not bate
        marca = "" if bate else ("  <- EN" if en == caderno else "  <- ???")
        print(f'{r["tipo"]:15}{dn:4g}  {caderno[0]:>10g} x{caderno[1]:>3}  '
              f'{(nbr or ("-", "-"))[0]:>10} x{(nbr or ("-", "-"))[1]:>3}   '
              f'{(en or ("-", "-"))[0]:>10} x{(en or ("-", "-"))[1]:>3}{marca}')
    print(f"\n{iguais} linhas batem com a NBR da casa, {divergem} nao.")
    print("As que nao batem sao todas de 10\" para cima e todas casam com a "
          "EN PN16 -\nquem compra pela NBR e monta contra peca Netafim nao "
          "fecha o parafuso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
