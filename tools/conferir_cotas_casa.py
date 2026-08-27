#!/usr/bin/env python3
"""Confere a tabela medida no DXF da casa: o que serve e o que nao serve.

Duas razoes para uma cota medida nao servir:

  discordante  a mesma peca foi medida duas vezes com resultado diferente
               acima de 10%. Quase sempre e rotulo grudado na peca errada, e
               nesse caso nao da para escolher uma das duas leituras - a
               chave inteira sai.
  suspeita     a casa declarou que aquela familia pode ter entrado fora de
               escala. Hoje e so o registro de gaveta.

Confere tambem se a serie de cada familia CRESCE com a bitola: cota que
diminui quando a bitola aumenta e leitura errada, nao peca estranha.

Uso: python3 tools/conferir_cotas_casa.py
"""
import collections
import sys

sys.path.insert(0, ".")
from motor import cotas  # noqa: E402


def main():
    leituras = cotas.leituras_da_casa()
    boas = {k: v for k, v in leituras.items() if v["confiavel"]}
    discordantes = {k: v for k, v in leituras.items() if not v["concorda"]}
    suspeitas = {k: v for k, v in leituras.items()
                 if v["concorda"] and not v["confiavel"]}

    print(f"{len(leituras)} cotas medidas · {len(boas)} servem · "
          f"{len(discordantes)} discordantes · {len(suspeitas)} suspeitas\n")

    print("== por familia")
    por = collections.Counter(k[0] for k in boas)
    for familia, n in sorted(por.items()):
        print(f"  {n:3}  {familia}")

    if discordantes:
        print(f"\n== discordantes: medidas duas vezes, respostas diferentes")
        for chave in sorted(discordantes)[:14]:
            v = discordantes[chave]
            print(f"  {chave[0]:18} {chave[1] or '-':>4} DN{chave[2]:<6g} "
                  f"{chave[4]:18} {v['minimo']:8.1f} .. {v['maximo']:8.1f}")
    if suspeitas:
        print(f"\n== suspeitas: a casa avisou que podem estar fora de escala")
        for chave in sorted(suspeitas):
            v = suspeitas[chave]
            print(f"  {chave[0]:18} {chave[1] or '-':>4} DN{chave[2]:<6g} "
                  f"{chave[4]:18} {v['valor']:8.1f}")

    print("\n== a serie cresce com a bitola?")
    series = collections.defaultdict(list)
    for (familia, variante, dn, menor, significado), v in boas.items():
        series[(familia, variante, significado)].append((dn, v["valor"]))
    quebras = 0
    for chave, pontos in sorted(series.items()):
        pontos.sort()
        if len(pontos) < 3:
            continue
        fora = [(a, b) for (dna, a), (dnb, b) in zip(pontos, pontos[1:])
                if b < a]
        if fora:
            quebras += 1
            print(f"  {chave[0]:18} {chave[1] or '-':>4} {chave[2]:18} "
                  f"{[f'{dn:g}:{v:.0f}' for dn, v in pontos]}")
    if not quebras:
        print("  todas as series com tres pontos ou mais crescem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
