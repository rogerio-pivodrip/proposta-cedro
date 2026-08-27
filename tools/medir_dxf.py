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
            textos.append((p.x, p.y, entidade.dxf.text.strip(),
                           entidade.dxf.height or 3.0))
            continue
        if tipo == "MTEXT":
            p = entidade.dxf.insert
            textos.append((p.x, p.y, entidade.text.strip().replace("\\P", " "),
                           entidade.dxf.char_height or 3.0))
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


def aglomerar(caixas_e_camadas, celula=CELULA):
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
        for cx in range(int(x0 // celula), int(x1 // celula) + 1):
            for cy in range(int(y0 // celula), int(y1 // celula) + 1):
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
    for tx, ty, texto, altura in textos:
        if texto:
            unicos[(round(tx, 1), round(ty, 1), texto)] = (tx, ty, texto, altura)
    lista = list(unicos.values())

    # A largura do texto sai da ALTURA dele. O rotulo desses arquivos tem 2 a
    # 4 mm de altura num desenho de metros; estimar a largura por um numero
    # fixo dava 400 mm de rotulo e fundia a coluna inteira num bloco so.
    def larg(parte):
        return len(parte[2]) * parte[3] * 0.62

    caixas_texto = [((p[0], p[1], p[0] + larg(p), p[1] + p[3]), "TEXTO")
                    for p in lista]
    celula_texto = max(3.0, sum(p[3] for p in lista) / max(len(lista), 1) * 2.5)
    rotulos = []
    for indices in aglomerar(caixas_texto, celula_texto):
        partes = sorted((lista[i] for i in indices), key=lambda p: -p[1])
        rotulos.append({"x0": min(p[0] for p in partes),
                        "x1": max(p[0] + larg(p) for p in partes),
                        "topo": max(p[1] for p in partes),
                        "texto": " ".join(p[2] for p in partes)})

    for peca in pecas:
        peca["nome"] = ""
        peca["distancia"] = None

    # Emparelhar, nao pegar o vizinho mais proximo. Numa coluna de seis curvas
    # com seis rotulos, "o mais proximo" faz duas curvas disputarem o mesmo
    # rotulo e sobram quatro sem nome. Emparelhando por distancia crescente,
    # com cada rotulo e cada peca usados uma vez, os seis fecham.
    pares = []
    for r, rotulo in enumerate(rotulos):
        meio = (rotulo["x0"] + rotulo["x1"]) / 2
        for p, peca in enumerate(pecas):
            if not (peca["x0"] - CELULA <= meio <= peca["x1"] + CELULA):
                continue
            if peca["y0"] <= rotulo["topo"] <= peca["y1"]:
                distancia = 0.0
            elif rotulo["topo"] < peca["y0"]:
                distancia = peca["y0"] - rotulo["topo"]
            else:
                distancia = rotulo["topo"] - peca["y1"]
            pares.append((distancia, r, p))
    pares.sort()
    usados_rotulo, usadas_peca = set(), set()
    for distancia, r, p in pares:
        if r in usados_rotulo or p in usadas_peca:
            continue
        usados_rotulo.add(r)
        usadas_peca.add(p)
        pecas[p]["nome"] = rotulos[r]["texto"]
        pecas[p]["distancia"] = round(distancia, 1)


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
