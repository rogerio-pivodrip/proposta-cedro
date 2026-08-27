"""O simbolo de cada familia, desenhado com a cota real do fabricante.

Nao e clipart: cada peca ocupa no papel a medida que tem em milimetro, a flange
sai com a quantidade certa de furos no circulo certo, e o simbolo devolve as
portas com coordenada e direcao - e isso que deixa encaixar uma peca na outra.

    s = tubo(8, 1000)
    s.portas   -> [Porta('entrada', 0, 0, 180), Porta('saida', 1000, 0, 0)]
    s.caixa    -> (0, -170, 1000, 340)   # em mm, para o balao e a colisao

Cinco primitivas fazem todas as familias: eixo, cone, placa, giro e caixa.
"""
import csv
import math
import os
from collections import namedtuple

from . import cotas

DADOS = os.path.join(os.path.dirname(__file__), "..", "data")

Porta = namedtuple("Porta", "papel x y direcao dn_pol")
Simbolo = namedtuple("Simbolo",
                     "familia rotulo elementos portas caixa fonte params")

# Diametro externo do tubo AZ, do caderno de desenhos Netafim (coluna D)
DE_TUBO = {2: 48, 2.5: 60, 3: 76, 4: 102, 5: 133, 6: 152, 8: 203, 10: 261,
           12: 318, 14: 368, 16: 419, 18: 470, 20: 521, 24: 622, 28: 711}

_flanges = None


def flange(dn_pol, norma="NBR PN16"):
    """Diametro externo, circulo de furacao, quantidade e diametro do furo."""
    global _flanges
    if _flanges is None:
        _flanges = {}
        with open(f"{DADOS}/flanges_irrigafour.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["norma"] == "DIN 2533 PN 16":
                    _flanges.setdefault(float(r["dn_pol"]), {})["externo"] = \
                        float(r["d_externo_mm"])
        with open(f"{DADOS}/regras_furacao.csv", encoding="utf-8") as fh:
            for r in (x for x in csv.DictReader(
                    l for l in fh if not l.startswith("#")) if x["dn_pol"]):
                if r["norma"] != norma:
                    continue
                d = _flanges.setdefault(float(r["dn_pol"]), {})
                d.update(circulo=float(r["circulo_mm"]), furos=int(r["furos"]),
                         furo=float(r["furo_mm"]), espessura=float(r["esp_flange_mm"]))
    ficha = dict(_flanges.get(float(dn_pol), {}))
    ficha.setdefault("externo", (DE_TUBO.get(dn_pol, 100) * 1.7))
    ficha.setdefault("circulo", ficha["externo"] * 0.85)
    ficha.setdefault("furos", 8)
    ficha.setdefault("furo", 22.0)
    ficha.setdefault("espessura", 20.0)
    return ficha


# ---------------------------------------------------------------- primitivas
def _p(d, classe="corpo"):
    return {"tipo": "path", "d": d, "classe": classe}


def eixo(x, comprimento, dn_pol, y=0.0):
    """Corpo cilindrico visto de lado: duas paredes e a linha de centro."""
    r = DE_TUBO.get(dn_pol, 100) / 2
    return [_p(f"M{x:.1f} {y-r:.1f} H{x+comprimento:.1f}"),
            _p(f"M{x:.1f} {y+r:.1f} H{x+comprimento:.1f}")]


def cone(x, comprimento, dn_maior, dn_menor, alinhamento="centro", y=0.0):
    """Reducao. O alinhamento e o unico parametro que separa concentrica de
    excentrica - uma primitiva, duas familias."""
    ra = DE_TUBO.get(dn_maior, 100) / 2
    rb = DE_TUBO.get(dn_menor, 60) / 2
    if alinhamento == "centro":
        topo_b, base_b = y - rb, y + rb
    elif alinhamento == "fundo":              # plano embaixo: recalque
        topo_b, base_b = y + ra - 2 * rb, y + ra
    else:                                     # plano em cima: succao
        topo_b, base_b = y - ra, y - ra + 2 * rb
    return [_p(f"M{x:.1f} {y-ra:.1f} L{x+comprimento:.1f} {topo_b:.1f}"),
            _p(f"M{x:.1f} {y+ra:.1f} L{x+comprimento:.1f} {base_b:.1f}")]


def placa(x, dn_pol, y=0.0, direcao=0.0, norma="NBR PN16", lado="entrada"):
    """Flange de lado, com a face no ponto de encaixe.

    A chapa fica inteira DENTRO da peca: na entrada ela cresce para dentro, na
    saida tambem. Duas pecas ligadas mostram duas chapas encostadas - face a
    face, que e como a junta flangeada e - e nao uma sobreposta na outra.
    """
    f = flange(dn_pol, norma)
    metade, esp = f["externo"] / 2, f["espessura"]
    x0 = x if lado == "entrada" else (x - esp if lado == "saida" else x - esp / 2)
    saida = [{"tipo": "rect", "x": x0, "y": y - metade, "w": esp,
              "h": f["externo"], "classe": "flange"}]
    # cada furo aparece como um traco na altura do circulo de furacao
    passo = f["circulo"] / 2
    for sinal in (-1, 1):
        saida.append(_p(f"M{x0:.1f} {y+sinal*passo:.1f} h{esp:.1f}", "furo"))
    saida.append({"tipo": "texto_furos", "x": x, "y": y, "n": f["furos"],
                  "furo": f["furo"]})
    if direcao:
        for e in saida:
            e["girar"] = (direcao, x, y)
    return saida


def giro(x, perna, angulo, dn_pol, sentido=1, y=0.0, gomos=4):
    """Curva de gomos - que e como a curva de aco zincado e feita de verdade.

    Nao e um arco liso: sao chapas cortadas e soldadas. Uma curva de 90 com 4
    gomos vira 15 + 30 + 30 + 15 graus, exatamente como o caderno Netafim
    desenha (Z1 a Z4). As pontas viram metade do que os gomos do meio viram.

    Devolve as paredes, as soldas entre gomos, e a saida (x, y, direcao).
    """
    r = DE_TUBO.get(dn_pol, 100) / 2
    t = math.radians(angulo)
    # O gomo ocupa quase toda a perna: sobra so um toco reto para a flange.
    # Com raio pequeno as pernas retas comiam os gomos das pontas e a curva
    # saia com dois gomos largos no meio e dois fiapos nas beiras.
    recuo = perna * 0.86
    raio = max(recuo / math.tan(t / 2), r * 1.05)
    recuo = raio * math.tan(t / 2)
    if recuo > perna * 0.92:
        recuo = perna * 0.92
        raio = recuo / math.tan(t / 2)

    vx, vy = x + perna, y
    # cortes: as pontas viram metade do gomo do meio
    n = max(int(gomos), 2)
    passo = angulo / (n - 1)
    cortes = [0.0]
    for i in range(n):
        cortes.append(cortes[-1] + (passo / 2 if i in (0, n - 1) else passo))
    cortes = [c for c in cortes if c <= angulo + 1e-6]
    if abs(cortes[-1] - angulo) > 1e-6:
        cortes.append(angulo)

    # centro do arco, do lado de dentro da curva
    t1 = (vx - recuo, vy)
    centro = (t1[0], t1[1] - raio * sentido)
    pontos = []
    for c in cortes:
        a = math.radians(c) * sentido
        # ponto do arco medido a partir de t1, girando em torno de centro
        px = centro[0] + raio * math.sin(a) * sentido
        py = centro[1] + raio * math.cos(a) * sentido
        pontos.append((px, py))
    inicio = (x, y)
    dsx, dsy = math.cos(-t * sentido), math.sin(-t * sentido)
    fim = (vx + perna * dsx, vy + perna * dsy)
    t2 = (vx + recuo * dsx, vy + recuo * dsy)
    # pontos ja contem os dois pontos de tangencia (corte 0 e corte final):
    # repeti-los criava dois segmentos a mais e a curva de 4 gomos aparecia
    # com 6. A linha e: perna de entrada, os N gomos, perna de saida.
    centro_linha = [inicio] + pontos + [fim]

    def normal(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        return (-dy / n, dx / n)

    def parede(lado):
        saida = []
        for i in range(len(centro_linha) - 1):
            a, b = centro_linha[i], centro_linha[i + 1]
            nx, ny = normal(a, b)
            saida.append(((a[0] + nx * r * lado, a[1] + ny * r * lado),
                          (b[0] + nx * r * lado, b[1] + ny * r * lado)))
        # une os segmentos pelo encontro aproximado: o proprio vertice deslocado
        pts = [saida[0][0]]
        for i, (_, b) in enumerate(saida):
            pts.append(b if i == len(saida) - 1 else
                       ((b[0] + saida[i + 1][0][0]) / 2,
                        (b[1] + saida[i + 1][0][1]) / 2))
        return pts

    fora, dentro = parede(1 * sentido), parede(-1 * sentido)
    caminho = lambda pts: "M" + " L".join(f"{p[0]:.1f} {p[1]:.1f}" for p in pts)
    elementos = [_p(caminho(fora)), _p(caminho(dentro))]
    # solda so entre gomo e gomo: N gomos dao N-1 soldas. As juntas com as
    # pernas nao aparecem, que e onde o tubo continua reto.
    for i in range(2, len(fora) - 2):
        elementos.append(_p(f"M{fora[i][0]:.1f} {fora[i][1]:.1f} "
                            f"L{dentro[i][0]:.1f} {dentro[i][1]:.1f}", "solda"))
    return (elementos, (fim[0], fim[1], -angulo * sentido), (centro, raio),
            centro_linha)


def eixo_de(pontos, sobra=60.0):
    """Traco-ponto seguindo a linha de centro, com sobra nas duas pontas.

    Numa curva de gomos o eixo nao e uma reta que quebra no vertice: ele
    acompanha os gomos, quebrando junto com eles em cada solda.
    """
    def estica(a, b, quanto):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        return (b[0] + dx / n * quanto, b[1] + dy / n * quanto)

    caminho = [estica(pontos[1], pontos[0], sobra)] + list(pontos[1:-1]) + \
        [estica(pontos[-2], pontos[-1], sobra)]
    return "M" + " L".join(f"{p[0]:.1f} {p[1]:.1f}" for p in caminho)


def caixa(x, largura, altura_acima, altura_abaixo, y=0.0, classe="corpo"):
    return [{"tipo": "rect", "x": x, "y": y - altura_acima, "w": largura,
             "h": altura_acima + altura_abaixo, "classe": classe}]


def _caixa(elementos):
    xs, ys = [], []
    for e in elementos:
        if e["tipo"] == "rect":
            xs += [e["x"], e["x"] + e["w"]]
            ys += [e["y"], e["y"] + e["h"]]
        elif e["tipo"] == "path":
            for n in _numeros(e["d"]):
                pass
    return xs, ys


def _numeros(d):
    import re
    return [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]


def limites(elementos):
    """Retangulo que contem tudo, em mm - ja com o que esta girado no lugar."""
    xs, ys = [], []
    for e in elementos:
        pontos = []
        if e["tipo"] == "rect":
            pontos = [(e["x"], e["y"]), (e["x"] + e["w"], e["y"]),
                      (e["x"], e["y"] + e["h"]), (e["x"] + e["w"], e["y"] + e["h"])]
        elif e["tipo"] == "path":
            n = _numeros(e["d"])
            pontos = list(zip(n[0::2][:24], n[1::2][:24]))
        elif e["tipo"] == "circulo":
            pontos = [(e["cx"] - e["r"], e["cy"] - e["r"]),
                      (e["cx"] + e["r"], e["cy"] + e["r"])]
        girar = e.get("girar")
        if girar:
            ang, cx, cy = math.radians(girar[0]), girar[1], girar[2]
            cos, sen = math.cos(ang), math.sin(ang)
            pontos = [(cx + (px - cx) * cos - (py - cy) * sen,
                       cy + (px - cx) * sen + (py - cy) * cos) for px, py in pontos]
        xs += [p[0] for p in pontos]
        ys += [p[1] for p in pontos]
    if not xs:
        return (0, 0, 1, 1)
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _montar(familia, rotulo, elementos, portas, fonte=None, params=None):
    return Simbolo(familia, rotulo, elementos, portas, limites(elementos),
                   fonte, params or {})


def _cota(familia, dn, variante="", significado="face_a_face_mm", menor=None):
    return cotas.cota_com_fonte(familia, dn, variante, significado, None, menor)


# ------------------------------------------------------------------ familias
def tubo(dn_pol, comprimento_mm=1000):
    el = eixo(0, comprimento_mm, dn_pol)
    el += placa(0, dn_pol) + placa(comprimento_mm, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comprimento_mm + 60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comprimento_mm, 0, 0, dn_pol)]
    return _montar("TUBO", f'tubo {dn_pol:g}" {comprimento_mm/1000:g} m',
                   el, portas, "descricao")


def curva(dn_pol, angulo=90, sentido=1, gomos=None):
    perna, fonte = _cota("CURVA", dn_pol, str(angulo), "perna_mm")
    perna = perna or DE_TUBO.get(dn_pol, 100) * 1.5
    gomos = gomos or (4 if angulo >= 90 else 3 if angulo >= 45 else 2)
    el, (sx, sy, direcao), _, eixo_linha = giro(0, perna, angulo, dn_pol,
                                                sentido, gomos=gomos)
    el += placa(0, dn_pol)
    bocal = placa(sx, dn_pol, sy, lado="saida")
    for e in bocal:
        e["girar"] = (direcao, sx, sy)
    el += bocal
    el.append(_p(eixo_de(eixo_linha), "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", sx, sy, direcao, dn_pol)]
    return _montar("CURVA", f'curva {angulo}° {dn_pol:g}" {gomos} gomos',
                   el, portas, fonte)


def reducao(dn_maior, dn_menor, tipo="CONCENTRICA", lado_plano="topo",
            crescente=False):
    """Cone entre duas bitolas.

    crescente=True desenha o menor na entrada e o maior na saida - e o que o
    catalogo Irrigafour chama de AUMENTO, e o que a linha faz no recalque, onde
    a bomba entrega pequeno e a adutora segue grande. A peca e a mesma; o que
    muda e por que ponta a linha entra.
    """
    familia = f"REDUCAO_{tipo}"
    comp, fonte = _cota(familia, dn_maior, "", "face_a_face_mm", dn_menor)
    comp = comp or 150
    alinhamento = "centro" if tipo == "CONCENTRICA" else lado_plano
    a, b = (dn_menor, dn_maior) if crescente else (dn_maior, dn_menor)
    ra, rb = DE_TUBO.get(a, 100) / 2, DE_TUBO.get(b, 60) / 2
    if alinhamento == "centro":
        topo_b, base_b = -rb, rb
    elif alinhamento == "fundo":
        topo_b, base_b = (ra - 2 * rb), ra
    else:
        topo_b, base_b = -ra, (-ra + 2 * rb)
    el = [_p(f"M0 {-ra:.1f} L{comp:.1f} {topo_b:.1f}"),
          _p(f"M0 {ra:.1f} L{comp:.1f} {base_b:.1f}")]
    desloca = (topo_b + base_b) / 2
    el += placa(0, a) + placa(comp, b, desloca, lado="saida")
    el.append(_p(f"M-60 0 H{comp*0.55:.0f}", "centro"))
    el.append(_p(f"M{comp*0.45:.0f} {desloca:.0f} H{comp + 60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, a),
              Porta("saida", comp, desloca, 0, b)]
    curto = "conc" if tipo == "CONCENTRICA" else "exc"
    rot = f'{"aumento" if crescente else "redução"} {curto} {a:g}"×{b:g}"'
    return _montar(familia, rot, el, portas, fonte,
                   {"dn_maior": dn_maior, "dn_menor": dn_menor, "tipo": tipo,
                    "lado_plano": lado_plano, "crescente": crescente})


def te(dn_pol, dn_derivacao=None):
    dn_derivacao = dn_derivacao or dn_pol
    comp, fonte = _cota("TE", dn_pol, "", "face_a_face_mm")
    comp = comp or 1000
    alt, _ = _cota("TE", dn_pol, "", "derivacao_mm")
    alt = alt or DE_TUBO.get(dn_pol, 100) * 1.2
    r = DE_TUBO.get(dn_pol, 100) / 2
    rd = DE_TUBO.get(dn_derivacao, 60) / 2
    meio = comp / 2
    el = eixo(0, comp, dn_pol)
    el += [_p(f"M{meio-rd:.1f} {-r:.1f} V{-alt:.1f}"),
           _p(f"M{meio+rd:.1f} {-r:.1f} V{-alt:.1f}")]
    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    bocal = placa(meio, dn_derivacao, -alt, lado="saida")
    for e in bocal:
        e["girar"] = (-90, meio, -alt)
    el += bocal
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    el.append(_p(f"M{meio:.0f} 40 V{-alt-60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol),
              Porta("derivacao", meio, -alt, -90, dn_derivacao)]
    return _montar("TE", f'tê {dn_pol:g}"×{dn_derivacao:g}"', el, portas, fonte)


def crivo(dn_pol, variante=""):
    """Cesto cilindrico de chapa perfurada, flange em cima e chapa lisa no fundo.

    O caderno Netafim (desenho 01523, vista inferior) e o catalogo Irrigafour
    desenham a mesma peca. O que muda e o comprimento: a Netafim cresce com a
    bitola, 100 mm em 3" e 495 em 14"; a Irrigafour e 300 fixo ate 20".
    """
    comp, fonte = _cota("CRIVO", dn_pol, variante, "comprimento_mm")
    comp = comp or 300
    r = DE_TUBO.get(dn_pol, 100) / 2
    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"), _p(f"M0 {r:.1f} H{comp:.1f}"),
          _p(f"M0 {-r:.1f} V{2*r:.1f}", "chapa_lisa")]     # o fundo e fechado
    passo = max(comp / 9, 12)
    n = max(int(comp / passo) - 1, 3)
    el += [_p(f"M{passo*(i+1):.1f} {-r:.1f} v{2*r:.1f}", "malha") for i in range(n)]
    el += placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-40 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("CRIVO", f'crivo {dn_pol:g}"', el, portas, fonte)


def flange_cega(dn_pol):
    """Fecha a linha: a placa cega e o toco de tubo que morre nela."""
    f = flange(dn_pol)
    toco = f["externo"] * 0.5
    el = eixo(-toco, toco, dn_pol) + placa(0, dn_pol, lado="entrada")
    r = DE_TUBO.get(dn_pol, 100) / 2
    el += [_p(f"M{-toco*0.75 + i*toco*0.2:.1f} {-r:.1f} l{-toco*0.16:.1f} "
              f"{2*r:.1f}", "malha") for i in range(4)]
    el.append(_p(f"M{-toco-40:.0f} 0 H{f['espessura']/2:.0f}", "centro"))
    return _montar("FLANGE_CEGA", f'flange cega {dn_pol:g}"', el,
                   [Porta("entrada", -toco, 0, 180, dn_pol)], "norma")


def adaptador(dn_pol):
    comp, fonte = _cota("ADAPTADOR", dn_pol)
    comp = comp or 110
    el = eixo(0, comp, dn_pol) + placa(0, dn_pol)
    r = DE_TUBO.get(dn_pol, 100) / 2
    el += [_p(f"M{comp*0.55 + i*comp*0.09:.1f} {-r:.1f} V{r:.1f}", "malha")
           for i in range(4)]
    el.append(_p(f"M-60 0 H{comp+40:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("ADAPTADOR", f'adaptador {dn_pol:g}"', el, portas, fonte)


# ------------------------------------------------------- familias de equipamento
def _corpo_valvula(dn_pol, comp, acima, abaixo):
    """Corpo com flange nas duas pontas: a base de toda valvula flangeada."""
    el = caixa(0, comp, acima, abaixo)
    el += placa(0, dn_pol) + placa(comp, dn_pol)
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    return el


def valvula_borboleta(dn_pol, acionamento="ALAVANCA"):
    """Wafer: corpo estreito entre flanges, disco na diagonal, e o acionamento.

    O corpo nao tem a altura do tubo - tem a do disco, que a ficha da em A.
    Ele fica dentro do circulo de parafusos, que e o que segura a valvula.
    """
    comp, fonte = _cota("VALVULA_BORBOLETA", dn_pol, acionamento)
    comp = comp or 60
    acima, _ = _cota("VALVULA_BORBOLETA", dn_pol, acionamento, "altura_acima_mm")
    disco, _ = _cota("VALVULA_BORBOLETA", dn_pol, acionamento, "diametro_disco_mm")
    alcance, _ = _cota("VALVULA_BORBOLETA", dn_pol, acionamento,
                       "alcance_acionamento_mm")
    f = flange(dn_pol)
    disco = disco or DE_TUBO.get(dn_pol, 100) * 0.95
    corpo = min(disco * 1.22, f["circulo"] * 0.94)
    acima = acima or corpo * 0.9
    alcance = alcance or corpo * 1.4
    meio = comp / 2
    el = caixa(0, comp, corpo / 2, corpo / 2)
    # a boca: onde a agua passa
    el.append(_p(f"M0 {-disco/2:.1f} H{comp:.1f} M0 {disco/2:.1f} H{comp:.1f}",
                 "oculto"))
    # disco fechado, na diagonal
    el.append(_p(f"M{meio - comp*0.34:.1f} {disco*0.47:.1f} "
                 f"L{meio + comp*0.34:.1f} {-disco*0.47:.1f}", "obturador"))
    # flange do atuador em cima do corpo, e a haste
    topo = -corpo / 2
    flangete = comp * 0.55
    el += caixa(meio - comp*0.7, comp*1.4, -topo + flangete, topo)
    el.append(_p(f"M{meio:.1f} {topo - flangete:.1f} V{-acima + comp*0.8:.1f}",
                 "haste"))
    yl = -acima + comp * 0.8
    if acionamento == "ALAVANCA":
        el += caixa(meio - comp*0.5, comp, -yl + comp*0.45, yl + comp*0.45,
                    classe="acionamento")
        el.append(_p(f"M{meio:.1f} {yl:.1f} h{alcance:.1f}", "acionamento"))
        el.append(_p(f"M{meio + alcance*0.15:.1f} {yl - comp*0.22:.1f} "
                     f"h{alcance*0.75:.1f}", "acionamento"))
        el.append(_p(f"M{meio:.1f} {yl:.1f} l{alcance*0.71:.1f} {-alcance*0.71:.1f}",
                     "acionamento fantasma"))
    else:
        el += caixa(meio - comp*0.9, comp*1.8, -yl, yl + comp*1.3,
                    classe="acionamento")
        ex = meio + comp * 1.7
        yv = yl + comp * 0.55
        el.append(_p(f"M{meio + comp*0.9:.1f} {yv:.1f} H{ex:.1f}", "acionamento"))
        el.append(_p(f"M{ex:.1f} {yv - alcance/2:.1f} v{alcance:.1f}",
                     "acionamento"))
        el.append(_p(f"M{ex - comp*0.3:.1f} {yv - alcance/2:.1f} h{comp*0.6:.1f} "
                     f"M{ex - comp*0.3:.1f} {yv + alcance/2:.1f} h{comp*0.6:.1f}",
                     "acionamento"))
    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    rot = f'borboleta {dn_pol:g}" {"alavanca" if acionamento == "ALAVANCA" else "caixa"}'
    return _montar("VALVULA_BORBOLETA", rot, el, portas, fonte)


def valvula_gaveta(dn_pol):
    """Corpo curto, castelo aparafusado, cunha emborrachada e volante fixo."""
    comp, fonte = _cota("VALVULA_GAVETA", dn_pol)
    comp = comp or 230
    alt, _ = _cota("VALVULA_GAVETA", dn_pol, "", "altura_total_mm")
    volante, _ = _cota("VALVULA_GAVETA", dn_pol, "", "volante_mm")
    f = flange(dn_pol)
    corpo = f["externo"] * 0.62
    alt = alt or corpo * 2.4
    volante = volante or corpo
    meio = comp / 2
    bocal = DE_TUBO.get(dn_pol, 100)
    el = [_p(f"M0 {-bocal/2:.1f} L{comp*0.24:.1f} {-corpo/2:.1f} "
             f"H{comp*0.76:.1f} L{comp:.1f} {-bocal/2:.1f}"),
          _p(f"M0 {bocal/2:.1f} L{comp*0.24:.1f} {corpo/2:.1f} "
             f"H{comp*0.76:.1f} L{comp:.1f} {bocal/2:.1f}")]
    # castelo: flange do corpo e a tampa
    castelo = comp * 0.5
    topo = -alt * 0.46
    el += caixa(meio - castelo/2, castelo, -topo, topo + corpo/2)
    el.append(_p(f"M{meio - castelo*0.62:.1f} {-corpo*0.5:.1f} h{castelo*1.24:.1f}",
                 "obturador"))
    el.append(_p(f"M{meio - castelo*0.56:.1f} {topo:.1f} h{castelo*1.12:.1f}",
                 "obturador"))
    # cunha, tracejada dentro do corpo
    el.append(_p(f"M{meio - bocal*0.3:.1f} {-corpo*0.42:.1f} h{bocal*0.6:.1f} "
                 f"v{corpo*0.72:.1f} l{-bocal*0.3:.1f} {corpo*0.12:.1f} "
                 f"l{-bocal*0.3:.1f} {-corpo*0.12:.1f} Z", "oculto"))
    el.append(_p(f"M{meio:.1f} {topo:.1f} V{-alt + comp*0.06:.1f}", "haste"))
    yv = -alt + comp * 0.06
    el.append(_p(f"M{meio - volante/2:.1f} {yv:.1f} h{volante:.1f}", "acionamento"))
    el.append(_p(f"M{meio - volante/2:.1f} {yv - comp*0.05:.1f} v{comp*0.1:.1f} "
                 f"M{meio + volante/2:.1f} {yv - comp*0.05:.1f} v{comp*0.1:.1f}",
                 "acionamento"))
    el.append(_p(f"M{meio - comp*0.09:.1f} {yv + comp*0.02:.1f} h{comp*0.18:.1f} "
                 f"v{comp*0.09:.1f} h{-comp*0.18:.1f} Z", "acionamento"))
    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("VALVULA_GAVETA", f'gaveta {dn_pol:g}"', el, portas, fonte)


def valvula_hidraulica(dn_pol, serie="47"):
    comp, fonte = _cota("VALVULA_HIDRAULICA", dn_pol, serie)
    comp = comp or 462
    alt, _ = _cota("VALVULA_HIDRAULICA", dn_pol, serie, "altura_total_mm")
    r = DE_TUBO.get(dn_pol, 100) / 2
    alt = alt or r * 3
    meio = comp / 2
    el = caixa(0, comp, r * 1.1, r * 1.1)
    # castelo: a tampa abaulada que guarda o diafragma
    castelo, topo = comp * 0.62, -alt * 0.78
    el.append(_p(f"M{meio - castelo/2:.1f} {-r*1.1:.1f} V{topo + castelo*0.18:.1f} "
                 f"Q{meio - castelo/2:.1f} {topo:.1f} {meio - castelo*0.3:.1f} {topo:.1f} "
                 f"H{meio + castelo*0.3:.1f} "
                 f"Q{meio + castelo/2:.1f} {topo:.1f} {meio + castelo/2:.1f} "
                 f"{topo + castelo*0.18:.1f} V{-r*1.1:.1f}"))
    # o diafragma, e a haste que desce ate o obturador
    el.append(_p(f"M{meio - castelo*0.46:.1f} {topo + castelo*0.42:.1f} "
                 f"h{castelo*0.92:.1f}", "obturador"))
    el.append(_p(f"M{meio:.1f} {topo + castelo*0.42:.1f} V{r*0.35:.1f}", "haste"))
    el.append(_p(f"M{meio - r*0.62:.1f} {r*0.35:.1f} h{r*1.24:.1f}", "obturador"))
    # piloto: corpo pequeno ligado ao castelo por tubinho - sempre listado junto
    px, py = meio + comp * 0.42, topo + castelo * 0.25
    el.append(_p(f"M{meio + castelo/2:.1f} {topo + castelo*0.55:.1f} "
                 f"H{px:.1f} V{py + comp*0.09:.1f}", "piloto"))
    el += caixa(px - comp*0.07, comp*0.14, -py + comp*0.05, py + comp*0.09,
                classe="piloto")
    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("VALVULA_HIDRAULICA", f'hidráulica {serie}-{dn_pol:g}"',
                   el, portas, fonte)


def medidor(dn_pol):
    """Woltmann: corpo entre flanges, torre do registrador e o mostrador."""
    comp, fonte = _cota("MEDIDOR", dn_pol)
    comp = comp or 350
    alt, _ = _cota("MEDIDOR", dn_pol, "", "altura_total_mm")
    baixo, _ = _cota("MEDIDOR", dn_pol, "", "altura_abaixo_mm")
    largura, _ = _cota("MEDIDOR", dn_pol, "", "largura_mm")
    f = flange(dn_pol)
    corpo = (largura or f["externo"]) * 0.62
    baixo = baixo or corpo / 2
    alt = alt or corpo * 2
    meio = comp / 2
    bocal = DE_TUBO.get(dn_pol, 100)
    el = [_p(f"M0 {-bocal/2:.1f} L{comp*0.2:.1f} {-corpo/2:.1f} "
             f"H{comp*0.8:.1f} L{comp:.1f} {-bocal/2:.1f}"),
          _p(f"M0 {bocal/2:.1f} L{comp*0.2:.1f} {corpo/2:.1f} "
             f"H{comp*0.8:.1f} L{comp:.1f} {bocal/2:.1f}")]
    torre = comp * 0.44
    topo = -(alt - baixo)
    el += caixa(meio - torre/2, torre, -topo, topo + corpo/2)
    # o registrador, com o mostrador virado para cima
    el += caixa(meio - torre*0.62, torre*1.24, -topo + torre*0.34, topo)
    cx, cy, rr = meio, topo - torre * 0.17, torre * 0.24
    el.append({"tipo": "circulo", "cx": cx, "cy": cy, "r": rr, "classe": "mostrador"})
    el.append(_p(f"M{cx:.1f} {cy:.1f} L{cx + rr*0.6:.1f} {cy - rr*0.52:.1f}",
                 "mostrador"))
    el.append(_p(f"M{cx:.1f} {cy - rr:.1f} v{rr*0.3:.1f} M{cx + rr:.1f} {cy:.1f} "
                 f"h{-rr*0.3:.1f}", "mostrador"))
    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("MEDIDOR", f'medidor {dn_pol:g}"', el, portas, fonte)


def curva_saida(dn_pol, angulo=90, dn_saida=2, sentido=1, gomos=4):
    """Curva com saida de 2" no dorso - e onde a ventosa entra.

    O catalogo Irrigafour desenha essa familia separada. A saida fica na parte
    convexa do giro, que e o ponto alto da curva quando ela sobe: e por isso
    que a ventosa vive ali.
    """
    perna, fonte = _cota("CURVA_SAIDA", dn_pol, str(angulo), "perna_mm")
    if perna is None:
        perna, fonte = _cota("CURVA", dn_pol, str(angulo), "perna_mm")
    perna = perna or DE_TUBO.get(dn_pol, 100) * 1.5
    el, (sx, sy, direcao), (centro, raio), eixo_linha = giro(
        0, perna, angulo, dn_pol, sentido, gomos=gomos)
    r = DE_TUBO.get(dn_pol, 100) / 2
    rs = DE_TUBO.get(dn_saida, 60) / 2
    # dorso: do centro do arco para o meio da curva
    a = math.radians(angulo / 2) * sentido
    ux, uy = math.sin(a) * sentido, math.cos(a) * sentido
    base = (centro[0] + (raio + r) * ux, centro[1] + (raio + r) * uy)
    haste = DE_TUBO.get(dn_saida, 60) * 1.6
    topo = (base[0] + haste * ux, base[1] + haste * uy)
    tx, ty = -uy, ux
    el.append(_p(f"M{base[0] + tx*rs:.1f} {base[1] + ty*rs:.1f} "
                 f"L{topo[0] + tx*rs:.1f} {topo[1] + ty*rs:.1f}"))
    el.append(_p(f"M{base[0] - tx*rs:.1f} {base[1] - ty*rs:.1f} "
                 f"L{topo[0] - tx*rs:.1f} {topo[1] - ty*rs:.1f}"))
    graus = math.degrees(math.atan2(uy, ux))
    bocal = placa(topo[0], dn_saida, topo[1], lado="saida")
    for e in bocal:
        e["girar"] = (graus, topo[0], topo[1])
    el += bocal
    el += placa(0, dn_pol)
    saida_fl = placa(sx, dn_pol, sy, lado="saida")
    for e in saida_fl:
        e["girar"] = (direcao, sx, sy)
    el += saida_fl
    el.append(_p(eixo_de(eixo_linha), "centro"))
    el.append(_p(f"M{base[0] - ux*20:.1f} {base[1] - uy*20:.1f} "
                 f"L{topo[0] + ux*30:.1f} {topo[1] + uy*30:.1f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", sx, sy, direcao, dn_pol),
              Porta("derivacao", topo[0], topo[1], graus, dn_saida)]
    return _montar("CURVA_SAIDA",
                   f'curva {angulo}° {dn_pol:g}" c/ saída {dn_saida:g}"',
                   el, portas, fonte)


def valvula_pe(dn_pol):
    alt, fonte = _cota("VALVULA_PE", dn_pol, "COM_CRIVO", "altura_total_mm")
    alt = alt or 330
    r = DE_TUBO.get(dn_pol, 100) / 2
    corpo = alt * 0.40
    cesto = alt - corpo
    el = caixa(0, corpo, r * 1.3, r * 1.3)
    el.append(_p(f"M{corpo*0.18:.1f} {-r*0.85:.1f} L{corpo*0.8:.1f} {r*0.25:.1f}",
                 "obturador"))
    el.append(_p(f"M{corpo*0.15:.1f} {-r*0.95:.1f} h{corpo*0.12:.1f}", "obturador"))
    el += caixa(-cesto, cesto, r * 0.95, r * 0.95)
    el += [_p(f"M{-cesto + cesto*0.15*(i+1):.1f} {-r*0.95:.1f} v{r*1.9:.1f}",
              "malha") for i in range(6)]
    el += placa(corpo, dn_pol, lado="saida")
    el.append(_p(f"M{-cesto-40:.0f} 0 H{corpo+60:.0f}", "centro"))
    portas = [Porta("saida", corpo, 0, 0, dn_pol)]
    return _montar("VALVULA_PE", f'válvula de pé {dn_pol:g}"', el, portas, fonte)


# ------------------------------------------------------------------- montagem
Posto = namedtuple("Posto", "simbolo dx dy giro entrada saida")
# a reducao chama as pontas de maior e menor; para a linha sao entrada e saida
ENTRADA = ("entrada", "maior")
SAIDA = ("saida", "menor")


def porta(simbolo, papeis):
    return next((p for p in simbolo.portas if p.papel in papeis), None)


def orientar(lista):
    """Vira as reducoes para o lado certo, olhando os vizinhos.

    Virar a porta nao basta: a peca tem que ser redesenhada espelhada, e quem
    sabe fazer isso e ela propria. Entao a reducao e refeita com crescente
    ligado ou desligado, conforme a bitola que chega e a que sai.

    Sem isso da para ligar a reducao do lado errado sem o desenho reclamar - o
    cone apontando contra o fluxo, ou a peca crescendo para tras.
    """
    saida = list(lista)
    for i, simbolo in enumerate(saida):
        if not simbolo.familia.startswith("REDUCAO") or not simbolo.params:
            continue
        antes = [p.dn_pol for p in saida[i - 1].portas
                 if p.papel in SAIDA] if i else []
        depois = [p.dn_pol for p in saida[i + 1].portas
                  if p.papel in ENTRADA] if i + 1 < len(saida) else []
        maior, menor = simbolo.params["dn_maior"], simbolo.params["dn_menor"]
        crescente = None
        if antes:
            crescente = abs(antes[0] - menor) < 0.01
        elif depois:
            crescente = abs(depois[0] - maior) < 0.01
        if crescente is None or crescente == simbolo.params["crescente"]:
            continue
        p = dict(simbolo.params, crescente=crescente)
        saida[i] = reducao(p["dn_maior"], p["dn_menor"], p["tipo"],
                           p["lado_plano"], p["crescente"])
    return saida


def montar(lista):
    """Encadeia simbolos: a saida de um vira a entrada do proximo.

    Cada peca e desenhada uma vez, na origem, olhando para +x. Encaixar e uma
    transformacao rigida - girar pelo angulo corrente e transladar ate o ponto
    corrente. Nenhuma peca tem posicao propria:

        tamanho  vem da tabela de cotas, por bitola e fabricante
        angulo   vem da peca (a curva e a unica que gira a linha)
        rotacao  e acumulada: cada peca herda a direcao que a anterior deixou

    Devolve os postos ja colocados e o ponto onde a linha termina.
    """
    lista = orientar(lista)
    x = y = 0.0
    direcao = 0.0
    postos = []
    for simbolo in lista:
        entrada = porta(simbolo, ENTRADA)
        saida = porta(simbolo, SAIDA)
        if entrada is None:                      # crivo, valvula de pe: comeca a linha
            entrada = Porta("entrada", 0, 0, 180, saida.dn_pol if saida else None)
        if saida is None:                        # flange cega: termina a linha
            saida = entrada

        rad = math.radians(direcao)
        cos, sen = math.cos(rad), math.sin(rad)
        # o ponto corrente e onde a entrada desta peca tem que cair
        dx = x - (entrada.x * cos - entrada.y * sen)
        dy = y - (entrada.x * sen + entrada.y * cos)
        postos.append(Posto(simbolo, dx, dy, direcao,
                            (x, y),
                            (dx + saida.x * cos - saida.y * sen,
                             dy + saida.x * sen + saida.y * cos)))
        x, y = postos[-1].saida
        direcao += saida.direcao if saida is not entrada else 0
    return postos, (x, y, direcao)


def encaixa(a, b):
    """A saida de a serve em alguma ponta de b? Devolve (ok, motivo)."""
    sa = porta(a, SAIDA)
    if sa is None:
        return False, "peça terminal"
    pontas = [p for p in b.portas if p.papel in ENTRADA + SAIDA]
    if not pontas:
        return False, "peça terminal"
    if any(abs((p.dn_pol or 0) - (sa.dn_pol or 0)) < 0.01 for p in pontas):
        return True, ""
    bitolas = " ou ".join(f'{p.dn_pol:g}"' for p in pontas)
    return False, f'{sa.dn_pol:g}" contra {bitolas}'


def junta_flangeada(x, y=0.0, direcao=0.0, dn_pol=8, norma="NBR PN16"):
    """Os parafusos e a junta que fecham o encontro de duas flanges.

    Nao pertencem a nenhuma das duas pecas - pertencem a juncao, do mesmo jeito
    que na lista de materiais: quem puxa junta plana, parafuso, porca e arruela
    e a junta flangeada, nao o tubo nem a curva.

    O parafuso atravessa as duas chapas e sobra para as porcas dos dois lados;
    aparece no circulo de furacao real, que e onde ele esta.
    """
    f = flange(dn_pol, norma)
    esp = f["espessura"]
    raio_furo = f["circulo"] / 2
    d = f["furo"] * 0.85                      # a haste, nao o furo
    porca = d * 1.6
    comprimento = 2 * esp + 2 * porca * 0.75
    x0 = x - esp - porca * 0.75
    el = [_p(f"M{x:.1f} {y - f['externo']/2:.1f} V{y + f['externo']/2:.1f}",
             "junta")]
    for sinal in (-1, 1):
        yy = y + sinal * raio_furo
        el.append({"tipo": "rect", "x": x0, "y": yy - d / 2, "w": comprimento,
                   "h": d, "classe": "parafuso"})
        for xn in (x0, x0 + comprimento - porca * 0.75):
            el.append({"tipo": "rect", "x": xn, "y": yy - porca / 2,
                       "w": porca * 0.75, "h": porca, "classe": "porca"})
    if direcao:
        for e in el:
            e["girar"] = (direcao, x, y)
    return el
