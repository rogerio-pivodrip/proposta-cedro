#!/usr/bin/env python3
"""Confere a Bitola: os tres bugs que ela existe para impedir, e a prova física.

Bitola como numero causou tres bugs, e todos os tres eram a mesma coisa - um
numero nao sabe de que serie ele e. O teste cobra os tres, e mais duas coisas
que so aparecem quando se olha o catalogo inteiro.

  **3/4" nao e 4".** O denominador da fracao casava com o padrao de polegada.
  Este e o mais barato de conferir e o que mais custou quando passou.

  **90 de PVC nao e 90 de grau.** A Bitola recusa comparacao com numero: se
  alguem escrever `bitola == 90`, a resposta e False e nao um acerto por
  acidente.

  **225 mm e 8" sao a mesma bitola.** E a prova FISICA: as duas tomam a mesma
  flange, com o mesmo numero de furos, no mesmo circulo. O teste vai buscar na
  tabela de furacao, e nao no que a Bitola diz de si mesma - senao estaria
  conferindo a tabela contra ela mesma.

  **A tabela e uma so.** As quatro copias que existiam - POLEGADA_MM,
  POLEGADA_PARA_DN, PVC_PARA_DN e PEAD_POL - continuam de pe com os nomes
  antigos, e o teste cobra que as quatro digam o mesmo que a Bitola. E o que
  garante que a unificacao nao mudou resultado nenhum.

  **O catalogo inteiro atravessa.** Toda peca da lista com DN tem de virar uma
  Bitola sem excecao; e as que caem fora da serie da linha sao nomeadas, porque
  isso e informacao de projeto - e assim que o 5" aparece.

Uso: python3 tools/conferir_bitola.py
"""
import collections
import json
import sys

sys.path.insert(0, ".")
from motor import regras, simbolos                    # noqa: E402
from motor.bitola import (Bitola, METRICO, NOMINAL,  # noqa: E402
                          qualquer_mm)
from motor.traducao import POLEGADA_MM                # noqa: E402

CATALOGO = "data/catalogo.json"


def main():
    problemas = []

    def conferir(caso, condicao, detalhe=""):
        if condicao:
            print(f"  ok {caso}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}" + (f": {detalhe}" if detalhe else ""))

    print("== os três bugs")
    tres_quartos = Bitola.de_texto('QC 3/4"')
    conferir('3/4" dá DN20 e não DN100',
             tres_quartos == Bitola.de_polegada(0.75), repr(tres_quartos))
    conferir('1 1/4" dá DN32', Bitola.de_texto('1 1/4"') ==
             Bitola.de_polegada(1.25))
    noventa = Bitola.de_mm(90, "METRICO")
    conferir("90 de PVC é DN80, e não DN90",
             noventa == Bitola.de_polegada(3), repr(noventa))
    conferir("comparar bitola com número dá False",
             (noventa == 90) is False)
    conferir("90 não existe como DN nominal",
             Bitola.de_mm(90, "NOMINAL") is None)
    conferir('225 mm é a mesma bitola que 8"',
             Bitola.de_mm(225, "METRICO") == Bitola.de_polegada(8))

    print("\n== a prova física: a mesma flange")
    # nao pergunta a Bitola se sao iguais - pergunta a tabela de furacao, que e
    # medida (NBR 7675, a de 8" confirmada pela casa)
    pares = [(225, 8), (160, 6), (110, 4), (90, 3), (280, 10), (315, 12),
             (355, 14)]
    for mm, pol in pares:
        de_mm = Bitola.de_mm(mm, "METRICO")
        de_pol = Bitola.de_polegada(pol)
        f1 = regras.FUROS.get(("NBR PN16", int(de_mm.dn_mm))) if de_mm else None
        f2 = regras.FUROS.get(("NBR PN16", int(de_pol.dn_mm))) if de_pol else None
        if not (f1 and f2):
            conferir(f'{mm} mm e {pol}" têm furação na tabela', False,
                     "uma das duas não tem")
            continue
        conferir(f'{mm} mm e {pol}" tomam a mesma flange '
                 f'({f1["furos"]}×⌀{f1["furo_mm"]:g} em {f1["circulo_mm"]:g})',
                 f1 == f2)

    print("\n== a tabela é uma só")
    for pol, mm in POLEGADA_MM.items():
        b = Bitola.de_polegada(pol)
        conferir(f'POLEGADA_MM[{pol:g}] = {mm:g} bate com a Bitola',
                 b and b.em_mm_externo() == mm) if pol in (3, 8, 14) else None
    iguais = all(Bitola.de_polegada(p) and
                 Bitola.de_polegada(p).em_mm_externo() == mm
                 for p, mm in POLEGADA_MM.items())
    conferir("POLEGADA_MM inteira bate com a Bitola", iguais)
    conferir("POLEGADA_PARA_DN é a tabela nominal",
             regras.POLEGADA_PARA_DN == NOMINAL)
    conferir("PVC_PARA_DN é a métrica ao contrário",
             regras.PVC_PARA_DN == {e: d for d, e in METRICO.items()})
    conferir("PEAD_POL bate com a Bitola",
             all(Bitola.de_mm(mm, "METRICO").em_polegada() == pol
                 for mm, pol in simbolos.PEAD_POL.items()))
    conferir("dn_nominal e dn_em_polegada seguem a Bitola",
             regras.dn_nominal(225, "mm") == 200
             and regras.dn_em_polegada(225, "mm") == 8
             and regras.dn_nominal(8) == 200)

    print('\n== o 5", que prova a regra da série')
    cinco = Bitola.de_polegada(5)
    conferir('5" não é bitola de linha', not cinco.na_linha())
    conferir('5" é bitola de bocal de bomba', cinco.no_bocal())
    conferir('8" é as duas coisas', Bitola.de_polegada(8).na_linha()
             and Bitola.de_polegada(8).no_bocal())

    print("\n== o catálogo inteiro atravessa")
    with open(CATALOGO, encoding="utf-8") as fh:
        dados = json.load(fh)
    itens = dados["itens"] if isinstance(dados, dict) else dados
    # ferragem tem bitola de ROSCA e nao de tubo: 5/8", 1 1/8". Nao entra na
    # conta, e nao entrar e o certo - a Bitola e de tubulacao
    FERRAGEM = {"PARAFUSO", "PORCA", "ARRUELA", "BARRA_ROSCADA", "QUADRO",
                "FILTRO", "PECA_REPOSICAO", "PILOTO", "FLUTUADOR"}
    sem_bitola, fora_da_linha = collections.Counter(), collections.Counter()
    suspeitos, total, ferragem = [], 0, 0
    for item in itens:
        for medida in (item.get("dn") or []):
            if not isinstance(medida, (int, float)):
                continue
            total += 1
            unidade = item.get("unidade_dn") or "in"
            b = (qualquer_mm(medida) if unidade == "mm"
                 else Bitola.de_polegada(medida))
            if b is not None:
                if unidade == "in" and not b.na_linha():
                    fora_da_linha[str(b)] += 1
                continue
            if item.get("familia") in FERRAGEM:
                ferragem += 1
                continue
            # leitura errada tem cara: 304 vem do "AISI 304", 2000.75 de um
            # comprimento lido como diametro, 0 de nada
            if medida in (0,) or medida > 800 or 300 < medida < 310:
                suspeitos.append((item["sap"], medida, unidade,
                                  item["descricao"][:46]))
            else:
                sem_bitola[(medida, unidade)] += 1
    fica = sum(sem_bitola.values())
    print(f"  {total} medidas no catálogo")
    print(f"  {ferragem} são de ferragem - bitola de rosca, não de tubo")
    print(f"  {len(suspeitos)} têm cara de leitura errada da descrição:")
    for sap, medida, unidade, descricao in suspeitos[:8]:
        print(f"      {sap} {medida:g} {unidade}  {descricao}")
    print(f"  {fica} medidas de tubo que nenhuma série reconhece:")
    for (medida, unidade), quantas in sem_bitola.most_common(14):
        print(f"      {medida:>8g} {unidade}  ×{quantas}")
    print("  polegadas que não são bitola de linha, e quantas vezes aparecem:")
    for nome, quantas in fora_da_linha.most_common(10):
        print(f"      {nome:8} {quantas}")
    conferir("as séries reconhecem mais de 95% das medidas de tubo",
             (total - fica - len(suspeitos)) / total > 0.95,
             f"{(total - fica - len(suspeitos)) / total:.1%}")

    print(f"\n{len(problemas)} problemas")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
