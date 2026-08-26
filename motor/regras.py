"""Regras de montagem: compatibilidade de portas e ferragem derivada.

Duas responsabilidades:
 1. dado o encontro de duas portas, dizer se conecta direto ou qual peca de
    transicao (reducao/adaptador) precisa entrar no meio;
 2. dada uma junta flangeada, gerar a ferragem (junta plana, parafuso, porca,
    arruela) - itens derivados, nunca digitados a mao.
"""
import csv
import os
from fractions import Fraction

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABELA_FLANGE = os.path.join(RAIZ, "data", "regras_flange.csv")

# Bitolas UNC existentes no catalogo (01542-*), em polegadas
BITOLAS = ["5/16", "3/8", "1/2", "5/8", "3/4", "7/8", "1", "1 1/8", "1 1/4"]
# Comprimentos de parafuso de estoque, em polegadas
COMPRIMENTOS = [2, 2.25, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7]

# Altura de porca e espessura de arruela por bitola (mm), aproximacao UNC
ALTURA_PORCA = {"1/2": 12.7, "5/8": 15.9, "3/4": 19.0, "7/8": 22.2, "1": 25.4,
                "1 1/8": 28.6, "1 1/4": 31.8, "3/8": 9.5, "5/16": 7.9}
ESP_ARRUELA = 3.0
FOLGA_MM = 3.0

TIPOS_FLANGE = {"FLANGE", "FLANGE_K"}


def pol(txt):
    """'1 1/8' -> Fraction(9,8)."""
    partes = str(txt).split()
    if len(partes) == 2:
        return Fraction(int(partes[0])) + Fraction(partes[1])
    return Fraction(partes[0])


def carregar_tabela_flange(caminho=TABELA_FLANGE):
    tabela = {}
    with open(caminho, encoding="utf-8") as fh:
        linhas = [ln for ln in fh if not ln.startswith("#")]
    for reg in csv.DictReader(linhas):
        chave = (reg["norma"], float(reg["dn_pol"]))
        tabela[chave] = {
            "furos": int(reg["furos"]),
            "bitola_pol": reg["bitola_pol"],
            "esp_flange_mm": float(reg["esp_flange_mm"]),
            "esp_junta_mm": float(reg["esp_junta_mm"]),
            "homologado": reg["homologado"].strip().upper() == "SIM",
        }
    return tabela


TABELA = carregar_tabela_flange()


class Incompatibilidade(Exception):
    pass


def resolver_juncao(porta_a, porta_b):
    """Como as duas portas se encontram.

    Retorna (acao, dados):
      ('direta',   {'junta': 'FLANGE'|'ENGATE_K'|...})
      ('reducao',  {'de': dn_a, 'para': dn_b, 'tipo': 'CONCENTRICA'|'EXCENTRICA'})
      ('adaptador',{'de': (tipo,norma), 'para': (tipo,norma), 'dn': dn})
      ('erro',     {'motivo': ...})
    """
    if porta_a["dn"] != porta_b["dn"]:
        return "reducao", {"de": porta_a["dn"], "para": porta_b["dn"],
                           "tipo": "CONCENTRICA"}
    mesmo_tipo = porta_a["tipo"] == porta_b["tipo"]
    if mesmo_tipo and porta_a["norma"] == porta_b["norma"]:
        return "direta", {"junta": porta_a["tipo"], "dn": porta_a["dn"],
                          "norma": porta_a["norma"]}
    if porta_a["tipo"] in TIPOS_FLANGE and porta_b["tipo"] in TIPOS_FLANGE:
        # duas flanges de normas diferentes: nao aparafusa, precisa adaptador
        return "adaptador", {"dn": porta_a["dn"],
                             "de": (porta_a["tipo"], porta_a["norma"]),
                             "para": (porta_b["tipo"], porta_b["norma"])}
    return "adaptador", {"dn": porta_a["dn"],
                         "de": (porta_a["tipo"], porta_a["norma"]),
                         "para": (porta_b["tipo"], porta_b["norma"])}


def comprimento_parafuso(dn, norma):
    """Aperto = 2 flanges + junta + 2 arruelas + porca + folga, arredondado
    para o comprimento de estoque imediatamente acima."""
    reg = TABELA.get((norma, float(dn)))
    if not reg:
        return None
    necessario = (
        2 * reg["esp_flange_mm"]
        + reg["esp_junta_mm"]
        + 2 * ESP_ARRUELA
        + ALTURA_PORCA.get(reg["bitola_pol"], 20.0)
        + FOLGA_MM
    )
    for comp in COMPRIMENTOS:
        if comp * 25.4 >= necessario:
            return comp, round(necessario, 1)
    return COMPRIMENTOS[-1], round(necessario, 1)


def ferragem_da_junta(dn, norma):
    """Itens derivados de UMA junta flangeada. Lista de (papel, especificacao, qtd)."""
    reg = TABELA.get((norma, float(dn)))
    if not reg:
        raise Incompatibilidade(
            f"sem tabela de furacao para {norma} DN {dn}\" - cadastrar em regras_flange.csv"
        )
    comp = comprimento_parafuso(dn, norma)
    bit = reg["bitola_pol"]
    n = reg["furos"]
    return [
        ("JUNTA_PLANA", {"dn": dn}, 1),
        ("PARAFUSO", {"bitola_pol": bit, "comprimento_pol": comp[0]}, n),
        ("PORCA", {"bitola_pol": bit}, n),
        ("ARRUELA", {"bitola_pol": bit}, 2 * n),
    ]
