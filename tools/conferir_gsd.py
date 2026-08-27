#!/usr/bin/env python3
"""Confere a folha dimensional da GSD, que veio de tabela com celula mesclada.

Celula mesclada e o feitio de tabela mais facil de ler errado: o valor aparece
uma vez e vale para o grupo, e quem le linha a linha herda do vizinho de cima
em vez do proprio grupo. As guardas de tools/extrair_gsd.py corrigem isso; este
teste confere se corrigiram.

Quatro perguntas, e as quatro a folha responde sozinha:

  o NOME diz o DN2? Na GSD 125-250 o 125 e a descarga e o 250 e o rotor - a
  mesma regra do folheto da KSB, ja homologada aqui;
  a succao e sempre uma bitola acima da descarga?
  h1 e h2 CRESCEM com o rotor dentro da mesma descarga?
  f1 e f2 valem o mesmo em todo o grupo do suporte? Sao cotas que medem do
  flange do motor, entao pertencem ao suporte e nao a bomba.

Uso: python3 tools/conferir_gsd.py
"""
import collections
import csv
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402
from motor.bomba import MM_PARA_POLEGADA  # noqa: E402

TABELA = "data/bombas_gsd.csv"


def main():
    linhas = list(csv.DictReader(open(TABELA, encoding="utf-8")))
    print(f"{len(linhas)} modelos na folha dimensional 406.1\n")

    erros = 0

    print("== o nome diz o DN2?")
    fora = [r["modelo"] for r in linhas
            if float(r["dn2_mm"]) != float(r["modelo"].split("-")[0])]
    print(f"  {len(linhas) - len(fora)} de {len(linhas)} conferem"
          + (f" · fora: {', '.join(fora)}" if fora else ""))
    erros += len(fora)

    # A succao e SEMPRE maior que a descarga, mas nao e um tamanho fixo acima:
    # na EBARA a 40-125 tem succao DN50 e a 40-200 tem DN65. Quem manda e a
    # folha; o invariante que da para cobrar dela e so a desigualdade.
    print("\n== a sucção é maior que a descarga?")
    fora = [r["modelo"] for r in linhas
            if float(r["dn1_mm"]) <= float(r["dn2_mm"])]
    print(f"  {len(linhas) - len(fora)} de {len(linhas)} conferem"
          + (f" · fora: {', '.join(fora)}" if fora else ""))
    erros += len(fora)
    pares = sorted({(float(r["dn2_mm"]), float(r["dn1_mm"])) for r in linhas})
    print("  pares que a folha dá: "
          + ", ".join(f"{d2:.0f}→{d1:.0f}" for d2, d1 in pares))

    print("\n== h1 e h2 crescem com o rotor, na mesma descarga?")
    series = collections.defaultdict(list)
    for r in linhas:
        rotor = float(r["modelo"].split("-")[1].rstrip("L").split(".")[0])
        series[r["dn2_mm"]].append((rotor, float(r["h1_mm"]),
                                    float(r["h2_mm"])))
    quebras = 0
    for dn2, pontos in sorted(series.items(), key=lambda kv: float(kv[0])):
        pontos.sort()
        for (ra, h1a, h2a), (rb, h1b, h2b) in zip(pontos, pontos[1:]):
            if h1b < h1a or h2b < h2a:
                quebras += 1
                print(f"  DN{float(dn2):.0f}: rotor {ra:.0f}->{rb:.0f} "
                      f"h1 {h1a:.0f}->{h1b:.0f}  h2 {h2a:.0f}->{h2b:.0f}")
    if not quebras:
        print("  todas as séries crescem.")
    erros += quebras

    print("\n== f1 e f2 valem o mesmo em todo o grupo do suporte?")
    por_grupo = collections.defaultdict(set)
    for r in linhas:
        if r["grupo_suporte"]:
            por_grupo[r["grupo_suporte"]].add((r["f1_mm"], r["f2_mm"]))
    for grupo, pares in sorted(por_grupo.items()):
        f1, f2 = sorted(pares)[0]
        marca = "" if len(pares) == 1 else f"  << {len(pares)} valores"
        print(f"  {grupo}  f1={float(f1):.0f}  f2={float(f2):.0f}  "
              f"face de sucção → eixo da descarga = "
              f"{float(f1)-float(f2):.0f} mm{marca}")
        if len(pares) > 1:
            erros += 1

    print("\n== todas montam?")
    nao = []
    for r in linhas:
        try:
            s.bomba_gsd(r["modelo"], 30)
        except Exception as erro:                        # noqa: BLE001
            nao.append(f'{r["modelo"]} ({erro})')
    print(f"  {len(linhas) - len(nao)} de {len(linhas)} montam"
          + (f" · {'; '.join(nao)}" if nao else ""))
    erros += len(nao)

    print(f"\n{erros} problemas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
