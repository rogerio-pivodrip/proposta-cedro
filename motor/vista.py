"""A vista lateral da linha: o documento virado desenho.

Estava em tools/desenhar_linha.py, que e uma ferramenta. Subiu para o motor
pelo mesmo motivo que motor/svg.py subiu: a tela do programa precisa do mesmo
desenho da folha, e o desenho e do motor.

A funcao de baixo desenha uma lista de SIMBOLOS. A de cima recebe a `Linha` -
o documento - e faz a ponte: cada peca do catalogo vira um simbolo por
motor/desenho.de_item, e o id da peca vai junto para o grupo do SVG.
"""
import math

from . import colisao, desenho, regras, simbolos as s
from .svg import (DEFS, ESTILO, ESTILO_LINHA, cor_de,  # noqa: F401
                  desenhar, desenhar_peca, luz_de, texto_no_eixo)

MODOS = ("traco", "pb", "metal")

MARGEM = 46

# O BALAO DE DETALHAMENTO, como o de vista explodida de manual: um pontinho
# pousado na peca, um traco reto saindo dele e o numero do item num circulo.
#
# Tudo aqui e PIXEL de anotacao, e nao milimetro real - o balao nao cresce
# quando a linha muda de escala, do mesmo jeito que a cota nao cresce. E a
# distancia padrao nao e um numero fixo: o traco anda ate SAIR da peca em que
# pousou, e so entao o circulo comeca. Numa peca grande ele anda mais, e e por
# isso que o balao continua fora do desenho quando a linha muda de bitola.
BALAO_R = 10.0          # raio do circulo do numero
BALAO_FOLGA = 14.0      # do contorno da peca ate a borda do circulo
BALAO_PONTO = 1.9       # o pontinho que pousa na peca
BALAO_PASSO = 4.0       # o quanto um balao se afasta ao esbarrar no vizinho


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
            # o CORTE vai junto: o tubo e a unica peca que se corta, e o
            # comprimento dele e da instancia, nao do codigo
            simbolo = desenho.de_item(peca.item,
                                      getattr(peca, "pose", None),
                                      peca.comprimento_mm)
            # o `sentido` da peca e o espelho da linha se multiplicam: a curva
            # que ja descia, numa linha espelhada, volta a subir. Espelhar o
            # SIMBOLO e o que faz a corrente inteira acompanhar - montar()
            # encadeia pelas portas, e a porta espelhada vira a linha para o
            # outro lado sozinha
            if peca.sentido * espelho_da_linha < 0:
                simbolo = s.espelhado(simbolo)
            prontos.append((peca, simbolo))
        except Exception as erro:                       # noqa: BLE001
            # recusa DELIBERADA - peca sem simbolo, tamanho fora da folha -
            # sai so com o motivo; o nome da excecao ali so serviria para
            # assustar quem esta montando. O tipo fica para o que e defeito
            # de verdade, que e onde ele ajuda a achar o erro
            proposital = isinstance(erro, (desenho.SemSimbolo, ValueError))
            recusadas.append({"id": peca.id, "sap": peca.sap,
                              "descricao": peca.descricao,
                              "motivo": (str(erro) if proposital
                                         else f"{type(erro).__name__}: {erro}")})
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


def bocas_livres(simbolo, gastas=0):
    """As bocas que a corrente nao usa, da primeira em diante.

    `gastas` sao as que o acessorio ja tomou: uma pilha de acessorios ocupa
    UMA boca, nao uma por acessorio - eles se empilham um no outro. O ramo
    entra na proxima, e por isso ele nunca nasce em cima da flange cega.
    """
    livres = [p for p in simbolo.portas
              if p.papel not in s.ENTRADA + s.SAIDA]
    return livres[gastas:]


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


def ramos_de(projeto, montagem):
    """A arvore de ramos que pende desta montagem, pronta para desenhar.

    Recursiva: um ramo pode ter ramos. E o que faz um barrilete com quatro
    saidas, uma delas virando outro barrilete, sair no mesmo desenho.
    """
    saida = []
    for filho in projeto.filhos(montagem):
        prontos, _recusadas = simbolos_da_linha(filho)
        por_peca = {p.id: lista for p, lista in
                    zip(filho.pecas, acessorios_da_linha(filho))}
        saida.append({
            "montagem": filho.id,
            "peca": (filho.origem or {}).get("peca"),
            "boca": (filho.origem or {}).get("boca", 0),
            "pecas": [sim for _p, sim in prontos],
            "ids": [p.id for p, _sim in prontos],
            "acessorios": [por_peca.get(p.id, []) for p, _sim in prontos],
            "ramos": ramos_de(projeto, filho),
        })
    return saida


def vista(linha, largura=940, altura_max=620, giro=None, modo="traco",
          escala=None, anota=1.0, projeto=None):
    """O SVG da linha, com cada peca marcada pelo id dela.

    Com um `projeto`, desenha a ARVORE: a montagem de onde esta pende e tudo
    o que sai dela. E o que faz ver o barrilete inteiro enquanto se edita uma
    saida - quem monta duas bombas em paralelo precisa ver as duas.
    """
    if projeto is not None:
        raiz = projeto.raiz(linha)
        if raiz is not linha:
            return vista(raiz, largura=largura, altura_max=altura_max,
                         giro=giro, modo=modo, escala=escala, anota=anota,
                         projeto=projeto)
    prontos, recusadas = simbolos_da_linha(linha)
    if not prontos:
        return {"svg": "", "pecas": 0, "recusadas": recusadas, "modo": modo,
                "colisoes": []}
    if giro is None:
        giro = getattr(linha, "giro", 0.0)
    ids = [peca.id for peca, _ in prontos]
    por_peca = {peca.id: lista for peca, lista in
                zip(linha.pecas, acessorios_da_linha(linha))}
    # o balao de cada peca vem do DOCUMENTO, com o numero que a lista deu -
    # a vista nao numera nada. Fosse ela a contar, o numero mudaria ao girar a
    # folha ou ao esconder um balao, e o desenho discordaria da lista
    if projeto is not None:
        numerados = {b["id"]: b for b in projeto.baloes(linha)}
        ramos = ramos_de(projeto, linha)
    else:
        numerados = {b["id"]: b for b in linha.baloes()}
        ramos = None
    svg, postos, fim, colisoes = desenhar_linha(
        [sim for _, sim in prontos], largura=largura, giro=giro,
        altura_max=altura_max, ids=ids, modo=modo, escala=escala, anota=anota,
        acessorios=[por_peca.get(peca.id, []) for peca, _ in prontos],
        baloes=numerados, ramos=ramos, montagem=linha.id)
    return {"svg": svg, "pecas": len(prontos), "recusadas": recusadas,
            "fim": list(fim), "modo": modo, "colisoes": colisoes,
            "baloes": [{"id": b["id"], "item": b["n"]}
                       for b in numerados.values()]}


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


def _pouso_do_balao(posto, escala, ox, oy):
    """Onde o pontinho pousa na peca, e a caixa que o traco tem de vencer.

    Devolve os dois em pixel de tela. A caixa e a do CORPO - a caixa cheia
    inclui a linha de eixo, que sai 40 mm antes da peca e 60 depois, e o balao
    ficaria pendurado longe, apontando para o vazio.
    """
    x0, y0, w, h = s.caixa_do_corpo(posto.simbolo)
    # no tubo o pontinho nao pousa no meio: o meio ja e da cota, e o balao
    # cairia bem em cima do numero do comprimento
    fatia = 0.28 if posto.simbolo.familia == "TUBO" else 0.5
    rad = math.radians(posto.giro)
    cos, sen = math.cos(rad), math.sin(rad)

    def na_tela(cx, cy):
        return (ox + (posto.dx + cx * cos - cy * sen) * escala,
                oy + (posto.dy + cx * sen + cy * cos) * escala)

    cantos = [na_tela(cx, cy) for cx, cy in
              ((x0, y0), (x0 + w, y0), (x0, y0 + h), (x0 + w, y0 + h))]
    caixa = (min(c[0] for c in cantos), min(c[1] for c in cantos),
             max(c[0] for c in cantos), max(c[1] for c in cantos))
    return na_tela(x0 + w * fatia, y0 + h / 2), caixa


def _saida_da_caixa(ponto, caixa, ux, uy):
    """Quanto o traco anda, do pouso ate deixar a caixa da peca."""
    andar = []
    if abs(ux) > 1e-6:
        andar.append(((caixa[2] if ux > 0 else caixa[0]) - ponto[0]) / ux)
    if abs(uy) > 1e-6:
        andar.append(((caixa[3] if uy > 0 else caixa[1]) - ponto[1]) / uy)
    return max(min([a for a in andar if a > 0], default=0.0), 0.0)


def _saida_do_desenho(ponto, propria, caixas, ux, uy):
    """O mesmo, mas atravessando o que estiver ENCOSTADO na peca.

    Sair da propria caixa nao basta quando ha peca em cima: a ventosa
    enroscada na luva da flange cega ocupa o canto para onde o balao dela
    ia, e o numero pousava sobre o desenho. Entao o traco segue enquanto o
    proximo passo ainda cair dentro de alguma caixa, e para no primeiro vao.

    Para no VAO, e nao na ultima peca da folha, de proposito: parar so no fim
    faria o balao de um tubo do meio viajar a linha inteira.
    """
    anda = _saida_da_caixa(ponto, propria, ux, uy)
    for _volta in range(len(caixas) + 1):
        px = ponto[0] + ux * (anda + 0.5)
        py = ponto[1] + uy * (anda + 0.5)
        vizinha = next((c for c in caixas
                        if c[0] <= px <= c[2] and c[1] <= py <= c[3]), None)
        if vizinha is None:
            return anda
        anda = max(anda, _saida_da_caixa(ponto, vizinha, ux, uy))
    return anda


def lugares_dos_baloes(postos, baloes, escala, ox, oy, anota=1.0,
                       estorvos=()):
    """Onde cada balao cai. [(id, numero, pouso, centro)], em pixel.

    O angulo e o do CROQUI - anti-horario, 0 para a direita - e nao o do SVG,
    que tem o y para baixo. Quem digita "45" quer o balao para cima e para a
    direita, e a conversao e aqui, num lugar so.

    Dois baloes nunca se sobrepoem: o segundo anda mais pelo proprio traco ate
    limpar o primeiro. Afastar pelo traco, e nao para o lado, mantem o balao
    apontando para a mesma peca - so o fio fica um pouco mais longo.
    """
    raio = BALAO_R * anota
    pousos = [(identidade, posto) + _pouso_do_balao(posto, escala, ox, oy)
              for identidade, posto in postos]
    # o que o traco tem de vencer: a caixa de cada peca E a da ferragem que
    # nasce entre elas, que nao e de peca nenhuma
    caixas = [caixa for _i, _p, _pouso, caixa in pousos] + [
        (ox + x0 * escala, oy + y0 * escala,
         ox + x1 * escala, oy + y1 * escala) for x0, y0, x1, y1 in estorvos]
    lugares = []
    for identidade, _posto, pouso, caixa in pousos:
        ficha = (baloes or {}).get(identidade)
        if not ficha:
            continue
        rad = math.radians(ficha.get("angulo") or 0.0)
        ux, uy = math.cos(rad), -math.sin(rad)
        anda = ficha.get("distancia")
        if anda is None:
            anda = (_saida_do_desenho(pouso, caixa, caixas, ux, uy)
                    + (BALAO_FOLGA + BALAO_R) * anota)
        else:
            anda = float(anda) * anota
        centro = (pouso[0] + ux * anda, pouso[1] + uy * anda)
        # o desempate: enquanto encostar em quem ja esta posto, anda mais
        for _volta in range(60):
            perto = next((c for _i, _n, _p, c in lugares
                          if math.dist(c, centro) < 2 * raio + 3 * anota), None)
            if perto is None:
                break
            anda += (2 * raio + BALAO_PASSO * anota)
            centro = (pouso[0] + ux * anda, pouso[1] + uy * anda)
        lugares.append((identidade, ficha["n"], pouso, centro))
    return lugares


def _desenhar_balao(identidade, numero, pouso, centro, anota=1.0):
    """O pontinho, o fio e o numero no circulo. Um grupo por balao.

    O grupo leva o id da peca porque o balao E a peca: clicar nele seleciona,
    arrastar move o balao dela. Por isso ele fica FORA do grupo `anota`, que
    nao recebe clique nenhum.
    """
    raio = BALAO_R * anota
    dx, dy = centro[0] - pouso[0], centro[1] - pouso[1]
    dist = math.hypot(dx, dy) or 1.0
    # o fio para na BORDA do circulo, e nao no centro: atravessado, ele
    # cortaria o numero ao meio
    fx = centro[0] - dx / dist * raio
    fy = centro[1] - dy / dist * raio
    traco = 0.8 * anota
    return (f'<g class="balao" data-id="{identidade}" data-item="{numero}">'
            f'<line class="fio" x1="{pouso[0]:.2f}" y1="{pouso[1]:.2f}" '
            f'x2="{fx:.2f}" y2="{fy:.2f}" '
            f'style="stroke-width:{traco:.2f}"/>'
            f'<circle class="pouso" cx="{pouso[0]:.2f}" cy="{pouso[1]:.2f}" '
            f'r="{BALAO_PONTO * anota:.2f}"/>'
            f'<circle class="bola" cx="{centro[0]:.2f}" cy="{centro[1]:.2f}" '
            f'r="{raio:.2f}" style="stroke-width:{traco:.2f}"/>'
            f'<text class="n" x="{centro[0]:.2f}" '
            f'y="{centro[1] + 3.4 * anota:.2f}" '
            f'style="font-size:{9.5 * anota:.2f}px">{numero}</text></g>')


def _rigida(x, y, graus):
    """A transformacao que leva (0,0) olhando para +x ate (x,y) olhando para `graus`."""
    rad = math.radians(graus)
    cos, sen = math.cos(rad), math.sin(rad)

    def levar(px, py):
        return (x + px * cos - py * sen, y + px * sen + py * cos)

    return levar, graus


def _encaixar_corrente(postos, levar, giro):
    """A corrente inteira levada para a boca em que ela nasce.

    E a mesma transformacao rigida do acessorio, aplicada a uma CORRENTE em
    vez de a uma peca. Por isso o ramo nao precisou de geometria propria: o
    que ja sabia montar uma linha monta o ramo, e o que sabia pendurar um
    acessorio pendura a linha inteira.
    """
    saida = []
    for p in postos:
        dx, dy = levar(p.dx, p.dy)
        saida.append(p._replace(dx=dx, dy=dy, giro=p.giro + giro,
                                entrada=levar(*p.entrada),
                                saida=levar(*p.saida)))
    return saida


def desenhar_linha(pecas, largura=940, giro=0.0, altura_max=620, ids=None,
                   modo="traco", escala=None, anota=1.0, acessorios=None,
                   baloes=None, ramos=None, montagem=None):
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
    # OS PARES QUE SE ENCOSTAM DE PROPOSITO. A conferencia de colisao precisa
    # deles: duas pecas encadeadas se tocam face a face, e a chapa da flange e
    # desenhada para dentro do corpo - sem esta lista todo par vizinho viraria
    # aviso. Ver motor/colisao.py
    encostam = [(a, b) for a, b in zip(ids or [], (ids or [])[1:])]
    de_ramo = {}          # id da peca -> id da montagem, para as de ramo
    for i, posto in enumerate(postos):
        # OS ACESSORIOS SE EMPILHAM. O primeiro entra na boca livre da peca da
        # corrente; o segundo, na boca livre do PRIMEIRO, e assim por diante -
        # que e como a coisa sobe na obra: o te recebe a flange cega, a flange
        # cega tem a luva de 2", e e na luva que a ventosa enrosca. Pondo os
        # dois na mesma boca eles sairiam um dentro do outro
        # `empilhada` e a peca em que o PROXIMO acessorio vai entrar: a
        # primeira e a da corrente, a segunda e o acessorio anterior. (Ja se
        # chamou `montagem`, e o nome colidiu com a montagem do documento
        # quando ela passou a ser marcada em cada grupo do SVG.)
        empilhada = posto
        anterior_id = (ids or [None] * len(postos))[i]
        desta = []
        for identidade, simbolo in ((acessorios or [None] * len(postos))[i]
                                    or []):
            boca = porta_livre(empilhada.simbolo)
            if boca is None:
                continue
            rad = math.radians(empilhada.giro)
            cos, sen = math.cos(rad), math.sin(rad)
            px = empilhada.dx + boca.x * cos - boca.y * sen
            py = empilhada.dy + boca.x * sen + boca.y * cos
            direcao = empilhada.giro + boca.direcao
            entrada = s.porta(simbolo, s.ENTRADA) or s.porta(simbolo, s.SAIDA)
            ex, ey = (entrada.x, entrada.y) if entrada else (0.0, 0.0)
            rad2 = math.radians(direcao)
            c2, s2 = math.cos(rad2), math.sin(rad2)
            empilhada = s.Posto(
                simbolo, px - (ex * c2 - ey * s2), py - (ex * s2 + ey * c2),
                direcao, (px, py), (px, py))
            # A ORDEM DE MONTAGEM E O CONTRARIO DA ORDEM DE PINTURA. A ventosa
            # ENROSCA na luva da flange cega: ela entra por dentro, e quem tem
            # de ficar por cima e a luva. Empilhando na ordem em que se monta,
            # o ultimo desenhado tapa o anterior e a ventosa cobria a luva em
            # que ela esta enfiada. Entao a cadeia se monta para frente e se
            # pinta para tras
            desta.insert(0, (identidade, empilhada))
            encostam.append((anterior_id, identidade))
            anterior_id = identidade
            # a boca em que ele entrou: e ela que diz se ha JUNTA FLANGEADA
            # ali. A luva e rosca e nao leva parafuso; a derivacao do te e
            # flange e leva - e sem isto a flange cega saia sem ferragem
            # nenhuma, encostada no te por nada
            juntas_extra.append((px, py, direcao, boca, simbolo))
        postos_extra += desta

    # OS RAMOS. Cada um e uma corrente inteira que nasce numa boca livre de
    # uma peca desta - o barrilete com quatro saidas, as duas bombas em
    # paralelo, a adução que sai do te. Ele nao e acessorio: acessorio FECHA a
    # boca, o ramo CONTINUA a partir dela.
    #
    # E a mesma transformacao rigida do acessorio, so que aplicada a uma
    # corrente: monta-se o ramo na origem, acha-se a boca em que ele nasce, e
    # leva-se tudo para la. Por isso o ramo nao precisou de geometria propria.
    def pendurar(nos, identidades, gastas_por_peca, filhos_do_no):
        """Poe cada ramo na boca em que ele nasce - e os ramos dele tambem.

        Recursivo de proposito: barrilete com quatro saidas, e uma delas
        virando outro barrilete, e a mesma coisa duas vezes.
        """
        for ramo in (filhos_do_no or []):
            _pendurar_um(nos, identidades, gastas_por_peca, ramo)

    def _pendurar_um(nos, identidades, gastas_por_peca, ramo):
        onde = next(((i, p) for i, p in enumerate(nos)
                     if i < len(identidades)
                     and identidades[i] == ramo.get("peca")), None)
        if onde is None:
            return
        i, dono = onde
        gastas = gastas_por_peca[i] if i < len(gastas_por_peca) else 0
        bocas = bocas_livres(dono.simbolo, gastas)
        indice = int(ramo.get("boca") or 0)
        if indice >= len(bocas):
            return                      # boca que nao existe: o ramo nao cai
        boca = bocas[indice]
        rad = math.radians(dono.giro)
        cos, sen = math.cos(rad), math.sin(rad)
        px = dono.dx + boca.x * cos - boca.y * sen
        py = dono.dy + boca.x * sen + boca.y * cos
        direcao = dono.giro + boca.direcao
        filhos, _fim = s.montar(ramo["pecas"])
        if not filhos:
            return
        levar, volta = _rigida(px, py, direcao)
        # a corrente nasce com a entrada na origem; o que sobra e leva-la
        entrada = s.porta(filhos[0].simbolo, s.ENTRADA)
        recuo = (entrada.x, entrada.y) if entrada else (0.0, 0.0)
        colocados = _encaixar_corrente(
            [p._replace(dx=p.dx - recuo[0], dy=p.dy - recuo[1],
                        entrada=(p.entrada[0] - recuo[0],
                                 p.entrada[1] - recuo[1]),
                        saida=(p.saida[0] - recuo[0], p.saida[1] - recuo[1]))
             for p in filhos], levar, volta)
        marcas = ramo.get("ids") or [None] * len(colocados)
        postos_extra.extend(zip(marcas, colocados))
        # o ramo encosta em quem o carrega, e as pecas dele encostam entre si
        encostam.append((identidades[i], marcas[0]))
        encostam.extend(zip(marcas, marcas[1:]))
        # a peca do ramo nao e acessorio, e e de OUTRA montagem: quem clicar
        # nela tem de cair na montagem dela, e nao numa peca que a aba aberta
        # nao conhece
        for marca in marcas:
            de_ramo[marca] = ramo.get("montagem")
        # a boca em que ele nasceu leva ferragem como qualquer outra juncao
        juntas_extra.append((px, py, direcao, boca, filhos[0].simbolo))
        # e os ramos DELE, na mesma conta
        pendurar(colocados, list(marcas), [0] * len(colocados),
                 ramo.get("ramos"))

    pendurar(postos, list(ids or [None] * len(postos)),
             [1 if a else 0 for a in (acessorios or [None] * len(postos))],
             ramos)
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
    # DUAS PECAS NO MESMO LUGAR. So aqui isso se pode saber: e a pose que
    # colide, e a pose so existe depois de encadear os simbolos e girar a
    # folha. Ver motor/colisao.py - le os postos ja colocados, os mesmos que
    # viram SVG, para nao criar uma terceira geometria
    colisoes = colisao.conferir(
        list(zip(ids or [None] * len(postos), postos)) + list(postos_extra),
        encostam)
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
    # a origem do desenho na folha: e por ela que a anotacao converte
    # milimetro real em pixel de tela, e nao pela margem - depois dos baloes a
    # margem de cima ja nao e a de baixo
    ox, oy = margem - minx * escala, margem - miny * escala


    # o modo e uma CLASSE, e nao um desenho diferente: a geometria e uma so, em
    # milimetro real, e as tres leituras saem da mesma folha de estilo
    if modo not in MODOS:
        modo = "traco"
    # um degrade por (cor, angulo) que a linha realmente usa - nao por peca:
    # vinte tubos deitados na mesma cor compartilham o mesmo
    degrades = {}
    # o tamanho da folha e a origem do desenho so se sabem depois de por os
    # baloes, e os baloes so se poem depois de saber o que ha na folha para
    # eles desviarem. Entao o cabecalho fica marcado e se preenche no fim -
    # o mesmo que ja se faz com os degrades
    partes = ["@SVG@", DEFS, "@DEGRADES@", "@GEO@"]
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

    estorvos = []          # o que o balao tem de contornar, alem das pecas

    def guardar(elementos, embrulho=("", "")):
        if elementos:
            sobre.append(embrulho[0]
                         + "".join(desenhar(e) for e in elementos)
                         + embrulho[1])
            # so o que sai em milimetro absoluto entra na conta do balao. O
            # sanduiche da wafer vai embrulhado no proprio grupo da peca, e a
            # caixa dele ja e a da peca
            if embrulho == ("", ""):
                x0, y0, w, h = s.limites(elementos)
                estorvos.append((x0, y0, x0 + w, y0 + h))

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
                      + (f' data-montagem="{montagem}"' if montagem else "")
                      + f' data-familia="{p.simbolo.familia}"'
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
        # acessorio e peca de ramo saem os dois daqui, e nao sao a mesma
        # coisa: o acessorio vive DENTRO da peca que o carrega, o ramo e uma
        # montagem inteira pendurada numa boca. Quem clica precisa saber qual
        ramo = de_ramo.get(identidade)
        partes.append(f'<g class="peca {"ramo" if ramo else "acessorio"}"'
                      f' data-id="{identidade}"'
                      + (f' data-montagem="{ramo or montagem}"'
                         if (ramo or montagem) else "")
                      + f'{f" data-cor={chr(34)}{cor}{chr(34)}" if cor else ""}'
                      f' data-familia="{p.simbolo.familia}" style="{estilo}" '
                      f'transform="translate({p.dx:.1f} {p.dy:.1f}) '
                      f'rotate({p.giro:g})">{corpo}</g>')
    partes += sobre
    partes.append("</g>")

    # O BALAO ENTRA NO ENQUADRAMENTO. Ele sai do desenho para nao tapar peca
    # nenhuma, e sair do desenho e sair da folha se a folha nao crescer junto:
    # os de cima ficariam cortados na borda. Entao mede-se onde eles cairam e
    # abre-se o tanto que falta, de cada lado.
    #
    # E so aqui, e nao la em cima, porque a FERRAGEM DA JUNTA nao pertence a
    # peca nenhuma - ela nasce entre duas - e sem ela na conta o balao pousava
    # em cima dos parafusos, que e justamente onde o desenho e mais cheio
    lugares = lugares_dos_baloes(
        [(ids[i] if ids and i < len(ids) else None, p)
         for i, p in enumerate(postos)] + list(postos_extra),
        baloes, escala, ox, oy, anota, estorvos)
    if lugares:
        raio = BALAO_R * anota + 2 * anota
        esq = max(0.0, raio - min(c[0] for _i, _n, _p, c in lugares))
        topo = max(0.0, raio - min(c[1] for _i, _n, _p, c in lugares))
        dir_ = max(0.0, max(c[0] for _i, _n, _p, c in lugares) + raio - largura)
        baixo = max(0.0, max(c[1] for _i, _n, _p, c in lugares) + raio - altura)
        if esq or topo or dir_ or baixo:
            largura += esq + dir_
            altura += topo + baixo
            ox, oy = ox + esq, oy + topo
            lugares = [(i, n, (p[0] + esq, p[1] + topo),
                        (c[0] + esq, c[1] + topo))
                       for i, n, p, c in lugares]
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
        mx = ox + local[0] * escala
        my = oy + local[1] * escala
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
                px = ox + ponto[0] * escala
                py = oy + ponto[1] * escala - meia - 4 * anota
                partes.append(f'<text class="marca" x="{px:.2f}" '
                              f'y="{py:.2f}" '
                              f'style="font-size:{9.0 * anota:.2f}px">'
                              f'{porta.dn_pol:g}"</text>')
    for p, motivo in ruins:
        px = ox + p.saida[0] * escala
        py = oy + p.saida[1] * escala
        partes.append(f'<circle class="juncao ruim" cx="{px:.1f}" cy="{py:.1f}" '
                      f'r="{4 * anota:.2f}"/>')
    partes.append("</g>")
    if lugares:
        partes.append('<g class="baloes">')
        partes += [_desenhar_balao(i, n, pouso, centro, anota)
                   for i, n, pouso, centro in lugares]
        partes.append("</g>")
    partes.append("</svg>")
    saida = "".join(partes)
    saida = saida.replace(
        "@SVG@", f'<svg class="modo-{modo}" viewBox="0 0 {largura:.2f} '
                 f'{altura:.2f}" width="{largura:.2f}" '
                 f'height="{altura:.2f}" role="img" '
                 f'aria-label="linha montada">', 1)
    saida = saida.replace(
        "@GEO@", f'<g class="geo" transform="translate({ox:.2f} {oy:.2f}) '
                 f'scale({escala:.5f})">', 1)
    saida = saida.replace("@DEGRADES@",
                          f'<defs>{"".join(degrades.values())}</defs>'
                          if degrades else "")
    return saida, postos, fim, colisoes
