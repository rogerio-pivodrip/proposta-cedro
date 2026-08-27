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
