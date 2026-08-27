#!/usr/bin/env python3
"""Tabela de dimensoes da KSB Megabloc, transcrita do manual tecnico.

A bomba e a ancora do desenho: tudo se posiciona em relacao a ela, e a altura
do eixo decide onde a succao entra. Ate agora o motor sabia o DN dos bocais
pela nomenclatura e nao sabia onde eles ficam.

Fonte: KSB Bombas Hidraulicas, Manual Tecnico Megabloc, folheto A2744.12P/2,
       tabelas de dimensoes IV polos (1750 rpm) e II polos (3500 rpm), 60 Hz.
       data/fichas/KSB_megabloc_manual_tecnico.pdf

Letras do desenho, lidas na vista lateral (a mesma projecao do motor):

  a  do eixo da bomba a FACE do flange de descarga - vertical, para cima
  b  da base ao eixo da bomba - e a altura do eixo, que decide onde a
     succao entra
  c  da face do flange de succao ao EIXO do flange de descarga - horizontal

A folha de II polos chama de a1 o que a de IV polos chama de a, e traz mais
duas cotas que so existem na vista sem motor: a (eixo ao topo do flange, 20 mm
acima da face) e b1 (eixo ao pe do proprio corpo). Nao entram aqui - o que a
casa compra e IV polos.

h e l mudam com a potencia do motor: h e a carcaca IEC (90, 100, 112, 132,
160, 180, 200, 225) e l o comprimento total, da face da succao ate a tampa do
ventilador. Transcritos aqui na MENOR potencia de cada tamanho, que e o que o
desenho usa como padrao - a cauda do motor nao e cota de tubulacao.

Flange: ANSI B16.1 125# FF, exceto os tamanhos marcados (1) no catalogo, que
sao ANSI B16.1 250# FF. Ate o tamanho 65-200 os bocais podem vir rosqueados
(BSP) em vez de flangeados - nota (1) da folha de II polos.

Esta transcricao deixou de ser a fonte primaria quando o manual tecnico
A2744.0.3P/2 chegou - ele traz a mesma tabela extraivel, por potencia, com
peso e carcaca de motor. Ela FICA como segunda fonte independente: e uma
leitura a mao de outro folheto, e serve para conferir a extracao contra ela
- ver tools/conferir_bomba_ksb.py.

Uso: python3 tools/bombas_ksb.py > data/bombas_ksb_megabloc_folheto.csv
"""
import csv
import sys

ANSI250 = {"32-250", "32-250.1", "40-250", "50-250", "50-315", "65-250", "80-250"}

# tamanho, DN succao (pol), DN descarga (pol), a, b, c, h, l
# h e l sao os da menor potencia listada para o tamanho
IV_POLOS = [
    ("32-200.1", 2,    1.25, 180, 160,  80,  90, 362),
    ("32-200",   2,    1.25, 180, 160,  80,  90, 362),
    ("32-250.1", 2,    1.25, 225, 180, 100,  90, 387),
    ("32-250",   2,    1.25, 225, 180, 100,  90, 387),
    ("40-160",   2.5,  1.5,  160, 132,  80,  90, 362),
    ("40-200",   2.5,  1.5,  180, 160, 100,  90, 362),
    ("40-250",   2.5,  1.5,  225, 180, 100, 100, 412),
    ("50-125",   3,    2,    160, 132, 100,  90, 362),
    ("50-160",   3,    2,    180, 160, 100,  90, 387),
    ("50-200",   3,    2,    200, 160, 100, 100, 412),
    ("50-250",   3,    2,    228, 180, 125, 112, 433),
    ("50-315",   3,    2,    280, 225, 125, 132, 473),
    ("65-125",   4,    2.5,  180, 160, 100,  90, 362),
    ("65-160",   4,    2.5,  200, 160, 100, 100, 412),
    ("65-200",   4,    2.5,  225, 180, 100, 100, 412),
    ("65-250",   4,    2.5,  250, 200, 125, 132, 473),
    ("65-315",   4,    2.5,  280, 225, 125, 132, 511),
    ("80-160",   5,    3,    225, 180, 125, 100, 412),
    ("80-200",   5,    3,    250, 180, 125, 112, 442),
    ("80-250",   5,    3,    280, 225, 125, 132, 511),
    ("80-315",   5,    3,    315, 250, 125, 160, 613),
    ("100-200",  5,    4,    280, 200, 125, 132, 502),
    ("100-250",  5,    4,    280, 225, 140, 160, 613),
    ("100-315",  5,    4,    315, 250, 140, 200, 732),
    ("125-200",  6,    5,    315, 250, 140, 160, 601),
    ("125-250",  6,    5,    335, 250, 140, 180, 681),
    ("150-200",  8,    6,    400, 280, 160, 160, 601),
    ("150-250",  8,    6,    375, 280, 160, 200, 728),
]
# Ate esse tamanho o bocal pode vir rosqueado BSP em vez de flangeado
LIMITE_ROSCA = {"25-150", "25-200", "32-125", "32-125.1", "32-160", "32-160.1",
                "32-200", "32-200.1", "40-125", "40-160", "40-200",
                "50-125", "50-160", "50-200", "65-125", "65-160", "65-200"}
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
                       "a_mm", "b_mm", "c_mm", "h_mm", "l_mm", "norma_flange",
                       "rosca_possivel", "fonte"])
    for tamanho, succao, recalque, a, b, c, h, l in IV_POLOS:
        escritor.writerow([tamanho, 4, f"{succao:g}", f"{recalque:g}",
                           a, b, c, h, l, norma(tamanho),
                           int(tamanho in LIMITE_ROSCA), FONTE])
    for tamanho, succao, recalque in II_POLOS_BOCAIS:
        escritor.writerow([tamanho, 2, f"{succao:g}", f"{recalque:g}",
                           "", "", "", "", "", norma(tamanho),
                           int(tamanho in LIMITE_ROSCA), FONTE])
    print(f"# {len(IV_POLOS)} tamanhos com dimensao (IV polos) + "
          f"{len(II_POLOS_BOCAIS)} so com bocais (II polos)", file=sys.stderr)


if __name__ == "__main__":
    main()
