#!/usr/bin/env python3
"""Confronta o catalogo Irrigafour com o que ja esta tabelado no repositorio.

Duas perguntas:
  1. a furacao que geramos da NBR 7675 bate com uma fonte independente?
  2. a cota de cada familia e a mesma entre fabricantes?

Rode tools/extrair_irrigafour.py antes.
Uso: python3 tools/conferir_irrigafour.py
"""
import collections
import csv

FLANGES = "data/flanges_irrigafour.csv"
COTAS = "data/cotas_irrigafour.csv"
NOSSA_FURACAO = "data/regras_furacao.csv"
NOSSA_COTA = "data/cotas_por_familia.csv"

CASA = [2, 2.5, 3, 4, 5, 6, 8, 10, 12, 14]   # bitolas da casa de maquinas


def ler(caminho, comentario=False):
    linhas = open(caminho, encoding="utf-8")
    if comentario:
        linhas = (l for l in linhas if not l.startswith("#"))
    return list(csv.DictReader(linhas))


def furacao():
    irri = {(float(r["dn_pol"]), r["norma"]): r for r in ler(FLANGES)}
    nossa = {(float(r["dn_pol"]), r["norma"]): r
             for r in ler(NOSSA_FURACAO, comentario=True) if r["dn_pol"]}

    print("== FURACAO: nossa NBR PN16 x DIN 2533 PN16 do Irrigafour")
    bate = diverge = 0
    for dn in CASA:
        a, b = nossa.get((dn, "NBR PN16")), irri.get((dn, "DIN 2533 PN 16"))
        if not a or not b:
            print(f"  {dn:>4g}\"  sem par para comparar")
            continue
        igual = int(a["furos"]) == int(b["furos"])
        bate, diverge = bate + igual, diverge + (not igual)
        print(f"  {dn:>4g}\"  {a['furos']:>2} x {b['furos']:>2} furos"
              f"   {'ok' if igual else 'DIVERGE'}")
    print(f"  -> {bate} confirmadas, {diverge} divergentes\n")

    print("== ARMADILHA: onde PN10 e PN16 tem furacao diferente")
    for dn in CASA:
        p10, p16 = irri.get((dn, "DIN 2532 PN 10")), irri.get((dn, "DIN 2533 PN 16"))
        if p10 and p16 and p10["furos"] != p16["furos"]:
            print(f"  {dn:>4g}\"  PN10 = {p10['furos']} furos,"
                  f"  PN16 = {p16['furos']} furos")
    print()


def cotas():
    irri = ler(COTAS)
    nossa = {(r["familia"], r["variante"], float(r["dn_pol"])): float(r["cota_mm"])
             for r in ler(NOSSA_COTA)}

    print("== COTA: caderno Netafim x catalogo Irrigafour")

    red = collections.defaultdict(set)
    for r in irri:
        if r["familia"] == "REDUCAO_CONCENTRICA" and r["cota"] == "E":
            maior = max(float(r["dn_a_pol"]), float(r["dn_c_pol"]))
            red[maior].add(int(r["valor_mm"]))
    print("  reducao concentrica (Netafim: face a face | Irrigafour: E, corpo)")
    for dn in CASA:
        if dn in red:
            print(f"    {dn:>4g}\"  netafim {nossa.get(('REDUCAO', '', dn), '-'):>6}"
                  f"   irrigafour {sorted(red[dn])}")

    cur = collections.defaultdict(dict)
    for r in irri:
        if r["familia"] == "CURVA" and r["cota"] == "C":
            cur[r["variante"]][float(r["dn_a_pol"])] = int(r["valor_mm"])
    print("\n  curva 90 (perna face a face)")
    for dn in CASA:
        n = nossa.get(("CURVA", "90", dn))
        i = cur.get("90/4gomos", {}).get(dn)
        if n and i:
            print(f"    {dn:>4g}\"  netafim {n:>6.0f}   irrigafour {i:>6}"
                  f"   delta {i - n:+.0f}")

    g3 = cur.get("90/3gomos", {})
    g4 = cur.get("90/4gomos", {})
    iguais = sum(1 for dn in g4 if g3.get(dn) == g4[dn])
    print(f"\n  gomos: {iguais} de {len(g4)} bitolas tem C identico entre 3 e 4 gomos"
          f" -> gomo e fabricacao, nao geometria")

    cri = {float(r["dn_a_pol"]): int(r["valor_mm"])
           for r in irri if r["familia"] == "CRIVO" and r["cota"] == "C"}
    print("\n  crivo (Netafim: cone | Irrigafour: cesto cilindrico)")
    for dn in CASA:
        if dn in cri:
            print(f"    {dn:>4g}\"  netafim {nossa.get(('CRIVO', '', dn), '-'):>6}"
                  f"   irrigafour {cri[dn]:>6}")


def main():
    furacao()
    cotas()


if __name__ == "__main__":
    main()
