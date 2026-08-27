#!/usr/bin/env python3
"""Le as duas paginas de flange do caderno Netafim e monta a tabela.

Sao duas folhas diferentes e vale a pena separa-las:

  pagina 6  "Flange para soldar - Norma EN 1092-1 PN16"   -> a flange normal,
            a que solda na ponta do tubo de aco. E a mesma peca que entra
            solta no colar de PEAD: muda o que ela aperta, nao o desenho.
  pagina 4  "Flange cega com luva femea 2\" BSP (ISO7)"    -> a flange que
            fecha a linha. A luva de 2" e o furo por onde entra a ventosa
            ou o manometro; existe tambem a versao sem luva.

Da folha da flange cega sai um dado que so ela tem: a luva de 2" BSP mede
30 mm de comprimento por 40 mm de externo - a mesma luva que aparece no
manifold (colunas F3/F4 e G3/G4 da pagina 25).

Uso: python3 tools/extrair_flanges_netafim.py > data/flanges_netafim.csv
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

CADERNO = "data/fichas/NETAFIM_desenhos_tubos_conexoes_aco_PN16_rev20.pdf"
PAGINA_SOLDAR, PAGINA_CEGA = 6, 4

# o OCR troca a aspa da polegada por 1: FL 211 e FL 2", FL 101 e FL 10".
# O diametro em milimetros vem entre parenteses e nao tem essa ambiguidade,
# entao e por ele que a bitola e identificada.
MM_POL = {48: 2, 60: 2.5, 76: 3, 102: 4, 133: 5, 135: 5, 152: 6, 203: 8,
          261: 10, 318: 12, 368: 14, 419: 16, 470: 18, 521: 20, 622: 24}
RX_MM = re.compile(r"\((\d{2,3})\s?MM\)", re.I)
RX_POL_CEGA = re.compile(r"FL\s+CEGA\s+AZ\s+(\d+)\s?\"", re.I)
RX_NUM = re.compile(r"\d+(?:,\d+)?")


RX_ACESSORIO = re.compile(r'C/\s?(LG|FL)\s?\d+\s?"', re.I)


def numeros(linha):
    """So a tabela: fora o codigo SAP na frente e a descricao do acessorio.

    A descricao termina em C/ LG 2" e esse 2 entra no meio dos numeros se a
    linha nao for limpa antes - foi assim que a primeira leitura saiu com
    todas as colunas deslocadas de uma casa.
    """
    corte = re.split(r"PN\s?16", linha, maxsplit=1)
    if len(corte) < 2:
        return []
    return [float(n.replace(",", "."))
            for n in RX_NUM.findall(RX_ACESSORIO.sub("", corte[1]))]


def texto(pdf, pagina):
    return (pdf.pages[pagina - 1].extract_text() or "").splitlines()


def flanges_para_soldar(pdf):
    """45 esp 3 furo_central externo ressalto 360 circulo furo 90 n_furos"""
    for linha in texto(pdf, PAGINA_SOLDAR):
        mm = RX_MM.search(linha)
        if not mm or "FL" not in linha:
            continue
        n = numeros(linha)
        if len(n) < 11:
            continue
        yield {"tipo": "SOLDAR", "norma": "EN 1092-1 PN16",
               "dn_pol": MM_POL.get(int(mm.group(1))), "dn_mm": int(mm.group(1)),
               "esp_mm": n[1], "d_externo_mm": n[4], "d_ressalto_mm": n[5],
               "d_furo_central_mm": n[3], "circulo_mm": n[7], "d_furo_mm": n[8],
               "furos": int(n[10]), "luva_pol": "", "luva_comp_mm": "",
               "luva_externo_mm": "", "pagina": PAGINA_SOLDAR}


def flanges_cegas(pdf):
    """45 esp 3 externo ressalto furo_central circulo furo 90 n_furos x
       + luva 2" bsp femea 30 40"""
    for linha in texto(pdf, PAGINA_CEGA):
        pol = RX_POL_CEGA.search(linha)
        if not pol:
            continue
        n = numeros(linha)
        if len(n) < 11:
            continue
        tem_luva = "bsp" in linha.lower()
        yield {"tipo": "CEGA_COM_LUVA" if tem_luva else "CEGA",
               "norma": "NBR 7675 PN16",
               "dn_pol": float(pol.group(1)), "dn_mm": "",
               "esp_mm": n[1], "d_externo_mm": n[3], "d_ressalto_mm": n[4],
               "d_furo_central_mm": n[5], "circulo_mm": n[6], "d_furo_mm": n[7],
               "furos": int(n[9]),
               "luva_pol": 2 if tem_luva else "",
               "luva_comp_mm": n[-2] if tem_luva else "",
               "luva_externo_mm": n[-1] if tem_luva else "",
               "pagina": PAGINA_CEGA}


def main():
    pdf = pdfplumber.open(CADERNO)
    linhas = list(flanges_para_soldar(pdf)) + list(flanges_cegas(pdf))
    campos = ["tipo", "norma", "dn_pol", "dn_mm", "esp_mm", "d_externo_mm",
              "d_ressalto_mm", "d_furo_central_mm", "circulo_mm", "d_furo_mm",
              "furos", "luva_pol", "luva_comp_mm", "luva_externo_mm", "pagina"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow(linha)


if __name__ == "__main__":
    main()
