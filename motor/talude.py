"""Subir e descer o talude.

Duas maneiras, conforme o material:

  aco zincado -> duas curvas de 45 graus, uma no pe e outra no topo
  Plasson     -> duas curvas de 90 graus giradas uma em relacao a outra, que
                 juntas fazem o angulo que precisar

O segundo caso tem geometria: duas curvas de 90 com giro relativo (phi) entre os
planos defletem o eixo em theta, e a relacao e cos(theta) = sen(phi). Ou seja,
sem giro (phi=0) da 90 graus; com giro de 90 graus as duas se cancelam e a linha
volta ao rumo original, so deslocada.
"""
import math

ACO = "ACO_ZINCADO"
PLASSON = "PVC_PLASSON"

RECEITA = {
    ACO: {"angulo_curva": 45, "curvas": 2,
          "nota": "uma curva no pe e outra no topo do talude"},
    PLASSON: {"angulo_curva": 90, "curvas": 2,
              "nota": "duas de 90 giradas entre si dao o angulo necessario"},
}


def giro_para(theta_graus):
    """Giro entre as duas curvas de 90 para defletir theta graus.

    cos(theta) = sen(phi)  ->  phi = arcsen(cos(theta))
    """
    if not 0 <= theta_graus <= 180:
        raise ValueError("deflexao fora de 0 a 180 graus")
    return math.degrees(math.asin(max(-1.0, min(1.0, math.cos(
        math.radians(theta_graus))))))


def deflexao_do_giro(phi_graus):
    """O caminho inverso: que angulo sai de um dado giro."""
    return math.degrees(math.acos(max(-1.0, min(1.0, math.sin(
        math.radians(phi_graus))))))


def travessia(catalogo, dn, material=ACO, norma="NBR PN16", theta_graus=None):
    """Pecas para vencer o talude. Devolve (itens, plano, faltando)."""
    receita = RECEITA.get(material)
    if not receita:
        return [], None, [("material sem receita de talude", material)]
    # o Plasson solda, entao nao adianta filtrar pela norma da linha
    item = (catalogo.melhor("CURVA", dn, norma=norma,
                            angulo=receita["angulo_curva"], material=material)
            or catalogo.melhor("CURVA", dn, angulo=receita["angulo_curva"],
                               material=material)
            or catalogo.melhor("CURVA", dn, angulo=receita["angulo_curva"],
                               material=None))
    faltando = [] if item else [("CURVA", dn, receita["angulo_curva"])]
    itens = [(item, receita["curvas"])] if item else []
    plano = dict(receita)
    if material == PLASSON and theta_graus is not None:
        plano["deflexao_graus"] = theta_graus
        plano["giro_graus"] = round(giro_para(theta_graus), 1)
    elif material == ACO:
        plano["deflexao_graus"] = receita["angulo_curva"]
    return itens, plano, faltando
