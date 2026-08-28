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
import json
import math
import re
import sys

sys.path.insert(0, ".")
from motor import arquivo, vista             # noqa: E402
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
    # DOIS acessorios, e a ordem importa: a flange cega fecha a boca do te e
    # a ventosa enrosca na luva de 2" DELA. O desenho empilha um sobre o
    # outro nessa ordem - ver vista.desenhar_linha
    certo("e carrega a flange cega com a luva de 2\"",
             len(te.acessorios) == 2 and "2" in te.acessorios[0].descricao,
             str([a.descricao for a in te.acessorios]))
    certo("e a ventosa sobe na luva dela",
             te.acessorios[1].familia == "VENTOSA"
             and "COMBINADA" in te.acessorios[1].descricao.upper(),
             te.acessorios[1].descricao)
    # a ventosa ENROSCA: so entra em luva ou rosca femea da mesma bitola. Na
    # boca do te, que e flange, ela nao entra - e o desenho nao pode mostrar
    # uma montagem que nao fecha
    certo("a ventosa na luva da cega passa",
             not vista.ventosas_mal_montadas(linha),
             str(vista.ventosas_mal_montadas(linha)))
    from motor.linha import Linha as _L, Peca as _P
    solta = _L(catalogo, tipo="RECALQUE")
    solta.inserir(_P(te.item, pose="derivacao"))
    solta.acoplar(solta.pecas[0].id, _P(te.acessorios[1].item))
    fora = vista.ventosas_mal_montadas(solta)
    certo("e direto na flange do tê, não",
             len(fora) == 1 and "enrosca" in fora[0]["motivo"],
             str(fora))

    bom, _avisos = linha.lista_materiais()
    certo("o acessório entra na lista de materiais",
             any(r["sap"] == te.acessorios[0].sap for r in bom))
    certo("e a ventosa também",
             any(r["sap"] == te.acessorios[1].sap for r in bom))

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

    print("\n== o balão repete o número da lista, e não conta peças")
    # o recalque tem DUAS curvas de 90 do mesmo codigo e TRES tubos, dois
    # deles iguais: e ai que balao-por-peca e balao-por-item se separam
    linha, _faltando = templates.recalque(catalogo, 6)
    itens, _avisos = linha.lista_materiais()
    numeros = {r["sap"]: r["item"] for r in itens}
    certo("a lista numera de 1 a n, sem buraco",
             [r["item"] for r in itens] == list(range(1, len(itens) + 1)),
             str([r["item"] for r in itens]))
    baloes = linha.baloes()
    certo("cada peça desenhada tem balão",
             len(baloes) == len(list(linha.todas_as_pecas())),
             f'{len(baloes)} balões para '
             f'{len(list(linha.todas_as_pecas()))} peças')
    certo("e o número dele é o do item que se compra",
             all(b["n"] == numeros[p.sap]
                 for b, p in zip(baloes, linha.todas_as_pecas())))
    curvas = [p for p in linha.pecas if p.familia == "CURVA"]
    certo("duas peças do mesmo código levam o mesmo número",
             len(curvas) == 2 and curvas[0].sap == curvas[1].sap
             and numeros[curvas[0].sap] == numeros[curvas[1].sap])

    # tirar uma peca renumera o resto sozinho, e sem deixar buraco
    sobrando = next(p for p in linha.pecas if p.familia == "VALVULA_RETENCAO")
    antes = retrato(linha)
    linha.remover(sobrando.id)
    depois, _avisos = linha.lista_materiais()
    certo("tirar uma peça renumera o resto",
             [r["item"] for r in depois] == list(range(1, len(depois) + 1))
             and sobrando.sap not in {r["sap"] for r in depois})
    linha.desfazer()
    conferir("e desfazer devolve a numeração", antes, retrato(linha))

    print("\n== marcar, desmarcar, reordenar")
    tubo = next(p for p in linha.pecas if p.familia == "TUBO")
    linha.alterar(tubo.id, balao=False)
    itens, _avisos = linha.lista_materiais()
    certo("peça sem balão continua na lista",
             any(r["sap"] == tubo.sap for r in itens))
    certo("e sai do desenho",
             tubo.id not in {b["id"] for b in linha.baloes()})
    linha.desfazer()
    certo("e volta ao remarcar",
             tubo.id in {b["id"] for b in linha.baloes()})

    # o acessorio e o caso que motivou o desmarcar: ele se compra, mas nem
    # sempre se aponta. `alterar` chega nele sem indice, por `achar`
    ventosa = next(a for p in linha.pecas for a in p.acessorios
                   if a.familia == "VENTOSA")
    linha.alterar(ventosa.id, balao=False)
    certo("o acessório também se desmarca, e ele não tem índice",
             ventosa.id not in {b["id"] for b in linha.baloes()})
    linha.desfazer()

    antes = retrato(linha)
    fim = [r["sap"] for r in linha.lista_materiais()[0]][-1]
    numeracao = linha.renumerar([fim])
    certo("renumerar põe o item pedido em 1", numeracao[fim] == 1)
    certo("e o resto anda atrás, na ordem de leitura",
             list(numeracao.values()) == list(range(1, len(numeracao) + 1)))
    certo("e o balão da peça acompanha",
             all(b["n"] == 1 for b in linha.baloes()
                 if linha.achar(b["id"]).sap == fim))
    linha.desfazer()
    conferir("desfazer devolve a ordem", antes, retrato(linha))

    print("\n== o balão no desenho")
    desenhada = vista.vista(linha, largura=1100, altura_max=620)
    svg = desenhada["svg"]
    certo("o desenho traz um balão por peça",
             svg.count('class="balao"') == len(linha.baloes()),
             f'{svg.count(chr(34)+"balao"+chr(34))} no desenho, '
             f'{len(linha.baloes())} no documento')
    certo("cada um com o id da peça, que é o mesmo da lista",
             {i for i in re.findall(r'class="balao" data-id="([^"]+)"', svg)}
             == {b["id"] for b in linha.baloes()})
    bolas = [(float(x), float(y), float(r)) for x, y, r in re.findall(
        r'class="bola" cx="([-\d.]+)" cy="([-\d.]+)" r="([\d.]+)"', svg)]
    encostados = [(a, b) for i, a in enumerate(bolas) for b in bolas[i + 1:]
                  if math.dist(a[:2], b[:2]) < a[2] + b[2]]
    certo("e nenhum por cima do outro", not encostados, str(encostados[:2]))
    fora = [b for b in bolas
            if not (b[2] <= b[0] <= float(re.search(r'width="([\d.]+)"',
                                                    svg).group(1)) - b[2])]
    certo("e nenhum cortado na borda da folha", not fora, str(fora[:2]))

    print("\n== a wafer é apertada por tirante, e não por parafuso")
    # A borboleta e a retencao wafer NAO tem flange: elas sao abraçadas pelas
    # duas vizinhas, e a furacao inteira vai de tirante. O desenho ja fundia
    # as duas juncoes numa so; a lista cobrava os parafusos assim mesmo, e a
    # valvula saia com tirante E parafuso - o dobro do que se aperta
    linha = Linha(catalogo)
    flangeado = catalogo.melhor("TUBO", 8, material=None, norma="NBR PN16")
    borboleta = catalogo.melhor("VALVULA_BORBOLETA", 8, material=None)
    for item in (flangeado, borboleta, flangeado):
        linha.inserir(Peca(item))
    bom, _avisos = linha.lista_materiais()
    parafusos = [r for r in bom if "PARAFUSO" in r["descricao"].upper()]
    barras = [r for r in bom if "BARRA ROSCA" in r["descricao"].upper()]
    juntas = [r for r in bom if "JUNTA PLANA" in r["descricao"].upper()]
    certo("a válvula wafer não leva parafuso nenhum", not parafusos,
             str([r["descricao"] for r in parafusos]))
    certo("leva as três barras roscadas", barras and barras[0]["qtd"] == 3,
             str([(r["qtd"], r["descricao"]) for r in barras]))
    certo("e uma junta de cada lado", juntas and juntas[0]["qtd"] == 2,
             str([(r["qtd"], r["descricao"]) for r in juntas]))

    print("\n== a boca em que o ramo nasce é uma junta, e ela se compra")
    from motor.projeto import Projeto                      # noqa: E402
    projeto = Projeto(catalogo)
    tronco = Linha(catalogo, nome="Barrilete")
    projeto.criar(tronco)
    for familia in ("TUBO", "TE", "TUBO"):
        item = (flangeado if familia == "TUBO"
                else catalogo.melhor("TE", 8, material=None))
        tronco.inserir(Peca(item))
    te = next(p for p in tronco.pecas if p.familia == "TE")
    sozinho, _avisos = projeto.lista_materiais(tronco)
    juntas_antes = sum(r["qtd"] for r in sozinho
                       if "JUNTA PLANA" in r["descricao"].upper())
    ramo = projeto.ramificar(te.id, nome="Saída 1")
    ramo.inserir(Peca(flangeado))
    com_ramo, _avisos = projeto.lista_materiais(tronco)
    juntas_depois = sum(r["qtd"] for r in com_ramo
                        if "JUNTA PLANA" in r["descricao"].upper())
    certo("o ramo trouxe a junta da boca em que ele nasceu",
             juntas_depois == juntas_antes + 1,
             f"{juntas_antes} antes, {juntas_depois} depois")
    # 8" NBR PN16 tem 12 furos, e a boca do te e uma flange dessas
    furos = 12
    parafusos_antes = sum(r["qtd"] for r in sozinho
                          if "PARAFUSO" in r["descricao"].upper())
    parafusos_depois = sum(r["qtd"] for r in com_ramo
                           if "PARAFUSO" in r["descricao"].upper())
    certo("e os parafusos dela também",
             parafusos_depois == parafusos_antes + furos,
             f"{parafusos_antes} antes, {parafusos_depois} depois")

    print("\n== várias peças de uma vez, e um desfazer só")
    linha, _faltando = templates.recalque(catalogo, 6)
    antes = retrato(linha)
    marca = len(linha.feitos)
    with linha.lote("bitola"):
        for peca in list(linha.pecas):
            novo = catalogo.equivalente(peca.item, 8)
            if novo and novo["sap"] != peca.sap:
                trocada = Peca(novo)
                trocada.acessorios = list(peca.acessorios)
                linha.substituir(peca.id, trocada)
    certo("doze substituições viram um comando no histórico",
             len(linha.feitos) - marca == 1,
             f"{len(linha.feitos) - marca} comandos")
    certo("e a linha inteira mudou de bitola",
             all('8"' in p.descricao for p in linha.pecas
                 if p.familia in ("CURVA", "TUBO", "TE")),
             str([p.descricao for p in linha.pecas]))
    linha.desfazer()
    conferir("um desfazer devolve as doze", antes, retrato(linha))
    linha.refazer()
    linha.desfazer()
    conferir("e refazer e desfazer de novo também", antes, retrato(linha))

    # a peca de duas bitolas nao tem equivalente, e isso e recusa e nao falha
    dupla = next((i for i in catalogo.itens
                  if (i["familia"] or "").startswith("REDUCAO")
                  and len(set(i["dn"] or [])) > 1), None)
    if dupla:
        certo("redução não tem equivalente: qual das duas bitolas?",
                 catalogo.equivalente(dupla, 8) is None, dupla["descricao"])
    # e a saida NAO e bitola da peca: a flange cega de 6" com luva de 2" tem
    # equivalente em 4", com a mesma luva de 2"
    cega = catalogo.por_sap.get("01542-103015")
    if cega:
        outra = catalogo.equivalente(cega, 4)
        certo("a luva de 2\" não conta como bitola da flange cega",
                 outra is not None and 2.0 in (outra["dn"] or []),
                 outra["descricao"] if outra else "sem equivalente")

    print("\n== mover um bloco é um comando, e ele chega inteiro")
    linha = monta(catalogo)
    ordem = [p.id for p in linha.pecas]
    antes = retrato(linha)
    marca = len(linha.feitos)
    linha.mover_bloco([ordem[0], ordem[1]], 3)
    certo("o bloco é um comando só", len(linha.feitos) - marca == 1)
    depois = [p.id for p in linha.pecas]
    certo("as duas chegam juntas e na ordem em que estavam",
             depois.index(ordem[1]) == depois.index(ordem[0]) + 1,
             str(depois))
    certo("e nenhuma peça se perdeu no caminho",
             sorted(depois) == sorted(ordem))
    linha.desfazer()
    conferir("desfazer devolve a sequência", antes, retrato(linha))

    print("\n== salvar e abrir: o arquivo guarda a escolha, não o resultado")
    linha, _faltando = templates.recalque(catalogo, 6)
    linha.alterar(linha.pecas[2].id, comprimento_mm=1234)   # corte de campo
    linha.renumerar([linha.pecas[-1].sap])
    texto = arquivo.guardar(linha)
    # abrir devolve o PROJETO - uma montagem sozinha volta como projeto de uma
    projeto, avisos = arquivo.abrir(catalogo, texto)
    volta = projeto.ativa
    certo("abriu sem recado", not avisos, str(avisos))
    # o id NAO volta igual, e nao deve: ele nasce com a peca desta sessao. O
    # que tem de voltar igual e tudo o que se compra e tudo o que se desenha
    sem_id = lambda r: (r[0], [g[1:] for g in r[1]], r[3])
    conferir("a lista, a geometria e os avisos voltam iguais",
             sem_id(retrato(linha)), sem_id(retrato(volta)))
    certo("o corte de campo volta com a peça",
             volta.pecas[2].comprimento_mm == 1234,
             str(volta.pecas[2].comprimento_mm))
    certo("a numeração volta como estava",
             volta.ordem_baloes == linha.ordem_baloes)
    certo("e o acessório volta dentro da peça que o carrega",
             [len(p.acessorios) for p in volta.pecas]
             == [len(p.acessorios) for p in linha.pecas])
    certo("abrir não é edição: o desfazer começa vazio",
             not volta.feitos and not volta.desfeitos)

    # o arquivo guarda a cota que valia, e ela NAO manda: manda a folha de
    # hoje. O que ele faz e dizer o que mudou desde entao
    adulterado = json.loads(texto)
    adulterado["montagens"][0]["pecas"][0]["medido_mm"] = 999
    _projeto, avisos = arquivo.abrir(catalogo, json.dumps(adulterado))
    certo("cota que a folha mudou desde o dia em que se salvou vira aviso",
             any("999" in a and "folha de hoje" in a for a in avisos),
             str(avisos))
    sumido = json.loads(texto)
    sumido["montagens"][0]["pecas"][1]["sap"] = "00000-000000"
    perdida, avisos = arquivo.abrir(catalogo, json.dumps(sumido))
    perdida = perdida.ativa
    certo("código que saiu da lista não derruba a abertura",
             len(perdida.pecas) == len(linha.pecas) - 1
             and any("não está mais na lista" in a for a in avisos),
             str(avisos))
    for ruim, motivo in (('{"formato": "outro"}', "não é uma montagem"),
                         ("nem json", "não consegui ler"),
                         ('{"formato": "linha-pivodrip", "versao": 99}',
                          "atualize o programa")):
        try:
            arquivo.abrir(catalogo, ruim)
            certo(f"recusa {motivo!r}", False, "abriu assim mesmo")
        except arquivo.Recusado as erro:
            certo(f"recusa e explica: {motivo}", motivo in str(erro), str(erro))

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
