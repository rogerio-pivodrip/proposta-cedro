#!/usr/bin/env python3
"""Tabela de dimensoes da KSB Megabloc, transcrita do manual tecnico.

A bomba e a ancora do desenho: tudo se posiciona em relacao a ela, e a altura
do eixo decide onde a succao entra. Ate agora o motor sabia o DN dos bocais
pela nomenclatura e nao sabia onde eles ficam.

Fonte: KSB Bombas Hidraulicas, Manual Tecnico Megabloc, folheto A2744.12P/2,
       tabelas de dimensoes IV polos (1750 rpm) e II polos (3500 rpm), 60 Hz.
       data/fichas/KSB_megabloc_manual_tecnico.pdf

Letras do desenho, as que nao mudam com o motor:
  a  do eixo da descarga a face do flange de succao (horizontal)
  b  da base ao eixo da bomba
  c  do eixo da descarga a face do flange de descarga

As demais (h, l, m1, m2, n1, n2, q, r1, t1, t2, w) mudam com a potencia do
motor e estao na ficha - nao transcritas aqui.

Flange: ANSI B16.1 125# FF, exceto os tamanhos marcados (1) no catalogo, que
sao ANSI B16.1 250# FF.

Uso: python3 tools/bombas_ksb.py > data/bombas_ksb_megabloc.csv
"""
import csv
import sys

ANSI250 = {"32-250", "32-250.1", "40-250", "50-250", "50-315", "65-250", "80-250"}

# polos, tamanho, DN succao (pol), DN descarga (pol), a, b, c
IV_POLOS = [
    ("32-200.1", 2,    1.25, 180, 160,  80),
    ("32-200",   2,    1.25, 180, 160,  80),
    ("32-250.1", 2,    1.25, 225, 180, 100),
    ("32-250",   2,    1.25, 225, 180, 100),
    ("40-160",   2.5,  1.5,  160, 132,  80),
    ("40-200",   2.5,  1.5,  180, 160, 100),
    ("40-250",   2.5,  1.5,  225, 180, 100),
    ("50-125",   3,    2,    160, 132, 100),
    ("50-160",   3,    2,    180, 160, 100),
    ("50-200",   3,    2,    200, 160, 100),
    ("50-250",   3,    2,    228, 180, 125),
    ("50-315",   3,    2,    280, 225, 125),
    ("65-125",   4,    2.5,  180, 160, 100),
    ("65-160",   4,    2.5,  200, 160, 100),
    ("65-200",   4,    2.5,  225, 180, 100),
    ("65-250",   4,    2.5,  250, 200, 125),
    ("65-315",   4,    2.5,  280, 225, 125),
    ("80-160",   5,    3,    225, 180, 125),
    ("80-200",   5,    3,    250, 180, 125),
    ("80-250",   5,    3,    280, 225, 125),
    ("80-315",   5,    3,    315, 250, 125),
    ("100-200",  5,    4,    280, 200, 125),
    ("100-250",  5,    4,    280, 225, 140),
    ("100-315",  5,    4,    315, 250, 140),
    ("125-200",  6,    5,    315, 250, 140),
    ("125-250",  6,    5,    335, 250, 140),
    ("150-200",  8,    6,    400, 280, 160),
    ("150-250",  8,    6,    375, 280, 160),
]
# II polos: a tabela tem a e a1 (rosca e flange). Aqui so os bocais - as
# dimensoes ficam para quando a casa usar bomba de 3500 rpm.
II_POLOS_BOCAIS = [
    ("25-150",   1.25, 1),
    ("25-200",   1.5,  1),
    ("32-125",   2,    1.25), ("32-125.1", 2, 1.25),
    ("32-160",   2,    1.25), ("32-160.1", 2, 1.25),
    ("32-200",   2,    1.25), ("32-200.1", 2, 1.25),
    ("32-250",   2,    1.25), ("32-250.1", 2, 1.25),
    ("40-125",   2.5,  1.5), ("40-160", 2.5, 1.5),
    ("40-200",   2.5,  1.5), ("40-250", 2.5, 1.5),
    ("50-125",   3,    2), ("50-160", 3, 2), ("50-200", 3, 2),
    ("65-125",   4,    2.5), ("65-160", 4, 2.5), ("65-200", 4, 2.5),
]
FONTE = "KSB Megabloc manual tecnico A2744.12P/2, 60Hz"


def norma(tamanho):
    return "ANSI 250" if tamanho in ANSI250 else "ANSI 125"


def main():
    escritor = csv.writer(sys.stdout)
    escritor.writerow(["tamanho", "polos", "dn_succao_pol", "dn_recalque_pol",
                       "a_mm", "b_mm", "c_mm", "norma_flange", "fonte"])
    for tamanho, succao, recalque, a, b, c in IV_POLOS:
        escritor.writerow([tamanho, 4, f"{succao:g}", f"{recalque:g}",
                           a, b, c, norma(tamanho), FONTE])
    for tamanho, succao, recalque in II_POLOS_BOCAIS:
        escritor.writerow([tamanho, 2, f"{succao:g}", f"{recalque:g}",
                           "", "", "", norma(tamanho), FONTE])
    print(f"# {len(IV_POLOS)} tamanhos com dimensao (IV polos) + "
          f"{len(II_POLOS_BOCAIS)} so com bocais (II polos)", file=sys.stderr)


if __name__ == "__main__":
    main()
