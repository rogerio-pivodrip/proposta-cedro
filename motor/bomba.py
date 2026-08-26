"""Nomenclatura da bomba: os bocais estao no proprio codigo.

Regra da casa:
  dois grupos  (000-000)     -> saida da bomba, rotor padrao
  tres grupos  (000-000-000) -> entrada, saida, rotor padrao

E dai que saem as reducoes: a succao termina na ENTRADA e o recalque comeca na
SAIDA. Como a linha quase sempre e maior que os bocais, ha uma reducao de cada
lado - e por isso que 161 das reducoes do catalogo tem uma ponta em norma de
equipamento e a outra em NBR PN16.
"""
import re

RX_TRES = re.compile(r"\b(\d{2,3})[-/](\d{2,3})[-/](\d{2,4})(?:\.\d)?\b")
RX_DOIS = re.compile(r"\b(\d{2,3})[-/](\d{2,4})(?:\.\d)?\b")

# Bocal em milimetro -> polegada comercial
MM_PARA_POLEGADA = {25: 1, 32: 1.25, 40: 1.5, 50: 2, 65: 2.5, 80: 3, 100: 4,
                    125: 5, 150: 6, 200: 8, 250: 10, 300: 12, 350: 14,
                    400: 16, 450: 18, 500: 20}

# Familias de bomba centrifuga que usam essa nomenclatura
RX_FAMILIA = re.compile(
    r"\b(METB|METN|MCPK|ETB|ETN|ETA|INI|INIB|ITAP|BLOC|MEG|CPK|KWP)\b", re.I)


def interpretar(descricao):
    """Descricao da bomba -> bocais e rotor. None se nao reconhecer."""
    texto = descricao.upper()
    if not RX_FAMILIA.search(texto):
        return None
    m = RX_TRES.search(texto)
    if m:
        entrada, saida, rotor = (int(g) for g in m.groups())
        grupos = 3
    else:
        m = RX_DOIS.search(texto)
        if not m:
            return None
        saida, rotor = (int(g) for g in m.groups())
        entrada, grupos = None, 2
    return {
        "grupos": grupos,
        "entrada_mm": entrada,
        "saida_mm": saida,
        "rotor_mm": rotor,
        "entrada_pol": MM_PARA_POLEGADA.get(entrada) if entrada else None,
        "saida_pol": MM_PARA_POLEGADA.get(saida),
    }


def reducoes(bomba, dn_succao_pol=None, dn_recalque_pol=None):
    """Quais reducoes a bomba exige, dadas as bitolas da linha.

    Succao: linha -> entrada, EXCENTRICA (topo reto, para nao formar bolsa de ar).
    Recalque: saida -> linha, CONCENTRICA.
    """
    saida = []
    entrada_pol = bomba.get("entrada_pol")
    if entrada_pol is None and bomba["grupos"] == 2:
        # bomba de dois grupos nao declara a entrada; nao inventar
        entrada_pol = None
    if dn_succao_pol and entrada_pol and dn_succao_pol != entrada_pol:
        saida.append({"lado": "SUCCAO", "tipo": "REDUCAO_EXCENTRICA",
                      "de": dn_succao_pol, "para": entrada_pol})
    if dn_recalque_pol and bomba["saida_pol"] and dn_recalque_pol != bomba["saida_pol"]:
        saida.append({"lado": "RECALQUE", "tipo": "REDUCAO_CONCENTRICA",
                      "de": bomba["saida_pol"], "para": dn_recalque_pol})
    return saida
