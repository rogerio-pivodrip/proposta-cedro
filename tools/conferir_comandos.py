#!/usr/bin/env python3
"""Confere os cinco comandos e o desfazer/refazer.

A `Linha` e o documento unico do programa: desenho e lista sao duas projecoes
dela, e os comandos sao a unica porta de escrita. Entao o que precisa ser
verdade nao e "o comando roda", e sim:

  **desfazer devolve o documento ao estado exato de antes.** Nao "parecido":
  exato, medido nas duas projecoes - a lista de materiais e a geometria. Se as
  duas voltam iguais, o desenho e a tabela voltam iguais, que e o que o
  projetista ve.

  **refazer devolve ao estado de depois**, pelo mesmo criterio.

  **o id sobrevive ao que deve sobreviver.** Alterar o comprimento de um tubo
  nao troca a peca comprada, entao o id fica; substituir troca, entao o id
  muda. Mover nao cria nem destroi ninguem.

Por que medir as projecoes e nao a lista de pecas: comparar `linha.pecas`
compararia os mesmos objetos consigo mesmos e passaria mesmo com o recalculo
quebrado. A lista de materiais e a geometria sao derivadas - elas so voltam
iguais se tudo que depende delas voltou.

Uso: python3 tools/conferir_comandos.py
"""
import sys

sys.path.insert(0, ".")
from motor.catalogo import Catalogo          # noqa: E402
from motor.linha import Linha, Peca          # noqa: E402


def retrato(linha):
    """As duas projecoes do documento, como texto comparavel."""
    bom, avisos = linha.lista_materiais()
    materiais = [(r["sap"], r["qtd"]) for r in bom]
    geo = [(p["peca"].id, tuple(round(v, 3) for v in p["de"]),
            tuple(round(v, 3) for v in p["para"]),
            round(p["direcao_saida"], 3), p["fonte_cota"])
           for p in linha.geometria()]
    ids = [p.id for p in linha.pecas]
    return (materiais, geo, ids, sorted(avisos))


def monta(catalogo):
    linha = Linha(catalogo, tipo="RECALQUE")
    # a curva e pedida em 90 de proposito: e a que as duas folhas cotam
    # diferente (335 no Irrigafour, 297 na Netafim), e e nela que o comando
    # `alterar a fonte` tem o que provar
    for familia, dn, busca, extra in (
            ("TUBO", 8, {}, {"comprimento_mm": 6000}),
            ("CURVA", 8, {"angulo": 90}, {}),
            ("TUBO", 8, {}, {"comprimento_mm": 3000}),
            ("VALVULA_BORBOLETA", 8, {}, {}),
            ("TUBO", 8, {}, {"comprimento_mm": 1000})):
        item = catalogo.melhor(familia, dn, material=None, **busca)
        if not item:
            raise SystemExit(f"catalogo sem {familia} {dn}")
        linha.inserir(Peca(item, **extra))
    return linha


def main():
    catalogo = Catalogo()
    problemas = []

    def conferir(caso, esperado, obtido):
        if esperado != obtido:
            problemas.append(caso)
            print(f"  ! {caso}")
            for nome, a, b in zip(("materiais", "geometria", "ids", "avisos"),
                                  esperado, obtido):
                if a != b:
                    print(f"      {nome}: antes {a}")
                    print(f"      {nome}: depois {b}")
        else:
            print(f"  ok {caso}")

    linha = monta(catalogo)
    print(f"linha de {len(linha.pecas)} peças\n")

    # cada comando: guarda o retrato, aplica, desfaz, compara; refaz, compara
    tubo_extra = Peca(catalogo.melhor("TUBO", 8, material=None),
                      comprimento_mm=2000)
    outra = Peca(catalogo.melhor("CURVA", 8, angulo=45, material=None))
    casos = [
        ("inserir no meio", lambda: linha.inserir(tubo_extra, 2)),
        ("remover a última", lambda: linha.remover(-1)),
        ("substituir a curva", lambda: linha.substituir(linha.pecas[1].id,
                                                        outra)),
        ("alterar o comprimento", lambda: linha.alterar(linha.pecas[0].id,
                                                        comprimento_mm=4500)),
        # a curva de 8" mede 335 mm de perna no Irrigafour e 297 na Netafim:
        # trocar a fonte tem de mover tudo o que vem depois dela
        ("alterar a fonte da curva", lambda: linha.alterar(
            linha.pecas[1].id, fonte="NETAFIM")),
        ("mover para o começo", lambda: linha.mover(linha.pecas[2].id, 0)),
    ]
    print("== cada comando desfaz e refaz")
    for nome, roda in casos:
        antes = retrato(linha)
        roda()
        depois = retrato(linha)
        if antes == depois:
            problemas.append(f"{nome}: não mudou nada")
            print(f"  ! {nome}: não mudou nada")
        linha.desfazer()
        conferir(f"{nome} → desfazer volta ao anterior", antes, retrato(linha))
        linha.refazer()
        conferir(f"{nome} → refazer volta ao posterior", depois, retrato(linha))
        linha.desfazer()          # deixa a linha como estava para o proximo

    print("\n== a pilha inteira")
    linha = monta(catalogo)
    inicial = retrato(linha)
    linha.inserir(Peca(catalogo.melhor("TUBO", 8, material=None),
                       comprimento_mm=2000), 1)
    linha.mover(linha.pecas[0].id, 3)
    linha.alterar(linha.pecas[0].id, comprimento_mm=1234)
    linha.remover(linha.pecas[-1].id)
    final = retrato(linha)
    for _ in range(4):
        linha.desfazer()
    conferir("quatro comandos → quatro desfazer volta ao inicial",
             inicial, retrato(linha))
    for _ in range(4):
        linha.refazer()
    conferir("quatro refazer volta ao final", final, retrato(linha))

    print("\n== o que o id tem de fazer")
    linha = monta(catalogo)
    ids = [p.id for p in linha.pecas]
    linha.alterar(ids[0], comprimento_mm=9000)
    conferir("alterar mantém o id (a peça comprada é a mesma)",
             ids, [p.id for p in linha.pecas])
    linha.mover(ids[0], 2)
    conferir("mover não cria nem destrói id",
             sorted(ids), sorted(p.id for p in linha.pecas))
    nova = Peca(catalogo.melhor("CURVA", 8, angulo=45, material=None))
    linha.substituir(ids[1], nova)
    if nova.id in [p.id for p in linha.pecas] and ids[1] not in \
            [p.id for p in linha.pecas]:
        print("  ok substituir troca o id (a peça comprada mudou)")
    else:
        problemas.append("substituir não trocou o id")
        print("  ! substituir não trocou o id")

    print("\n== o que o comando tem de recusar")
    for caso, roda in (
            ("alterar campo que não é alterável",
             lambda: linha.alterar(linha.pecas[0].id, familia="TUBO")),
            ("endereçar id que não existe",
             lambda: linha.remover("p999999")),
            ("endereçar posição fora da linha",
             lambda: linha.remover(99))):
        try:
            roda()
        except (ValueError, KeyError, IndexError) as erro:
            print(f"  ok {caso}: {type(erro).__name__}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}: passou sem reclamar")

    print("\n== editar depois de desfazer apaga o refazer")
    linha = monta(catalogo)
    linha.remover(-1)
    linha.desfazer()
    linha.alterar(linha.pecas[0].id, comprimento_mm=777)
    if linha.refazer() is None:
        print("  ok o refazer some quando a edição cria outro futuro")
    else:
        problemas.append("refazer sobreviveu a uma edição")
        print("  ! refazer sobreviveu a uma edição")

    print(f"\n{len(problemas)} problemas")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
