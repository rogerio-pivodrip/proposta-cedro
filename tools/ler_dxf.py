#!/usr/bin/env python3
"""Inventaria um DXF: quais blocos tem, em que camada, e que tamanho medem.

Feito para ler a biblioteca da casa. O que interessa de um bloco de projeto
nao e o desenho - e a MEDIDA: se o bloco da gaveta de 3" mede 190 mm de face
a face, isso e uma quarta fonte independente para conferir contra a tabela de
cotas, ao lado do Irrigafour, da Netafim e do fabricante da valvula.

Uso: python3 tools/ler_dxf.py arquivo.dxf [outro.dxf ...]
"""
import collections
import sys

import ezdxf


def medida(entidades):
    """A caixa do bloco em unidade do arquivo, e o que tem dentro."""
    xs, ys = [], []
    tipos = collections.Counter()
    camadas = collections.Counter()
    for e in entidades:
        tipos[e.dxftype()] += 1
        camadas[e.dxf.layer] += 1
        try:
            if e.dxftype() == "LWPOLYLINE":
                for x, y in e.get_points("xy"):
                    xs.append(x)
                    ys.append(y)
            elif e.dxftype() == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif e.dxftype() in ("CIRCLE", "ARC"):
                r = e.dxf.radius
                xs += [e.dxf.center.x - r, e.dxf.center.x + r]
                ys += [e.dxf.center.y - r, e.dxf.center.y + r]
            elif e.dxftype() == "POLYLINE":
                for v in e.vertices:
                    xs.append(v.dxf.location.x)
                    ys.append(v.dxf.location.y)
        except AttributeError:
            continue
    caixa = ((max(xs) - min(xs), max(ys) - min(ys)) if xs else (0, 0))
    return caixa, tipos, camadas


UNIDADE = {0: "sem unidade", 1: "polegada", 2: "pe", 4: "milimetro",
           5: "centimetro", 6: "metro"}


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1
    for caminho in sys.argv[1:]:
        doc = ezdxf.readfile(caminho)
        unidade = doc.header.get("$INSUNITS", 0)
        print(f"\n=== {caminho}")
        print(f"  versao {doc.dxfversion} · unidade "
              f"{UNIDADE.get(unidade, unidade)}")
        camadas = [(l.dxf.name, l.dxf.color, l.dxf.linetype)
                   for l in doc.layers]
        print(f"  {len(camadas)} camadas: "
              + ", ".join(f"{n}({c})" for n, c, _ in camadas[:14]))

        blocos = [b for b in doc.blocks if not b.name.startswith(("*", "_"))]
        print(f"  {len(blocos)} blocos")
        for b in sorted(blocos, key=lambda b: b.name):
            (larg, alt), tipos, _ = medida(b)
            resumo = " ".join(f"{n}×{t}" for t, n in tipos.most_common(3))
            print(f"    {b.name:38} {larg:8.1f} × {alt:7.1f}   {resumo}")

        modelo = doc.modelspace()
        inserts = collections.Counter(
            e.dxf.name for e in modelo if e.dxftype() == "INSERT")
        if inserts:
            print(f"  {sum(inserts.values())} inserts no modelo:")
            for nome, n in inserts.most_common():
                print(f"    {nome:38} ×{n}")
        soltas = collections.Counter(
            e.dxftype() for e in modelo if e.dxftype() != "INSERT")
        if soltas:
            (larg, alt), _, camadas_soltas = medida(
                [e for e in modelo if e.dxftype() != "INSERT"])
            print(f"  geometria solta no modelo: {dict(soltas)}")
            print(f"    caixa {larg:.1f} × {alt:.1f} · camadas "
                  f"{dict(camadas_soltas.most_common(6))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
