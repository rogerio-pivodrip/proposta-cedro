#!/usr/bin/env python3
"""Monta a tabela de cotas por familia, variante e bitola.

O caderno de desenhos mostra que a cota nao e por codigo: a reducao de 8" mede
300 mm de face a face seja qual for o diametro menor e seja qual for a norma da
outra ponta. A cota do desenho sai de (familia, variante, DN), e uma tabela de
8 a 14 linhas por variante cobre o catalogo inteiro.

Variante e o segundo parametro que muda a forma dentro da familia:
  CURVA     -> o angulo (45 ou 90): a curva de 45 e mais longa que a de 90
  MANIFOLD  -> o modelo de derivacao (D02, D05, D11...), que define o corpo
  demais    -> vazio, a bitola sozinha ja fixa a cota

Uso: python3 tools/extrair_cotas.py > data/cotas_por_familia.csv
"""
import collections
import csv
import json
import re
import sys

DESENHOS = "data/desenhos_netafim.csv"
CATALOGO = "data/catalogo.json"

# Pagina -> familia e o que a primeira cota significa. O caderno nao nomeia a
# peca em texto extraivel, mas os codigos ja cadastrados na pagina dizem.
SIGNIFICADO = {
    "REDUCAO_CONCENTRICA": "face_a_face_mm",
    "REDUCAO_EXCENTRICA": "face_a_face_mm",
    "TE": "raio_mm",
    "CURVA": "raio_mm",
    "CRIVO": "face_a_face_mm",
    "ADAPTADOR": "face_a_face_mm",
    "MANIFOLD": "comprimento_mm",
    "FLANGE_CEGA": "espessura_mm",
}
RX_PRIMEIRA = re.compile(r"^\s*(\d[\d.]*(?:,\d+)?)")
# Paginas de reducao: a linha comeca com "x d" e a cota vem depois
RX_REDUCAO = re.compile(r"^x\s?d\s*(\d{3})")
RX_DERIVACAO = re.compile(r"\bD\s?(\d{2})\b")


def cota(texto):
    m = RX_REDUCAO.match(texto.strip())
    if m:
        return float(m.group(1)), "REDUCAO"
    m = RX_PRIMEIRA.match(texto)
    if not m:
        return None, None
    bruto = m.group(1)
    try:
        return float(bruto.replace(".", "").replace(",", ".")), None
    except ValueError:
        return None, None


def moda(valores):
    return collections.Counter(v for v in valores if v).most_common(1)[0][0]


def variante(familia, itens):
    """O segundo parametro da forma, lido dos codigos que a pagina cita."""
    if familia == "CURVA":
        angulos = [i.get("angulo") for i in itens if i.get("angulo")]
        return str(moda(angulos)) if angulos else ""
    if familia == "MANIFOLD":
        achados = [RX_DERIVACAO.search(i["descricao"]) for i in itens]
        achados = [m.group(1) for m in achados if m]
        return "D" + moda(achados) if achados else ""
    return ""


def main():
    with open(DESENHOS, encoding="utf-8") as fh:
        linhas = list(csv.DictReader(fh))
    with open(CATALOGO, encoding="utf-8") as fh:
        catalogo = {i["sap"]: i for i in json.load(fh)}

    por_pagina = collections.defaultdict(list)
    for x in linhas:
        por_pagina[x["pagina"]].append(x)

    # familia e variante de cada pagina, pelos codigos que ela cita
    familia_pagina, variante_pagina = {}, {}
    for pagina, itens in por_pagina.items():
        fichas = [catalogo[x["sap"]] for x in itens if x["sap"] in catalogo]
        contagem = collections.Counter(f["familia"] for f in fichas if f["familia"])
        if not contagem:
            continue
        familia = contagem.most_common(1)[0][0]
        familia_pagina[pagina] = familia
        variante_pagina[pagina] = variante(familia, fichas)

    # (familia, variante, dn) -> cotas vistas
    tabela = collections.defaultdict(list)
    for x in linhas:
        valor, marca = cota(x["cotas"])
        if valor is None:
            continue
        familia = "REDUCAO" if marca == "REDUCAO" else familia_pagina.get(x["pagina"])
        if not familia:
            continue
        chave = (familia, variante_pagina.get(x["pagina"], ""), int(x["dn_pol"]))
        tabela[chave].append(valor)

    escritor = csv.writer(sys.stdout)
    escritor.writerow(["familia", "variante", "dn_pol", "cota_mm", "significado",
                       "amostras", "divergentes"])
    divergentes = 0
    for (familia, var, dn), valores in sorted(tabela.items()):
        contagem = collections.Counter(valores)
        valor, _ = contagem.most_common(1)[0]
        divergentes += len(contagem) - 1
        escritor.writerow([familia, var, dn, f"{valor:g}",
                           SIGNIFICADO.get(familia, "cota_mm"),
                           len(valores), len(contagem) - 1])
    print(f"# {len(tabela)} combinacoes, {divergentes} divergentes", file=sys.stderr)


if __name__ == "__main__":
    main()
