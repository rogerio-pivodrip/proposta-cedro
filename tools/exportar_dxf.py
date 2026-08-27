#!/usr/bin/env python3
"""Exporta os simbolos e as linhas para DXF, em bloco.

A casa ja tem biblioteca de bloco em DWG. Isto nao concorre com ela: produz o
mesmo tipo de coisa, gerada. Cada peca vira um BLOCK com o nome dela, a linha
vira um INSERT por peca com a rotacao acumulada da corrente, e a cota sai em
milimetro real - o desenho abre no CAD ja na escala certa.

As camadas seguem a convencao do desenho: EIXO vermelho traco-ponto, CORPO
preto, FLANGE e ferragem separadas. Da para apagar todos os eixos de uma vez
ou plotar so o corpo.

Uso: python3 tools/exportar_dxf.py --dn 8 --saida dxf/
"""
import argparse
import os
import sys

sys.path.insert(0, ".")
from motor import dxf  # noqa: E402
from motor import simbolos as s  # noqa: E402
from tools.desenhar_linha import (manifold_ventosas, recalque,  # noqa: E402
                                  succao_horizontal, succao_mancalizada,
                                  succao_vertical, trecho_pead)
from tools.desenhar_simbolos import elenco  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    p.add_argument("--saida", default="dxf")
    args = p.parse_args()
    os.makedirs(args.saida, exist_ok=True)
    bitola = f'{args.dn:g}'.replace(".", "_")

    pecas = [peca for _, grupo in elenco(args.dn) for peca in grupo]
    caminho = os.path.join(args.saida, f"simbolos_{bitola}pol.dxf")
    doc = dxf.escrever_pecas(caminho, pecas)
    blocos = [b.name for b in doc.blocks
              if not b.name.startswith(("*", "_"))]
    print(f"{caminho}: {len(blocos)} blocos")

    menor = {14: 12, 12: 10, 10: 8, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(args.dn, 2)
    linhas = {"succao_vertical": (succao_vertical(args.dn), -90),
              "succao_horizontal": (succao_horizontal(args.dn), -90),
              "succao_mancalizada": (succao_mancalizada(args.dn), -90),
              "recalque": (recalque(args.dn, menor), 0),
              "manifold": (manifold_ventosas(args.dn), 0),
              "trecho_pead": (trecho_pead(args.dn), 0)}
    for nome, (montagem, giro) in linhas.items():
        postos, _ = s.montar(montagem)
        if giro:
            postos = _girar_postos(postos, giro)
        caminho = os.path.join(args.saida, f"{nome}_{bitola}pol.dxf")
        dxf.escrever_linha(caminho, postos)
        print(f"{caminho}: {len(postos)} inserts")
    return 0


def _girar_postos(postos, giro):
    """A sucção nasce no poço e sobe: a linha inteira gira para ficar de pé."""
    import math
    rad = math.radians(giro)
    cos, sen = math.cos(rad), math.sin(rad)
    vira = lambda x, y: (x * cos - y * sen, x * sen + y * cos)
    return [p._replace(dx=vira(p.dx, p.dy)[0], dy=vira(p.dx, p.dy)[1],
                       giro=p.giro + giro, entrada=vira(*p.entrada),
                       saida=vira(*p.saida)) for p in postos]


if __name__ == "__main__":
    sys.exit(main())
