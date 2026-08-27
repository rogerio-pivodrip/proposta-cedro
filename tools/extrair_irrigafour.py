#!/usr/bin/env python3
"""Extrai as tabelas de cota do catalogo Irrigafour (data/fichas/IRRIGAFOUR_*).

Sao 43 paginas, cada uma uma tabela de dimensoes por bitola. O catalogo confirma
a tese do motor - a cota e da familia, nao do codigo - e acrescenta uma chave
que o caderno Netafim nao tem: o numero de gomos da curva.

Gera dois CSV:
  data/flanges_irrigafour.csv  furacao por (bitola, norma), 6 normas
  data/cotas_irrigafour.csv    cota por (familia, variante, bitola)

Uso: python3 tools/extrair_irrigafour.py
"""
import csv
import glob
import re
import sys
import types

# a cryptography do sistema esta quebrada e o pdfminer so a usa para PDF cifrado
for _m in ("cryptography", "cryptography.hazmat", "cryptography.hazmat.primitives",
           "cryptography.hazmat.primitives.ciphers", "cryptography.hazmat.backends",
           "cryptography.hazmat.primitives.ciphers.algorithms",
           "cryptography.hazmat.primitives.ciphers.modes"):
    sys.modules[_m] = types.ModuleType(_m)
sys.modules["cryptography.hazmat.primitives.ciphers"].Cipher = object
sys.modules["cryptography.hazmat.primitives.ciphers"].algorithms = object
sys.modules["cryptography.hazmat.primitives.ciphers"].modes = object
sys.modules["cryptography.hazmat.backends"].default_backend = lambda: None

import pdfplumber  # noqa: E402

FICHAS = "data/fichas/IRRIGAFOUR_catalogo_parte*.pdf"
SAIDA_FLANGE = "data/flanges_irrigafour.csv"
SAIDA_COTA = "data/cotas_irrigafour.csv"

# titulo da pagina -> familia, variante, nomes das cotas na ordem, tem coluna C
PAGINAS = {
    "CURVA 90° AZ FL 4 GOMOS":       ("CURVA", "90/4gomos", ["C"], False),
    "CURVA 90° AZ FL 3 GOMOS":       ("CURVA", "90/3gomos", ["C"], False),
    "CURVA 90° AZ FL SAÍDA 4 GOMOS": ("CURVA_SAIDA", "90/4gomos", ["C", "D"], False),
    "CURVA 90° AZ FL SAÍDA 3 GOMOS": ("CURVA_SAIDA", "90/3gomos", ["C", "D"], False),
    "CURVA 60° AZ FL 3 GOMOS":       ("CURVA", "60/3gomos", ["C", "D"], False),
    "CURVA 60° AZ FL 2 GOMOS":       ("CURVA", "60/2gomos", ["C", "D"], False),
    "CURVA 45° AZ FL 3 GOMOS":       ("CURVA", "45/3gomos", ["C", "D"], False),
    "CURVA 45° AZ FL 2 GOMOS":       ("CURVA", "45/2gomos", ["C", "D"], False),
    "CURVA 30° AZ FL 2 GOMOS":       ("CURVA", "30/2gomos", ["C", "D"], False),
    "CURVA DUPLA AZ FL":             ("CURVA_DUPLA", "", ["C", "D"], False),
    "REDUÇÃO CONCÊNTRICA (AUMENTO AZ FL)": ("REDUCAO_CONCENTRICA", "", ["E"], True),
    "REDUÇÃO EXCÊNTRICA AZ FL":      ("REDUCAO_EXCENTRICA", "", ["E"], True),
    "DERIVADO T AZ FL":              ("TE", "", ["E", "F"], True),
    "DERIVADO T 45° AZ FL":          ("TE_45", "", ["C", "D"], False),
    "PEÇAS Y AZ FL":                 ("Y", "", ["E", "F"], True),
    "PEÇA Y 45° AZ FL":              ("Y_45", "", ["C", "D"], False),
    "MANIFOLD AZ FL":                ("MANIFOLD", "", ["C", "D", "E", "F"], False),
    "CRUZETA AZ FL":                 ("CRUZETA", "", ["C", "D"], False),
    "CRIVOS AZ FL":                  ("CRIVO", "", ["C"], False),
    "ARTICULADOR FLEXÍVEL AZ FL":    ("ARTICULADOR", "", ["C_tubo", "D_conjunto"], False),
    "ANCORAGEM AZ":                  ("ANCORAGEM", "", ["C"], False),
    "ANCORAGEM MEIA LUA AZ":         ("ANCORAGEM_MEIA_LUA", "", ["C_altura"], False),
    "ADAPTADOR ESPIGÃO AZ FL":       ("ADAPTADOR_ESPIGAO", "", ["C"], False),
    "PEÇA TRANS. C/ NIPLE AZ FL":    ("PECA_TRANSICAO_NIPLE", "", ["C"], False),
    "PEÇA TRANS. C/ LUVA AZ FL":     ("PECA_TRANSICAO_LUVA", "", ["C"], False),
}
TITULO_FLANGE = "FLANGES"
TITULO_TUBO = "TUBO FL AZ"

RX_BITOLA = re.compile(r'^(\d+(?:\.\d+/\d+)?)"$')
RX_INTEIRO = re.compile(r"^\d{2,4}$")
RX_MEDIDA_FLANGE = re.compile(r"^\d{1,4}(?:,\d+)?$")
RX_TIPO = re.compile(r"^\d+,\d+m$")


def polegada(texto):
    """1.1/4" -> 1.25 ; 8" -> 8.0"""
    m = RX_BITOLA.match((texto or "").strip())
    if not m:
        return None
    bruto = m.group(1)
    if "." in bruto and "/" in bruto:
        inteiro, fracao = bruto.split(".", 1)
        a, b = fracao.split("/")
        return int(inteiro) + int(a) / int(b)
    return float(bruto)


def celulas(linha):
    return [(c or "").replace("\n", " ").strip() for c in linha]


def paginas():
    arquivos = sorted(glob.glob(FICHAS))
    if not arquivos:
        sys.exit(f"nenhum PDF em {FICHAS}")
    for arq in arquivos:
        parte = re.search(r"parte(\d)", arq).group(1)
        with pdfplumber.open(arq) as pdf:
            for i, pagina in enumerate(pdf.pages, 1):
                yield f"{parte}.{i:02d}", pagina


def main():
    flanges, cotas = [], []
    contexto = None          # (familia, variante, nomes, tem_c) da ultima pagina titulada
    modo = None              # "flange" | "cota" | None
    dn_a = None              # A corrente, para as tabelas agrupadas
    vistos = set()

    for tag, pagina in paginas():
        tabela = pagina.extract_table()
        if not tabela:
            continue
        titulo = next((c for c in celulas(tabela[0]) if c), "")
        titulo = titulo.split("\n")[0].strip()

        if titulo == TITULO_FLANGE:
            modo, contexto = "flange", None
        elif titulo.startswith(TITULO_TUBO):
            modo = None                       # tabela do tubo nao sai em celula
        elif titulo in PAGINAS:
            modo, contexto = "cota", PAGINAS[titulo]
            dn_a = None
        # sem titulo conhecido: pagina de continuacao, mantem modo e contexto

        for linha in tabela:
            campos = celulas(linha)
            bitolas = [polegada(c) for c in campos]
            bitolas = [b for b in bitolas if b is not None]
            numeros = [int(c) for c in campos if RX_INTEIRO.match(c)]

            if modo == "flange":
                # a quantidade de furos tem um digito so ate 8 furos, e o
                # diametro do furo ANSI vem em polegada convertida (25,4)
                numeros = [float(c.replace(",", ".")) for c in campos
                           if RX_MEDIDA_FLANGE.match(c)]
                norma = next((c for c in campos
                              if c.startswith("DIN") or c.startswith("ANSI")), None)
                if not bitolas or not norma or len(numeros) < 4:
                    continue
                externo, interno, furos, furo = numeros[-4:]
                externo, interno, furos = int(externo), int(interno), int(furos)
                chave = (bitolas[0], norma)
                if chave in vistos:
                    continue
                vistos.add(chave)
                flanges.append({
                    "dn_pol": f"{bitolas[0]:g}", "norma": norma,
                    "esp_flange_pol": next((c for c in campos if "/" in c and '"' in c
                                            and polegada(c) is None), ""),
                    "d_externo_mm": externo, "d_interno_mm": interno,
                    "furos": furos, "d_furo_mm": f"{furo:g}", "pagina": tag,
                })
                continue

            if modo != "cota" or not contexto:
                continue
            familia, variante, nomes, tem_c = contexto
            if not bitolas or len(numeros) < len(nomes):
                continue

            var = variante
            if familia == "CURVA_DUPLA":
                var = next((c for c in campos if RX_TIPO.match(c)), var)

            if tem_c:
                if len(bitolas) >= 2:
                    dn_a, dn_c = bitolas[0], bitolas[1]
                elif dn_a is not None:
                    dn_c = bitolas[0]
                else:
                    continue
            else:
                dn_a, dn_c = bitolas[0], None

            for nome, valor in zip(nomes, numeros[-len(nomes):]):
                cotas.append({
                    "familia": familia, "variante": var,
                    "dn_a_pol": f"{dn_a:g}",
                    "dn_c_pol": f"{dn_c:g}" if dn_c is not None else "",
                    "cota": nome, "valor_mm": valor, "pagina": tag,
                })

    with open(SAIDA_FLANGE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, ["dn_pol", "norma", "esp_flange_pol", "d_externo_mm",
                                "d_interno_mm", "furos", "d_furo_mm", "pagina"])
        w.writeheader()
        w.writerows(flanges)
    with open(SAIDA_COTA, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, ["familia", "variante", "dn_a_pol", "dn_c_pol",
                                "cota", "valor_mm", "pagina"])
        w.writeheader()
        w.writerows(cotas)

    familias = sorted({c["familia"] for c in cotas})
    print(f"{len(flanges)} linhas de flange -> {SAIDA_FLANGE}")
    print(f"{len(cotas)} cotas em {len(familias)} familias -> {SAIDA_COTA}")
    for f in familias:
        n = sum(1 for c in cotas if c["familia"] == f)
        print(f"  {f:24} {n:4}")


if __name__ == "__main__":
    main()
