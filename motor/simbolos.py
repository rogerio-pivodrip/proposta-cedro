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
Simbolo = namedtuple("Simbolo", "familia rotulo elementos portas caixa fonte")

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


def placa(x, dn_pol, y=0.0, direcao=0.0, norma="NBR PN16"):
    """Flange de lado: a placa, e os furos na posicao real do circulo."""
    f = flange(dn_pol, norma)
    metade, esp = f["externo"] / 2, f["espessura"]
    x0 = x - esp / 2
    saida = [{"tipo": "rect", "x": x0, "y": y - metade, "w": esp,
              "h": f["externo"], "classe": "flange"}]
    # cada furo aparece como um traco na altura do circulo de furacao
    passo = f["circulo"] / 2
    for lado in (-1, 1):
        saida.append(_p(f"M{x0:.1f} {y+lado*passo:.1f} h{esp:.1f}", "furo"))
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
    raio = max(perna * 0.5, r * 1.15)
    recuo = min(raio * math.tan(t / 2), perna * 0.85)
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
    centro_linha = [inicio, t1] + pontos[1:-1] + [t2, fim]

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
    # a solda de cada gomo, so nas juntas do meio
    for i in range(1, len(fora) - 1):
        elementos.append(_p(f"M{fora[i][0]:.1f} {fora[i][1]:.1f} "
                            f"L{dentro[i][0]:.1f} {dentro[i][1]:.1f}", "solda"))
    return elementos, (fim[0], fim[1], -angulo * sentido)


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


def _montar(familia, rotulo, elementos, portas, fonte=None):
    return Simbolo(familia, rotulo, elementos, portas, limites(elementos), fonte)


def _cota(familia, dn, variante="", significado="face_a_face_mm", menor=None):
    return cotas.cota_com_fonte(familia, dn, variante, significado, None, menor)


# ------------------------------------------------------------------ familias
def tubo(dn_pol, comprimento_mm=1000):
    el = eixo(0, comprimento_mm, dn_pol)
    el += placa(0, dn_pol) + placa(comprimento_mm, dn_pol)
    el.append(_p(f"M-60 0 H{comprimento_mm + 60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comprimento_mm, 0, 0, dn_pol)]
    return _montar("TUBO", f'tubo {dn_pol:g}" {comprimento_mm/1000:g} m',
                   el, portas, "descricao")


def curva(dn_pol, angulo=90, sentido=1, gomos=None):
    perna, fonte = _cota("CURVA", dn_pol, str(angulo), "perna_mm")
    perna = perna or DE_TUBO.get(dn_pol, 100) * 1.5
    gomos = gomos or (4 if angulo >= 90 else 3 if angulo >= 45 else 2)
    el, (sx, sy, direcao) = giro(0, perna, angulo, dn_pol, sentido, gomos=gomos)
    el += placa(0, dn_pol)
    bocal = placa(sx, dn_pol, sy)
    for e in bocal:
        e["girar"] = (direcao, sx, sy)
    el += bocal
    rad = math.radians(direcao)
    el.append(_p(f"M-60 0 H{perna:.0f} L{sx + 60*math.cos(rad):.0f} "
                 f"{sy + 60*math.sin(rad):.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", sx, sy, direcao, dn_pol)]
    return _montar("CURVA", f'curva {angulo}° {dn_pol:g}" {gomos} gomos',
                   el, portas, fonte)


def reducao(dn_maior, dn_menor, tipo="CONCENTRICA", lado_plano="topo"):
    familia = f"REDUCAO_{tipo}"
    comp, fonte = _cota(familia, dn_maior, "", "face_a_face_mm", dn_menor)
    comp = comp or 150
    alinhamento = "centro" if tipo == "CONCENTRICA" else lado_plano
    el = cone(0, comp, dn_maior, dn_menor, alinhamento)
    el += placa(0, dn_maior)
    ra, rb = DE_TUBO.get(dn_maior, 100) / 2, DE_TUBO.get(dn_menor, 60) / 2
    desloca = 0 if alinhamento == "centro" else (ra - rb) * (1 if alinhamento == "fundo" else -1)
    el += placa(comp, dn_menor, desloca)
    el.append(_p(f"M-60 0 H{comp*0.55:.0f}", "centro"))
    el.append(_p(f"M{comp*0.45:.0f} {desloca:.0f} H{comp + 60:.0f}", "centro"))
    portas = [Porta("maior", 0, 0, 180, dn_maior),
              Porta("menor", comp, desloca, 0, dn_menor)]
    rot = f'redução {"conc" if tipo == "CONCENTRICA" else "exc"} {dn_maior:g}"×{dn_menor:g}"'
    return _montar(familia, rot, el, portas, fonte)


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
    el += placa(0, dn_pol) + placa(comp, dn_pol)
    bocal = placa(meio, dn_derivacao, -alt)
    for e in bocal:
        e["girar"] = (-90, meio, -alt)
    el += bocal
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    el.append(_p(f"M{meio:.0f} 40 V{-alt-60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol),
              Porta("derivacao", meio, -alt, -90, dn_derivacao)]
    return _montar("TE", f'tê {dn_pol:g}"×{dn_derivacao:g}"', el, portas, fonte)


def crivo(dn_pol, variante="cesto"):
    comp, fonte = _cota("CRIVO", dn_pol, variante, "comprimento_mm")
    comp = comp or 300
    r = DE_TUBO.get(dn_pol, 100) / 2
    if variante == "cone":
        el = [_p(f"M{comp:.1f} {-r:.1f} L0 0 L{comp:.1f} {r:.1f}")]
        malha = [_p(f"M{comp*(0.25+0.2*i):.1f} {-r*(0.3+0.22*i):.1f} "
                    f"V{r*(0.3+0.22*i):.1f}", "malha") for i in range(4)]
    else:
        el = [_p(f"M0 {-r:.1f} H{comp:.1f} V{r:.1f} H0 Z")]
        malha = [_p(f"M{comp*(0.12+0.12*i):.1f} {-r:.1f} V{r:.1f}", "malha")
                 for i in range(7)]
    el += malha + placa(comp, dn_pol)
    el.append(_p(f"M-40 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("CRIVO", f'crivo {variante} {dn_pol:g}"', el, portas, fonte)


def flange_cega(dn_pol):
    """Fecha a linha: a placa cega e o toco de tubo que morre nela."""
    f = flange(dn_pol)
    toco = f["externo"] * 0.5
    el = eixo(-toco, toco, dn_pol) + placa(0, dn_pol)
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
    comp, fonte = _cota("VALVULA_BORBOLETA", dn_pol, acionamento)
    comp = comp or 60
    acima, _ = _cota("VALVULA_BORBOLETA", dn_pol, acionamento, "altura_acima_mm")
    acima = acima or DE_TUBO.get(dn_pol, 100)
    alcance, _ = _cota("VALVULA_BORBOLETA", dn_pol, acionamento,
                       "alcance_acionamento_mm")
    alcance = alcance or 200
    r = DE_TUBO.get(dn_pol, 100) / 2
    meio = comp / 2
    el = caixa(0, comp, r * 1.15, r * 1.15)
    # disco na diagonal: a borboleta fechada aparece assim na vista lateral
    el.append(_p(f"M{meio - comp*0.32:.1f} {r*0.95:.1f} "
                 f"L{meio + comp*0.32:.1f} {-r*0.95:.1f}", "obturador"))
    topo = -r * 1.15
    el.append(_p(f"M{meio:.1f} {topo:.1f} V{-acima + comp*0.6:.1f}", "haste"))
    if acionamento == "ALAVANCA":
        yl = -acima + comp * 0.6
        el += caixa(meio - comp*0.55, comp*1.1, -yl + comp*0.55, yl + comp*0.55,
                    classe="acionamento")
        el.append(_p(f"M{meio:.1f} {yl:.1f} h{alcance:.1f}", "acionamento"))
        el.append(_p(f"M{meio:.1f} {yl:.1f} l{alcance*0.71:.1f} {-alcance*0.71:.1f}",
                     "acionamento fantasma"))
    else:
        yc = -acima + comp * 0.6
        el += caixa(meio - comp*0.8, comp*1.6, -yc, yc + comp*1.1,
                    classe="acionamento")
        # volante lateral, visto de perfil: um traco do diametro real
        eixo_x = meio + comp * 1.5
        el.append(_p(f"M{meio + comp*0.8:.1f} {yc + comp*0.4:.1f} "
                     f"H{eixo_x:.1f}", "acionamento"))
        el.append(_p(f"M{eixo_x:.1f} {yc + comp*0.4 - alcance/2:.1f} "
                     f"v{alcance:.1f}", "acionamento"))
        el.append(_p(f"M{eixo_x - comp*0.25:.1f} {yc + comp*0.4 - alcance/2:.1f} "
                     f"h{comp*0.5:.1f} M{eixo_x - comp*0.25:.1f} "
                     f"{yc + comp*0.4 + alcance/2:.1f} h{comp*0.5:.1f}",
                     "acionamento fantasma"))
    el += placa(0, dn_pol) + placa(comp, dn_pol)
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    rot = f'borboleta {dn_pol:g}" {"alavanca" if acionamento == "ALAVANCA" else "caixa"}'
    return _montar("VALVULA_BORBOLETA", rot, el, portas, fonte)


def valvula_gaveta(dn_pol):
    comp, fonte = _cota("VALVULA_GAVETA", dn_pol)
    comp = comp or 230
    alt, _ = _cota("VALVULA_GAVETA", dn_pol, "", "altura_total_mm")
    volante, _ = _cota("VALVULA_GAVETA", dn_pol, "", "volante_mm")
    r = DE_TUBO.get(dn_pol, 100) / 2
    alt = alt or r * 3
    volante = volante or r * 2
    meio = comp / 2
    el = caixa(0, comp, r * 1.25, r * 1.25)
    el += caixa(meio - comp*0.24, comp*0.48, alt*0.52, -r*1.25, classe="corpo")
    # cunha dentro do corpo, e a haste ate o volante
    el.append(_p(f"M{meio - r*0.5:.1f} {r*1.0:.1f} v{-r*1.5:.1f} "
                 f"h{r:.1f} v{r*1.5:.1f} Z", "obturador"))
    el.append(_p(f"M{meio:.1f} {-alt*0.52:.1f} V{-alt + comp*0.05:.1f}", "haste"))
    # o volante e horizontal: de lado ele e um traco do diametro real
    yv = -alt + comp * 0.05
    el.append(_p(f"M{meio - volante/2:.1f} {yv:.1f} h{volante:.1f}", "acionamento"))
    el.append(_p(f"M{meio - volante/2:.1f} {yv - comp*0.06:.1f} v{comp*0.12:.1f} "
                 f"M{meio + volante/2:.1f} {yv - comp*0.06:.1f} v{comp*0.12:.1f}",
                 "acionamento"))
    el += placa(0, dn_pol) + placa(comp, dn_pol)
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("VALVULA_GAVETA", f'gaveta {dn_pol:g}"', el, portas, fonte)


def valvula_hidraulica(dn_pol, serie="47"):
    comp, fonte = _cota("VALVULA_HIDRAULICA", dn_pol, serie)
    comp = comp or 462
    alt, _ = _cota("VALVULA_HIDRAULICA", dn_pol, serie, "altura_total_mm")
    r = DE_TUBO.get(dn_pol, 100) / 2
    alt = alt or r * 3
    el = caixa(0, comp, r * 1.1, r * 1.1)
    meio = comp / 2
    # castelo com diafragma, e o piloto do lado
    el += caixa(meio - comp*0.26, comp*0.52, alt*0.72, -r*1.1)
    el.append(_p(f"M{meio - comp*0.26:.1f} {-alt*0.42:.1f} h{comp*0.52:.1f}",
                 "obturador"))
    el.append(_p(f"M{meio:.1f} {-alt*0.45:.1f} V{r*0.4:.1f}", "haste"))
    el.append(_p(f"M{meio - r*0.5:.1f} {r*0.4:.1f} h{r:.1f}", "obturador"))
    # o piloto e o tubinho que o liga ao castelo - sempre listado junto
    el.append(_p(f"M{meio + comp*0.26:.1f} {-alt*0.58:.1f} h{comp*0.3:.1f} "
                 f"v{alt*0.26:.1f} h{-comp*0.1:.1f}", "piloto"))
    el.append({"tipo": "circulo", "cx": meio + comp*0.56, "cy": -alt*0.46,
               "r": comp*0.06, "classe": "piloto"})
    el += placa(0, dn_pol) + placa(comp, dn_pol)
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("VALVULA_HIDRAULICA", f'hidráulica {serie}-{dn_pol:g}"',
                   el, portas, fonte)


def medidor(dn_pol):
    comp, fonte = _cota("MEDIDOR", dn_pol)
    comp = comp or 350
    alt, _ = _cota("MEDIDOR", dn_pol, "", "altura_total_mm")
    baixo, _ = _cota("MEDIDOR", dn_pol, "", "altura_abaixo_mm")
    r = DE_TUBO.get(dn_pol, 100) / 2
    baixo = baixo or r
    alt = alt or r * 3
    el = caixa(0, comp, r, r)
    meio = comp / 2
    el += caixa(meio - comp*0.28, comp*0.56, alt - baixo, -r)
    el.append({"tipo": "circulo", "cx": meio, "cy": -(alt - baixo) + comp*0.16,
               "r": comp*0.15, "classe": "mostrador"})
    el.append(_p(f"M{meio:.1f} {-(alt-baixo)+comp*0.16:.1f} v{-comp*0.11:.1f}",
                 "mostrador"))
    el += placa(0, dn_pol) + placa(comp, dn_pol)
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("MEDIDOR", f'medidor {dn_pol:g}"', el, portas, fonte)


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
    el += placa(corpo, dn_pol)
    el.append(_p(f"M{-cesto-40:.0f} 0 H{corpo+60:.0f}", "centro"))
    portas = [Porta("saida", corpo, 0, 0, dn_pol)]
    return _montar("VALVULA_PE", f'válvula de pé {dn_pol:g}"', el, portas, fonte)
