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

MM_PARA_POLEGADA = {mm: pol for pol, mm in POLEGADA_MM.items()}

# DN nominal (mm) de cada medida. Duas series entram na mesma tabela de furacao:
# o aco em polegada e o PVC pelo diametro externo.
POLEGADA_PARA_DN = {2: 50, 2.5: 65, 3: 80, 4: 100, 5: 125, 6: 150, 8: 200,
                    10: 250, 12: 300, 14: 350, 16: 400, 18: 450, 20: 500,
                    24: 600}
PVC_PARA_DN = {63: 50, 75: 65, 90: 80, 110: 100, 140: 125, 160: 150, 225: 200,
               280: 250, 315: 300, 355: 350}

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
    """225 mm de Plasson usa a mesma flange de 8". A conversao comercial
    polegada/milimetro serve para as duas tabelas."""
    if unidade == "mm":
        return MM_PARA_POLEGADA.get(dn)
    return dn


def dn_nominal(dn, unidade="in"):
    """Medida do desenho -> DN nominal em mm, que e a chave da furacao."""
    if unidade == "mm":
        if dn in PVC_PARA_DN:
            return PVC_PARA_DN[dn]
        pol = MM_PARA_POLEGADA.get(dn)
        return POLEGADA_PARA_DN.get(pol) if pol else None
    return POLEGADA_PARA_DN.get(dn)


# A regra do Plasson vale so quando o flange Plasson encontra outro flange
# Plasson. PEAD entra por colar de tomada, nao por flange Plasson.
PLASSON = {"PVC", "PVC_PLASSON"}


def contexto_da_junta(material_a, material_b):
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
        return "reducao", {"de": porta_a["dn"], "para": porta_b["dn"],
                           "tipo": "CONCENTRICA"}
    if porta_a["tipo"] == porta_b["tipo"] and porta_a["norma"] == porta_b["norma"]:
        return "direta", {"junta": porta_a["tipo"], "dn": porta_a["dn"],
                          "norma": porta_a["norma"]}
    return "adaptador", {"dn": porta_a["dn"],
                         "de": (porta_a["tipo"], porta_a["norma"]),
                         "para": (porta_b["tipo"], porta_b["norma"])}


def especificacao_parafuso(dn_pol, contexto):
    faixas = FERRAGENS.get(contexto) or FERRAGENS["MISTO"]
    for faixa in faixas:
        if dn_pol <= faixa["dn_max"]:
            return faixa
    return faixas[-1]


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
        ("ARRUELA", {"bitola_pol": bit}, 2 * n),
    ]


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
