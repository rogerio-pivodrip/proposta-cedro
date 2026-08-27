#!/usr/bin/env python3
"""Faixa de cada serie de valvula: que DN tem corpo cadastrado e que DN so
aparece em acessorio.

Quando a mola diz "47-8\" A 14\"" mas nao existe corpo de 14", o acessorio esta
denunciando um buraco de cadastro na lista - a valvula existe na linha do
fabricante, o codigo do corpo e que nao esta na LM.

Uso: python3 tools/conferir_serie_valvula.py [serie ...]
"""
import json
import re
import sys
from collections import defaultdict

CATALOGO = "data/catalogo.json"
RX_SERIE = re.compile(r"\b(\d{2,3})\s?[-/]\s?(\d{1,2})(?:\s?[\"'])")
# A faixa exige aspas no primeiro numero e so aceita A/ATE como ligacao: com
# hifen ela casaria "47-8", que e serie e bitola, nao uma faixa.
RX_FAIXA = re.compile(r'(\d{1,2})\s?"\s*(?:A|ATE)\s*(\d{1,2})\s?"')


def dns_citados(descricao, serie):
    """DN que a descricao associa a essa serie, inclusive faixas."""
    achados = set()
    for m in RX_SERIE.finditer(descricao):
        if m.group(1) == serie:
            achados.add(float(m.group(2)))
    if serie in descricao:
        for m in RX_FAIXA.finditer(descricao):
            inicio, fim = int(m.group(1)), int(m.group(2))
            if inicio < fim:
                achados.update(float(d) for d in (inicio, fim))
    return achados


def main():
    catalogo = json.load(open(CATALOGO, encoding="utf-8"))
    series = sys.argv[1:] or ["47", "75", "96", "405"]
    for serie in series:
        corpos, acessorios = set(), defaultdict(list)
        duplicados = defaultdict(list)
        for item in catalogo:
            desc = item["descricao"].upper()
            if not re.search(rf"\b{serie}\s?[-/]", desc):
                continue
            if item["familia"] == "VALVULA_HIDRAULICA":
                for dn in item["dn"]:
                    corpos.add(dn)
                    duplicados[dn].append(item["sap"])
            else:
                for dn in dns_citados(desc, serie):
                    acessorios[dn].append(item["sap"])

        print(f'\n== serie {serie} ==')
        print("  corpos cadastrados:",
              ", ".join(f'{d:g}"' for d in sorted(corpos)) or "nenhum")
        so_acessorio = sorted(d for d in acessorios if d not in corpos)
        for dn in so_acessorio:
            print(f'  ! {dn:g}" aparece so em acessorio '
                  f'({", ".join(acessorios[dn])}) - falta o corpo na lista')
        for dn, saps in sorted(duplicados.items()):
            if len(saps) > 1:
                print(f'  ? {dn:g}" tem {len(saps)} codigos: {", ".join(saps)}')


if __name__ == "__main__":
    main()
