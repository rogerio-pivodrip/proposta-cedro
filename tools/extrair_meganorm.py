#!/usr/bin/env python3
"""Le a tabela de medidas da KSB Meganorm (METN), pagina 9 do manual A2742.

A folha e a Tabela 06, "Tabela de medidas (mm)", com as letras da EN 733 /
ISO 2858 - a Meganorm e normalizada, entao as letras sao as da norma e nao
as do fabricante:

  a   da face do flange de succao ao EIXO do flange de descarga (horizontal)
  f   do eixo da descarga ao fim do mancal
  h1  da base ao eixo da bomba
  h2  da base a FACE do flange de descarga
  b   largura do pe
  m1 m2 n1 n2 s1 s2 v w   a furacao do pe
  d1 l t u                 a ponta do eixo, para a luva

Isso liga direto no que ja existe para a Megabloc, que usa outras letras para
as mesmas tres medidas:

  Meganorm a       = Megabloc c
  Meganorm h1      = Megabloc b
  Meganorm h2 - h1 = Megabloc a

A tabela tem celula mesclada em quase toda coluna - o valor vale para as
linhas de baixo ate aparecer outro. O pdfplumber devolve None nessas celulas,
entao arrastar o ultimo valor para baixo E a leitura certa, nao um remendo.

Uso: python3 tools/extrair_meganorm.py > data/bombas_ksb_meganorm.csv
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
PAGINA = 9
# a ordem das colunas depois do nome do tamanho. O cabecalho junta d1 e m6
# numa celula so, entao m6 nao sai - e nao faz falta para a vista lateral.
COLUNAS = ["dn1_mm", "dn2_mm", "a_mm", "f_mm", "h1_mm", "h2_mm", "b_mm",
           "g1_mm", "g2_mm", "l1_mm", "m1_mm", "m2_mm", "m3_mm", "n1_mm",
           "n2_mm", "n3_mm", "n4_mm", "s1_mm", "s2_mm", "v_mm", "w_mm",
           "d1_mm", "l_mm", "t_mm", "u_mm", "x_mm"]
RX_TAMANHO = re.compile(r"^\d{2,3}-\d{3}(\.\d)?$")
FONTE = "KSB Meganorm manual tecnico A2742.0P/8, tabela 06"
# a nota da folha: esses dois nao sao previstos na ISO 2858
FORA_DA_ISO = {"25-150", "25-200"}


def numero(texto):
    if texto is None:
        return None
    texto = texto.strip().replace(",", ".")
    return texto if re.fullmatch(r"\d+(\.\d+)?", texto) else None


def main():
    pdf = pdfplumber.open(MANUAL)
    bruto = pdf.pages[PAGINA - 1].extract_table(
        {"vertical_strategy": "lines", "horizontal_strategy": "lines"})
    corrente = {}
    linhas = []
    for linha in bruto or []:
        tamanho = (linha[0] or "").strip()
        if not RX_TAMANHO.fullmatch(tamanho):
            continue
        registro = {"tamanho": tamanho}
        for i, campo in enumerate(COLUNAS, start=1):
            valor = numero(linha[i]) if i < len(linha) else None
            if valor is not None:
                corrente[campo] = valor      # celula nova: passa a valer daqui
            registro[campo] = corrente.get(campo, "")
        registro["rotor_mm"] = tamanho.split("-")[1].split(".")[0]
        registro["iso_2858"] = int(tamanho not in FORA_DA_ISO)
        registro["fonte"] = FONTE
        linhas.append(registro)

    campos = ["tamanho", "rotor_mm"] + COLUNAS + ["iso_2858", "fonte"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow(linha)
    print(f"# {len(linhas)} tamanhos lidos da pagina {PAGINA}", file=sys.stderr)


if __name__ == "__main__":
    main()
