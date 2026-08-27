#!/usr/bin/env python3
"""Caderno de desenhos x lista de materiais: onde os dois discordam.

O caderno de desenhos Netafim (rev.20) e a LM Canal sao duas fontes que deviam
concordar e nao concordam. Este relatorio mostra os dois sentidos:

  - codigo que o desenho cita e a lista nao tem;
  - posicao que a propria Netafim marcou "CADASTRAR" no desenho, ou seja, peca
    desenhada que ainda nao virou codigo.

Uso: python3 tools/conferir_desenhos.py [-v]
"""
import collections
import csv
import json
import sys

DESENHOS = "data/desenhos_netafim.csv"
CATALOGO = "data/catalogo.json"
FAIXA = range(3, 15)


def main():
    detalhar = "-v" in sys.argv
    with open(DESENHOS, encoding="utf-8") as fh:
        linhas = list(csv.DictReader(fh))
    with open(CATALOGO, encoding="utf-8") as fh:
        catalogo = {i["sap"]: i for i in json.load(fh)}

    citados = {x["sap"] for x in linhas if x["sap"]}
    ausentes = sorted(s for s in citados if s not in catalogo)
    print(f"caderno de desenhos: {len(linhas)} posicoes, "
          f"{len(citados)} codigos citados")
    print(f"  na LM Canal:        {len(citados) - len(ausentes)}")
    print(f"  fora da LM Canal:   {len(ausentes)}")
    if detalhar:
        for sap in ausentes:
            exemplo = next(x for x in linhas if x["sap"] == sap)
            print(f'    {sap}  pag {exemplo["pagina"]:>3}  '
                  f'{exemplo["dn_pol"]:>2}"  {exemplo["cotas"][:52]}')

    cadastrar = [x for x in linhas if x["situacao"] == "CADASTRAR"]
    na_faixa = [x for x in cadastrar if int(x["dn_pol"]) in FAIXA]
    print(f'\nposicoes marcadas CADASTRAR pela Netafim: {len(cadastrar)}')
    print(f'  dentro de 3" a 14": {len(na_faixa)}')
    por_dn = collections.Counter(int(x["dn_pol"]) for x in cadastrar)
    print("  por bitola: " + ", ".join(f'{d}"={por_dn[d]}'
                                       for d in sorted(por_dn)))
    if detalhar:
        for x in na_faixa:
            print(f'    pag {x["pagina"]:>3}  {x["dn_pol"]:>2}"  '
                  f'{x["cotas"][:56]}')

    truncados = [x for x in linhas if x["situacao"] == "indefinido"]
    if truncados:
        print(f'\n{len(truncados)} posicoes sem codigo legivel - o PDF corta o '
              "texto da coluna. Conferir a mao nas paginas: " +
              ", ".join(sorted({x["pagina"] for x in truncados}, key=int)[:12]))


if __name__ == "__main__":
    main()
