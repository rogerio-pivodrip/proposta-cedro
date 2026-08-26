#!/usr/bin/env python3
"""Importa a Lista de Materiais (xlsx Netafim) para JSON bruto.

Uso: python3 tools/importar_catalogo.py [caminho.xlsx] [saida.json]
"""
import json
import sys
import warnings

import openpyxl

PADRAO_XLSX = "data/LM_CANAL_REV1_JUL26.xlsx"
PADRAO_SAIDA = "data/catalogo_bruto.json"


def importar(caminho):
    warnings.simplefilter("ignore")
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    ws = wb["Materiais"]
    itens = []
    for linha in ws.iter_rows(min_row=3, values_only=True):
        codigo = linha[0]
        if not codigo:
            continue
        itens.append(
            {
                "sap": str(codigo).strip(),
                "descricao": " ".join(str(linha[1] or "").replace("\xa0", " ").split()),
                "un": (linha[2] or "").strip() if isinstance(linha[2], str) else linha[2],
                "grupo": linha[3],
                "procedencia": linha[4],
            }
        )
    wb.close()
    return itens


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else PADRAO_XLSX
    saida = sys.argv[2] if len(sys.argv) > 2 else PADRAO_SAIDA
    itens = importar(caminho)
    with open(saida, "w", encoding="utf-8") as fh:
        json.dump(itens, fh, ensure_ascii=False, indent=1)
    print(f"{len(itens)} itens -> {saida}")


if __name__ == "__main__":
    main()
