"""Templates de linha: a receita padrao, resolvida contra o catalogo.

A succao da casa segue sempre a mesma ordem:

    crivo -> valvula de retencao -> tubo de 1 m -> curva (se precisar)
          -> reducao -> bomba

A curva e opcional e a reducao sai da bomba: concentrica ou excentrica conforme
a orientacao, e sempre no DN do bocal de entrada.
"""
from .bomba import HORIZONTAL, entrada_presumida, interpretar, tipo_reducao_succao
from .linha import Linha, Peca

NORMA = "NBR PN16"


def _melhor(catalogo, familia, dn, **extra):
    """Tenta com a norma da linha; se nao houver, aceita a peca de qualquer
    material - valvula e crivo nao sao de aco zincado."""
    return (catalogo.melhor(familia, dn, norma=NORMA, **extra)
            or catalogo.melhor(familia, dn, material=None, norma=NORMA, **extra)
            or catalogo.melhor(familia, dn, material=None, **extra))


def succao(catalogo, dn_linha, modelo_bomba=None, orientacao=HORIZONTAL,
           curva=None, area="P01"):
    """Monta a succao padrao. curva = None, 45 ou 90."""
    linha = Linha(catalogo, tipo="SUCCAO", area=area)
    faltando = []

    receita = [("CRIVO", {}), ("VALVULA_RETENCAO", {}),
               ("TUBO", {"comprimento_mm": 1000})]
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
