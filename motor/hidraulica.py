"""Valvula hidraulica: onde ela fica e o que vem junto.

Ordem confirmada nos tres projetos:

    filtro -> valvula hidraulica -> medidor

A valvula nunca vem sozinha: leva um esquema de piloto. O esquema do fabricante
lista os itens do piloto mas avisa em rodape que material de ligacao - solda
plastica, solucao limpadora, parafuso, porca, arruela - fica de fora. E o mesmo
buraco que o resto deste programa fecha.
"""
import csv
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOTOS = os.path.join(RAIZ, "data", "pilotos.csv")
MEDIDORES = os.path.join(RAIZ, "data", "medidores.csv")
MEDIDORES_WI = os.path.join(RAIZ, "data", "medidores_wi.csv")

# Sequencia canonica do recalque depois do filtro
SEQUENCIA = ["FILTRO", "VALVULA_HIDRAULICA", "MEDIDOR"]


def _carregar():
    with open(PILOTOS, encoding="utf-8") as fh:
        linhas = [ln for ln in fh if not ln.startswith("#")]
    return {r["funcao"]: r for r in csv.DictReader(linhas)}


KITS = _carregar()


def _carregar_medidores():
    with open(MEDIDORES, encoding="utf-8") as fh:
        linhas = [ln for ln in fh if not ln.startswith("#")]
    return list(csv.DictReader(linhas))


MEDIDORES = _carregar_medidores()


def medidor(dn_pol, situacao="usar"):
    """Lista fechada, por codigo - buscar por familia traria os digitais.

    situacao="usar" e a linha ARAD IRT analogica de pulso. Os ARAD IRT ER sao
    digitais e dependem do cabo 70220-030000: ficam marcados nao_usar.
    """
    for reg in MEDIDORES:
        if float(reg["dn_pol"]) == float(dn_pol) and reg["situacao"] == situacao:
            return reg
    return None


_wi = None


def _carregar_wi():
    """A folha do medidor tangencial WI, indexada por (bitola, PN)."""
    global _wi
    if _wi is None:
        _wi = {}
        with open(MEDIDORES_WI, encoding="utf-8") as fh:
            linhas = [ln for ln in fh if not ln.startswith("#")]
        for r in csv.DictReader(linhas):
            _wi[(float(r["dn_pol"]), int(r["pn"]))] = {
                "dn_pol": float(r["dn_pol"]), "dn_mm": float(r["dn_mm"]),
                "pn": int(r["pn"]),
                "face_a_face_mm": float(r["L_mm"]),
                "altura_total_mm": float(r["H_mm"]),
                "parafuso_mm": float(r["parafuso_mm"]),
                "furo_mm": float(r["furo_mm"]), "furos": int(r["furos"]),
                "furo_derivado": r["furo_derivado"].strip().upper() == "SIM",
                "peso_kg": float(r["peso_kg"]),
                "fonte": "akvometer WI",
            }
    return _wi


def ficha_wi(dn_pol, pn=16):
    """A ficha do medidor tangencial WI nessa bitola e nesse PN.

    O PN nao e detalhe: em 8" a MESMA peca sai com 8 furos em PN10 e 12 em
    PN16, com o mesmo comprimento e a mesma altura. A linha da casa e PN16, de
    12 furos - receber o PN10 e receber uma peca que nao aparafusa, e a folha e
    o unico lugar onde isso esta dito.
    """
    return _carregar_wi().get((float(dn_pol), int(pn)))


def furacoes_do_medidor(dn_pol):
    """Todas as furacoes que o medidor tem nessa bitola, por PN.

    Devolve {pn: (furos, furo_mm)}. Mais de uma entrada quer dizer que a
    bitola tem versoes que NAO se substituem: e preciso dizer o PN no pedido.
    """
    return {pn: (f["furos"], f["furo_mm"])
            for (d, pn), f in sorted(_carregar_wi().items())
            if d == float(dn_pol)}


def norma_do_medidor(dn_pol, pn=16):
    """Em que norma de furacao o medidor cai nessa bitola.

    Devolve a lista de normas cuja furacao bate com a da folha. Ate 8" NBR e
    EN coincidem e a resposta e as duas; em 10" e 12" so EN bate, e ai a
    resposta e uma so - e e uma resposta que muda o parafuso.
    """
    from . import bitola, regras
    f = ficha_wi(dn_pol, pn)
    if not f:
        return []
    dn = bitola.nominal(dn_pol)
    return [norma for norma in ("NBR PN16", "EN PN16", "ANSI 150")
            if (reg := regras.FUROS.get((norma, dn)))
            and reg["furos"] == f["furos"]
            and abs(reg["furo_mm"] - f["furo_mm"]) <= 0.5]


def medidores_por_situacao(situacao):
    return [r for r in MEDIDORES if r["situacao"] == situacao]


def kit_piloto(funcao="REDUTORA_SUSTENTADORA"):
    reg = KITS.get(funcao)
    if not reg:
        return None
    return {
        "funcao": funcao,
        "piloto_sap": reg["piloto_sap"],
        "piloto_descricao": reg["piloto_descricao"],
        "kit_sap": reg["kit_sap"] or None,
        "molas": [m for m in reg["mola_opcoes"].split("|") if m],
        "esquema": reg["esquema"],
    }


def conferir_sequencia(familias):
    """Confere a ordem filtro -> valvula hidraulica -> medidor.

    Recebe a lista de familias na ordem da linha e devolve os problemas.
    """
    problemas = []
    posicoes = {}
    for i, familia in enumerate(familias):
        posicoes.setdefault(familia, []).append(i)

    for i in posicoes.get("FILTRO", []):
        depois = [j for j in posicoes.get("VALVULA_HIDRAULICA", []) if j > i]
        if not depois:
            problemas.append(
                "filtro sem valvula hidraulica na saida - e ali que ela fica")
            continue
        medidores = [j for j in posicoes.get("MEDIDOR", []) if j > i]
        if medidores and medidores[0] < depois[0]:
            problemas.append(
                "medidor antes da valvula hidraulica - a ordem e filtro, "
                "valvula, medidor")
    return problemas
