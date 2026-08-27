#!/usr/bin/env python3
"""Le a tabela do conjunto Meganorm - secao 15 do manual A2742, paginas 10 a 14.

A tabela 06 (pagina 9) cota a BOMBA. Esta cota o CONJUNTO: para cada tamanho
de bomba, quais carcacas de motor a KSB monta, e qual base perfilada cada
combinacao usa. E o que faltava para o desenho da mancalizada nao ter motor
inventado - a carcaca sai da folha, nao de uma regra de CV.

Colunas cujo significado a Fig.05 deixa claro:

  carcaca  a carcaca IEC do motor (63, 71, 80 ... 225), uma linha por opcao
  a f h1 h2  as mesmas quatro cotas da tabela 06 - repetidas aqui, e por isso
             servem de conferencia cruzada dentro do proprio manual
  base     o numero da base perfilada (BD-0501-B ...)

As demais letras da base - h3, H, H1, G1, k, E, E1, D1 - vao gravadas com o
nome que a folha usa e nada mais. Sem a figura em resolucao maior nao da para
afirmar qual e o comprimento e qual e a furacao, e chutar isso e o que essa
tabela existe para evitar.

A folha tem duas metades espelhadas (dois arranjos de base para a mesma
bomba); esta leitura guarda a primeira, que e a que o desenho usa. E o manual
tem duas secoes de base: 15.1 base perfilada, nas paginas 10 a 15, e 15.2 base
estrutural, da 16 em diante. Esta leitura e da 15.1.

Uso: python3 tools/extrair_meganorm_conjunto.py > data/bombas_ksb_meganorm_conjunto.csv
"""
import csv
import re
import sys
import types

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

MANUAL = "data/fichas/KSB_meganorm_manual_tecnico_A2742.pdf"
# A pagina 10 traz a figura junto com o inicio da tabela, e a coluna sai
# deslocada: a carcaca 100 vira "00" e o H invade o H1. Os quatro tamanhos que
# ficam nela - 25-150, 25-200, 32-125, 32-125.1 - tem recalque de 25 ou 32 mm,
# abaixo de 2", fora do que a casa usa. Entao a leitura comeca na 11.
PAGINAS = range(11, 16)
FONTE = "KSB Meganorm manual tecnico A2742.0P/8, secao 15"
RX_TAMANHO = re.compile(r"^\d{2,3}-\d{3}(\.\d)?$")
RX_CARCACA = re.compile(r"^\d{2,3}[SML]?$")
RX_BASE = re.compile(r"^\d{4}-[A-Z]$")
# colunas 8 a 16 da folha, na ordem do cabecalho
BASE = ["base", "h3_mm", "H_mm", "H1_mm", "G1_mm", "k_mm", "E_mm", "E1_mm",
        "D1_mm"]


def limpa(celula):
    return celula.replace("\n", "").strip() if celula else ""


def main():
    pdf = pdfplumber.open(MANUAL)
    linhas = []
    tamanho = dn1 = dn2 = ""
    cota = {}
    corrente = {}
    for n in PAGINAS:
        tabela = pdf.pages[n - 1].extract_table(
            {"vertical_strategy": "lines", "horizontal_strategy": "lines"})
        for bruta in tabela or []:
            celulas = [limpa(c) for c in bruta]
            if len(celulas) < 17:
                continue
            if RX_TAMANHO.fullmatch(celulas[0]):
                tamanho, dn1, dn2 = celulas[0], celulas[1], celulas[2]
                cota = dict(zip(("a_mm", "f_mm", "h1_mm", "h2_mm"),
                                celulas[4:8]))
                corrente = {}
            if not tamanho or not RX_CARCACA.fullmatch(celulas[3]):
                continue
            for i, campo in enumerate(BASE, start=8):
                valor = celulas[i]
                if campo == "base" and valor and not RX_BASE.fullmatch(valor):
                    valor = ""
                if valor:
                    corrente[campo] = valor
            linhas.append({"tamanho": tamanho, "dn1_mm": dn1, "dn2_mm": dn2,
                           "carcaca_motor": celulas[3], **cota,
                           **{c: corrente.get(c, "") for c in BASE},
                           "fonte": FONTE})

    campos = (["tamanho", "dn1_mm", "dn2_mm", "carcaca_motor", "a_mm", "f_mm",
               "h1_mm", "h2_mm"] + BASE + ["fonte"])
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow(linha)
    tamanhos = len({ln["tamanho"] for ln in linhas})
    print(f"# {len(linhas)} combinacoes bomba x motor, {tamanhos} tamanhos",
          file=sys.stderr)


if __name__ == "__main__":
    main()
