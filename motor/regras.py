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

TIPOS_FLANGE = {"FLANGE", "FLANGE_K"}

# Engate rapido K nao e usado nas montagens da casa. Fica reconhecido no
# catalogo (204 conexoes) so para o motor apontar quando uma peca escolhida
# tem ponta K e avisar, em vez de aceitar em silencio.
TIPOS_RECUSADOS = {"ENGATE_K"}

# Valvulas do tipo wafer, presas por tirante em vez de parafuso passante.
BARRA_ROSCADA_POR_PECA = {
    "VALVULA_RETENCAO": 3,
    "VALVULA_BORBOLETA": 3,
}
# Comprimento do tirante ainda nao definido. Enquanto for None a lista sai em
# tirantes; definido, o planejador de corte converte para barras de 1000 mm.
COMPRIMENTO_TIRANTE_MM = None
BARRA_MM = 1000

MM_PARA_POLEGADA = {mm: pol for pol, mm in POLEGADA_MM.items()}


class Incompatibilidade(Exception):
    pass


def _carregar(caminho):
    with open(caminho, encoding="utf-8") as fh:
        return list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))


def _tabela_furacao():
    tabela = {}
    for reg in _carregar(FURACAO):
        tabela[(reg["norma"], float(reg["dn_pol"]))] = {
            "furos": int(reg["furos"]),
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


FUROS = _tabela_furacao()
FERRAGENS = _tabela_ferragem()


def dn_em_polegada(dn, unidade="in"):
    """225 mm de Plasson usa a mesma flange de 8" - 12 furos. A conversao
    comercial polegada/milimetro serve para as duas tabelas."""
    if unidade == "mm":
        return MM_PARA_POLEGADA.get(dn)
    return dn


def contexto_da_junta(material_a, material_b):
    plasticos = {"PVC", "PVC_PLASSON", "PEAD"}
    if "BOMBA" in (material_a, material_b):
        return "BOMBA"
    if material_a in plasticos and material_b in plasticos:
        return "PLASSON_PLASSON"
    if material_a == material_b == "ACO_ZINCADO":
        return "AZ_AZ"
    return "MISTO"


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
    reg = FUROS.get((norma, float(dn_pol)))
    if not reg:
        raise Incompatibilidade(
            f'sem furacao para {norma} DN {dn_pol}" - cadastrar em regras_furacao.csv'
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


def barra_roscada_da_peca(familia, dn, unidade="in", contexto="AZ_AZ"):
    """Valvula wafer (retencao, borboleta) leva 3 tirantes de barra roscada."""
    qtd = BARRA_ROSCADA_POR_PECA.get(familia)
    if not qtd:
        return []
    dn_pol = dn_em_polegada(dn, unidade) or dn
    bit = especificacao_parafuso(dn_pol, contexto)["bitola_pol"]
    itens = [("BARRA_ROSCADA", {"bitola_pol": bit,
                                "comprimento_mm": COMPRIMENTO_TIRANTE_MM}, qtd)]
    # cada tirante fecha com porca e arruela nas duas pontas
    itens.append(("PORCA", {"bitola_pol": bit}, 2 * qtd))
    itens.append(("ARRUELA", {"bitola_pol": bit}, 2 * qtd))
    return itens
