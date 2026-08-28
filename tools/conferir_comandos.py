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

    def certo(caso, condicao, detalhe=""):
        """Para o que e sim ou nao - `conferir` compara dois retratos."""
        if condicao:
            print(f"  ok {caso}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}" + (f": {detalhe}" if detalhe else ""))

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

    print("\n== espelhar e girar")
    from motor import vista, simbolos as s          # noqa: E402
    linha = monta(catalogo)
    curva = next(p for p in linha.pecas if p.familia == "CURVA")

    def saida_da_curva(linha):
        """Para onde a curva manda a linha, na vista - o que o espelho vira."""
        postos, _ = vista.postos_da_linha(linha)
        i = [p.id for p in linha.pecas].index(curva.id)
        return round(postos[i].saida[1] - postos[i].entrada[1], 1)

    antes = saida_da_curva(linha)
    linha.alterar(curva.id, sentido=-1)
    depois = saida_da_curva(linha)
    if antes == -depois and antes != 0:
        print(f"  ok espelhar a curva inverte o desenho ({antes} → {depois})")
    else:
        problemas.append("espelhar não virou a curva no desenho")
        print(f"  ! espelhar não virou a curva no desenho: {antes} → {depois}")
    if curva.sap == next(p for p in linha.pecas if p.familia == "CURVA").sap:
        print("  ok espelhar não troca o código que se compra")

    marca = retrato(linha)
    linha.desfazer()
    if saida_da_curva(linha) == antes:
        print("  ok desfazer devolve a curva ao lado de origem")
    else:
        problemas.append("desfazer não devolveu o espelho")
        print("  ! desfazer não devolveu o espelho")
    linha.refazer()
    if retrato(linha) == marca:
        print("  ok refazer devolve o espelho")
    else:
        problemas.append("refazer não devolveu o espelho")
        print("  ! refazer não devolveu o espelho")

    linha = monta(catalogo)
    alto = lambda: max(abs(p.saida[1]) for p in vista.postos_da_linha(linha)[0])
    largo = lambda: max(abs(p.saida[0]) for p in vista.postos_da_linha(linha)[0])
    deitada = (largo(), alto())
    linha.pose(giro=-90)
    de_pe = (largo(), alto())
    if round(deitada[0]) == round(de_pe[1]) and round(deitada[1]) == round(de_pe[0]):
        print("  ok girar 90° troca a largura pela altura da linha inteira")
    else:
        problemas.append("girar não virou a linha")
        print(f"  ! girar não virou a linha: {deitada} → {de_pe}")
    linha.desfazer()
    if (round(largo()), round(alto())) == (round(deitada[0]), round(deitada[1])):
        print("  ok desfazer devolve a pose")
    else:
        problemas.append("desfazer não devolveu a pose")
        print("  ! desfazer não devolveu a pose")

    print("\n== peça de uma ponta só não entra no meio da linha")
    linha = monta(catalogo)
    crivo = catalogo.melhor("CRIVO", 8, material=None)
    if crivo:
        linha.inserir(Peca(crivo), 2)
        fora = vista.pontas_erradas(linha)
        if any(f["sap"] == crivo["sap"] for f in fora):
            print(f"  ok o motor reclama: {fora[0]['motivo']}")
        else:
            problemas.append("crivo no meio da linha passou calado")
            print("  ! crivo no meio da linha passou calado")
        linha.mover(linha.pecas[2].id, 0)
        if not vista.pontas_erradas(linha):
            print("  ok no começo da linha ele para de reclamar")
        else:
            problemas.append("crivo no começo ainda reclama")
            print("  ! crivo no começo ainda reclama")

    print("\n== o acessório vive dentro da peça que o carrega")
    from motor import templates                        # noqa: E402
    linha, faltando = templates.recalque(catalogo, 6)
    certo("o recalque monta inteiro", not faltando, str(faltando))
    familias = [p.familia for p in linha.pecas]
    certo("na ordem da casa",
             familias == ["CURVA", "VALVULA_HIDRAULICA", "TUBO", "MEDIDOR",
                          "TUBO", "VALVULA_RETENCAO", "TE", "CURVA", "TUBO"],
             str(familias))
    te = next(p for p in linha.pecas if p.familia == "TE")
    certo("o tê fica de pé sobre a derivação", te.pose == "derivacao")
    certo("e carrega a flange cega com a luva de 2\"",
             len(te.acessorios) == 1 and "2" in te.acessorios[0].descricao,
             str([a.descricao for a in te.acessorios]))
    bom, _avisos = linha.lista_materiais()
    certo("o acessório entra na lista de materiais",
             any(r["sap"] == te.acessorios[0].sap for r in bom))

    # o trecho reto do hidrometro e a unica cota calculada no template: a
    # barra tem de COBRIR o exigido, nunca chegar perto
    for t in linha.trechos_retos():
        if t["peca"].familia != "MEDIDOR":
            continue
        certo(f'o medidor tem os {t["exige_antes_mm"]/152.4:.0f} D antes '
                 f'e {t["exige_depois_mm"]/152.4:.0f} D depois', t["ok"],
                 f'{t["antes_mm"]:.0f}/{t["exige_antes_mm"]:.0f} antes · '
                 f'{t["depois_mm"]:.0f}/{t["exige_depois_mm"]:.0f} depois')

    antes = retrato(linha)
    item = catalogo.melhor("FLANGE_CEGA", 6, material=None)
    linha.acoplar(te.id, Peca(item))
    certo("acoplar muda o documento", retrato(linha) != antes)
    linha.desfazer()
    conferir("e desfazer devolve ao estado exato", antes, retrato(linha))
    linha.refazer()
    marca = retrato(linha)
    linha.desfazer()
    linha.refazer()
    conferir("refazer também", marca, retrato(linha))

    # o acessorio sai junto com a peca que o carrega - ele vive dentro dela
    sap_acessorio = te.acessorios[0].sap
    linha.remover(te.id)
    bom, _avisos = linha.lista_materiais()
    certo("tirar a peça leva o acessório junto",
             not any(r["sap"] == sap_acessorio for r in bom))

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
