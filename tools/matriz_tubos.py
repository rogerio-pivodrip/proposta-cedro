#!/usr/bin/env python3
"""Tubo de aco zincado: que comprimento existe em que bitola.

Comprimentos usuais da casa: 0,50 / 1,00 / 1,50 / 2,00 / 3,00 e 6,00 m. O
catalogo escreve tanto "1M" quanto "1000MM", e o interpretador ja normaliza os
dois para milimetro.

Marca:
    #  existe com as duas pontas em NBR PN16
    K  so existe com ponta de engate K, que a casa nao usa
    -  nao existe

Uso: python3 tools/matriz_tubos.py [-v]
"""
import sys

sys.path.insert(0, ".")
from motor.catalogo import Catalogo

NORMA = "NBR PN16"
BITOLAS = [3, 4, 5, 6, 8, 10, 12, 14]
COMPRIMENTOS = [500, 1000, 1500, 2000, 3000, 6000]


def limpos(catalogo, dn, comprimento):
    """Tubos desse DN e comprimento, separados por ter ou nao ponta K."""
    achados = catalogo.buscar("TUBO", float(dn), norma=NORMA,
                              comprimento_mm=comprimento)
    sem_k, com_k = [], []
    for item in achados:
        destino = com_k if any(c["tipo"] == "ENGATE_K" for c in item["conexoes"]) \
            else sem_k
        destino.append(item)
    return sem_k, com_k


def main():
    detalhar = "-v" in sys.argv
    catalogo = Catalogo()

    print("== tubo AZ: comprimento por bitola ==")
    print("   # NBR PN16 nas duas pontas    K so com engate K    - nao existe\n")
    cabecalho = "".join(f"{c/1000:>7.2f}m" for c in COMPRIMENTOS)
    print(f'{"":6s}{cabecalho}')
    buracos, so_k = [], []
    for dn in BITOLAS:
        celulas = []
        for comp in COMPRIMENTOS:
            sem_k, com_k = limpos(catalogo, dn, comp)
            if sem_k:
                celulas.append(f"# {len(sem_k)}")
            elif com_k:
                celulas.append(f"K {len(com_k)}")
                so_k.append((dn, comp, com_k))
            else:
                celulas.append("-")
                buracos.append((dn, comp))
        print(f'{str(dn) + chr(34):>5} ' + "".join(f"{c:>8}" for c in celulas))

    if buracos:
        print("\nnao existe:")
        for dn, comp in buracos:
            print(f'  {dn:>2}" {comp/1000:.2f} m')
    if so_k:
        print("\nso com ponta de engate K (a casa nao usa):")
        for dn, comp, itens in so_k:
            print(f'  {dn:>2}" {comp/1000:.2f} m   ' +
                  ", ".join(i["sap"] for i in itens[:3]))

    if detalhar:
        print("\n== codigos ==")
        for dn in BITOLAS:
            for comp in COMPRIMENTOS:
                sem_k, _ = limpos(catalogo, dn, comp)
                for item in sem_k:
                    print(f'  {dn:>2}" {comp/1000:.2f}m  {item["sap"]}  '
                          f'{item["descricao"][:44]}')


if __name__ == "__main__":
    main()
