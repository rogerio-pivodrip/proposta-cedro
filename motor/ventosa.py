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


# A ventosa NAO aparafusa: ela ENROSCA. A de 2" so entra em luva ou em peca
# com rosca femea de 2" - a luva da flange cega, a luva da curva de saida, o
# colar de tomada. Numa flange ela nao entra, e numa luva de outra bitola
# tambem nao.
PAPEIS_DE_ROSCA = ("luva", "rosca", "tomada")


def encaixa_na_boca(porta, dn_pol=SAIDA_PADRAO_POL):
    """Essa boca recebe a ventosa? (ok, motivo)

    A regra e da casa e e curta: rosca femea, e da MESMA bitola. O papel da
    porta diz o tipo - `luva` e rosca, `derivacao` e flange - e o dn diz a
    bitola. Uma ventosa de 2" numa luva de 1" nao entra, e numa flange de 2"
    muito menos: nao ha rosca ali.
    """
    if porta is None:
        return False, "a peca nao tem boca livre"
    if porta.papel not in PAPEIS_DE_ROSCA:
        return False, (f'a boca e {porta.papel} - a ventosa enrosca, '
                       "e so entra em luva ou rosca femea")
    if abs(float(porta.dn_pol) - float(dn_pol)) > 0.01:
        return False, (f'a boca e de {porta.dn_pol:g}" e a ventosa e de '
                       f'{dn_pol:g}"')
    return True, ""
