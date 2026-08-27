#!/usr/bin/env python3
"""Confere a regra do bocal da bomba contra a tabela de dimensoes da KSB.

A regra ENTRADA_PELA_SAIDA saiu de medir a lista da Netafim: uma bomba que
declara so a saida tem a entrada uma bitola acima. O catalogo do fabricante e
uma fonte independente - e diz o DN dos dois bocais em texto, sem inferencia.

Uso: python3 tools/conferir_bomba_ksb.py
"""
import csv
import json
import re
import sys

sys.path.insert(0, ".")
from motor import bomba, regras  # noqa: E402

TABELA = "data/bombas_ksb_megabloc.csv"


def mm(polegada):
    for pol, dn in regras.POLEGADA_PARA_DN.items():
        if abs(pol - polegada) < 0.01:
            return dn
    return None


def main():
    pares = {}
    for r in csv.DictReader(open(TABELA, encoding="utf-8")):
        s = mm(float(r["dn_recalque_pol"]))    # o nome da bomba e a saida
        e = mm(float(r["dn_succao_pol"]))
        if s and e:
            pares.setdefault(s, set()).add(e)

    print("== bocal da bomba: regra da casa x catalogo KSB Megabloc")
    bate = falta = diverge = 0
    for saida in sorted(pares):
        nossa, quantas = bomba.entrada_presumida(saida)
        ksb = sorted(pares[saida])
        if nossa is None:
            print(f"  saida {saida:>3}mm  regra nao tem       KSB {ksb}")
            falta += 1
        elif [nossa] == ksb:
            print(f"  saida {saida:>3}mm  entrada {nossa:>3}mm "
                  f"({quantas} bombas na lista)   KSB confirma")
            bate += 1
        else:
            print(f"  saida {saida:>3}mm  regra diz {nossa}   KSB diz {ksb}   DIVERGE")
            diverge += 1
    print(f"  -> {bate} confirmadas, {diverge} divergentes, {falta} sem regra")

    faixa = [r for r in csv.DictReader(open(TABELA, encoding="utf-8"))
             if r["polos"] == "4" and float(r["dn_succao_pol"]) >= 3]
    print(f"\n== ancora do desenho: {len(faixa)} tamanhos com succao de 3\" ou mais")
    print(f"  {'tamanho':10} {'succao':>7} {'recalque':>9} {'eixo(b)':>8} "
          f"{'a':>5} {'c':>5}  flange")
    for r in faixa:
        print(f"  {r['tamanho']:10} {r['dn_succao_pol']+chr(34):>7} "
              f"{r['dn_recalque_pol']+chr(34):>9} {r['b_mm']:>8} "
              f"{r['a_mm']:>5} {r['c_mm']:>5}  {r['norma_flange']}")
    casar_com_a_lista()


def casar_com_a_lista():
    """Liga os codigos METB da lista aos tamanhos do catalogo.

    O nome na lista tem tres grupos - entrada, saida, rotor - e o catalogo
    nomeia com dois, saida e rotor, deixando a entrada implicita. Entao
    METB 150-125-200 e o tamanho 125-200 do catalogo, com succao de 150.
    """
    tabela = {r["tamanho"]: r for r in csv.DictReader(open(TABELA, encoding="utf-8"))
              if r["polos"] == "4"}
    catalogo = json.load(open("data/catalogo.json", encoding="utf-8"))
    metb = [i for i in catalogo if i.get("familia") == "BOMBA"
            and re.search(r"\bMETB\b", i["descricao"])]
    achou = perdeu = 0
    faltando = set()
    for item in metb:
        m = re.search(r"(\d{2,3})-(\d{2,3})-(\d{2,4})", item["descricao"])
        if not m:
            m2 = re.search(r"(\d{2,3})-(\d{2,4})(?!\d)", item["descricao"])
            chave = (f"{int(m2.group(1))}-{int(m2.group(2))}") if m2 else None
        else:
            chave = f"{int(m.group(2))}-{int(m.group(3))}"
        if chave and chave in tabela:
            achou += 1
        else:
            perdeu += 1
            if chave:
                faltando.add(chave)
    print(f"\n== lista x catalogo: {len(metb)} codigos METB")
    print(f"  {achou} tem dimensao na tabela, {perdeu} nao")
    if faltando:
        print(f"  tamanhos citados na lista e ausentes do folheto: "
              f"{', '.join(sorted(faltando))}")


if __name__ == "__main__":
    main()
