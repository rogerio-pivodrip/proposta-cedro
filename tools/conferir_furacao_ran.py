#!/usr/bin/env python3
"""Confere a furacao NBR 7675 contra a tabela de flanges do catalogo RAN.

O RAN publica PN10 e PN16 lado a lado, com circulo de furacao - que a tabela
do Irrigafour nao tinha. E o circulo e que decide se duas flanges casam:
mesma quantidade de furos com circulo diferente nao aparafusa.

Uso: python3 tools/conferir_furacao_ran.py
"""
import csv

NOSSA = "data/regras_furacao.csv"
# RAN Valvulas Fig. 37, tabela FLANGES: D externo, C circulo, F furo, NF furos
RAN = {
    #  dn:  PN10 (D, C, F, NF),      PN16 (D, C, F, NF)
    50:  ((165, 125, 19, 4),   (165, 125, 19, 4)),
    75:  ((200, 154, 19, 4),   (200, 160, 19, 4)),
    80:  ((200, 160, 19, 8),   (200, 160, 19, 8)),
    100: ((220, 180, 19, 8),   (220, 180, 19, 8)),
    125: ((250, 210, 19, 8),   (250, 210, 19, 8)),
    150: ((285, 240, 23, 8),   (285, 240, 23, 8)),
    200: ((340, 295, 23, 8),   (340, 295, 23, 12)),
    250: ((400, 350, 23, 12),  (400, 355, 28, 12)),
    300: ((455, 400, 23, 12),  (455, 410, 28, 12)),
    350: ((520, 460, 23, 16),  (520, 470, 28, 16)),
    400: ((580, 515, 28, 16),  (580, 525, 31, 16)),
}
CASA = [50, 80, 100, 125, 150, 200, 250, 300, 350]


def main():
    nossa = {}
    with open(NOSSA, encoding="utf-8") as fh:
        for r in csv.DictReader(l for l in fh if not l.startswith("#")):
            nossa[(r["norma"], int(r["dn_mm"]))] = (int(r["furos"]),
                                                    float(r["circulo_mm"]))

    print("== a nossa tabela 'NBR PN16' e PN10 ou PN16 do RAN?")
    print(f"  {'DN':>5}  {'nossa':>14}  {'RAN PN10':>14}  {'RAN PN16':>14}   igual a")
    conta = {"PN10": 0, "PN16": 0, "ambas": 0, "nenhuma": 0}
    for dn in CASA:
        n = nossa.get(("NBR PN16", dn))
        if not n or dn not in RAN:
            continue
        p10, p16 = RAN[dn]
        a = (p10[3], float(p10[1]))
        b = (p16[3], float(p16[1]))
        if a == n == b:
            veredito = "ambas (iguais)"
        elif n == a:
            veredito = "PN10"
        elif n == b:
            veredito = "PN16"
        else:
            veredito = "NENHUMA"
        conta[{"ambas (iguais)": "ambas", "PN10": "PN10",
               "PN16": "PN16"}.get(veredito, "nenhuma")] += 1
        print(f"  {dn:>5}  {n[0]:>3}f c{n[1]:>6.0f}  {p10[3]:>3}f c{p10[1]:>6}"
              f"  {p16[3]:>3}f c{p16[1]:>6}   {veredito}")
    print(f"  -> {conta}")

    print("\n== onde PN10 e PN16 nao aparafusam entre si (circulo diferente)")
    for dn in CASA:
        p10, p16 = RAN[dn]
        if p10[1] != p16[1] or p10[2] != p16[2]:
            print(f"  DN{dn:<4} PN10 circulo {p10[1]} furo {p10[2]}  |  "
                  f"PN16 circulo {p16[1]} furo {p16[2]}")


if __name__ == "__main__":
    main()
