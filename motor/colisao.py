"""Duas pecas no mesmo lugar: o conflito que so o desenho sabe.

A furacao, a classe e o sentido do fluxo se conferem PECA A PECA, lendo o
cadastro. Este nao: uma curva a mais fecha a linha sobre si mesma, um ramo
nasce numa boca que aponta para dentro da montagem, um acessorio sobe onde a
adutora ja passa - e nenhuma das pecas envolvidas tem defeito nenhum. O
conflito e da POSE, e a pose so existe depois de encadear os simbolos.

Por isso a conferencia mora aqui e nao na `Linha`: ela le os `Posto` que
`vista.desenhar_linha` ja colocou, com a mesma transformacao rigida que
desenhou o SVG. Refazer a colocacao para conferir seria criar uma terceira
geometria para brigar com as outras duas.

**Vizinho nao colide.** Duas pecas encadeadas se encostam face a face, e a
chapa da flange e desenhada PARA DENTRO da peca (ver `simbolos.placa`): as
caixas se tocam e se mordem alguns milimetros por construcao. Por isso o par
adjacente na corrente e o par peca/acessorio nao entram na conta, e o que
entra so vira aviso quando a area comum passa de `MINIMO`.

O teste e o do eixo separador (SAT) sobre os quatro cantos girados. Nao e
excesso: a curva de 45 graus poe caixas inclinadas, e comparar retangulos
alinhados ali acusaria colisao onde ha so uma diagonal passando perto.
"""
import math

# QUANTO PRECISA SE MORDER PARA VIRAR AVISO, medido contra a SECAO da peca
# mais estreita - o lado curto da caixa dela, ao quadrado - e nao contra a
# area da caixa.
#
# A fracao de area engana justamente no caso que mais importa. Dois tubos de
# 6 m de 6" cruzados de fio a fio se sobrepoem em 285x285 mm, que e uma peca
# atravessando a outra de lado a lado - e isso da 5% da area da caixa, menos
# que a mordida de uma flange. Contra a secao, o mesmo cruzamento da 100% e a
# mordida da flange (16 mm de chapa) da 6%.
MINIMO = 0.25


def conferir(placados, adjacentes=()):
    """Os pares que ocupam o mesmo lugar. [(a, b, fracao), ...]

    `placados` e [(identidade, posto), ...] na geometria final da folha.
    `adjacentes` sao os pares de identidade que se encostam de proposito -
    vizinhos na corrente, peca e acessorio, dono e primeira peca do ramo.
    """
    from . import simbolos as s

    juntos = set()
    for a, b in adjacentes:
        juntos.add((a, b))
        juntos.add((b, a))

    caixas = []
    for identidade, posto in placados:
        corpo = s.caixa_do_corpo(posto.simbolo)
        caixas.append((identidade,
                       _cantos(corpo, posto.dx, posto.dy, posto.giro),
                       abs(corpo[2] * corpo[3]),
                       min(abs(corpo[2]), abs(corpo[3]))))

    achados = []
    for i, (ida, ca, area_a, lado_a) in enumerate(caixas):
        for idb, cb, area_b, lado_b in caixas[i + 1:]:
            if (ida, idb) in juntos:
                continue
            comum = _area_comum(ca, cb)
            if not comum:
                continue
            secao = min(lado_a, lado_b) ** 2
            if comum < MINIMO * max(secao, 1e-6):
                continue
            # o numero que sai e o que se le: quanto da peca mais estreita
            # esta dentro da outra
            achados.append((ida, idb, comum / max(min(area_a, area_b), 1e-6)))
    return achados


def _cantos(caixa, dx, dy, giro):
    """Os quatro cantos da caixa, girados e postos no lugar dela na folha."""
    x0, y0, w, h = caixa
    rad = math.radians(giro)
    cos, sen = math.cos(rad), math.sin(rad)
    return [(dx + cx * cos - cy * sen, dy + cx * sen + cy * cos)
            for cx, cy in ((x0, y0), (x0 + w, y0),
                           (x0 + w, y0 + h), (x0, y0 + h))]


def _area_comum(a, b):
    """A area da interseccao de dois retangulos girados, por recorte."""
    if _separados(a, b) or _separados(b, a):
        return 0.0
    return _area(_recortar(a, b))


def _separados(a, b):
    """SAT: ha um lado de `a` cuja normal separa os dois poligonos?

    Projeta-se os dois nessa normal e olha-se se os intervalos se tocam. Ha
    separacao quando um acaba antes de o outro comecar - e ai nao ha
    interseccao possivel, qualquer que seja o resto.
    """
    for i in range(len(a)):
        x1, y1 = a[i]
        x2, y2 = a[(i + 1) % len(a)]
        nx, ny = y2 - y1, x1 - x2          # normal do lado
        pa = [nx * px + ny * py for px, py in a]
        pb = [nx * px + ny * py for px, py in b]
        if max(pa) <= min(pb) + 1e-9 or max(pb) <= min(pa) + 1e-9:
            return True
    return False


def _recortar(alvo, faca):
    """Sutherland-Hodgman: `alvo` cortado por cada lado do convexo `faca`."""
    saida = list(alvo)
    for i in range(len(faca)):
        x1, y1 = faca[i]
        x2, y2 = faca[(i + 1) % len(faca)]
        entrada, saida = saida, []
        if not entrada:
            break
        anterior = entrada[-1]
        for atual in entrada:
            de_dentro = _dentro(atual, x1, y1, x2, y2)
            if de_dentro:
                if not _dentro(anterior, x1, y1, x2, y2):
                    saida.append(_corte(anterior, atual, x1, y1, x2, y2))
                saida.append(atual)
            elif _dentro(anterior, x1, y1, x2, y2):
                saida.append(_corte(anterior, atual, x1, y1, x2, y2))
            anterior = atual
    return saida


def _lado(p, x1, y1, x2, y2):
    return (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1)


def _dentro(p, x1, y1, x2, y2):
    # `_cantos` devolve os quatro na ordem em que a caixa se percorre, e nessa
    # ordem o interior fica do lado POSITIVO do produto vetorial
    return _lado(p, x1, y1, x2, y2) >= -1e-9


def _corte(a, b, x1, y1, x2, y2):
    da, db = _lado(a, x1, y1, x2, y2), _lado(b, x1, y1, x2, y2)
    if abs(db - da) < 1e-12:
        return b
    t = da / (da - db)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _area(pontos):
    if len(pontos) < 3:
        return 0.0
    soma = 0.0
    for i, (x, y) in enumerate(pontos):
        xb, yb = pontos[(i + 1) % len(pontos)]
        soma += x * yb - xb * y
    return abs(soma) / 2
