"""Regras de montagem: compatibilidade de portas e ferragem derivada.

Duas responsabilidades:
 1. dado o encontro de duas portas, dizer se conecta direto ou qual peca de
    transicao (reducao/adaptador) precisa entrar no meio;
 2. dada uma junta flangeada, gerar a ferragem (junta plana, parafuso, porca,
    arruela) e, nas valvulas wafer, a barra roscada - itens derivados, nunca
    digitados a mao.

As tabelas ficam em data/*.csv para serem editadas sem mexer em codigo.
"""
import csv
import os

from . import bitola
from . import cotas
from .traducao import POLEGADA_MM

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FURACAO = os.path.join(RAIZ, "data", "regras_furacao.csv")
FERRAGEM = os.path.join(RAIZ, "data", "regras_ferragem.csv")
WAFER = os.path.join(RAIZ, "data", "valvulas_wafer.csv")
KITS_PVC = os.path.join(RAIZ, "data", "kits_flange_pvc.csv")

TIPOS_FLANGE = {"FLANGE", "FLANGE_K"}

# Engate rapido K nao e usado nas montagens da casa. Fica reconhecido no
# catalogo (204 conexoes) so para o motor apontar quando uma peca escolhida
# tem ponta K e avisar, em vez de aceitar em silencio.
TIPOS_RECUSADOS = {"ENGATE_K"}

# Trecho reto obrigatorio antes e depois de certos equipamentos, em multiplos
# do diametro nominal. O medidor so mede direito com o fluxo desenvolvido.
TRECHO_RETO = {
    "MEDIDOR": (10, 5),
}

# Pecas que perturbam o fluxo e por isso interrompem a contagem do trecho reto
PERTURBAM_FLUXO = {"CURVA", "TE", "TE_REDUZIDO", "Y", "REDUCAO_CONCENTRICA",
                   "REDUCAO_EXCENTRICA", "BUCHA_REDUCAO", "VALVULA_RETENCAO",
                   "VALVULA_BORBOLETA", "VALVULA_GAVETA", "VALVULA_HIDRAULICA",
                   "BOMBA", "MANIFOLD", "FILTRO", "CRIVO", "ARTICULADOR"}


# As barras que a casa monta, em milimetro. Nao e o que a lista tem - a lista
# tem tambem 1,2 · 2,5 · 4 · 12 m, que sao encomenda e nao estoque de projeto.
# Estes sao os degraus do desenho, e e por eles que esticar anda.
BARRAS_PADRAO_MM = (500, 1000, 1500, 2000, 3000, 6000)


def escada_de_barras(disponiveis, atual=None):
    """Os degraus que a tela oferece, do menor ao maior.

    E a INTERSECAO de duas coisas, e as duas mandam: os comprimentos que a
    casa usa (BARRAS_PADRAO_MM) e os que a lista tem codigo para aquele tubo.
    So o padrao ofereceria barra que ninguem vende; so a lista encheria o
    seletor de encomenda - 1,2 m e 2,5 m aparecem em 8" e nao aparecem em
    K10, e um seletor que muda de tamanho conforme a ponta do tubo confunde
    mais do que ajuda.

    O comprimento ATUAL entra sempre, mesmo fora do padrao: a peca que esta
    na linha tem de estar no seletor, senao a tela mostraria selecionado um
    degrau que nao e o dela.
    """
    tem = {round(float(c)) for c in disponiveis}
    escada = sorted(tem & set(BARRAS_PADRAO_MM))
    if atual is not None:
        atual = round(float(atual))
        if atual in tem and atual not in escada:
            escada = sorted(escada + [atual])
    return escada


def trecho_reto_exigido(familia, dn, unidade="in"):
    """(antes_mm, depois_mm) que a peca exige de tubo reto, ou None."""
    regra = TRECHO_RETO.get(familia)
    if not regra:
        return None
    dn_mm = dn_nominal(dn, unidade)
    if not dn_mm:
        return None
    return regra[0] * dn_mm, regra[1] * dn_mm


# Valvulas do tipo wafer, presas por tirante. A regra de compra e por BARRA
# INTEIRA, nao por tirante: 3 barras de 1 m por valvula. O corte acontece na
# montagem e nao reduz a quantidade comprada.
BARRAS_ROSCADAS_POR_PECA = {
    "VALVULA_RETENCAO": 3,
    "VALVULA_BORBOLETA": 3,
}
# Arruela por parafuso. UMA, do lado da PORCA: a cabeca assenta direto na
# chapa, e quem precisa de arruela e o lado que gira no aperto.
#
# Este numero e lido em dois lugares - a lista de materiais, que compra, e o
# desenho, que mostra. E de proposito: se cada um tivesse o seu, a folha
# mostraria duas e a compra traria uma, e ninguem veria a diferenca ate a obra.
ARRUELAS_POR_PARAFUSO = 1

# Porca do tirante: 2 por furo do flange - uma em cada ponta. A arruela segue a
# mesma conta, uma sob cada porca.
PORCAS_POR_FURO = 2


def furos_da_valvula(dn, unidade="in", norma="NBR PN16", ficha=None):
    """A valvula e fabricada na norma que se pedir, e a furacao segue a norma.

    Entao o numero de furos sai da tabela de furacao da linha, nao da ficha -
    a ficha traz a versao ASME 150 porque foi assim que ela foi publicada.
    """
    dn_nom = dn_nominal(dn, unidade)
    reg = FUROS.get((norma, dn_nom)) if dn_nom else None
    if reg:
        return reg["furos"]
    return ficha["furos"] if ficha else None


def barras_da_valvula(familia, ficha, dn=None, unidade="in", norma="NBR PN16"):
    """Quantas barras roscadas a valvula leva.

    Base: 3 barras por valvula. Quando o tirante e longo e nao rende um por
    furo, a quantidade sobe para cobrir a furacao - o que acontece de 10" para
    cima.
    """
    base = BARRAS_ROSCADAS_POR_PECA.get(familia)
    if not base:
        return 0, None
    if not ficha:
        return base, None
    por_barra = int(BARRA_MM // ficha["comp_prisioneiro_mm"])
    furos = furos_da_valvula(dn, unidade, norma, ficha) if dn else ficha["furos"]
    if not por_barra or not furos:
        return base, por_barra
    necessario = -(-furos // por_barra)   # arredonda para cima
    return max(base, necessario), por_barra
# Figura padrao das valvulas de retencao wafer. 162 = portinhola unica, que e a
# UNIFLAP do catalogo; 160 = dupla portinhola.
FIGURA_PADRAO = "162"
BARRA_MM = 1000

# As tres tabelas de conversao sao projecoes de motor/bitola.py, que e a unica
# do programa. Ficam com o nome antigo porque quem chama nao precisa saber que
# elas mudaram de casa - o que mudou e que agora ha uma so.
MM_PARA_POLEGADA = {mm: pol for pol, mm in POLEGADA_MM.items()}
POLEGADA_PARA_DN = dict(bitola.NOMINAL)
PVC_PARA_DN = {externo: dn for dn, externo in bitola.METRICO.items()}

# Aperto do tirante: arruela, porca e folga somadas as duas espessuras de flange
ESP_ARRUELA_MM = 3.0
ALTURA_PORCA_MM = {"5/8": 15.9, "3/4": 19.0, "7/8": 22.2, "1": 25.4,
                   "1 1/8": 28.6, "1 1/4": 31.8}
FOLGA_MM = 5.0


class Incompatibilidade(Exception):
    pass


def _carregar(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))


def _tabela_furacao():
    """Chaveada por (norma, DN nominal em mm) - o denominador comum entre a
    serie em polegada do aco e a serie em milimetro do PVC."""
    tabela = {}
    for reg in _carregar(FURACAO):
        def numero(campo):
            return float(reg[campo]) if reg[campo] else None
        tabela[(reg["norma"], int(reg["dn_mm"]))] = {
            "furos": int(reg["furos"]),
            "parafuso_norma": reg["parafuso_norma"],
            "bitola_unc_pol": reg["bitola_unc_pol"],
            "furo_mm": numero("furo_mm"),
            "circulo_mm": numero("circulo_mm"),
            "esp_flange_mm": numero("esp_flange_mm"),
            "homologado": reg["homologado"].strip().upper() == "SIM",
        }
    return tabela


def _tabela_ferragem():
    faixas = {}
    for reg in _carregar(FERRAGEM):
        faixas.setdefault(reg["contexto"], []).append({
            "dn_max": float(reg["dn_max_pol"]),
            "bitola_pol": reg["bitola_pol"],
            "comprimento_pol": reg["comprimento_pol"],
            "homologado": reg["homologado"].strip().upper() == "SIM",
        })
    for linhas in faixas.values():
        linhas.sort(key=lambda r: r["dn_max"])
    return faixas


def _tabela_wafer():
    """Ficha do fabricante: espessura do corpo, furos, bitola e - o que importa
    para o corte - o comprimento do prisioneiro, que e o tirante."""
    tabela = {}
    for reg in _carregar(WAFER):
        tabela[(reg["figura"], float(reg["dn_pol"]))] = {
            "tipo": reg["tipo"],
            "esp_corpo_mm": float(reg["esp_corpo_mm"]),
            "furos": int(reg["furos"]),
            "bitola_pol": reg["bitola_pol"],
            "comp_parafuso_mm": float(reg["comp_parafuso_mm"]),
            "comp_prisioneiro_mm": float(reg["comp_prisioneiro_mm"]),
            # A e B da ficha: o corpo tem que caber dentro do circulo de
            # furacao da flange, e e o desenho que precisa saber disso
            "d_externo_mm": float(reg["d_externo_mm"]) if reg.get("d_externo_mm") else None,
            "d_interno_mm": float(reg["d_interno_mm"]) if reg.get("d_interno_mm") else None,
        }
    return tabela


def _tabela_kits_pvc():
    return {int(r["dn_mm"]): (r["sap_flange"], r["sap_contra_flange"])
            for r in _carregar(KITS_PVC)}


FUROS = _tabela_furacao()
FERRAGENS = _tabela_ferragem()
WAFERS = _tabela_wafer()
KITS_FLANGE_PVC = _tabela_kits_pvc()


def contra_flange_de(item):
    """Flange de PVC nao prende no tubo sozinha: puxa a contra-flange, que e o
    adaptador soldavel. Uma para cada flange lancada na linha.
    """
    if item["familia"] != "FLANGE" or item["material"] not in PLASSON:
        return []
    if item["unidade_dn"] != "mm" or not item["dn"]:
        return []
    par = KITS_FLANGE_PVC.get(int(item["dn"][0]))
    if not par or par[0] != item["sap"]:
        return []
    return [("CONTRA_FLANGE_PVC", {"sap": par[1]}, 1)]


def dn_em_polegada(dn, unidade="in"):
    """225 mm de Plasson usa a mesma flange de 8".

    Delega em motor/bitola.py: a conversao e uma so no programa, e a prova de
    que 225 e 8" sao a mesma bitola e justamente esta tabela de furacao.
    """
    return bitola.em_polegada(dn, unidade)


def dn_nominal(dn, unidade="in"):
    """Medida do desenho -> DN nominal em mm, que e a chave da furacao."""
    return bitola.nominal(dn, unidade)


# A regra do Plasson vale so quando o flange Plasson encontra outro flange
# Plasson. PEAD entra por colar de tomada, nao por flange Plasson.
PLASSON = {"PVC", "PVC_PLASSON"}


def contexto_da_junta(material_a, material_b):
    # Valvula, medidor e filtro nao declaram material: o corpo e de ferro ou aco
    # e o flange segue a linha. Entao a ponta sem material adota a do vizinho.
    if material_a is None:
        material_a = material_b
    if material_b is None:
        material_b = material_a
    materiais = {material_a, material_b}
    if "BOMBA" in materiais:
        return "BOMBA"
    if material_a in PLASSON and material_b in PLASSON:
        return "PLASSON_PLASSON"
    if material_a == material_b == "ACO_ZINCADO":
        return "AZ_AZ"
    if "ACO_ZINCADO" in materiais and materiais & PLASSON:
        return "ACO_PLASSON"
    return "MISTO"


def contexto_sem_regra(contexto):
    """MISTO e o que sobra - nem aco com aco, nem Plasson, nem bomba, nem aco
    com Plasson. Sem regra fechada, o motor avisa em vez de escolher calado."""
    return contexto == "MISTO"


def resolver_juncao(porta_a, porta_b):
    """Como as duas portas se encontram.

    ('direta', ...) | ('reducao', ...) | ('adaptador', ...) | ('recusada', ...)
    """
    if porta_a["tipo"] in TIPOS_RECUSADOS or porta_b["tipo"] in TIPOS_RECUSADOS:
        return "recusada", {"motivo": "engate K nao e usado nas montagens",
                            "dn": porta_a["dn"]}
    if porta_a["dn"] != porta_b["dn"]:
        # A NORMA VAI JUNTO, e nao e detalhe: na boca da bomba a bitola E a
        # norma mudam ao mesmo tempo - o fabricante entrega a flange dele em
        # EN ou ANSI e a linha corre em NBR - e e por isso que a casa compra
        # reducao ESPECIFICA, com uma face em cada norma. Enquanto a bitola
        # saia daqui sozinha, a mensagem dizia "precisa de reducao" e calava a
        # metade que decide qual reducao
        return "reducao", {"de": porta_a["dn"], "para": porta_b["dn"],
                           "tipo": "CONCENTRICA",
                           "norma_de": porta_a["norma"],
                           "norma_para": porta_b["norma"],
                           "normas_diferentes": bool(
                               porta_a["norma"] and porta_b["norma"]
                               and porta_a["norma"] != porta_b["norma"])}
    if porta_a["tipo"] == porta_b["tipo"] and porta_a["norma"] == porta_b["norma"]:
        return "direta", {"junta": porta_a["tipo"], "dn": porta_a["dn"],
                          "norma": porta_a["norma"]}
    # Valvula, medidor e junta nao declaram norma na descricao - ela e definida
    # no pedido. Entao ponta sem norma encaixa na norma do vizinho, e nao e
    # caso de adaptador.
    if porta_a["tipo"] == porta_b["tipo"] and None in (porta_a["norma"],
                                                       porta_b["norma"]):
        norma = porta_a["norma"] or porta_b["norma"]
        return "direta", {"junta": porta_a["tipo"], "dn": porta_a["dn"],
                          "norma": norma,
                          "nota": "uma das pontas nao declara norma - "
                                  "pedir na norma da linha"}
    return "adaptador", {"dn": porta_a["dn"],
                         "de": (porta_a["tipo"], porta_a["norma"]),
                         "para": (porta_b["tipo"], porta_b["norma"])}


_plasson_pol = None


def par_plasson(dn_pol):
    """O par flange solta + colar Plasson dessa bitola, em polegada.

    A Plasson nomeia a bitola pelo externo do tubo em milimetro, e mais de um
    milimetro cai na mesma polegada: 50 e 63 sao os dois 2", 125 e 140 sao 5",
    200 e 225 sao 8". Quando ha duas, vale a MAIS GROSSA - o parafuso e um so
    para a polegada e tem de fechar a pior das duas.
    """
    global _plasson_pol
    if _plasson_pol is None:
        _plasson_pol = {}
        for d in cotas.bitolas_flangeadas_plasson():
            ficha = cotas.par_flangeado_plasson(d)
            if not ficha or ficha["ressalto"] is None:
                continue
            pol = bitola.em_polegada(d, "mm")
            if pol is None:
                continue
            grosso = ficha["espessura"] + ficha["ressalto"]
            atual = _plasson_pol.get(pol)
            if atual is None or grosso > atual["espessura"] + atual["ressalto"]:
                _plasson_pol[pol] = ficha
    return _plasson_pol.get(float(dn_pol))


def chapa_da_ponta(dn_pol, material):
    """Quanta chapa ESTA ponta poe na junta, e de que ela e feita.

    E a peca que faltava para medir parafuso fora do aco. Uma ponta de aco poe
    UMA chapa - a flange soldada. Uma ponta Plasson poe DUAS: o colar (desenho
    5510), soldado no tubo, com ressalto de espessura B; e a flange solta
    (5900), de espessura H, que corre por tras do ressalto. Nao e detalhe de
    desenho: e o dobro de chapa, e o parafuso sente.

    As camadas saem na ordem em que se atravessa a ponta A PARTIR DA JUNTA -
    ressalto primeiro, flange solta depois - para o outro lado poder ser
    lido de tras para frente e a junta inteira sair na ordem certa.

    Devolve None onde nao ha folha: contra a bomba, o flange e do fabricante
    dela; no PEAD, o ressalto do colar e estimado. Melhor calar que afirmar.
    """
    from . import simbolos
    if material in PLASSON:
        par = par_plasson(dn_pol)
        if not par:
            return None
        return {"mm": par["ressalto"] + par["espessura"],
                "furo": par["furo"], "furos": par["furos"],
                # o ressalto e mais estreito que o circulo de furacao (no d160,
                # 213 contra 241), entao ele NAO cobre o parafuso: quem cobre e
                # so a flange solta
                "vao": par["ressalto"], "chapa": par["espessura"],
                "face": par["ressalto_externo"],
                "camadas": [("colar", par["ressalto"]),
                            ("flange solta", par["espessura"])],
                "fonte": f'plasson 5900+5510 d{par["d_mm"]:g}'}
    if material in (None, "ACO_ZINCADO", "FERRO_FUNDIDO", "ACO"):
        f = simbolos.flange(dn_pol)
        return {"mm": f["espessura"], "furo": f["furo"], "furos": f["furos"],
                "vao": 0.0, "chapa": f["espessura"], "face": f["ressalto"],
                "camadas": [("chapa AZ", f["espessura"])], "fonte": f["fonte"]}
    return None


# Os materiais de cada contexto, para a conta do aperto. O contexto ja resolveu
# quem encontra quem; aqui so se pergunta o que cada ponta poe de chapa.
PONTAS_DO_CONTEXTO = {
    "AZ_AZ": ("ACO_ZINCADO", "ACO_ZINCADO"),
    "ACO_PLASSON": ("ACO_ZINCADO", "PVC"),
    "PLASSON_PLASSON": ("PVC", "PVC"),
}


def aperto_da_junta(dn_pol, contexto="AZ_AZ"):
    """Quanta chapa o parafuso atravessa nesta junta, e de que ela e feita.

    E a conta que decide o comprimento do parafuso, e ela nao e "duas chapas"
    em todo lugar - depende de QUEM se encontra:

        AZ_AZ            chapa + chapa                                  duas
        ACO_PLASSON      chapa + colar + flange solta                   tres
        PLASSON_PLASSON  flange solta + colar + colar + flange solta  quatro

    Por isso o parafuso Plasson e mais longo que o de aco na mesma bitola - nao
    por folga, por geometria.

    Devolve {"mm", "furo", "camadas", "fonte"} ou None quando falta ficha.
    BOMBA e MISTO devolvem None de proposito: o flange da bomba e do fabricante
    dela e nao ha folha aqui, e MISTO e o que sobrou sem regra. Medir esses com
    a chapa de aco dos dois lados daria um veredito sobre um sanduiche que nao
    existe, e um "fecha" falso vale menos que nao dizer nada.
    """
    pontas = PONTAS_DO_CONTEXTO.get(contexto)
    if not pontas:
        return None
    a = chapa_da_ponta(dn_pol, pontas[0])
    b = chapa_da_ponta(dn_pol, pontas[1])
    if not a or not b:
        return None
    camadas = list(reversed(a["camadas"])) + b["camadas"]
    fontes = dict.fromkeys((a["fonte"], b["fonte"]))
    return {"mm": a["mm"] + b["mm"],
            # o furo que manda e o MENOR dos dois: e ele que limita o parafuso
            "furo": min(a["furo"], b["furo"]),
            "camadas": camadas,
            "lados": (a["mm"], b["mm"]),
            # o vao: as duas flanges NAO se encostam, o que se encosta sao os
            # ressaltos dos colares. Entre elas fica o parafuso a mostra
            "vaos": (a["vao"], b["vao"]),
            "vao": a["vao"] + b["vao"],
            "face": min(a["face"], b["face"]),
            "fonte": " + ".join(fontes)}


def especificacao_parafuso(dn_pol, contexto):
    faixas = FERRAGENS.get(contexto) or FERRAGENS["MISTO"]
    for faixa in faixas:
        if dn_pol <= faixa["dn_max"]:
            return faixa
    return faixas[-1]


def polegada_em_mm(texto):
    """'2 1/2' -> 63.5. A tabela da casa fala em polegada, o desenho em mm."""
    import re as _re
    m = _re.match(r"\s*(?:(\d+)\s+)?(?:(\d+)/(\d+)|(\d+(?:[.,]\d+)?))\s*$",
                  str(texto))
    if not m:
        return None
    inteiro = float(m.group(1) or 0)
    if m.group(2):
        inteiro += float(m.group(2)) / float(m.group(3))
    elif m.group(4):
        inteiro += float(m.group(4).replace(",", "."))
    return inteiro * 25.4


def parafuso_da_junta(dn_pol, contexto="AZ_AZ"):
    """O parafuso que a casa poe nesta junta, em milimetro.

    A tabela e a mesma que a lista de materiais usa - data/regras_ferragem.csv,
    a regra da casa - so que convertida. E o que permite desenhar o parafuso no
    tamanho de verdade em vez de num tamanho plausivel: um desenho em escala em
    que o parafuso nao esta em escala mente exatamente onde mais se olha.
    """
    ficha = especificacao_parafuso(dn_pol, contexto)
    return {"bitola_mm": polegada_em_mm(ficha["bitola_pol"]),
            "comprimento_mm": polegada_em_mm(ficha["comprimento_pol"]),
            "bitola_pol": ficha["bitola_pol"],
            "comprimento_pol": ficha["comprimento_pol"],
            "homologado": ficha["homologado"]}


def ferragem_da_junta(dn, norma, unidade="in", contexto="AZ_AZ"):
    """Itens derivados de UMA junta flangeada: (papel, especificacao, qtd)."""
    dn_pol = dn_em_polegada(dn, unidade)
    if dn_pol is None:
        raise Incompatibilidade(
            f"sem equivalencia em polegada para DN {dn} {unidade}"
        )
    dn_nom = dn_nominal(dn, unidade)
    reg = FUROS.get((norma, dn_nom)) if dn_nom else None
    if not reg:
        raise Incompatibilidade(
            f'sem furacao para {norma} DN {dn_nom or dn} - '
            "rodar tools/gerar_furacao.py ou cadastrar a norma"
        )
    esp = especificacao_parafuso(dn_pol, contexto)
    n = reg["furos"]
    bit = esp["bitola_pol"]
    return [
        ("JUNTA_PLANA", {"dn": dn_pol}, 1),
        ("PARAFUSO", {"bitola_pol": bit,
                      "comprimento_pol": esp["comprimento_pol"]}, n),
        ("PORCA", {"bitola_pol": bit}, n),
        ("ARRUELA", {"bitola_pol": bit}, ARRUELAS_POR_PARAFUSO * n),
    ]


# A FLANGE DA BOMBA E DO FABRICANTE, E ELA E ANSI. KSB e EBARA entregam a boca
# em ANSI 150 ou ANSI 300 conforme a classe de pressao da maquina - quem disse
# foi a casa, que compra as duas. O cadastro nao traz essa informacao (a bomba
# entra na lista sem conexao nenhuma), e por isso ela mora aqui.
#
# E ANSI NUNCA CASA COM NBR: nem quando os furos e o diametro batem, porque o
# CIRCULO e outro - em 6" sao 241,3 contra 240. Entao toda boca de bomba pede
# a peca especifica, e e por isso que a casa tem 86 reducoes com uma face ANSI.
# Qual das duas classes vale sai da folha da maquina; o programa assume a 150,
# que e a comum, e AVISA para conferir.
NORMA_FLANGE_BOMBA = "ANSI 150"
# As tres furacoes com que a mesma bomba pode vir, conforme o pedido - a
# tabela "Modelo do flange" da KSB, material G. A do meio e a que engana: uma
# flange EN 1092-2 PERFURADA em ASME B16.1, ou seja, com corpo europeu e furo
# americano. E a prova de que quem manda e a FURACAO, e nao o nome da norma.
FURACOES_DE_BOMBA = {
    "ANSI 150": "ASME B16.1 Classe 125 (ou EN 1092-2 perfurada B16.1)",
    "ANSI 300": "ASME B16.1 Classe 250",
    "EN PN16": "EN 1092-2 PN 16",
}
CLASSES_FLANGE_BOMBA = tuple(FURACOES_DE_BOMBA)
FLANGES_BOMBA = os.path.join(RAIZ, "data", "flanges_bomba.csv")
_flanges_bomba = None


def _carregar_flanges_bomba():
    global _flanges_bomba
    if _flanges_bomba is None:
        _flanges_bomba = {}
        for reg in _carregar(FLANGES_BOMBA):
            chave = (reg["linha"].strip().upper(),
                     reg["tamanho"].strip().replace(" ", ""))
            _flanges_bomba[chave] = reg
    return _flanges_bomba


# Ate o tamanho 65-200 a KSB entrega a boca da Megabloc ROSQUEADA (BSP) ou
# flangeada,
# conforme o pedido - e rosca nao tem junta flangeada nenhuma, nem parafuso.
# O criterio pratico e a succao: DN65 e 2 1/2".
SUCCAO_QUE_PODE_SER_ROSCADA_POL = 2.5


# A nota e do manual MEGABLOC, e vale para a Megabloc. Para a EBARA a casa
# nao tem nota equivalente, e inventar uma seria pior que nao ter: a bomba
# entra flangeada, que e como a lista a vende.
LINHAS_QUE_PODEM_VIR_ROSCADAS = ("METB", "MEGABLOC")


def pode_vir_roscada(succao_pol, descricao=""):
    """A boca desta bomba pode ter vindo em rosca BSP em vez de flange?

    So a Megabloc, so as pequenas, e so quando a folha nao disser o
    contrario: as tres excecoes da nota (050-032-250.1, 050-032-250 e
    065-040-250) saem somente flangeadas, em 250#.
    """
    texto = (descricao or "").upper()
    if not any(m in texto for m in LINHAS_QUE_PODEM_VIR_ROSCADAS):
        return False
    if succao_pol is None or succao_pol > SUCCAO_QUE_PODE_SER_ROSCADA_POL:
        return False
    ficha = flange_da_bomba(descricao)
    return ficha["assumida"] or ficha["furacao"] != "ANSI 300"


def flange_da_bomba(descricao):
    """A flange da boca desta bomba: norma, classe e de onde veio.

    Com folha, sai a classe da maquina - CL 125 ou CL 250, que furam como as
    ANSI 150 e 300. Sem folha, o programa assume a 150, que e a comum, e diz
    que assumiu: e a mesma regra da valvula sem serie - emprestar e permitido,
    calar nao.
    """
    texto = (descricao or "").upper()
    for (linha, tamanho), reg in _carregar_flanges_bomba().items():
        if linha in texto and tamanho in texto.replace(" ", ""):
            return {"furacao": reg["furacao"].strip(),
                    "classe": reg["classe"].strip(),
                    "norma": reg["norma"].strip(),
                    "succao_pol": float(reg["succao_pol"]),
                    "recalque_pol": float(reg["recalque_pol"]),
                    "fonte": reg["ficha"].strip(), "assumida": False}
    return {"furacao": NORMA_FLANGE_BOMBA, "classe": None,
            "norma": "ASME B16.1", "succao_pol": None, "recalque_pol": None,
            "fonte": None, "assumida": True}


def furacao(norma, dn, unidade="in"):
    """(furos, furo_mm, circulo_mm) da norma nessa bitola. None se nao houver.

    E o que decide se duas faces PARAFUSAM: o nome da norma nao decide nada
    sozinho - NBR PN16 e EN PN16 tem a mesma furacao ate DN200 e divergem de
    DN250 para cima, e ANSI nunca casa com NBR. Ver docs/LOGICA.md 4.2.
    """
    dn_nom = dn_nominal(dn, unidade)
    reg = FUROS.get((norma, dn_nom)) if dn_nom else None
    if not reg:
        return None
    return (reg["furos"], reg["furo_mm"], reg["circulo_mm"])


def mesma_furacao(norma_a, norma_b, dn, unidade="in"):
    """As duas faces parafusam uma na outra? None quando falta tabela."""
    a, b = furacao(norma_a, dn, unidade), furacao(norma_b, dn, unidade)
    if a is None or b is None:
        return None
    return a == b


def ficha_wafer(dn_pol, figura=None):
    return WAFERS.get((figura or FIGURA_PADRAO, float(dn_pol)))


def barra_roscada_da_peca(familia, dn, unidade="in", contexto="AZ_AZ",
                          norma="NBR PN16", figura=None):
    """Valvula wafer leva 3 barras roscadas inteiras.

    A bitola vem da ficha do fabricante; o comprimento do tirante tambem, mas
    so para o desenho e para o aproveitamento - a compra e por barra.
    """
    if familia not in BARRAS_ROSCADAS_POR_PECA:
        return []
    dn_pol = dn_em_polegada(dn, unidade) or dn
    ficha = ficha_wafer(dn_pol, figura)
    qtd, _por_barra = barras_da_valvula(familia, ficha, dn, unidade, norma)
    bit = (ficha["bitola_pol"] if ficha
           else especificacao_parafuso(dn_pol, contexto)["bitola_pol"])
    furos = furos_da_valvula(dn, unidade, norma, ficha) or 0
    ferragem = PORCAS_POR_FURO * furos
    return [
        ("BARRA_ROSCADA", {"bitola_pol": bit}, qtd),
        ("PORCA", {"bitola_pol": bit}, ferragem),
        ("ARRUELA", {"bitola_pol": bit}, ferragem),
    ]
