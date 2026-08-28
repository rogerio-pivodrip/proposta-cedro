"""Templates de linha: a receita padrao, resolvida contra o catalogo.

Duas receitas por enquanto: a succao e o trecho de PEAD.

A succao da casa segue sempre a mesma ordem:

    crivo -> valvula de retencao -> tubo de 1 m -> curva (se precisar)
          -> reducao -> bomba

A curva e opcional e a reducao sai da bomba: concentrica ou excentrica conforme
a orientacao, e sempre no DN do bocal de entrada.

O articulador NAO entra aqui: ele fica na crista do talude, depois do trecho de
PEAD - ver motor/talude.py. A casa tambem nao usa flutuador; o manual descreve
succao com flutuante, mas ainda nao e praticado aqui.
"""
from .bomba import (HORIZONTAL, MM_PARA_POLEGADA, entrada_presumida,
                    interpretar, tipo_reducao_succao)
from . import regras
from .linha import Linha, Peca
from .traducao import POLEGADA_MM

NORMA = "NBR PN16"


def _melhor(catalogo, familia, dn, **extra):
    """Tenta com a norma da linha; se nao houver, aceita a peca de qualquer
    material - valvula e crivo nao sao de aco zincado."""
    return (catalogo.melhor(familia, dn, norma=NORMA, **extra)
            or catalogo.melhor(familia, dn, material=None, norma=NORMA, **extra)
            or catalogo.melhor(familia, dn, material=None, **extra))


def succao(catalogo, dn_linha, modelo_bomba=None, orientacao=HORIZONTAL,
           curva=None, area="P01"):
    """Monta a succao padrao. curva = None, 45 ou 90."""
    linha = Linha(catalogo, tipo="SUCCAO", area=area)
    # a succao NASCE de pe: o crivo fica no fundo do poco e a linha sobe ate a
    # bomba. Toda peca e desenhada olhando para +x, entao a linha inteira gira
    # 90 no anti-horario da tela - e como y do SVG aponta para baixo, isso e
    # -90. Nao entra no historico: e a pose de nascimento, nao uma edicao
    linha.giro = -90.0
    faltando = []

    receita = [("CRIVO", {}), ("VALVULA_RETENCAO", {}),
               ("TUBO", {"comprimento_mm": 1000})]
    if curva:
        receita.append(("CURVA", {"angulo": curva}))

    for familia, extra in receita:
        item = _melhor(catalogo, familia, dn_linha, **extra)
        if item:
            linha.inserir(Peca(item, comprimento_mm=extra.get("comprimento_mm")))
        else:
            faltando.append((familia, dn_linha, extra))

    reducao = None
    if modelo_bomba:
        bomba = interpretar(modelo_bomba)
        if bomba:
            entrada = bomba["entrada_pol"]
            if entrada is None:
                presumida, _ = entrada_presumida(bomba["saida_mm"])
                entrada = presumida and _polegada(presumida)
            if entrada and entrada != dn_linha:
                familia = tipo_reducao_succao(orientacao)
                item = _melhor(catalogo, familia, dn_linha, dn_saida=entrada)
                if item:
                    linha.inserir(Peca(item))
                    reducao = item
                else:
                    faltando.append((familia, dn_linha, {"dn_saida": entrada}))
    return linha, reducao, faltando


def _barra_que_cobre(catalogo, dn_pol, minimo_mm, material=None):
    """A menor barra da lista que cobre o trecho reto exigido.

    Trecho reto de medidor nao e enfeite: e a condicao para a medicao valer. A
    norma pede tantos diametros antes e depois, e a barra tem de COBRIR isso -
    nunca chegar perto. Por isso arredonda-se sempre para cima, e nao para o
    mais proximo.
    """
    barras = catalogo.barras_irmas(
        _melhor(catalogo, "TUBO", dn_pol, material=material) or {})
    escada = regras.escada_de_barras(barras)
    serve = [c for c in escada if c >= minimo_mm - 1]
    return serve[0] if serve else (escada[-1] if escada else None)


def recalque(catalogo, dn_linha, area="P01", trecho_antes=10, trecho_depois=5):
    """O recalque da casa de bomba, do filtro para a adutora.

    A ordem e a que a casa monta, e cada peca esta ali por um motivo:

        curva 90            sobe do filtro
        valvula hidraulica  o comando da linha
        tubo                trecho reto ANTES do hidrometro
        medidor             o hidrometro
        tubo                trecho reto DEPOIS
        valvula de retencao segura a coluna quando a bomba para
        te DE PE            a linha chega pela derivacao
          flange cega        na boca de cima, com a luva de 2" da ventosa
        curva 90            desce da boca de baixo
        tubo 1 m            e segue

    OS TRECHOS RETOS SAO A UNICA COTA CALCULADA AQUI, e vem em DIAMETROS: 10 D
    antes e 5 D depois, que e o que a medicao pede. Em 6" isso da 1,5 m e
    0,8 m, e a barra escolhida e a menor da escada que COBRE - arredondar para
    o mais proximo poderia entregar 1 m onde a norma pede 1,5.

    O te fica de pe sobre a derivacao. E o unico lugar do programa em que uma
    peca da corrente carrega outra: a boca que sobra nao continua a linha,
    termina - e o que fecha ela e um acessorio, nao um ramo.
    """
    from .bitola import em_mm

    linha = Linha(catalogo, tipo="RECALQUE", area=area)
    # o recalque CORRE DEITADO: a linha desce do filtro, a primeira curva a
    # poe na horizontal, e e nessa horizontal que ficam valvula, hidrometro e
    # retencao. Sem essa pose de nascimento a curva punha tudo em pe, e o te
    # do fim - que tem de ficar de pe, com a cega em cima e a curva embaixo -
    # saia deitado, porque a boca dele e relativa a direcao em que a linha
    # chega
    linha.giro = 90.0
    faltando = []
    diametro = em_mm(dn_linha) or dn_linha * 25.4

    def por(familia, **extra):
        item = _melhor(catalogo, familia, dn_linha, **extra)
        if item is None:
            faltando.append((familia, dn_linha, extra))
            return None
        return item

    receita = [
        ("CURVA", {"angulo": 90}, {}),
        ("VALVULA_HIDRAULICA", {}, {}),
        ("TUBO", {"comprimento_mm": _barra_que_cobre(
            catalogo, dn_linha, diametro * trecho_antes)}, {}),
        ("MEDIDOR", {}, {}),
        ("TUBO", {"comprimento_mm": _barra_que_cobre(
            catalogo, dn_linha, diametro * trecho_depois)}, {}),
        ("VALVULA_RETENCAO", {}, {}),
        ("TE", {}, {"pose": "derivacao"}),
        ("CURVA", {"angulo": 90}, {}),
        ("TUBO", {"comprimento_mm": 1000}, {}),
    ]
    te_montado = None
    for familia, busca, jeito in receita:
        item = por(familia, **busca)
        if item is None:
            continue
        peca = Peca(item, comprimento_mm=busca.get("comprimento_mm"), **jeito)
        linha.inserir(peca)
        if familia == "TE":
            te_montado = peca

    # a flange cega com a luva de 2" fecha a boca de cima do te - e por essa
    # luva que a ventosa entra. Preferida a que ja vem com a luva; sem ela, a
    # cega simples, e a ventosa fica pendente na lista
    if te_montado is not None:
        # a que ja vem com a luva de 2" tem "C/LV 2" na descricao - e por ela
        # que a ventosa entra. Sem ela, a cega simples, e a luva fica pendente
        # a lista escreve a luva de duas formas - "C/ LG 2"" e "C/LV 2"" - e
        # nao preenche saida_pol nessas. Ler a descricao e o que acha as duas
        import re as _re
        rx = _re.compile(r'C/\s*L[GV]\s*2\s*"', _re.I)
        com_luva = [i for i in catalogo.buscar("FLANGE_CEGA", dn_linha,
                                               material=None)
                    if rx.search(i["descricao"])]
        cega = (com_luva[0] if com_luva
                else _melhor(catalogo, "FLANGE_CEGA", dn_linha))
        if cega:
            linha.acoplar(te_montado.id, Peca(cega))
            # e na luva de 2" da cega sobe a VENTOSA. Ela vai como segundo
            # acessorio do te, e o desenho a empilha sobre a cega - que e como
            # ela sobe na obra. Sem a cega com luva nao ha onde enroscar, e ela
            # nao entra
            if _tem_luva(cega):
                # a COMBINADA e nao a anti-vacuo: no alto do recalque a linha
                # tem de expulsar o ar do enchimento E admitir na drenagem, e
                # so a combinada faz as duas. E de rosca BSP, porque o que ha
                # ali e uma luva - flange nao entra
                ar = _ventosa_combinada(catalogo, 2, pn=16)
                if ar is not None:
                    linha.acoplar(te_montado.id, Peca(ar))
                else:
                    faltando.append(("VENTOSA", 2, {}))
        else:
            faltando.append(("FLANGE_CEGA", dn_linha, {"saida_pol": 2}))
    return linha, faltando


def _ventosa_combinada(catalogo, dn_pol=2, pn=16):
    """A ventosa combinada de rosca, dessa bitola.

    Combinada, e nao anti-vacuo: no alto do recalque a linha precisa das duas
    funcoes - expulsar o ar no enchimento e admitir na drenagem - e a
    anti-vacuo so faz a segunda. A busca e por DESCRICAO porque a lista nao
    separa as duas em campo nenhum: 'VENTOSA (COMBINADA)' contra
    'ANTIVACUO (CINETICA)'.
    """
    import re as _re
    alvo = _re.compile(rf'COMBINADA.*{dn_pol:g}"|{dn_pol:g}".*COMBINADA', _re.I)
    achados = [i for i in catalogo.itens
               if i["familia"] == "VENTOSA" and alvo.search(i["descricao"] or "")
               and "BSP" in (i["descricao"] or "").upper()]
    # o PN pedido primeiro; sem ele, o que houver, com a descricao mais curta
    achados.sort(key=lambda i: (f"PN{pn}" not in i["descricao"].upper(),
                                len(i["descricao"])))
    return achados[0] if achados else None


def _tem_luva(item):
    """A cega escolhida e a que tem a luva de 2"? A lista escreve de duas
    formas - C/ LG 2" e C/LV 2" - e nao preenche saida_pol em nenhuma."""
    import re as _re
    return bool(_re.search(r'C/\s*L[GV]\s*2\s*"', item["descricao"] or "",
                           _re.I))


def _polegada(mm):
    from .bomba import MM_PARA_POLEGADA
    return MM_PARA_POLEGADA.get(mm)


# --------------------------------------------------------------------------
# Trecho de PEAD, depois da primeira bomba
# --------------------------------------------------------------------------
TUBOS_PEAD_PADRAO = 4      # o usual e de 4 a 8
COLARES_POR_TRECHO = 2     # um em cada ponta
FLANGES_AZ_POR_TRECHO = 2  # a flange solta que aperta contra o colar


def trecho_pead(catalogo, dn_pol, tubos=TUBOS_PEAD_PADRAO):
    """Depois da primeira bomba a linha vira PEAD.

    O trecho e sempre o mesmo conjunto: N tubos de PEAD e, em cada ponta, um
    colar de flange PEAD apertado por uma flange solta de aco. Conferido nos
    projetos - Lincoln Junqueira tem 4 tubos de 6" e 2 flanges AZ 6"; Thiago
    Derks tem 9 tubos de 10" e 2 flanges AZ 10".

    Devolve (itens, faltando), onde itens e [(registro, quantidade)].
    """
    dn_mm = POLEGADA_MM.get(dn_pol)
    itens, faltando = [], []

    def juntar(familia, dn, qtd, material=None, **extra):
        item = catalogo.melhor(familia, dn, material=material, **extra)
        if item:
            itens.append((item, qtd))
        else:
            faltando.append((familia, dn, extra))

    if dn_mm:
        juntar("TUBO", dn_mm, tubos, material="PEAD")
        juntar("COLAR_PEAD", dn_mm, COLARES_POR_TRECHO)
    else:
        faltando.append(("TUBO", dn_pol, {"material": "PEAD"}))
    juntar("FLANGE", dn_pol, FLANGES_AZ_POR_TRECHO, norma=NORMA)
    return itens, faltando


def _dn_pead_em_mm(dn_pol):
    return POLEGADA_MM.get(dn_pol)


# O flutuador bipartido existe no catalogo, de 3" a 16", mas a casa ainda nao
# usa succao flutuante. Fica fora do template ate haver regra.
FLUTUADOR_EM_USO = False


# ---------------------------------------------------------------- montagens
#
# **A MONTAGEM NAO E UM `if` NA API.** Sucção e recalque foram as duas
# primeiras, e por um tempo foram as duas unicas - a ponto de o tipo da linha
# ser tratado como se so pudesse ser uma das duas. A casa monta muito mais que
# isso: adução, barrilete, bomba em série, bomba em paralelo, e combinações
# delas. Entao o que existe aqui e um REGISTRO: uma montagem nova e uma funcao
# e uma linha nesta tabela, e ela aparece sozinha na barra de comando e na
# tela, pelo mesmo motivo que o vocabulario mora no motor.
#
# Toda montagem devolve (linha, faltando). O que ela nao devolve e opiniao: o
# que a lista nao tem entra em `faltando` e a linha sai montada com o resto.


def _da_succao(catalogo, dn, **extra):
    linha, _reducao, faltando = succao(
        catalogo, dn, modelo_bomba=extra.get("bomba"),
        curva=extra.get("curva"), area=extra.get("area") or "P01")
    if extra.get("nome"):
        linha.nome = extra["nome"]
    return linha, faltando


def _do_recalque(catalogo, dn, **extra):
    linha, faltando = recalque(catalogo, dn, area=extra.get("area") or "P01")
    if extra.get("nome"):
        linha.nome = extra["nome"]
    return linha, faltando


def _do_pead(catalogo, dn, **extra):
    """O trecho de PEAD como montagem propria, e nao como enxerto.

    `trecho_pead` devolve itens porque ele nasceu para ser acrescentado a uma
    linha que ja existia. Aqui ele vira montagem: o mesmo conjunto, numa linha
    so dele, que se pode encostar noutra depois.
    """
    itens, faltando = trecho_pead(catalogo, dn)
    linha = Linha(catalogo, tipo="PEAD", area=extra.get("area") or "P01",
                  nome=extra.get("nome"))
    for item, quantas in itens:
        for _ in range(quantas):
            linha.inserir(Peca(item))
    return linha, faltando


def _vazia(catalogo, dn=None, **extra):
    """Uma montagem em branco, para quem vai montar a mao.

    E a mais importante da tabela: sem ela o programa so sabe fazer o que ja
    esta escrito, e quem quer uma adução de três bombas em paralelo teria de
    esperar alguem escrever o template dela.
    """
    return Linha(catalogo, tipo=extra.get("tipo") or "LIVRE",
                 area=extra.get("area") or "P01",
                 nome=extra.get("nome") or "Montagem"), []


MONTAGENS = {
    "SUCCAO": {
        "nome": "sucção",
        "resumo": "poço → bomba: crivo, válvula de pé, tubo e a redução",
        "monta": _da_succao, "precisa_bitola": True,
    },
    "RECALQUE": {
        "nome": "recalque",
        "resumo": "bomba → campo: válvula, hidrômetro, retenção, tê e ventosa",
        "monta": _do_recalque, "precisa_bitola": True,
    },
    "PEAD": {
        "nome": "trecho de PEAD",
        "resumo": "tubos de PEAD com colar e flange solta nas duas pontas",
        "monta": _do_pead, "precisa_bitola": True,
    },
    "LIVRE": {
        "nome": "em branco",
        "resumo": "uma montagem vazia, para montar peça por peça",
        "monta": _vazia, "precisa_bitola": False,
    },
}


def montar(catalogo, chave, dn=None, **extra):
    """(linha, faltando) da montagem pedida. Ergue KeyError se ela nao existe.

    `chave` e qual montagem - SUCCAO, RECALQUE, PEAD, LIVRE. O `nome` que vier
    em `extra` e outro: e como ESTA montagem vai se chamar no projeto, e por
    isso os dois nao podem ser o mesmo argumento.
    """
    ficha = MONTAGENS.get((chave or "").upper())
    if ficha is None:
        raise KeyError(chave)
    if ficha["precisa_bitola"] and dn is None:
        raise ValueError(f'{ficha["nome"]} precisa da bitola da linha')
    return ficha["monta"](catalogo, dn, **extra)


def catalogo_de_montagens():
    """O que a tela e a barra oferecem - e nao uma lista copiada nelas."""
    return [{"chave": chave, **{k: v for k, v in ficha.items() if k != "monta"}}
            for chave, ficha in MONTAGENS.items()]
