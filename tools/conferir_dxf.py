#!/usr/bin/env python3
"""Confere o DXF exportado contra o simbolo que o gerou.

Exportar desenho e um lugar facil de errar em silencio: o CAD usa y para cima
e o simbolo desenha com y para baixo, entao um sinal trocado espelha a peca
sem quebrar nada. O jeito de pegar isso e medir os dois e comparar.

Confere, para cada peca: a caixa do bloco em milimetro, e o numero de
entidades contra o numero de elementos que o simbolo tem.

Uso: python3 tools/conferir_dxf.py [--dn 8]
"""
import argparse
import os
import sys
import tempfile

import ezdxf

sys.path.insert(0, ".")
from motor import dxf  # noqa: E402
from tools.desenhar_simbolos import elenco  # noqa: E402
from tools.ler_dxf import medida  # noqa: E402

FOLGA_MM = 1.0        # o texto da cota nao entra na caixa medida


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    args = p.parse_args()
    pecas = [peca for _, grupo in elenco(args.dn) for peca in grupo]

    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "conferencia.dxf")
        # escreve pelo mesmo caminho do exportador e guarda o nome que cada
        # peca recebeu - duas pecas de mesmo rotulo saem com nomes diferentes
        escrita = dxf._documento()
        nomes = [dxf.bloco(escrita, simbolo) for simbolo in pecas]
        escrita.saveas(caminho)
        doc = ezdxf.readfile(caminho)
        blocos = {b.name: b for b in doc.blocks}

        print(f'{"peça":40} {"símbolo (mm)":>16} {"bloco DXF (mm)":>18}')
        batem = erram = 0
        for simbolo, nome in zip(pecas, nomes):
            bloco = blocos.get(nome)
            if bloco is None:
                erram += 1
                print(f"{simbolo.rotulo:40} SEM BLOCO")
                continue
            (larg, alt), _, _ = medida(bloco)
            esperado = (simbolo.caixa[2], simbolo.caixa[3])
            ok = (abs(larg - esperado[0]) <= FOLGA_MM
                  and abs(alt - esperado[1]) <= FOLGA_MM)
            batem += ok
            erram += not ok
            marca = "" if ok else "   <-- diverge"
            print(f"{simbolo.rotulo:40} {esperado[0]:7.0f}×{esperado[1]:<8.0f} "
                  f"{larg:8.0f}×{alt:<9.0f}{marca}")
        print(f"\n{batem} de {batem + erram} blocos com a medida do símbolo")
    return 1 if erram else 0


if __name__ == "__main__":
    sys.exit(main())
