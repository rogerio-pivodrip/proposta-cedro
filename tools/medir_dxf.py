#!/usr/bin/env python3
"""Mede peca por peca num DXF de biblioteca da casa.

O arquivo da casa nao vem em bloco: as pecas estao desenhadas soltas, lado a
lado no modelo, com o nome escrito embaixo de cada uma. Entao medir e um
problema de separar antes de medir.

Como funciona:

  1. cada entidade da uma caixa (ezdxf.bbox), fora as de texto
  2. as caixas caem numa grade e a grade se une por vizinhanca - o que se
     toca e a mesma peca. E o passo que separa 45 metros de desenho em
     dezenas de pecas sem ninguem clicar em nada
  3. cada aglomerado recebe o texto mais proximo, que e o nome da peca

O que sai e o que interessa de um bloco de projeto: o NOME e a MEDIDA. E uma
fonte independente de cota, ao lado do Irrigafour, da Netafim e das fichas de
fabricante - e a unica que cobre PVC, Plasson e PEAD soldavel, que nenhuma
tabela do motor alcanca.

Uso: python3 tools/medir_dxf.py data/cad/*.dxf > data/cotas_cad.csv
"""
import csv
import math
import os
import sys

import ezdxf
from ezdxf import bbox

CELULA = 60.0          # mm: dois tracos a menos disso um do outro sao a mesma peca
MINIMO = 25.0          # mm: aglomerado menor que isso e sujeira, nao peca
FORA = {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"}
CAMADAS_FORA = {"Defpoints", "PDF_Text"}
# o eixo sobra dos dois lados da peca, e sobra diferente em cada desenho.
# Ele entra no aglomerado - e o que costura a peca - mas nao na medida.
CAMADAS_SEM_MEDIDA = {"eixo"}


def caixas(modelo):
    """(caixa, camada) de cada entidade que nao e texto, ja explodindo bloco."""
    saida, textos = [], []
    for entidade in modelo:
        tipo = entidade.dxftype()
        if entidade.dxf.layer in CAMADAS_FORA:
            continue
        if tipo == "TEXT":
            p = entidade.dxf.insert
            textos.append((p.x, p.y, entidade.dxf.text.strip()))
            continue
        if tipo == "MTEXT":
            p = entidade.dxf.insert
            textos.append((p.x, p.y, entidade.text.strip().replace("\\P", " ")))
            continue
        if tipo in FORA:
            continue
        alvos = ([entidade] if tipo != "INSERT"
                 else list(entidade.virtual_entities()))
        for alvo in alvos:
            if alvo.dxftype() in FORA:
                continue
            try:
                caixa = bbox.extents([alvo], fast=True)
            except Exception:
                continue
            if caixa.has_data:
                saida.append(((caixa.extmin.x, caixa.extmin.y,
                               caixa.extmax.x, caixa.extmax.y),
                              alvo.dxf.layer))
    return saida, textos


def aglomerar(caixas_e_camadas):
    """Une por vizinhanca na grade: o que se toca e a mesma peca."""
    pai = {}

    def raiz(a):
        while pai[a] != a:
            pai[a] = pai[pai[a]]
            a = pai[a]
        return a

    def juntar(a, b):
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            pai[rb] = ra

    celulas = {}
    for i, ((x0, y0, x1, y1), _) in enumerate(caixas_e_camadas):
        pai.setdefault(i, i)
        for cx in range(int(x0 // CELULA), int(x1 // CELULA) + 1):
            for cy in range(int(y0 // CELULA), int(y1 // CELULA) + 1):
                celulas.setdefault((cx, cy), []).append(i)
    for (cx, cy), donos in celulas.items():
        for outro in donos[1:]:
            juntar(donos[0], outro)
        for vx, vy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            vizinho = celulas.get((cx + vx, cy + vy))
            if vizinho:
                juntar(donos[0], vizinho[0])

    grupos = {}
    for i in pai:
        grupos.setdefault(raiz(i), []).append(i)
    return list(grupos.values())


def nomear(pecas, textos):
    """Liga cada rotulo a peca dele - do texto para a peca, nao ao contrario.

    Da peca para o texto nao funciona: peca larga rouba o rotulo da vizinha,
    porque o rotulo da vizinha tambem cai na faixa dela. Do texto para a peca
    funciona, porque cada texto tem uma peca so em cima dele.

    O rotulo costuma ter duas linhas - "CURVA 90. SOLDA 225MM" / "PLASSON/FIP"
    - entao os textos sao aglomerados primeiro e o bloco inteiro vira o nome.
    """
    unicos = {}
    for tx, ty, texto in textos:
        if texto:
            unicos[(round(tx, 1), round(ty, 1), texto)] = (tx, ty, texto)
    lista = list(unicos.values())

    # aglomera os textos em rotulos, pela mesma vizinhanca da geometria
    caixas_texto = [((tx, ty, tx + len(t) * 12, ty + 20), "TEXTO")
                    for tx, ty, t in lista]
    rotulos = []
    for indices in aglomerar(caixas_texto):
        partes = sorted((lista[i] for i in indices), key=lambda p: -p[1])
        rotulos.append({"x0": min(p[0] for p in partes),
                        "x1": max(p[0] + len(p[2]) * 12 for p in partes),
                        "topo": max(p[1] for p in partes),
                        "texto": " ".join(p[2] for p in partes)})

    for peca in pecas:
        peca["nome"] = ""
        peca["distancia"] = None
    for rotulo in rotulos:
        meio = (rotulo["x0"] + rotulo["x1"]) / 2
        # o rotulo pode estar acima ou abaixo da peca - a casa usa os dois
        # nos tres arquivos, e as vezes no mesmo arquivo. Entao vale a mais
        # PROXIMA na mesma coluna, para qualquer lado.
        candidatos = []
        for p in pecas:
            if not (p["x0"] - CELULA <= meio <= p["x1"] + CELULA):
                continue
            if p["y0"] <= rotulo["topo"] <= p["y1"]:
                candidatos.append((0.0, p))
            elif rotulo["topo"] < p["y0"]:
                candidatos.append((p["y0"] - rotulo["topo"], p))
            else:
                candidatos.append((rotulo["topo"] - p["y1"], p))
        candidatos.sort(key=lambda t: t[0])
        if not candidatos:
            continue
        distancia, peca = candidatos[0]
        if peca["nome"] and (peca["distancia"] or 0) <= distancia:
            continue
        peca["nome"] = rotulo["texto"]
        peca["distancia"] = distancia


def medir(caminho):
    doc = ezdxf.readfile(caminho)
    lista, textos = caixas(doc.modelspace())
    pecas = []
    for indices in aglomerar(lista):
        cxs = [lista[i][0] for i in indices]
        corpo = [lista[i][0] for i in indices
                 if lista[i][1] not in CAMADAS_SEM_MEDIDA] or cxs
        x0 = min(c[0] for c in corpo)
        y0 = min(c[1] for c in corpo)
        x1 = max(c[2] for c in corpo)
        y1 = max(c[3] for c in corpo)
        if x1 - x0 < MINIMO or y1 - y0 < MINIMO:
            continue
        camadas = {lista[i][1] for i in indices}
        pecas.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1,
                      "n": len(indices), "camadas": camadas})

    nomear(pecas, textos)
    return sorted(pecas, key=lambda p: (round(p["y1"], -3), p["x0"]),
                  reverse=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1
    campos = ["arquivo", "nome", "largura_mm", "altura_mm", "x_mm", "y_mm",
              "entidades", "camadas", "fonte"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    total = 0
    for caminho in sys.argv[1:]:
        arquivo = os.path.basename(caminho)
        for peca in medir(caminho):
            total += 1
            escritor.writerow({
                "arquivo": arquivo, "nome": peca["nome"],
                "largura_mm": round(peca["x1"] - peca["x0"], 1),
                "altura_mm": round(peca["y1"] - peca["y0"], 1),
                "x_mm": round(peca["x0"], 1), "y_mm": round(peca["y0"], 1),
                "entidades": peca["n"],
                "camadas": " ".join(sorted(peca["camadas"])),
                "fonte": f"DXF da casa: {arquivo}"})
    print(f"# {total} pecas medidas", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
