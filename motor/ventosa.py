"""Onde a ventosa entra na linha.

Duas maneiras, conforme o material do trecho:

  plastico (Plasson, PVC, PEAD) -> colar de tomada com saida de 2"
  aco zincado                   -> peca que ja vem com saida de 2": manifold
                                   com luva, flange cega com luva, ou curva
                                   de 90 com escape

Em aco a saida vem embutida na peca, entao a ventosa nao acrescenta um item de
tomada - ela troca a peca por uma versao com saida.
"""
SAIDA_PADRAO_POL = 2.0
PLASTICOS = {"PVC", "PVC_PLASSON", "PEAD"}

# Familias de aco que ja saem de fabrica com derivacao
COM_SAIDA = ("MANIFOLD", "FLANGE_CEGA", "CURVA")


def tem_saida(item, saida_pol=SAIDA_PADRAO_POL):
    return any(d["dn"] == saida_pol for d in item["derivacoes"])


def opcoes_em_aco(catalogo, dn, saida_pol=SAIDA_PADRAO_POL, norma="NBR PN16"):
    """Pecas de aco desse DN que ja trazem a saida para a ventosa."""
    achados = []
    for familia in COM_SAIDA:
        for item in catalogo.buscar(familia, dn, norma=norma):
            if tem_saida(item, saida_pol):
                achados.append(item)
    return achados


def colar_de_tomada(catalogo, dn_mm, saida_pol=SAIDA_PADRAO_POL):
    """Colar do diametro do tubo, com a saida pedida."""
    for item in catalogo.buscar("COLAR_TOMADA", dn_mm, material=None):
        if item.get("saida_pol") == saida_pol:
            return item
    return None


def montagem(catalogo, dn, material, unidade="in", saida_pol=SAIDA_PADRAO_POL,
             norma="NBR PN16"):
    """Como pendurar a ventosa nesse trecho.

    Devolve (modo, apoio, ventosa, faltando).
    """
    ventosa = None
    for item in catalogo.buscar("VENTOSA", saida_pol, material=None):
        ventosa = item
        break

    if material in PLASTICOS or unidade == "mm":
        apoio = colar_de_tomada(catalogo, dn, saida_pol)
        faltando = [] if apoio else [("COLAR_TOMADA", dn, saida_pol)]
        return "COLAR_TOMADA", apoio, ventosa, faltando

    opcoes = opcoes_em_aco(catalogo, dn, saida_pol, norma)
    faltando = [] if opcoes else [("peca de aco com saida", dn, saida_pol)]
    return "SAIDA_NA_PECA", opcoes, ventosa, faltando
