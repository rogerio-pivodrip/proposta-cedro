"""Templates de linha: a receita padrao, resolvida contra o catalogo.

Duas receitas por enquanto: a succao e o trecho de PEAD.

A succao da casa segue sempre a mesma ordem:

    crivo -> valvula de retencao -> tubo de 1 m -> curva (se precisar)
          -> reducao -> bomba

A curva e opcional e a reducao sai da bomba: concentrica ou excentrica conforme
a orientacao, e sempre no DN do bocal de entrada.

O ARTICULADOR de 30 graus entra como opcao da succao. A casa NAO usa flutuador
- o manual descreve succao com flutuante, mas ainda nao e praticado aqui.
"""
from .bomba import (HORIZONTAL, MM_PARA_POLEGADA, entrada_presumida,
                    interpretar, tipo_reducao_succao)
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
           curva=None, area="P01", articulador=False):
    """Monta a succao padrao. curva = None, 45 ou 90.

    articulador=True insere o articulador de 30 graus depois da tomada.
    """
    linha = Linha(catalogo, tipo="SUCCAO", area=area)
    faltando = []

    receita = [("CRIVO", {}), ("VALVULA_RETENCAO", {})]
    if articulador:
        receita.append(("ARTICULADOR", {}))
    receita.append(("TUBO", {"comprimento_mm": 1000}))
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
