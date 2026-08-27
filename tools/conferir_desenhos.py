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
import re
import sys

DESENHOS = "data/desenhos_netafim.csv"
CATALOGO = "data/catalogo.json"
FAIXA = range(3, 15)


# Pontas que nao sao o padrao da casa: engate K nao e usado na casa de maquinas,
# e EN 1092, ANSI, ponta lisa e rosca so aparecem na transicao com equipamento.
RX_FORA_DO_PADRAO = re.compile(
    r"\bK10\b|\bK\d+\b|EN\s?1092|ANSI|Ponta\s?Lisa|Rosca|bsp", re.I)
RX_PADRAO = re.compile(r"NBR\s?7675", re.I)


def familia_da_pagina(linhas, catalogo):
    """A pagina nao diz que peca desenha, mas os codigos ja cadastrados dizem."""
    familias = {}
    por_pagina = collections.defaultdict(list)
    for x in linhas:
        por_pagina[x["pagina"]].append(x)
    for pagina, itens in por_pagina.items():
        contagem = collections.Counter(
            catalogo[x["sap"]]["familia"] for x in itens
            if x["sap"] in catalogo and catalogo[x["sap"]]["familia"])
        familias[pagina] = contagem.most_common(1)[0][0] if contagem else None
    return familias


def _paginas_orfas(linhas, catalogo):
    """Pagina inteira fora da lista: a peca esta desenhada e nenhum codigo dela
    existe na LM. E o caso mais grave, porque nao e variante - e peca."""
    por_pagina = collections.defaultdict(list)
    for x in linhas:
        por_pagina[x["pagina"]].append(x)
    saida = []
    for pagina, itens in sorted(por_pagina.items(), key=lambda t: int(t[0])):
        citados = [x["sap"] for x in itens if x["sap"]]
        if not citados:
            continue
        dentro = [s for s in citados if s in catalogo]
        if dentro:
            continue
        cadastrar = sum(1 for x in itens if x["situacao"] == "CADASTRAR")
        saida.append(f'  pag {pagina:>3}: {len(citados)} codigos citados, '
                     f'nenhum na LM, mais {cadastrar} marcados CADASTRAR')
        exemplo = itens[0]
        saida.append(f'          {exemplo["dn_pol"]}" {exemplo["cotas"][:56]}')
    if not saida:
        return ""
    return "\npaginas em que a peca inteira esta fora da LM:\n" + "\n".join(saida)


def _necessidade(linhas, catalogo, detalhar):
    """Separa o que falta cadastrar entre padrao da casa e variante."""
    familias = familia_da_pagina(linhas, catalogo)
    padrao, variante = [], []
    for x in linhas:
        if x["situacao"] != "CADASTRAR" or int(x["dn_pol"]) not in FAIXA:
            continue
        x = dict(x, familia=familias.get(x["pagina"]) or "?")
        fora = RX_FORA_DO_PADRAO.search(x["cotas"])
        if fora and not RX_PADRAO.search(x["cotas"]):
            x["motivo"] = fora.group(0)
            variante.append(x)
        elif fora:
            x["motivo"] = f'uma ponta em {fora.group(0)}'
            variante.append(x)
        else:
            padrao.append(x)

    saida = [f'\ndas {len(padrao) + len(variante)} posicoes CADASTRAR entre '
             f'3" e 14":']
    saida.append(f'  {len(padrao):3d} sao padrao da casa - FL NBR7675 PN16 nas '
                 "duas pontas: FALTA MESMO")
    for x in padrao:
        saida.append(f'      pag {x["pagina"]:>3}  {x["dn_pol"]:>2}"  '
                     f'{x["familia"]:22s} {x["cotas"][:44]}')
    saida.append(f'  {len(variante):3d} sao variante que a casa nao usa '
                 "ou so usa na transicao")
    if detalhar:
        for x in variante:
            saida.append(f'      pag {x["pagina"]:>3}  {x["dn_pol"]:>2}"  '
                         f'{x["familia"]:22s} ({x["motivo"]}) '
                         f'{x["cotas"][:36]}')
    else:
        conta = collections.Counter(x["motivo"] for x in variante)
        for motivo, quantos in conta.most_common():
            saida.append(f'      {quantos:3d}  {motivo}')
    return "\n".join(saida)


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

    print(_necessidade(linhas, catalogo, detalhar))
    print(_paginas_orfas(linhas, catalogo))

    truncados = [x for x in linhas if x["situacao"] == "indefinido"]
    if truncados:
        print(f'\n{len(truncados)} posicoes sem codigo legivel - o PDF corta o '
              "texto da coluna. Conferir a mao nas paginas: " +
              ", ".join(sorted({x["pagina"] for x in truncados}, key=int)[:12]))


if __name__ == "__main__":
    main()
