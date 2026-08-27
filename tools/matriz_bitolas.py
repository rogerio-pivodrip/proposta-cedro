#!/usr/bin/env python3
"""Matriz de cobertura: que peca existe em que bitola, de 3" a 14".

Antes de o programa montar qualquer linha, precisa saber onde o catalogo tem
buraco. A matriz roda familia por familia e marca:

    #  serve na linha - ou e NBR PN16, ou a peca nao declara norma (valvula,
       junta e medidor tem a norma definida no pedido)
    o  existe, mas so declarada em outra norma
    -  nao existe nesse diametro

Uso: python3 tools/matriz_bitolas.py
"""
import sys

sys.path.insert(0, ".")
from motor.bomba import HORIZONTAL, VERTICAL
from motor.catalogo import Catalogo
from motor.templates import succao

NORMA = "NBR PN16"
BITOLAS = [3, 4, 5, 6, 8, 10, 12, 14]

# (rotulo, familia, filtros extras)
LINHAS = [
    ("crivo", "CRIVO", {}),
    ("valvula de retencao", "VALVULA_RETENCAO", {}),
    ("valvula borboleta", "VALVULA_BORBOLETA", {}),
    ("valvula gaveta", "VALVULA_GAVETA", {}),
    ("tubo 1 m", "TUBO", {"comprimento_mm": 1000}),
    ("tubo 3 m", "TUBO", {"comprimento_mm": 3000}),
    ("tubo 6 m", "TUBO", {"comprimento_mm": 6000}),
    ("curva 90", "CURVA", {"angulo": 90}),
    ("curva 45", "CURVA", {"angulo": 45}),
    ("te", "TE", {}),
    ("flange", "FLANGE", {}),
    ("flange cega", "FLANGE_CEGA", {}),
    ("junta plana", "JUNTA_PLANA", {}),
    ("manifold", "MANIFOLD", {}),
    ("medidor", "MEDIDOR", {}),
    ("articulador 30", "ARTICULADOR", {}),
]


def marca(catalogo, familia, dn, extra):
    if catalogo.melhor(familia, dn, norma=NORMA, **extra) or \
            catalogo.melhor(familia, dn, material=None, norma=NORMA, **extra):
        return "#"
    achado = catalogo.melhor(familia, dn, material=None, **extra)
    if not achado:
        return "-"
    # Junta plana, valvula e medidor nao trazem norma na descricao: a norma vem
    # no pedido, entao a peca serve - nao e caso de "so em outra norma".
    if not any(c["norma"] for c in achado["conexoes"]):
        return "#"
    return "o"


def matriz_pecas(catalogo):
    print("== peca por bitola ==   # serve   o so em outra norma   "
          "- nao existe\n")
    print(f'{"":22s}' + "".join(f'{str(d) + chr(34):>5}' for d in BITOLAS))
    for rotulo, familia, extra in LINHAS:
        celulas = [marca(catalogo, familia, float(d), extra) for d in BITOLAS]
        print(f"{rotulo:22s}" + "".join(f"{c:>5}" for c in celulas))


def matriz_reducoes(catalogo):
    """Reducao de cada bitola para a de baixo - o degrau que a linha usa."""
    print('\n== reducao de uma bitola para a anterior ==\n')
    print(f'{"":22s}' + "".join(f'{str(d) + chr(34):>5}' for d in BITOLAS[1:]))
    for rotulo, familia in (("concentrica", "REDUCAO_CONCENTRICA"),
                            ("excentrica", "REDUCAO_EXCENTRICA")):
        celulas = []
        for maior, menor in zip(BITOLAS[1:], BITOLAS[:-1]):
            celulas.append(marca(catalogo, familia, float(maior),
                                 {"dn_saida": float(menor)}))
        print(f"{rotulo:22s}" + "".join(f"{c:>5}" for c in celulas))


def bomba_para(catalogo, dn_entrada_pol):
    """Uma bomba de verdade do catalogo cujo bocal de entrada e esse DN."""
    from motor.bomba import MM_PARA_POLEGADA, interpretar
    for item in catalogo.itens:
        bomba = interpretar(item["descricao"])
        if not bomba or not bomba["entrada_mm"]:
            continue
        if MM_PARA_POLEGADA.get(bomba["entrada_mm"]) == dn_entrada_pol:
            return item["descricao"]
    return None


def matriz_template(catalogo):
    """Caso realista: a linha e uma bitola acima do bocal de entrada."""
    print('\n== o template de succao monta em cada bitola? ==\n')
    for anterior, dn in zip(BITOLAS[:-1], BITOLAS[1:]):
        modelo = bomba_para(catalogo, float(anterior))
        if not modelo:
            print(f'  {dn:>2}"  sem bomba no catalogo com entrada de {anterior}"')
            continue
        for orientacao, curva in ((HORIZONTAL, 90), (VERTICAL, None)):
            linha, _reducao, faltando = succao(
                catalogo, float(dn), modelo, orientacao, curva)
            estado = "ok" if not faltando else \
                "falta " + ", ".join(f[0] for f in faltando)
            print(f'  {dn:>2}" -> {anterior:>2}"  {orientacao.lower():10s} '
                  f'{len(linha.pecas)} pecas   {estado}   [{modelo[:34]}]')


def main():
    catalogo = Catalogo()
    matriz_pecas(catalogo)
    matriz_reducoes(catalogo)
    matriz_template(catalogo)


if __name__ == "__main__":
    main()
