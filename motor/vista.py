"""A vista lateral da linha: o documento virado desenho.

Estava em tools/desenhar_linha.py, que e uma ferramenta. Subiu para o motor
pelo mesmo motivo que motor/svg.py subiu: a tela do programa precisa do mesmo
desenho da folha, e o desenho e do motor.

A funcao de baixo desenha uma lista de SIMBOLOS. A de cima recebe a `Linha` -
o documento - e faz a ponte: cada peca do catalogo vira um simbolo por
motor/desenho.de_item, e o id da peca vai junto para o grupo do SVG.
"""
import math

from . import desenho, regras, simbolos as s
from .svg import (DEFS, ESTILO, ESTILO_LINHA, cor_de,  # noqa: F401
                  desenhar, desenhar_peca, luz_de, texto_no_eixo)

MODOS = ("traco", "pb", "metal")

MARGEM = 46


def simbolos_da_linha(linha):
    """(peca, simbolo) de cada peca que sabe se desenhar, e quem nao sabe.

    Peca sem simbolo nao derruba a vista: ela sai da lista de desenho e entra
    na de recusadas, com o motivo. A lista de materiais continua completa - o
    que falta e o traco, nao o item.
    """
    prontos, recusadas = [], []
    espelho_da_linha = getattr(linha, "espelho", 1)
    for peca in linha.pecas:
        try:
            simbolo = desenho.de_item(peca.item,
                                      getattr(peca, "pose", None))
            # o `sentido` da peca e o espelho da linha se multiplicam: a curva
            # que ja descia, numa linha espelhada, volta a subir. Espelhar o
            # SIMBOLO e o que faz a corrente inteira acompanhar - montar()
            # encadeia pelas portas, e a porta espelhada vira a linha para o
            # outro lado sozinha
            if peca.sentido * espelho_da_linha < 0:
                simbolo = s.espelhado(simbolo)
            prontos.append((peca, simbolo))
        except Exception as erro:                       # noqa: BLE001
            recusadas.append({"id": peca.id, "sap": peca.sap,
                              "descricao": peca.descricao,
                              "motivo": f"{type(erro).__name__}: {erro}"})
    return prontos, recusadas


def pontas_erradas(linha):
    """Peca de uma ponta so, posta onde ela nao cabe.

    Crivo e valvula de pe tem cesto fechado no fundo e flange so na saida:
    elas ABREM a linha. Flange cega e cap fecham, e nao tem saida. Postas no
    meio, a vizinha encosta no lado fechado e o desenho fica mentindo.

    Quem sabe disso e o SIMBOLO, que e onde as portas estao - por isso a
    conferencia mora aqui e nao numa lista de familias escrita a mao, que
    envelheceria a cada peca nova do catalogo.
    """
    prontos, _recusadas = simbolos_da_linha(linha)
    ultimo = len(prontos) - 1
    fora = []
    for i, (peca, simbolo) in enumerate(prontos):
        if s.porta(simbolo, s.ENTRADA) is None and i != 0:
            fora.append({"id": peca.id, "sap": peca.sap, "pos": i,
                         "motivo": f"{peca.descricao} só conecta pela flange - "
                                   f"é fechada do outro lado, e só entra no "
                                   f"começo da linha"})
        elif s.porta(simbolo, s.SAIDA) is None and i != ultimo:
            fora.append({"id": peca.id, "sap": peca.sap, "pos": i,
                         "motivo": f"{peca.descricao} fecha a linha - "
                                   f"nada encaixa depois dela"})
    return fora


def acessorios_da_linha(linha):
    """[(id, simbolo)] por peca da corrente - o que fecha a boca que sobra."""
    saida = []
    for peca in linha.pecas:
        desta = []
        for acessorio in getattr(peca, "acessorios", ()):
            try:
                desta.append((acessorio.id,
                              desenho.de_item(acessorio.item,
                                              getattr(acessorio, "pose", None))))
            except Exception:                           # noqa: BLE001
                pass
        saida.append(desta)
    return saida


def porta_livre(simbolo):
    """A boca que a corrente NAO usa - a derivacao do te, o bocal do manifold.

    `montar` encadeia por entrada e saida; o que sobra fica sem ninguem. E
    nessa boca que o acessorio entra.
    """
    return next((p for p in simbolo.portas
                 if p.papel not in s.ENTRADA + s.SAIDA), None)


def ventosas_mal_montadas(linha):
    """Ventosa pendurada onde ela nao enrosca.

    Ela nao aparafusa, ela ENROSCA: so entra em luva ou peca com rosca femea
    da mesma bitola. Uma ventosa de 2" numa flange de 2" nao entra - nao ha
    rosca ali - e numa luva de 1" tambem nao. O acessorio e desenhado na boca
    livre de quem o carrega, e sem esta conferencia ele saia desenhado em
    qualquer boca, o que faria o desenho prometer uma montagem que nao existe.
    """
    from . import ventosa as regra_ventosa
    fora = []
    for peca, montados in zip(linha.pecas, acessorios_da_linha(linha)):
        try:
            anfitriao = desenho.de_item(peca.item, getattr(peca, "pose", None))
        except Exception:                                   # noqa: BLE001
            continue
        montagem = anfitriao
        for identidade, simbolo in montados:
            boca = porta_livre(montagem.simbolo if hasattr(montagem, "simbolo")
                               else montagem)
            if simbolo.familia == "VENTOSA":
                dn = simbolo.params.get("dn_pol", 2)
                ok, motivo = regra_ventosa.encaixa_na_boca(boca, dn)
                if not ok:
                    fora.append({"id": identidade, "em": peca.id,
                                 "rotulo": simbolo.rotulo, "motivo": motivo})
            montagem = simbolo
    return fora


def parafusos_curtos(linha):
    """Junta em que o parafuso da tabela NAO fecha.

    O desenho passou a sair em escala de verdade - o parafuso no comprimento do
    codigo que a lista compra - e escala de verdade tem um efeito colateral
    util: da para MEDIR. Se depois da porca nao sobra rosca, o parafuso nao
    fecha, e isso e uma compra errada que so apareceria na obra.

    A conta e a mesma que o simbolo faz para desenhar, e de proposito: quem
    avisa e quem desenha veem o mesmo parafuso.

    **So mede onde o aperto e conhecido** - hoje AZ_AZ, ACO_PLASSON e
    PLASSON_PLASSON, que sao os tres que `regras.aperto_da_junta` sabe montar.
    Contra a bomba a outra chapa e do fabricante dela e nao ha folha aqui, e
    MISTO e o que sobrou sem regra: medir esses com a chapa de aco dos dois
    lados daria um veredito sobre um sanduiche que nao existe, e um "fecha"
    falso vale menos que nao dizer nada.
    """
    prontos, _recusadas = simbolos_da_linha(linha)
    fora = []
    for (peca, simbolo), (vizinha, adiante) in zip(prontos, prontos[1:]):
        saida = s.porta(simbolo, s.SAIDA)
        ok, _motivo = s.encaixa(simbolo, adiante)
        if not ok or saida is None or _os_dois_pead(simbolo, adiante):
            continue
        contexto = regras.contexto_da_junta(simbolo.params.get("material"),
                                            adiante.params.get("material"))
        aperto = regras.aperto_da_junta(saida.dn_pol, contexto)
        if not aperto:
            continue
        ficha = regras.parafuso_da_junta(saida.dn_pol, contexto)
        meio = aperto["mm"] / 2
        _el, sobra = s.parafuso_sextavado(-meio, meio, 0.0, ficha["bitola_mm"],
                                          ficha["comprimento_mm"])
        # menos de dois fios de rosca aparentes ja e aperto sem garantia; UNC
        # de 3/4" tem 10 fios por polegada, entao um fio e 2,54 mm
        if sobra < 2 * 25.4 / 10:
            fora.append({"de": peca.id, "para": vizinha.id,
                         "dn_pol": saida.dn_pol, "contexto": contexto,
                         "sobra_mm": sobra, "aperto_mm": aperto["mm"],
                         "bitola_pol": ficha["bitola_pol"],
                         "comprimento_pol": ficha["comprimento_pol"]})
    return fora


def _pilha_da_junta(dn_pol, materiais):
    """Como as duas pontas se empilham. (chapas, vaos, face_mm)

    `chapas` e quanto cada lado poe de espessura; `vaos`, quanto desse total
    NAO cobre o parafuso. No aco o vao e zero. No Plasson e o ressalto do
    colar, que e mais estreito que o circulo de furacao: as duas flanges
    soltas nao se encostam - quem se encosta sao os ressaltos - e entre elas o
    parafuso fica a mostra.

    Cai na chapa de aco quando a ponta nao tem ficha (bomba, PEAD): e o que o
    desenho ja fazia, e continua sendo um desenho plausivel. O que muda e o
    Plasson, que agora sai com a chapa que ele tem de verdade.
    """
    f = s.flange(dn_pol)
    pontas = [regras.chapa_da_ponta(dn_pol, m)
              or {"mm": f["espessura"], "vao": 0.0, "face": f["ressalto"]}
              for m in materiais]
    return (tuple(p["mm"] for p in pontas),
            tuple(p["vao"] for p in pontas),
            min(p["face"] for p in pontas))


def parafusos_curtos_por_caso(linha):
    """O mesmo, agrupado - o aviso e sobre a COMPRA, e nao sobre cada junta.

    Numa linha de 14" com tres juntas iguais, o problema e um so e a resposta e
    uma so: trocar o comprimento na tabela. Repetir tres vezes so faz a folha
    parecer cheia de defeito.
    """
    casos = {}
    for c in parafusos_curtos(linha):
        chave = (c["dn_pol"], c["contexto"], c["comprimento_pol"])
        registro = casos.setdefault(chave, dict(c, juntas=0))
        registro["juntas"] += 1
    return list(casos.values())


def postos_da_linha(linha, giro=None):
    """Onde cada peca cai, ja encadeada pelas portas. (postos, recusadas)

    E a mesma cadeia que o SVG usa, e de proposito: a vista da tela e o DXF de
    exportacao tem de sair do mesmo encadeamento, senao o que se ve e o que se
    entrega divergem.
    """
    prontos, recusadas = simbolos_da_linha(linha)
    if not prontos:
        return [], recusadas
    if giro is None:
        giro = getattr(linha, "giro", 0.0)
    postos, _fim = s.montar([sim for _, sim in prontos])
    if giro:
        postos = _girar_postos(postos, giro)
    return postos, recusadas


def _girar_postos(postos, giro):
    rad = math.radians(giro)
    cos, sen = math.cos(rad), math.sin(rad)

    def vira(x, y):
        return (x * cos - y * sen, x * sen + y * cos)

    return [p._replace(dx=vira(p.dx, p.dy)[0], dy=vira(p.dx, p.dy)[1],
                       giro=p.giro + giro, entrada=vira(*p.entrada),
                       saida=vira(*p.saida))
            for p in postos]


def extensao(postos):
    """A caixa que a linha montada ocupa, em milimetro real. (largura, altura)

    E a mesma conta que desenhar_linha faz para enquadrar - e sai daqui para
    que a folha impressa possa ESCOLHER a escala antes de mandar desenhar. Sem
    isso a folha teria de desenhar duas vezes: uma para medir, outra para
    valer.
    """
    cantos = []
    for p in postos:
        x0, y0, w, h = p.simbolo.caixa
        rad = math.radians(p.giro)
        cos, sen = math.cos(rad), math.sin(rad)
        for cx, cy in ((x0, y0), (x0 + w, y0), (x0, y0 + h), (x0 + w, y0 + h)):
            cantos.append((p.dx + cx * cos - cy * sen,
                           p.dy + cx * sen + cy * cos))
    if not cantos:
        return (1.0, 1.0)
    return (max(c[0] for c in cantos) - min(c[0] for c in cantos),
            max(c[1] for c in cantos) - min(c[1] for c in cantos))


def vista(linha, largura=940, altura_max=620, giro=None, modo="traco",
          escala=None, anota=1.0):
    """O SVG da linha, com cada peca marcada pelo id dela."""
    prontos, recusadas = simbolos_da_linha(linha)
    if not prontos:
        return {"svg": "", "pecas": 0, "recusadas": recusadas, "modo": modo}
    if giro is None:
        giro = getattr(linha, "giro", 0.0)
    ids = [peca.id for peca, _ in prontos]
    por_peca = {peca.id: lista for peca, lista in
                zip(linha.pecas, acessorios_da_linha(linha))}
    svg, postos, fim = desenhar_linha(
        [sim for _, sim in prontos], largura=largura, giro=giro,
        altura_max=altura_max, ids=ids, modo=modo, escala=escala, anota=anota,
        acessorios=[por_peca.get(peca.id, []) for peca, _ in prontos])
    return {"svg": svg, "pecas": len(prontos), "recusadas": recusadas,
            "fim": list(fim), "modo": modo}


def _os_dois_pead(a, b):
    """A juncao e soldada quando as duas pontas que se encontram sao de PEAD.

    O colar conta: ele solda no tubo por termofusao e leva a flange do outro
    lado - a flange dele nao esta nesta juncao, esta na ponta que vai para o
    aco.
    """
    return all(p.params.get("material") == "PEAD" for p in (a, b))


# As escalas de reducao da NBR 8196 / ISO 5455. As de "2,5" e "25" a norma
# admite em caso excepcional, e a casa usa as duas - casa de bomba de 6 m nao
# cabe em 1:20 numa A3 e sobra demais em 1:50.
ESCALAS = (1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 500, 1000)


def escala_que_cabe(largura_mm, altura_mm, extensao_x, extensao_y):
    """A maior escala NORMALIZADA em que o desenho cabe na area util.

    Escala de desenho nao e "o que couber": e um dos numeros da tabela, para
    que quem mede a folha com escalimetro ache a cota. Entao a conta e ao
    contrario do enquadramento de tela - acha-se o fator livre e sobe-se para
    a proxima escala da lista, sempre para o lado de caber.
    """
    livre = min(largura_mm / max(extensao_x, 1e-6),
                altura_mm / max(extensao_y, 1e-6))
    for divisor in ESCALAS:
        if 1 / divisor <= livre:
            return divisor
    return ESCALAS[-1]


def desenhar_linha(pecas, largura=940, giro=0.0, altura_max=620, ids=None,
                   modo="traco", escala=None, anota=1.0, acessorios=None):
    """A linha inteira em SVG, encadeando os simbolos pelas portas.

    Cada peca e desenhada uma vez, na origem, olhando para +x. Encaixar e uma
    transformacao rigida: girar pelo angulo corrente, transladar ate o ponto
    corrente. O tamanho vem da tabela de cotas, o angulo vem da curva, e a
    rotacao e acumulada - a peca herda a direcao que a anterior deixou.

    `ids` marca cada grupo com o id da peca. E o que liga o desenho a tabela:
    clicar no balao e clicar na linha sao a mesma peca, e a tela nao precisa
    saber desenhar nada para saber em quem o dedo caiu.
    """
    postos, fim = s.montar(pecas)
    # o acessorio entra na boca livre da peca que o carrega, encaixado como
    # qualquer outra: a entrada dele cai no ponto da boca, olhando para onde a
    # boca olha. E a mesma transformacao rigida de `montar`, uma peca so
    postos_extra = []
    juntas_extra = []
    for i, posto in enumerate(postos):
        # OS ACESSORIOS SE EMPILHAM. O primeiro entra na boca livre da peca da
        # corrente; o segundo, na boca livre do PRIMEIRO, e assim por diante -
        # que e como a coisa sobe na obra: o te recebe a flange cega, a flange
        # cega tem a luva de 2", e e na luva que a ventosa enrosca. Pondo os
        # dois na mesma boca eles sairiam um dentro do outro
        montagem = posto
        desta = []
        for identidade, simbolo in ((acessorios or [None] * len(postos))[i]
                                    or []):
            boca = porta_livre(montagem.simbolo)
            if boca is None:
                continue
            rad = math.radians(montagem.giro)
            cos, sen = math.cos(rad), math.sin(rad)
            px = montagem.dx + boca.x * cos - boca.y * sen
            py = montagem.dy + boca.x * sen + boca.y * cos
            direcao = montagem.giro + boca.direcao
            entrada = s.porta(simbolo, s.ENTRADA) or s.porta(simbolo, s.SAIDA)
            ex, ey = (entrada.x, entrada.y) if entrada else (0.0, 0.0)
            rad2 = math.radians(direcao)
            c2, s2 = math.cos(rad2), math.sin(rad2)
            montagem = s.Posto(
                simbolo, px - (ex * c2 - ey * s2), py - (ex * s2 + ey * c2),
                direcao, (px, py), (px, py))
            # A ORDEM DE MONTAGEM E O CONTRARIO DA ORDEM DE PINTURA. A ventosa
            # ENROSCA na luva da flange cega: ela entra por dentro, e quem tem
            # de ficar por cima e a luva. Empilhando na ordem em que se monta,
            # o ultimo desenhado tapa o anterior e a ventosa cobria a luva em
            # que ela esta enfiada. Entao a cadeia se monta para frente e se
            # pinta para tras
            desta.insert(0, (identidade, montagem))
            # a boca em que ele entrou: e ela que diz se ha JUNTA FLANGEADA
            # ali. A luva e rosca e nao leva parafuso; a derivacao do te e
            # flange e leva - e sem isto a flange cega saia sem ferragem
            # nenhuma, encostada no te por nada
            juntas_extra.append((px, py, direcao, boca, simbolo))
        postos_extra += desta
    if giro:
        # a sucção nasce no poço e sobe: a linha inteira gira para ficar de pé
        rad = math.radians(giro)
        cos, sen = math.cos(rad), math.sin(rad)
        vira = lambda x, y: (x * cos - y * sen, x * sen + y * cos)
        postos = [p._replace(dx=vira(p.dx, p.dy)[0], dy=vira(p.dx, p.dy)[1],
                             giro=p.giro + giro,
                             entrada=vira(*p.entrada), saida=vira(*p.saida))
                  for p in postos]
        fim = (*vira(fim[0], fim[1]), fim[2] + giro)
        postos_extra = [(identidade, p._replace(
            dx=vira(p.dx, p.dy)[0], dy=vira(p.dx, p.dy)[1],
            giro=p.giro + giro, entrada=vira(*p.entrada), saida=vira(*p.saida)))
            for identidade, p in postos_extra]
        juntas_extra = [(*vira(x, y), d + giro, boca, sim)
                        for x, y, d, boca, sim in juntas_extra]
    caixas = []
    for p in list(postos) + [p for _i, p in postos_extra]:
        x0, y0, w, h = p.simbolo.caixa
        rad = math.radians(p.giro)
        cos, sen = math.cos(rad), math.sin(rad)
        for cx, cy in ((x0, y0), (x0 + w, y0), (x0, y0 + h), (x0 + w, y0 + h)):
            caixas.append((p.dx + cx * cos - cy * sen, p.dy + cx * sen + cy * cos))
    minx = min(c[0] for c in caixas)
    maxx = max(c[0] for c in caixas)
    miny = min(c[1] for c in caixas)
    maxy = max(c[1] for c in caixas)
    # `escala` dada: a folha impressa manda, e o desenho sai no tamanho que
    # der. Sem ela, enquadra-se na caixa - cabendo na largura E na altura,
    # porque a sucção de bomba vertical é alta e estreita e escalando só pela
    # largura ela virava um poster
    margem = MARGEM * anota
    if escala is None:
        escala = min((largura - 2 * margem) / max(maxx - minx, 1),
                     (altura_max - 2 * margem) / max(maxy - miny, 1))
    largura = (maxx - minx) * escala + 2 * margem
    altura = (maxy - miny) * escala + 2 * margem

    # o modo e uma CLASSE, e nao um desenho diferente: a geometria e uma so, em
    # milimetro real, e as tres leituras saem da mesma folha de estilo
    if modo not in MODOS:
        modo = "traco"
    # um degrade por (cor, angulo) que a linha realmente usa - nao por peca:
    # vinte tubos deitados na mesma cor compartilham o mesmo
    degrades = {}
    partes = [f'<svg class="modo-{modo}" viewBox="0 0 {largura:.2f} '
              f'{altura:.2f}" width="{largura:.2f}" height="{altura:.2f}" '
              f'role="img" aria-label="linha montada">', DEFS, "@DEGRADES@",
              f'<g class="geo" transform="translate({margem - minx*escala:.2f} '
              f'{margem - miny*escala:.2f}) scale({escala:.5f})">']
    # A FERRAGEM FICA POR CIMA, e pode: nada dela cruza a chapa.
    #
    # O parafuso atravessa o furo da flange, e por dentro da chapa ele nao se
    # ve - mas quem resolve isso e a PROPRIA haste, que sai desenhada so nos
    # pedacos de fora (simbolos.haste_aparente). Poe-la debaixo da peca
    # resolveria a chapa e criaria outro problema: os parafusos que caem sobre
    # o tubo, que na projecao sao metade deles, sumiriam junto.
    #
    # A wafer e a excecao da juncao: ela nao tem flange, e abracada pelas duas
    # vizinhas, e entao as duas juncoes viram uma so, com barra roscada de
    # ponta a ponta.
    wafer = {i for i, p in enumerate(postos) if p.simbolo.params.get("wafer")}
    ruins = []
    sob, sobre = [], []

    def guardar(elementos, embrulho=("", "")):
        if elementos:
            sobre.append(embrulho[0]
                         + "".join(desenhar(e) for e in elementos)
                         + embrulho[1])

    for i, p in enumerate(postos[:-1]):
        if i in wafer or (i + 1) in wafer:
            continue
        ok, motivo = s.encaixa(p.simbolo, postos[i + 1].simbolo)
        saida = s.porta(p.simbolo, s.SAIDA)
        if ok and saida is not None:
            direcao = p.giro + (saida.direcao if saida.papel != "entrada" else 0)
            vizinho = postos[i + 1].simbolo
            # PEAD com PEAD e SOLDA e nao flange: nenhuma das duas pontas tem
            # chapa, e o que sobra na juncao e o cordao de termofusao. A flange
            # do PEAD aparece so onde o colar casa com a linha de aco
            if _os_dois_pead(p.simbolo, vizinho):
                guardar(s.solda_de_topo(
                    p.saida[0], p.saida[1], direcao,
                    p.simbolo.params.get("dn_mm") or 225))
            else:
                # o parafuso sai no tamanho do CODIGO que a lista vai comprar
                # - a mesma tabela dos dois lados. Desenhar um comprimento
                # plausivel mentiria exatamente onde mais se olha
                material = (p.simbolo.params.get("material"),
                            vizinho.params.get("material"))
                ficha = regras.parafuso_da_junta(
                    saida.dn_pol, regras.contexto_da_junta(*material))
                # e cada lado poe a chapa DELE: aco poe uma, Plasson poe duas
                # (ressalto do colar + flange solta). Onde os dois lados sao
                # diferentes a junta e assimetrica, e o parafuso tem de sair
                # deslocado - senao a cabeca fica dentro da flange de um lado
                chapas, vaos, face = _pilha_da_junta(saida.dn_pol, material)
                guardar(s.junta_flangeada(
                    p.saida[0], p.saida[1], direcao, saida.dn_pol,
                    comprimento_mm=ficha["comprimento_mm"],
                    bitola_mm=ficha["bitola_mm"],
                    chapas=chapas, vaos=vaos, face_mm=face))
        else:
            ruins.append((p, motivo))
    # a JUNTA DO ACESSORIO. Ele entra na boca livre de quem o carrega, e se
    # essa boca for FLANGE ela leva ferragem como qualquer outra - a flange
    # cega no alto do te nao se segura sozinha. Se for LUVA nao leva: ali e
    # rosca, e rosca nao tem parafuso
    for px, py, direcao, boca, simbolo in juntas_extra:
        if boca.papel not in ("derivacao", "bocal", "saida", "entrada"):
            continue
        material = (None, simbolo.params.get("material"))
        ficha = regras.parafuso_da_junta(
            boca.dn_pol, regras.contexto_da_junta(*material))
        chapas, vaos, face = _pilha_da_junta(boca.dn_pol, material)
        guardar(s.junta_flangeada(
            px, py, direcao, boca.dn_pol,
            comprimento_mm=ficha["comprimento_mm"],
            bitola_mm=ficha["bitola_mm"],
            chapas=chapas, vaos=vaos, face_mm=face))

    for i in sorted(wafer):
        p = postos[i]
        entrada = s.porta(p.simbolo, s.ENTRADA)
        comp = abs(s.porta(p.simbolo, s.SAIDA).x - entrada.x)
        # a ferragem sai no eixo da propria peca e viaja com ela, no mesmo
        # grupo de transformacao que o corpo - senao ela fica solta na folha
        guardar(s.sanduiche_wafer(0.0, comp, 0.0, 0.0, entrada.dn_pol),
                (f'<g transform="translate({p.dx:.1f} {p.dy:.1f}) '
                 f'rotate({p.giro:g})">', "</g>"))
    partes += sob

    for i, p in enumerate(postos):
        cor = cor_de(p.simbolo)
        espelhada = bool(p.simbolo.params.get("espelhado"))
        corpo = desenhar_peca([e for e in p.simbolo.elementos
                               if e["tipo"] != "texto_furos"],
                              cor, p.giro, espelhada, degrades)
        marca = (f' data-id="{ids[i]}"'
                 if ids and i < len(ids) and ids[i] else "")
        if marca:
            # a area de clique da peca. Sem ela so o traco recebe o dedo, e
            # traco de 1 px nao e alvo: quem quer selecionar o tubo aponta
            # para o meio dele, que e vazio
            cx, cy, cw, ch = s.caixa_do_corpo(p.simbolo)
            corpo = (f'<rect class="alvo" x="{cx:.1f}" y="{cy:.1f}" '
                     f'width="{max(cw, 1):.1f}" height="{max(ch, 1):.1f}"/>'
                     + corpo)
        # a librea vai no GRUPO da peca, e nao no traco: quem decide a cor e
        # o motor (svg.cor_de), a folha so aplica. E `luz_de` pre-gira o
        # degrade do tanto contrario ao giro da peca, para a luz continuar
        # vindo de cima da FOLHA - senao numa linha de pe o tubo fica claro de
        # um lado e escuro do outro, como se a luz viesse da parede
        pintura = f' data-cor="{cor}"' if cor else ""
        estilo, novos = luz_de(cor, p.giro, espelhada)
        degrades.update(novos)
        partes.append(f'<g class="peca"{marca}{pintura}'
                      f' data-familia="{p.simbolo.familia}"'
                      f' style="{estilo}" '
                      f'transform="translate({p.dx:.1f} {p.dy:.1f}) '
                      f'rotate({p.giro:g})">{corpo}</g>')
    for identidade, p in postos_extra:
        cor = cor_de(p.simbolo)
        espelhada = bool(p.simbolo.params.get("espelhado"))
        corpo = desenhar_peca([e for e in p.simbolo.elementos
                               if e["tipo"] != "texto_furos"],
                              cor, p.giro, espelhada, degrades)
        cx, cy, cw, ch = s.caixa_do_corpo(p.simbolo)
        corpo = (f'<rect class="alvo" x="{cx:.1f}" y="{cy:.1f}" '
                 f'width="{max(cw, 1):.1f}" height="{max(ch, 1):.1f}"/>' + corpo)
        estilo, novos = luz_de(cor, p.giro, espelhada)
        degrades.update(novos)
        partes.append(f'<g class="peca acessorio" data-id="{identidade}"'
                      f'{f" data-cor={chr(34)}{cor}{chr(34)}" if cor else ""}'
                      f' data-familia="{p.simbolo.familia}" style="{estilo}" '
                      f'transform="translate({p.dx:.1f} {p.dy:.1f}) '
                      f'rotate({p.giro:g})">{corpo}</g>')
    partes += sobre
    partes.append("</g>")
    # A MEDIDA VAI SO NO TUBO - aco zincado, PVC, Plasson, PEAD.
    #
    # E a unica peca cuja medida alguem precisa ler no desenho, porque e a
    # unica que se CORTA: o comprimento dela e decisao de projeto. O resto -
    # curva, valvula, reducao, manifold - vem com a medida presa ao codigo
    # SAP, e quem quiser conferir olha a lista, que esta na mesma folha.
    #
    # Cotar tudo enchia o desenho de numero que ninguem usa, e um desenho em
    # que toda peca fala e um desenho em que nenhuma se ouve.
    partes.append('<g class="anota">')
    for p in postos:
        if p.simbolo.familia != "TUBO":
            continue
        entrada, saida = s.porta(p.simbolo, s.ENTRADA), s.porta(p.simbolo, s.SAIDA)
        if entrada is None or saida is None:
            entrada = entrada or saida
            saida = saida or entrada
        comp = ((saida.x - entrada.x) ** 2 + (saida.y - entrada.y) ** 2) ** 0.5
        vao = comp * escala
        if vao < 44 * anota:         # peca curta: a cota nao cabe dentro dela
            continue
        # A COTA CAI NO EIXO DA PECA, e nao no meio entre as duas portas.
        # Numa curva o meio das portas cai na CORDA, que passa por fora do
        # tubo - a cota ia parar no ar ao lado da peca. `meio_do_eixo` anda
        # pelo eixo desenhado e para na metade do comprimento dele, que numa
        # curva e dentro da volta. E devolve a direcao do eixo ALI, que e
        # como a cota sabe em que angulo deitar.
        meio = s.meio_do_eixo(p.simbolo)
        rad = math.radians(p.giro)
        cos, sen = math.cos(rad), math.sin(rad)
        if meio is None:
            local = ((p.entrada[0] + p.saida[0]) / 2,
                     (p.entrada[1] + p.saida[1]) / 2)
            direcao = math.degrees(math.atan2(p.saida[1] - p.entrada[1],
                                              p.saida[0] - p.entrada[0]))
        else:
            local = (p.dx + meio[0] * cos - meio[1] * sen,
                     p.dy + meio[0] * sen + meio[1] * cos)
            direcao = meio[2] + p.giro
        mx = margem + (local[0] - minx) * escala
        my = margem + (local[1] - miny) * escala
        # a cota deita junto com o eixo, mas nunca de cabeca para baixo: fora
        # de -90..90 ela leria ao contrario, e ai vira meia volta
        direcao = (direcao + 180) % 360 - 180
        if direcao > 90 or direcao < -90:
            direcao -= 180 if direcao > 0 else -180
        gira = (f' transform="rotate({direcao:.1f} {mx:.2f} {my:.2f})"'
                if abs(direcao) > 0.5 else "")
        duas = abs((entrada.dn_pol or 0) - (saida.dn_pol or 0)) > 0.01
        # no PEAD a bitola do papel e o DN em milimetro, que E o externo
        bitola = (f'DN{p.simbolo.params["dn_mm"]:g}'
                  if p.simbolo.params.get("dn_mm")
                  else f'{(entrada.dn_pol or 0):g}"')
        rotulo = f"{comp:.0f}" if duas else f"{bitola}  {comp:.0f}"
        partes.append(texto_no_eixo(mx, my, rotulo, "marca", 9.0 * anota, gira))
        if duas:
            # a bitola de cada flange, na sua ponta
            for porta, ponto in ((entrada, p.entrada), (saida, p.saida)):
                meia = s.flange(porta.dn_pol)["externo"] / 2 * escala
                px = margem + (ponto[0] - minx) * escala
                py = margem + (ponto[1] - miny) * escala - meia - 4 * anota
                partes.append(f'<text class="marca" x="{px:.2f}" '
                              f'y="{py:.2f}" '
                              f'style="font-size:{9.0 * anota:.2f}px">'
                              f'{porta.dn_pol:g}"</text>')
    for p, motivo in ruins:
        px = margem + (p.saida[0] - minx) * escala
        py = margem + (p.saida[1] - miny) * escala
        partes.append(f'<circle class="juncao ruim" cx="{px:.1f}" cy="{py:.1f}" '
                      f'r="{4 * anota:.2f}"/>')
    partes.append("</g></svg>")
    saida = "".join(partes)
    saida = saida.replace("@DEGRADES@",
                          f'<defs>{"".join(degrades.values())}</defs>'
                          if degrades else "")
    return saida, postos, fim
