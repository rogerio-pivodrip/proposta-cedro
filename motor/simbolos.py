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
import re
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
    ficha.setdefault("ressalto", ficha["externo"] * 0.78)
    folha = flange_netafim(dn_pol)
    if folha:
        # a folha do caderno tem duas cotas que a tabela de furacao nao tem:
        # o ressalto, que e onde a junta assenta, e a espessura da chapa
        ficha["ressalto"] = folha["d_ressalto_mm"]
        ficha["espessura"] = folha["esp_mm"]
    return ficha


_netafim = None


def flange_netafim(dn_pol, tipo="SOLDAR"):
    """A folha de flange do caderno Netafim - paginas 4 e 6.

    Vale a pena ler alem da furacao: a folha traz o ressalto (o diametro onde
    a junta assenta), a espessura real da chapa e, na flange cega, a luva de
    2" BSP por onde entra a ventosa.

    A furacao dessa folha nao e a NBR da tabela da casa a partir de 10": o
    caderno desenha 355 / 410 / 470 de circulo, que e EN PN16, contra
    350 / 400 / 460 da NBR - ver tools/conferir_flanges_netafim.py.
    """
    global _netafim
    if _netafim is None:
        _netafim = {}
        with open(f"{DADOS}/flanges_netafim.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                linha = {k: (float(v) if v and k.endswith("_mm") else v)
                         for k, v in r.items()}
                linha["furos"] = int(r["furos"])
                _netafim[(r["tipo"], float(r["dn_pol"]))] = linha
    return _netafim.get((tipo, float(dn_pol)))


# A luva roscada de ventosa e sempre a mesma peca: 2" BSP femea, 30 mm de
# comprimento por 40 mm de externo. Aparece com essas medidas nas duas folhas
# onde o caderno a desenha - a flange cega (pagina 4) e o manifold (pagina 25).
LUVA_BSP = {"dn_pol": 2, "comprimento_mm": 30.0, "externo_mm": 40.0}


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
    """Curva de gomos: N chapas retas soldadas, com N-1 dobras.

    Cada gomo e um cilindro reto - nada de arco. As direcoes sao 0, um passo,
    dois passos, ate o angulo cheio, entao um gomo vira sempre o mesmo tanto.
    O primeiro gomo sai na direcao da entrada e o ultimo chega na direcao da
    saida, que e por isso que a flange encosta perpendicular nas duas pontas.

    A dobra fica onde as retas de dois gomos vizinhos se cruzam - e a mesma
    construcao do serralheiro: duas chapas cortadas no meio do angulo.
    """
    r = DE_TUBO.get(dn_pol, 100) / 2
    n = max(int(gomos), 2)
    total = math.radians(angulo)
    passo = total / (n - 1)
    meia = math.tan(passo / 2)

    # raio de dobra: o toco reto na flange fica curto, o gomo domina a perna
    raio = perna * 0.88 / math.tan(total / 2)
    vx, vy = x + perna, y
    centro = (vx - raio * math.tan(total / 2), vy - raio * sentido)

    def direcao(k):
        a = -k * passo * sentido
        return math.cos(a), math.sin(a)

    dobras = []
    for k in range(n - 1):
        a = k * passo * sentido
        tangente = (centro[0] + raio * math.sin(a) * sentido,
                    centro[1] + raio * math.cos(a) * sentido)
        dx, dy = direcao(k)
        dobras.append((tangente[0] + raio * meia * dx,
                       tangente[1] + raio * meia * dy))

    dsx, dsy = direcao(n - 1)
    fim = (vx + perna * dsx, vy + perna * dsy)
    centro_linha = [(x, y)] + dobras + [fim]

    def normal(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        c = math.hypot(dx, dy) or 1
        return (-dy / c, dx / c)

    def parede(lado):
        # cada gomo deslocado de meio diametro; a dobra e o encontro das duas
        # retas vizinhas, nao a media - senao a parede estrangula na dobra
        retas = []
        for i in range(len(centro_linha) - 1):
            a, b = centro_linha[i], centro_linha[i + 1]
            nx, ny = normal(a, b)
            retas.append(((a[0] + nx * r * lado, a[1] + ny * r * lado),
                          (b[0] + nx * r * lado, b[1] + ny * r * lado)))
        pontos = [retas[0][0]]
        for i in range(len(retas) - 1):
            pontos.append(_cruzamento(retas[i], retas[i + 1]) or retas[i][1])
        pontos.append(retas[-1][1])
        return pontos

    fora, dentro = parede(1 * sentido), parede(-1 * sentido)
    caminho = lambda pts: "M" + " L".join(f"{p[0]:.1f} {p[1]:.1f}" for p in pts)
    elementos = [_p(caminho(fora)), _p(caminho(dentro))]
    for i in range(1, len(fora) - 1):
        elementos.append(_p(f"M{fora[i][0]:.1f} {fora[i][1]:.1f} "
                            f"L{dentro[i][0]:.1f} {dentro[i][1]:.1f}", "solda"))
    return (elementos, (fim[0], fim[1], -angulo * sentido), (centro, raio),
            centro_linha, (fora, dentro))


def _atravessa(polilinha, alvo):
    """Onde a polilinha cruza a horizontal y=alvo, indo para frente."""
    for i in range(len(polilinha) - 1):
        (ax, ay), (bx, by) = polilinha[i], polilinha[i + 1]
        if (ay - alvo) * (by - alvo) <= 0 and abs(by - ay) > 1e-9:
            t = (alvo - ay) / (by - ay)
            return ax + t * (bx - ax)
    return None


def _cruzamento(r1, r2):
    (x1, y1), (x2, y2) = r1
    (x3, y3), (x4, y4) = r2
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-9:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


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


RX_TOKEN = re.compile(r"([A-Za-z])|(-?\d+(?:\.\d+)?)")


def _bezier2(p0, p1, p2, passos=10):
    """A quadratica amostrada, sem o ponto de partida."""
    return [tuple((1 - k / passos) ** 2 * p0[j]
                  + 2 * (1 - k / passos) * (k / passos) * p1[j]
                  + (k / passos) ** 2 * p2[j] for j in (0, 1))
            for k in range(1, passos + 1)]


def _bezier3(p0, p1, p2, p3, passos=12):
    """A cubica amostrada, sem o ponto de partida."""
    saida = []
    for k in range(1, passos + 1):
        u = k / passos
        v = 1 - u
        saida.append(tuple(v**3 * p0[j] + 3 * v * v * u * p1[j]
                           + 3 * v * u * u * p2[j] + u**3 * p3[j]
                           for j in (0, 1)))
    return saida


def pontos_do_path(d):
    """Le o path do simbolo e devolve as polilinhas em coordenada absoluta.

    O desenho usa um subconjunto pequeno de SVG - M, L, H, V, os relativos e
    Z. Ter um parser de verdade aqui importa por dois motivos: e ele que da a
    caixa certa da peca, e e ele que o exportador de DXF usa. Antes disso a
    caixa saia de zipar os numeros do path em pares x,y, o que erra em toda
    peca que usa H ou V - e quase toda peca usa.

    Curva de Bezier e AMOSTRADA, nao reduzida a reta ate o ponto final. Foi
    esse atalho que fez a valvula hidraulica sair 26% mais baixa do que a
    folha cota: a barriga dela e uma quadratica, e como a caixa lia so as
    pontas, a barriga nao existia para o medidor de altura. O ponto de
    controle tambem nao serve - ele fica bem fora da curva, e usa-lo daria
    barriga de sobra em vez de barriga de menos.
    """
    itens = [(a or b) for a, b in RX_TOKEN.findall(d)]
    linhas, atual = [], []
    x = y = 0.0
    i, comando = 0, "M"
    while i < len(itens):
        if itens[i].isalpha():
            comando = itens[i]
            i += 1
            continue
        n = lambda k: float(itens[i + k])
        if comando in "Mm":
            x, y = ((n(0), n(1)) if comando == "M" else (x + n(0), y + n(1)))
            if len(atual) > 1:
                linhas.append(atual)
            atual = [(x, y)]
            i += 2
            comando = "L" if comando == "M" else "l"
            continue
        if comando in "Ll":
            x, y = ((n(0), n(1)) if comando == "L" else (x + n(0), y + n(1)))
            i += 2
        elif comando in "Hh":
            x = n(0) if comando == "H" else x + n(0)
            i += 1
        elif comando in "Vv":
            y = n(0) if comando == "V" else y + n(0)
            i += 1
        elif comando in "Qq":
            cx, cy = (n(0), n(1)) if comando == "Q" else (x + n(0), y + n(1))
            fx, fy = (n(2), n(3)) if comando == "Q" else (x + n(2), y + n(3))
            atual += _bezier2((x, y), (cx, cy), (fx, fy))
            x, y = fx, fy
            i += 4
        elif comando in "Tt":
            x, y = ((n(0), n(1)) if comando == "T" else (x + n(0), y + n(1)))
            i += 2
        elif comando in "Cc":
            c1 = (n(0), n(1)) if comando == "C" else (x + n(0), y + n(1))
            c2 = (n(2), n(3)) if comando == "C" else (x + n(2), y + n(3))
            fx, fy = (n(4), n(5)) if comando == "C" else (x + n(4), y + n(5))
            atual += _bezier3((x, y), c1, c2, (fx, fy))
            x, y = fx, fy
            i += 6
        else:
            i += 1
            continue
        atual.append((x, y))
    if len(atual) > 1:
        linhas.append(atual)
    return linhas


def _rodar(x, y, angulo, cx=0.0, cy=0.0):
    """Gira um ponto como o rotate() do SVG - horario, porque o y cresce para
    baixo."""
    a = math.radians(angulo)
    dx, dy = x - cx, y - cy
    return (cx + dx * math.cos(a) - dy * math.sin(a),
            cy + dx * math.sin(a) + dy * math.cos(a))


def meio_do_eixo(simbolo):
    """O ponto no MEIO do eixo da peca, medido pelo comprimento dele.

    Na peca reta isso e o meio dela e nada muda. Na curva muda tudo: o meio
    entre as duas portas cai na corda, fora do tubo, e a cota ia parar no ar ao
    lado da peca. O meio do eixo cai no meio da curva, dentro dela.

    O primeiro eixo e o que vale - no te o segundo e o da derivacao.
    """
    eixo = next((e for e in simbolo.elementos
                 if e.get("classe") == "centro" and e["tipo"] == "path"), None)
    if eixo is None:
        return None
    pontos = [p for linha in pontos_do_path(eixo["d"]) for p in linha]
    girar = eixo.get("girar")
    if girar:
        pontos = [_rodar(x, y, girar[0], girar[1], girar[2])
                  for x, y in pontos]
    if eixo.get("girar_fora"):
        pontos = [_rodar(x, y, eixo["girar_fora"]) for x, y in pontos]
    if len(pontos) < 2:
        return pontos[0] if pontos else None
    passos = [math.dist(a, b) for a, b in zip(pontos, pontos[1:])]
    metade = sum(passos) / 2
    andado = 0.0
    for (a, b), passo in zip(zip(pontos, pontos[1:]), passos):
        if andado + passo >= metade and passo:
            fracao = (metade - andado) / passo
            return (a[0] + (b[0] - a[0]) * fracao,
                    a[1] + (b[1] - a[1]) * fracao)
        andado += passo
    return pontos[-1]


def posicao_da_nota(nota):
    """Onde a nota cai DEPOIS do giro da peca.

    A nota e anotacao: sai em pixel fixo, fora da escala, e por isso nao passa
    pelo transform que gira a geometria. Quem desenha tem de girar o ponto na
    mao - sem isso, a nota de uma peca posada de pe vai para outro lugar da
    celula, e foi assim que o DN da curva apareceu fora da peca.
    """
    x, y = nota["x"], nota["y"]
    girar = nota.get("girar")
    if girar:
        x, y = _rodar(x, y, girar[0], girar[1], girar[2])
    fora = nota.get("girar_fora")
    if fora:
        x, y = _rodar(x, y, fora)
    return x, y


def limites(elementos):
    """Retangulo que contem tudo, em mm - ja com o que esta girado no lugar."""
    xs, ys = [], []
    for e in elementos:
        pontos = []
        if e["tipo"] == "rect":
            pontos = [(e["x"], e["y"]), (e["x"] + e["w"], e["y"]),
                      (e["x"], e["y"] + e["h"]),
                      (e["x"] + e["w"], e["y"] + e["h"])]
        elif e["tipo"] == "path":
            pontos = [p for linha in pontos_do_path(e["d"]) for p in linha]
        elif e["tipo"] == "circulo":
            pontos = [(e["cx"] - e["r"], e["cy"] - e["r"]),
                      (e["cx"] + e["r"], e["cy"] + e["r"])]
        for ang_graus, cx, cy in ([e["girar"]] if e.get("girar") else []) + \
                ([(e["girar_fora"], 0.0, 0.0)] if e.get("girar_fora") else []):
            ang = math.radians(ang_graus)
            cos, sen = math.cos(ang), math.sin(ang)
            pontos = [(cx + (px - cx) * cos - (py - cy) * sen,
                       cy + (px - cx) * sen + (py - cy) * cos)
                      for px, py in pontos]
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
    el, (sx, sy, direcao), _, eixo_linha, _paredes = giro(
        0, perna, angulo, dn_pol, sentido, gomos=gomos)
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
    # o eixo liga o centro de uma flange ao centro da outra: na excentrica ele
    # sai inclinado, e e essa inclinacao que mostra o desalinhamento das bocas
    inclina = desloca / comp if comp else 0
    el.append(_p(f"M-60 {-60 * inclina:.1f} L{comp + 60:.1f} "
                 f"{desloca + 60 * inclina:.1f}", "centro"))
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


_crivos = None


def ficha_crivo(dn_pol):
    """A folha do crivo - pagina 14 do caderno."""
    global _crivos
    if _crivos is None:
        with open(f"{DADOS}/crivos_netafim.csv", encoding="utf-8") as fh:
            _crivos = {float(r["dn_pol"]): r for r in csv.DictReader(fh)}
    return _crivos.get(float(dn_pol))


def chapa_perfurada(x0, x1, meia_altura, ficha=None, limite=2600):
    """Os furos da chapa perfurada, em quincuncio - o mesmo gerador para o
    crivo AZ e para o cesto da valvula de pe.

    E a mesma chapa na obra, entao tem de ser a mesma no desenho: a casa viu os
    dois lado a lado na folha e o furo de um estava no dobro do outro. Sair de
    uma funcao so e o que garante que nao volte a divergir.

    A furacao vai desenhada em DOBRO, furo e passo juntos, para a proporcao
    entre chapa e vazio nao mudar - o furo de 6 mm no tamanho real e um ponto.
    Devolve (furos, furo_real, passo_real) para quem chama escrever a nota.
    """
    ficha = ficha or {}
    margem = float(ficha.get("margem_mm") or 10.0)
    passo_livre = float(ficha.get("passo_mm") or 3.0)
    furo = float(ficha.get("furo_mm") or 6.0)
    amplia = 2.0
    furo_visto = furo * amplia
    passo_visto = (furo + passo_livre) * amplia

    colunas = int((x1 - x0) / passo_visto)
    fileiras = int((2 * meia_altura - 2 * margem) / passo_visto)
    mostradas = min(colunas, max(1, limite // max(fileiras, 1)))
    furos = []
    for i in range(mostradas):
        x = x0 + furo_visto / 2 + passo_visto * i
        for j in range(fileiras):
            y = (-meia_altura + margem + furo_visto / 2 + passo_visto * j
                 + (passo_visto / 2 if i % 2 else 0))
            if abs(y) < meia_altura - margem:
                furos.append({"tipo": "circulo", "cx": x, "cy": y,
                              "r": furo_visto / 2, "classe": "malha"})
    return furos, furo, passo_livre


def crivo(dn_pol, variante=""):
    """Cesto de chapa perfurada: furo de 6 mm a cada 3, fundo fechado.

    A folha do caderno (pagina 14) cota tudo o que o desenho precisa - o
    comprimento por bitola, a parede da chapa, a margem lisa de 10 mm antes do
    primeiro furo e o passo de 3 mm entre furos. O fundo e CHAPA LISA: a agua
    entra so pela parede, e e isso que separa o crivo de um tubo aberto.

    A furacao vai desenhada em DOBRO - furo e passo juntos, para a proporcao
    entre chapa e vazio nao mudar. No tamanho real o furo de 6 mm num cesto de
    368 e um ponto, e a casa pediu para se ver o que e. A cota nao vai escrita
    no desenho: ela mora na folha (data/crivos_netafim.csv), e quem precisa
    dela pede pela ficha.
    """
    ficha = ficha_crivo(dn_pol) or {}
    comp, fonte = _cota("CRIVO", dn_pol, variante, "comprimento_mm")
    comp = float(ficha.get("comprimento_mm") or comp or 300)
    fonte = "netafim" if ficha else fonte
    de = float(ficha.get("d_externo_mm") or DE_TUBO.get(dn_pol, 100))
    parede = float(ficha.get("parede_mm") or 2.0)
    margem = float(ficha.get("margem_mm") or 10.0)
    passo_livre = float(ficha.get("passo_mm") or 3.0)
    furo = float(ficha.get("furo_mm") or 6.0)
    passo = furo + passo_livre
    r = de / 2
    # A furacao vai desenhada em DOBRO, furo e passo juntos. O furo de 6 mm num
    # cesto de 368 e um ponto - a casa pediu o dobro para se ver o que e. A cota
    # de verdade continua escrita na nota, e dobrar o passo com o furo mantem a
    # proporcao entre chapa e vazio, que e o que o desenho comunica.
    amplia = 2.0
    furo_visto = furo * amplia
    passo_visto = passo * amplia

    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"), _p(f"M0 {r:.1f} H{comp:.1f}"),
          _p(f"M0 {-r+parede:.1f} H{comp:.1f}", "malha"),
          _p(f"M0 {r-parede:.1f} H{comp:.1f}", "malha"),
          # o fundo: chapa lisa fechando o cesto, com a espessura da folha
          {"tipo": "rect", "x": 0, "y": -r, "w": parede * 2, "h": 2 * r,
           "classe": "chapa_lisa"}]

    # a malha, em quincuncio, comecando depois da margem lisa e parando perto
    # da flange - o gerador e o mesmo da valvula de pe
    inicio = margem + parede * 2
    fim = comp - margem
    el += chapa_perfurada(inicio, fim, r, ficha)[0]
    # A cota da furacao NAO vai escrita no desenho: a casa tirou. Ela continua
    # onde sempre esteve - em data/crivos_netafim.csv, que e a folha - e quem
    # precisa dela pede pela ficha, nao le do desenho.

    el += placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-40 0 H{comp+60:.0f}", "centro"))
    portas = [Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("CRIVO", f'crivo {dn_pol:g}"', el, portas, fonte,
                   {"fundo": "CHAPA_LISA", "furo_mm": furo})


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


def luva(x, y=0.0, direcao=0.0, dn_pol=2, comprimento=None, externo=None):
    """A luva roscada que recebe a ventosa - 2" BSP femea, 30 x 40.

    Sai da parede da peca e nao do eixo: e um toco soldado num furo. Por isso
    o desenho e sempre o mesmo, mude o corpo em que ela esta cravada.
    """
    comprimento = comprimento or LUVA_BSP["comprimento_mm"]
    externo = externo or LUVA_BSP["externo_mm"]
    r = externo / 2
    furo = r - 3.5                      # a parede da luva, para a rosca aparecer
    el = [{"tipo": "rect", "x": x, "y": y - r, "w": comprimento, "h": externo,
           "classe": "corpo"},
          _p(f"M{x:.1f} {y-furo:.1f} H{x+comprimento:.1f}", "malha"),
          _p(f"M{x:.1f} {y+furo:.1f} H{x+comprimento:.1f}", "malha")]
    if direcao:
        for e in el:
            e["girar"] = (direcao, x, y)
    return el


def flange_cega(dn_pol, saida_pol=None, saida_tipo="LUVA"):
    """Fecha a linha. Tres versoes, e o catalogo tem as tres:

        sem luva     FL CEGA AZ 3" NBR PN16
        com luva     FL CEGA AZ 12" NBR PN16 C/ LG 2"    -> ventosa, manometro
        com flange   FL CEGA AZ 20" NBR PN16 C/ FL 3"    -> derivacao pequena

    Nao tem toco de tubo: e o anel de flange com a chapa fechando o meio, e a
    propria face flangeada e a ligacao. A chapa vai hachurada porque em corte
    e material macico - e o que separa no papel uma cega de uma flange comum.
    """
    f = flange(dn_pol)
    esp = f["espessura"]
    meia = f["ressalto"] / 2
    el = list(placa(0, dn_pol, lado="entrada"))
    el.append({"tipo": "rect", "x": 0, "y": -meia, "w": esp, "h": f["ressalto"],
               "classe": "chapa_lisa"})
    for i in range(1, 7):
        yy = -meia + f["ressalto"] * i / 7
        el.append(_p(f"M0 {yy:.1f} l{esp:.1f} {-esp:.1f}", "malha"))
    rotulo = f'flange cega {dn_pol:g}"'
    fim = esp
    if saida_pol and saida_tipo == "LUVA":
        el += luva(esp, 0, 0, saida_pol)
        fim = esp + LUVA_BSP["comprimento_mm"]
        rotulo += f' c/ luva {saida_pol:g}"'
    elif saida_pol:
        el += eixo(esp, 100, saida_pol) + placa(esp + 100, saida_pol,
                                                lado="saida")
        fim = esp + 100
        rotulo += f' c/ flange {saida_pol:g}"'
    el.append(_p(f"M-60 0 H{fim + 40:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol)]
    if saida_pol and saida_tipo != "LUVA":
        portas.append(Porta("derivacao", fim, 0, 0, saida_pol))
    return _montar("FLANGE_CEGA", rotulo, el, portas, "netafim",
                   {"saida_pol": saida_pol, "saida_tipo": saida_tipo})


def flange_avulsa(dn_pol, tipo="SOLDAR"):
    """A flange sozinha, como peca de lista.

    SOLDAR  solda na ponta do tubo de aco - o furo central e o diametro do
            tubo, entao ela encosta e o cordao fecha.
    SOLTA   e a mesma chapa entrando no tubo de PEAD: nao solda em nada, corre
            livre pelo tubo ate travar no ressalto do colar. Por isso o furo
            central e maior que o tubo.
    """
    folha = flange_netafim(dn_pol) or {}
    f = flange(dn_pol)
    esp = f["espessura"]
    bore = folha.get("d_furo_central_mm") or DE_TUBO.get(dn_pol, 100) + 2
    if tipo == "SOLTA":
        bore += 4                       # folga para correr no tubo
    el = [{"tipo": "rect", "x": 0, "y": -f["externo"] / 2, "w": esp,
           "h": f["externo"], "classe": "flange"}]
    for sinal in (-1, 1):
        el.append(_p(f"M0 {sinal*bore/2:.1f} h{esp:.1f}", "malha"))
        el.append(_p(f"M0 {sinal*f['circulo']/2:.1f} h{esp:.1f}", "furo"))
    el.append({"tipo": "texto_furos", "x": 0, "y": 0, "n": f["furos"],
               "furo": f["furo"]})
    if tipo == "SOLTA":
        # o tubo atravessando: e por ele que ela corre ate travar no ressalto
        rt = bore / 2 - 2
        for sinal in (-1, 1):
            el.append(_p(f"M-70 {sinal*rt:.1f} H{esp+70:.1f}", "malha"))
    el.append(_p(f"M-40 0 H{esp+40:.0f}", "centro"))
    nome = "flange" if tipo == "SOLDAR" else "flange solta"
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", esp, 0, 0, dn_pol)]
    return _montar("FLANGE", f'{nome} {dn_pol:g}"', el, portas, "netafim",
                   {"tipo": tipo})


# ------------------------------------------------- PVC, Plasson e PEAD
# No PVC e no PEAD o DN E o diametro externo. A cota dessas familias nao esta
# em folha de fabricante nenhuma: esta medida no DXF da casa, e entra por
# cotas.cota_da_casa - ver tools/cotas_da_casa.py.
#
# O traco segue o bloco da casa, e ele ensina tres coisas que eu nao teria
# inventado:
#
#   curva de PVC e ARCO LISO, nao gomos. Gomo e de chapa soldada; peca
#   injetada e lisa, com o canto de dentro arredondado.
#
#   bolsa e uma CINTA na ponta - uma faixa curta um pouco mais gorda que o
#   corpo. E a assinatura visual da peca de bolsa, do mesmo jeito que a
#   flange e a da peca de aco.
#
#   cada ponta leva o SEU DN escrito. Na luva de reducao a casa escreve 100
#   embaixo e 50 em cima, e e isso que diz de que lado a peca entra.


def _pvc_em_polegada(dn_mm):
    """A equivalencia que a casa pratica, para a porta poder conversar com a
    linha de aco. Fora da tabela, devolve None e a porta so casa por mm."""
    from .bomba import MM_PARA_POLEGADA
    if dn_mm in PEAD_POL:
        return PEAD_POL[dn_mm]
    return MM_PARA_POLEGADA.get(dn_mm)


def _cota_casa(familia, dn_mm, variante, significado, dn_menor=None):
    return cotas.cota_da_casa(familia, dn_mm, variante, significado, dn_menor)


def arco(cx, cy, raio, a0, a1, passos=14):
    """Pontos de um arco, em grau. O desenho nao usa o A do SVG: o parser de
    path do motor le reta, e reta amostrada e o que o DXF da casa tambem tem."""
    return [(cx + raio * math.cos(math.radians(a0 + (a1 - a0) * k / passos)),
             cy + raio * math.sin(math.radians(a0 + (a1 - a0) * k / passos)))
            for k in range(passos + 1)]


def _polilinha(pontos, classe="corpo"):
    d = f"M{pontos[0][0]:.1f} {pontos[0][1]:.1f} " + " ".join(
        f"L{x:.1f} {y:.1f}" for x, y in pontos[1:])
    return _p(d, classe)


CINTA = 1.05      # a bolsa e ~5% mais gorda que o corpo da peca


def bolsa(x, dn_mm, externo, lado="entrada", classe="corpo"):
    """A cinta da bolsa na ponta da peca - a assinatura da peca de encaixe.

    externo e o diametro da CINTA, nao do corpo: a cinta e o ponto mais gordo
    da peca, e e nela que a trena da casa encosta. Quem chama desenha o corpo
    em externo/CINTA.
    """
    largura = max(externo * 0.09, 6.0)
    lip = externo / 2
    x0 = x if lado == "entrada" else x - largura
    return [{"tipo": "rect", "x": x0, "y": -lip, "w": largura, "h": 2 * lip,
             "classe": classe},
            # o encosto interno da bolsa: onde o tubo para
            _p(f"M{x0 + largura if lado == 'entrada' else x0:.1f} "
               f"{-dn_mm/2:.1f} V{dn_mm/2:.1f}", "malha")]


def _cantos_de_cinta(x, y, direcao_rad, externo, largura):
    """Os quatro cantos da cinta. Sai separado do desenho porque a curva
    precisa deles antes de desenhar: e a cinta que fecha o envelope que a casa
    mede, e a perna e resolvida contra essa medida."""
    lip = externo / 2
    ux, uy = math.cos(direcao_rad), math.sin(direcao_rad)
    nx, ny = -uy, ux
    a = (x + nx * lip, y + ny * lip)
    b = (x - nx * lip, y - ny * lip)
    return [a, b, (b[0] + ux * largura, b[1] + uy * largura),
            (a[0] + ux * largura, a[1] + uy * largura)]


def _cinta(x, y, direcao_rad, dn_mm, externo, classe="corpo"):
    """A mesma banda da bolsa(), em poligono para poder girar.

    A bolsa() desenha um rect e so serve para a ponta horizontal; a saida da
    curva aponta para qualquer angulo, e ai a cinta tem de girar com ela.
    direcao_rad aponta para DENTRO da peca.
    """
    largura = max(externo * 0.09, 6.0)
    cantos = _cantos_de_cinta(x, y, direcao_rad, externo, largura)
    ux, uy = math.cos(direcao_rad), math.sin(direcao_rad)
    nx, ny = -uy, ux
    fx, fy = x + ux * largura, y + uy * largura
    return [_polilinha(cantos + [cantos[0]], classe),
            # o encosto interno: onde o tubo para dentro da bolsa
            _polilinha([(fx + nx * dn_mm / 2, fy + ny * dn_mm / 2),
                        (fx - nx * dn_mm / 2, fy - ny * dn_mm / 2)], "malha")]


def _dn_nas_pontas(portas, dn_por_porta, recuo, desvio):
    """Uma nota com o DN em cada ponta - a casa escreve os dois.

    A nota anda para DENTRO da peca na direcao da porta, nao em x: na curva a
    ponta de saida aponta para cima, e um recuo em x cairia fora da peca.

    recuo e desvio vem de quem chama e em milimetro da peca, nao fixos: a
    anotacao e desenhada em pixel constante, entao numa peca pequena um
    desvio fixo joga o texto sobre a linha, e numa grande o abandona longe.
    """
    notas = []
    for porta, dn in zip(portas, dn_por_porta):
        dentro = math.radians((porta.direcao or 0) + 180)
        # o desvio sai sempre para CIMA do eixo: a casa escreve os dois DN na
        # mesma linha, e uma nota de cada lado faria a peca parecer cotada em
        # dois lugares diferentes. Na ponta vertical, cima nao existe: ai vai
        # para a direita
        px, py = math.sin(dentro), -math.cos(dentro)
        if py > 1e-9 or (abs(py) <= 1e-9 and px < 0):
            px, py = -px, -py
        notas.append({"tipo": "nota",
                      "x": porta.x + math.cos(dentro) * recuo + px * desvio,
                      "y": porta.y + math.sin(dentro) * recuo + py * desvio,
                      "texto": f"{dn:g}"})
    return notas


def luva_pvc(dn_mm, junta="BOLSA"):
    """Luva: corpo curto com uma bolsa em cada ponta.

    A casa escreve o DN nas duas pontas mesmo sendo o mesmo numero - e o que
    diz que a peca nao e reducao.
    """
    comp = _cota_casa("LUVA", dn_mm, junta, "comprimento_mm") or dn_mm * 1.2
    externo = _cota_casa("LUVA", dn_mm, junta, "d_externo_mm") or dn_mm * 1.18
    r = externo / 2 / CINTA
    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"), _p(f"M0 {r:.1f} H{comp:.1f}"),
          _p(f"M0 {-r:.1f} V{r:.1f}"), _p(f"M{comp:.1f} {-r:.1f} V{r:.1f}")]
    if junta == "BOLSA":
        el += bolsa(0, dn_mm, externo, "entrada")
        el += bolsa(comp, dn_mm, externo, "saida")
    else:
        # sem cinta por fora, a bolsa tem de aparecer por dentro: o furo e o
        # diametro do TUBO, e a crista no meio e onde as duas pontas param.
        # Sem isso a luva grande sai um quadrado e nao se le como peca
        el += [_p(f"M0 {-dn_mm/2:.1f} H{comp:.1f}", "malha"),
               _p(f"M0 {dn_mm/2:.1f} H{comp:.1f}", "malha"),
               _p(f"M{comp/2:.1f} {-dn_mm/2:.1f} V{dn_mm/2:.1f}", "malha")]
    el.append(_p(f"M{-comp*0.2:.1f} 0 H{comp*1.2:.1f}", "centro"))
    dn_pol = _pvc_em_polegada(dn_mm)
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol)]
    el += _dn_nas_pontas(portas, (dn_mm, dn_mm), comp * 0.30, r * 0.5)
    return _montar("LUVA", f'luva {junta.lower()} DN{dn_mm:g}', el, portas,
                   "casa", {"dn_mm": dn_mm, "junta": junta})


def luva_reducao(dn_maior, dn_menor, junta="BOLSA"):
    """Luva de reducao: duas bolsas de bitola diferente e o cone entre elas.

    A casa desenha as duas bolsas empilhadas com a transicao conica no meio, e
    escreve a bitola de cada lado - 100 embaixo, 50 em cima. E isso que evita
    ligar do lado errado.
    """
    comp = (_cota_casa("LUVA_REDUCAO", dn_maior, junta, "comprimento_mm",
                       dn_menor)
            or _cota_casa("LUVA_REDUCAO", dn_maior, junta, "comprimento_mm")
            or dn_maior * 1.2)
    externo = (_cota_casa("LUVA_REDUCAO", dn_maior, junta, "d_externo_mm",
                          dn_menor)
               or _cota_casa("LUVA_REDUCAO", dn_maior, junta, "d_externo_mm")
               or dn_maior * 1.18)
    ra = externo / 2 / CINTA
    rb = ra * dn_menor / dn_maior
    a, meio, b = comp * 0.42, comp * 0.20, comp * 0.38
    el = [_polilinha([(0, -ra), (a, -ra), (a + meio, -rb), (comp, -rb)]),
          _polilinha([(0, ra), (a, ra), (a + meio, rb), (comp, rb)]),
          _p(f"M0 {-ra:.1f} V{ra:.1f}"), _p(f"M{comp:.1f} {-rb:.1f} V{rb:.1f}")]
    if junta == "BOLSA":
        el += bolsa(0, dn_maior, externo, "entrada")
        el += bolsa(comp, dn_menor, rb * 2 * CINTA, "saida")
    else:
        # como na luva reta: sem cinta por fora, a bolsa aparece por dentro,
        # e aqui sao duas - uma por bitola, com o cone entre elas
        el += [_polilinha([(0, -dn_maior / 2), (a, -dn_maior / 2),
                           (a + meio, -dn_menor / 2), (comp, -dn_menor / 2)],
                          "malha"),
               _polilinha([(0, dn_maior / 2), (a, dn_maior / 2),
                           (a + meio, dn_menor / 2), (comp, dn_menor / 2)],
                          "malha")]
    el.append(_p(f"M{-comp*0.2:.1f} 0 H{comp*1.2:.1f}", "centro"))
    portas = [Porta("maior", 0, 0, 180, _pvc_em_polegada(dn_maior)),
              Porta("menor", comp, 0, 0, _pvc_em_polegada(dn_menor))]
    el += _dn_nas_pontas(portas, (dn_maior, dn_menor), comp * 0.26, rb * 0.5)
    return _montar("LUVA_REDUCAO",
                   f'luva red DN{dn_maior:g}×{dn_menor:g}', el, portas, "casa",
                   {"dn_mm": dn_maior, "dn_menor_mm": dn_menor, "junta": junta})


# Raio do arco em raios de tubo. A curva injetada e apertada, e o limite quem
# da e a peca soldavel grande: a de DN225 mede 362 mm de envelope, e com raio
# acima de 2,1 r a peca nao caberia dentro da propria medida.
RAIO_CURVA = 1.8


def _paredes_de_curva(entrada, reta, angulo, r, lado, raio):
    """As duas paredes e o eixo de uma curva lisa de duas pernas dadas.

    entrada e a reta antes do arco, reta a de depois dele. Sao duas e nao uma
    porque a casa mede DOIS envelopes, e no bloco dela as pernas nao sao
    iguais - a de 45 grau tem a de entrada bem maior.
    """
    cx, cy = entrada, raio * lado
    a0 = -90 * lado
    a1 = a0 + angulo * lado
    direcao = math.radians(angulo * lado)

    def caminho(desvio):
        pontos = [(0, -desvio * lado), (cx, -desvio * lado)]
        pontos += arco(cx, cy, raio + desvio, a0, a1)
        pontos.append((pontos[-1][0] + math.cos(direcao) * reta,
                       pontos[-1][1] + math.sin(direcao) * reta))
        return pontos

    return caminho(r), caminho(-r), caminho(0.0), direcao


def _resolver_pernas(medir, alvo_largura, alvo_altura, minimo):
    """As duas pernas que produzem a caixa medida - Newton com jacobiano por
    diferenca finita.

    Sao duas incognitas e duas medidas, entao da para fechar exato em vez de
    escolher uma perna e aceitar o erro na outra. Devolve tambem o residuo,
    porque quem chama testa as duas trocas de eixo e fica com a melhor.
    """
    e = s = max(alvo_largura, alvo_altura) * 0.4
    for _ in range(24):
        largura, altura = medir(e, s)
        dl, da = alvo_largura - largura, alvo_altura - altura
        if abs(dl) < 0.2 and abs(da) < 0.2:
            break
        l1, a1 = medir(e + 1.0, s)
        l2, a2 = medir(e, s + 1.0)
        j11, j21, j12, j22 = l1 - largura, a1 - altura, l2 - largura, a2 - altura
        det = j11 * j22 - j12 * j21
        if abs(det) < 1e-9:
            break
        e = max(e + (dl * j22 - j12 * da) / det, minimo)
        s = max(s + (j11 * da - dl * j21) / det, minimo)
    largura, altura = medir(e, s)
    return e, s, abs(alvo_largura - largura) + abs(alvo_altura - altura)


def curva_pvc(dn_mm, angulo=90, junta="BOLSA", sentido=1):
    """Curva injetada: arco liso tangente as duas pernas.

    Nao tem gomo. Gomo e de chapa soldada; essa peca e injetada, e o bloco da
    casa desenha o arco liso - e essa a diferenca de traco entre a linha de
    aco e a de PVC.

    O que a casa mede sao os dois ENVELOPES da peca, nao as pernas. Duas
    medidas e duas pernas, entao da para fechar exato: as pernas sao resolvidas
    contra as duas medidas de uma vez.

    Qual envelope caiu no x e qual no y depende so de como o bloco foi posado -
    a curva de 45 da casa esta de pe, com o lado maior no y. Por isso as duas
    trocas de eixo sao tentadas e fica a que fecha melhor.
    """
    variantes = (f"{angulo}/{junta}", f"{angulo}/SOLDA", f"{angulo}/BOLSA")

    def medida(significado):
        for variante in variantes:
            valor = _cota_casa("CURVA", dn_mm, variante, significado)
            if valor:
                return valor
        return None

    env_x, env_y = medida("envelope_x_mm"), medida("envelope_y_mm")
    r = dn_mm / 2
    externo = dn_mm * 1.16
    raio = r * RAIO_CURVA
    minimo = r * 0.15
    lado = -1 if sentido > 0 else 1          # -1 = vira para cima na tela

    def cintas(centro, direcao):
        """As duas cintas da peca, entrada e saida - vazio na soldavel."""
        if junta != "BOLSA":
            return []
        fim = centro[-1]
        return [(0.0, 0.0, 0.0), (fim[0], fim[1], direcao + math.pi)]

    def montar(entrada, reta):
        fora, dentro, centro, direcao = _paredes_de_curva(
            entrada, reta, angulo, r, lado, raio)
        pontos = fora + dentro
        # a casa mede a caixa da peca INTEIRA, cinta incluida: sem ela a perna
        # sai resolvida contra outra medida que a do bloco
        for x, y, para_dentro in cintas(centro, direcao):
            pontos += _cantos_de_cinta(x, y, para_dentro, externo,
                                       max(externo * 0.09, 6.0))
        return (fora, dentro, centro, direcao,
                max(p[0] for p in pontos) - min(p[0] for p in pontos),
                max(p[1] for p in pontos) - min(p[1] for p in pontos))

    def medir(entrada, reta):
        return montar(entrada, reta)[4:]

    if env_x and env_y:
        pernas = min((_resolver_pernas(medir, a, b, minimo)
                      for a, b in ((env_x, env_y), (env_y, env_x))),
                     key=lambda t: t[2])
        entrada, reta = pernas[0], pernas[1]
        envelope = max(env_x, env_y)
    else:
        # com um envelope so as duas pernas ficam iguais e o que se casa e o
        # lado maior da caixa - e o que da para afirmar com uma medida
        envelope = env_x or env_y or dn_mm * 2.4
        entrada = reta = max(envelope - r, minimo)
        for _ in range(8):
            largura, altura = medir(entrada, reta)
            obtido = max(largura, altura)
            if abs(obtido - envelope) < 0.3:
                break
            entrada = reta = max(entrada * envelope / obtido, minimo)

    fora, dentro, centro, direcao, _, _ = montar(entrada, reta)
    el = [_polilinha(fora), _polilinha(dentro)]
    fim = centro[-1]
    # a sobra do eixo sai do TAMANHO da peca, nao da perna: numa curva de
    # raio curto a perna e curta, e uma sobra proporcional a ela desaparecia
    folga = max(envelope * 0.07, r * 0.5)
    el.append(_polilinha([(-folga, 0)] + centro
                         + [(fim[0] + math.cos(direcao) * folga,
                             fim[1] + math.sin(direcao) * folga)],
                        "centro"))
    for x, y, para_dentro in cintas(centro, direcao):
        el += _cinta(x, y, para_dentro, dn_mm, externo)
    if junta != "BOLSA":
        # na soldavel a ponta e o proprio corte do tubo: fecha com uma reta
        el += [_polilinha([fora[0], dentro[0]]),
               _polilinha([fora[-1], dentro[-1]])]
    portas = [Porta("entrada", 0, 0, 180, _pvc_em_polegada(dn_mm)),
              Porta("saida", fim[0], fim[1], angulo * lado,
                    _pvc_em_polegada(dn_mm))]
    el += _dn_nas_pontas(portas, (dn_mm, dn_mm),
                         max(entrada * 0.5, r * 1.3), r * 0.5)
    return _montar("CURVA", f'curva {angulo}° {junta.lower()} DN{dn_mm:g}',
                   el, portas, "casa",
                   {"dn_mm": dn_mm, "junta": junta, "angulo": angulo,
                    "envelope_mm": envelope})


def te_pvc(dn_mm, dn_derivacao=None, junta="BOLSA"):
    """Te: corrido com bolsa nas duas pontas e derivacao com a sua.

    O V que desce da derivacao ate o eixo e do bloco da casa: e a transicao
    interna, onde o ramo encontra o corrido. Sem ele o te de lado fica igual a
    um tubo com um toco em cima.
    """
    familia = "TE_REDUZIDO" if dn_derivacao and dn_derivacao != dn_mm else "TE"
    menor = dn_derivacao if familia == "TE_REDUZIDO" else None
    comp = (_cota_casa(familia, dn_mm, junta, "face_a_face_mm", menor)
            or _cota_casa("TE", dn_mm, junta, "face_a_face_mm")
            or dn_mm * 2.3)
    alto = (_cota_casa(familia, dn_mm, junta, "altura_total_mm", menor)
            or _cota_casa("TE", dn_mm, junta, "altura_total_mm")
            or dn_mm * 1.7)
    dn_der = dn_derivacao or dn_mm
    r, rd = dn_mm / 2, dn_der / 2
    externo = dn_mm * 1.18       # o diametro da cinta
    rc = externo / 2 / CINTA     # o corpo, mais fino que ela
    meio = comp / 2
    # o corrido, com a bolsa em cada ponta
    el = [_p(f"M0 {-rc:.1f} H{comp:.1f}"), _p(f"M0 {rc:.1f} H{comp:.1f}"),
          _p(f"M0 {-rc:.1f} V{rc:.1f}"), _p(f"M{comp:.1f} {-rc:.1f} V{rc:.1f}")]
    if junta == "BOLSA":
        el += bolsa(0, dn_mm, externo, "entrada")
        el += bolsa(comp, dn_mm, externo, "saida")
    # a derivacao: sobe do corrido ate a altura total, com a bolsa dela
    # a altura total que a casa mede vai do topo da cinta da derivacao ao
    # fundo da cinta do corrido - e da cinta, nao do corpo
    # na soldavel nao tem cinta: o fundo da peca e o proprio corpo
    fundo = externo / 2 if junta == "BOLSA" else rc
    topo = -(alto - fundo)
    rde = dn_der * 1.18 / 2 / CINTA
    el += [_p(f"M{meio - rde:.1f} {-rc:.1f} V{topo:.1f}"),
           _p(f"M{meio + rde:.1f} {-rc:.1f} V{topo:.1f}"),
           _p(f"M{meio - rde:.1f} {topo:.1f} H{meio + rde:.1f}")]
    if junta == "BOLSA":
        el += [{"tipo": "rect", "x": meio - rde * CINTA,
                "y": topo, "w": rde * 2 * CINTA,
                "h": max(rde * 0.18, 6.0), "classe": "corpo"}]
    if junta != "BOLSA":
        # como na luva: sem cinta por fora, a bolsa aparece por dentro
        el += [_p(f"M0 {-r:.1f} H{comp:.1f}", "malha"),
               _p(f"M0 {r:.1f} H{comp:.1f}", "malha"),
               _p(f"M{meio - rd:.1f} {-r:.1f} V{topo:.1f}", "malha"),
               _p(f"M{meio + rd:.1f} {-r:.1f} V{topo:.1f}", "malha")]
    # o V da transicao interna
    el.append(_p(f"M{meio - rde:.1f} {-rc:.1f} L{meio:.1f} {rc*0.55:.1f} "
                 f"L{meio + rde:.1f} {-rc:.1f}", "malha"))
    el.append(_p(f"M{-comp*0.16:.1f} 0 H{comp*1.16:.1f}", "centro"))
    el.append(_p(f"M{meio:.1f} {topo - alto*0.14:.1f} V{rc*1.3:.1f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, _pvc_em_polegada(dn_mm)),
              Porta("saida", comp, 0, 0, _pvc_em_polegada(dn_mm)),
              Porta("derivacao", meio, topo, -90, _pvc_em_polegada(dn_der))]
    el += _dn_nas_pontas(portas[:2], (dn_mm, dn_mm), comp * 0.20, rc * 0.5)
    el.append({"tipo": "nota", "x": meio, "y": topo + alto * 0.16,
               "texto": f"{dn_der:g}"})
    rot = (f'tê DN{dn_mm:g}' if dn_der == dn_mm
           else f'tê red DN{dn_mm:g}×{dn_der:g}')
    return _montar(familia, f'{rot} {junta.lower()}', el, portas, "casa",
                   {"dn_mm": dn_mm, "dn_derivacao_mm": dn_der, "junta": junta})


def adaptador_flange(dn_mm):
    """Colar soldavel de Plasson: pescoco e o ressalto que segura a flange.

    E o mesmo papel do colar de PEAD termofundido, com outra ponta: aqui o
    pescoco solda por encaixe em vez de topo a topo. O ressalto continua sendo
    o que prende a flange solta.
    """
    comp = _cota_casa("ADAPTADOR_FLANGE", dn_mm, "", "comprimento_mm") or dn_mm
    externo = (_cota_casa("ADAPTADOR_FLANGE", dn_mm, "", "d_externo_mm")
               or dn_mm * 1.35)
    r, rr = dn_mm / 2, externo / 2
    esp = max(comp * 0.22, 10.0)
    el = [_p(f"M0 {-r:.1f} H{comp - esp:.1f}"),
          _p(f"M0 {r:.1f} H{comp - esp:.1f}"),
          _p(f"M0 {-r:.1f} V{r:.1f}"),
          {"tipo": "rect", "x": comp - esp, "y": -rr, "w": esp, "h": externo,
           "classe": "corpo"},
          _p(f"M0 {-r*0.72:.1f} H{comp:.1f}", "malha"),
          _p(f"M0 {r*0.72:.1f} H{comp:.1f}", "malha")]
    el.append(_p(f"M{-comp*0.25:.1f} 0 H{comp*1.25:.1f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, _pvc_em_polegada(dn_mm)),
              Porta("saida", comp, 0, 0, _pvc_em_polegada(dn_mm))]
    # o DN uma vez so: a peca e curta, e as duas notas cairiam uma sobre a
    # outra. Do lado da flange quem manda e a furacao, nao o DN do tubo
    el += _dn_nas_pontas(portas[:1], (dn_mm,), comp * 0.45, r * 0.45)
    return _montar("ADAPTADOR_FLANGE", f'adaptador p/ flange DN{dn_mm:g}',
                   el, portas, "casa", {"dn_mm": dn_mm})


def bucha_reducao(dn_maior, dn_menor):
    """Bucha de reducao: entra na bolsa da maior e recebe a menor.

    O bloco da casa desenha um corpo curto escalonado, sem cinta - bucha nao
    tem bolsa para fora, ela E a bolsa.
    """
    comp = (_cota_casa("BUCHA_REDUCAO", dn_maior, "SOLDA", "comprimento_mm",
                       dn_menor)
            or _cota_casa("BUCHA_REDUCAO", dn_maior, "", "comprimento_mm")
            or dn_maior * 0.6)
    externo = (_cota_casa("BUCHA_REDUCAO", dn_maior, "SOLDA", "d_externo_mm",
                          dn_menor)
               or _cota_casa("BUCHA_REDUCAO", dn_maior, "", "d_externo_mm")
               or dn_maior)
    ra = externo / 2
    rb = dn_menor / 2
    # O bloco da casa desenha a bucha como um retangulo simples: ela nao tem
    # bolsa para fora, ela E a bolsa. O que aparece dentro e o furo da menor.
    el = [{"tipo": "rect", "x": 0, "y": -ra, "w": comp, "h": externo,
           "classe": "corpo"},
          _p(f"M0 {-rb:.1f} H{comp:.1f}", "malha"),
          _p(f"M0 {rb:.1f} H{comp:.1f}", "malha")]
    el.append(_p(f"M{-comp*0.3:.1f} 0 H{comp*1.3:.1f}", "centro"))
    portas = [Porta("maior", 0, 0, 180, _pvc_em_polegada(dn_maior)),
              Porta("menor", comp, 0, 0, _pvc_em_polegada(dn_menor))]
    # aqui as duas bitolas vao EMPILHADAS, nao uma em cada ponta: a bucha e
    # curta, a anotacao e em pixel fixo, e os dois numeros lado a lado
    # encostam. Empilhado tambem le melhor - a bucha e a peca em que uma
    # bitola esta por dentro da outra
    el += [{"tipo": "nota", "x": comp / 2, "y": -ra * 0.42,
            "texto": f"{dn_maior:g}"},
           {"tipo": "nota", "x": comp / 2, "y": rb * 0.62,
            "texto": f"{dn_menor:g}"}]
    return _montar("BUCHA_REDUCAO", f'bucha red DN{dn_maior:g}×{dn_menor:g}',
                   el, portas, "casa",
                   {"dn_mm": dn_maior, "dn_menor_mm": dn_menor})


# ------------------------------------------------------------------ PEAD
# No PEAD o DN E o diametro externo: o tubo DN225 mede 225 mm por fora. Nao ha
# tabela de DE a consultar como no aco - o numero do codigo ja e o do desenho.
# A parede sai do SDR, que e a razao DN/parede fixada pela pressao.
SDR_POR_PN = {6: 26, 8: 21, 10: 17, 12.5: 13.6, 16: 11, 20: 9, 25: 7.4}
# A equivalencia que a casa pratica entre a linha de aco e a de PEAD, a mesma
# de motor/traducao.POLEGADA_MM lida ao contrario.
PEAD_POL = {63: 2, 75: 2.5, 90: 3, 110: 4, 140: 5, 160: 6, 225: 8, 280: 10,
            315: 12, 355: 14}


def _pead_em_polegada(dn_mm):
    if dn_mm in PEAD_POL:
        return PEAD_POL[dn_mm]
    return min(PEAD_POL.items(), key=lambda kv: abs(kv[0] - dn_mm))[1]


def tubo_pead(dn_mm, comprimento_mm=6000, pn=10):
    """A barra de PEAD: 6 metros, ponta lisa dos dois lados.

    Nao tem flange nem rosca - PEAD emenda por termofusao, topo a topo. O que
    aparece no desenho e a parede, que aqui e grossa o bastante para valer o
    traco: DN225 PN10 da 13 mm de cada lado.
    """
    r = dn_mm / 2
    parede = dn_mm / SDR_POR_PN.get(pn, 17)
    el = [_p(f"M0 {-r:.1f} H{comprimento_mm:.1f}"),
          _p(f"M0 {r:.1f} H{comprimento_mm:.1f}"),
          _p(f"M0 {-r+parede:.1f} H{comprimento_mm:.1f}", "malha"),
          _p(f"M0 {r-parede:.1f} H{comprimento_mm:.1f}", "malha"),
          _p(f"M0 {-r:.1f} V{r:.1f}"),
          _p(f"M{comprimento_mm:.1f} {-r:.1f} V{r:.1f}"),
          _p(f"M-80 0 H{comprimento_mm+80:.0f}", "centro")]
    portas = [Porta("entrada", 0, 0, 180, _pead_em_polegada(dn_mm)),
              Porta("saida", comprimento_mm, 0, 0, _pead_em_polegada(dn_mm))]
    return _montar("TUBO", f'tubo PEAD DN{dn_mm:g} {comprimento_mm/1000:g} m',
                   el, portas, "descricao",
                   {"material": "PEAD", "dn_mm": dn_mm, "pn": pn})


def tubo_pvc(dn_mm, comprimento_mm=6000, ponta="BOLSA"):
    """A barra de PVC, 6 metros - a ponta e que diz como ela emenda.

    Tres pontas na lista, e as tres estao na descricao:

      JEI  junta elastica integrada: a bolsa ja vem moldada num lado, e o anel
           de borracha mora dentro dela. Desenha bolsa de um lado so
      PB   ponta e bolsa: a mesma coisa dita do jeito antigo
      PP   ponta e ponta: os dois lados lisos, emenda com luva separada

    Nao tem cota medida: a barra e a barra, e o que vale e o comprimento da
    descricao. A parede sai do PN quando a descricao trouxer.
    """
    r = dn_mm / 2
    externo = dn_mm * 1.16
    el = [_p(f"M0 {-r:.1f} H{comprimento_mm:.1f}"),
          _p(f"M0 {r:.1f} H{comprimento_mm:.1f}"),
          _p(f"M0 {-r:.1f} V{r:.1f}"),
          _p(f"M{comprimento_mm:.1f} {-r:.1f} V{r:.1f}")]
    if ponta == "BOLSA":
        el += bolsa(0, dn_mm, externo, "entrada")
    folga = max(comprimento_mm * 0.015, dn_mm)
    el.append(_p(f"M{-folga:.0f} 0 H{comprimento_mm + folga:.0f}", "centro"))
    dn_pol = _pvc_em_polegada(dn_mm)
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comprimento_mm, 0, 0, dn_pol)]
    el += _dn_nas_pontas(portas[:1], (dn_mm,), comprimento_mm * 0.10, r * 0.5)
    ficha = "bolsa" if ponta == "BOLSA" else "ponta lisa"
    return _montar("TUBO",
                   f'tubo PVC DN{dn_mm:g} {comprimento_mm/1000:g} m {ficha}',
                   el, portas, "descricao",
                   {"material": "PVC", "dn_mm": dn_mm, "ponta": ponta})


def _rosca(x, comp, raio, lado="entrada"):
    """O filete da rosca: o que faz uma ponta lisa virar ponta rosqueada.

    Nao e decoracao. De lado, a unica coisa que separa um nipe de um pedaco de
    tubo e o filete - e separar os dois importa, porque um solda e o outro
    aparafusa.

    O traco e o do desenho tecnico: a CRISTA e a propria linha do corpo, e o
    FUNDO do filete e uma linha fina por dentro dela. Desenhar tracinhos sobre
    a linha do corpo nao aparece - eles caem exatamente onde o corpo ja esta.
    """
    fundo = raio * 0.86
    x0 = x if lado == "entrada" else x - comp
    x1 = x0 + comp
    el = [_p(f"M{x0:.1f} {-fundo:.1f} H{x1:.1f}", "malha"),
          _p(f"M{x0:.1f} {fundo:.1f} H{x1:.1f}", "malha")]
    # o fim da rosca: onde ela para, o filete fecha
    fim = x1 if lado == "entrada" else x0
    el.append(_p(f"M{fim:.1f} {-fundo:.1f} V{fundo:.1f}", "malha"))
    return el


def niple(dn_mm, junta="ROSCA", fonte="norma", norma=""):
    """Nipe: um toco com rosca macho nas duas pontas.

    A peca mais simples da lista, e a que mais precisa do filete: sem ele e um
    tubo curto. O comprimento nao esta em folha - o nipe duplo comercial mede
    perto de 2,4 diametros, e a tarja diz que isso e proporcao.
    """
    r = dn_mm / 2
    comp = dn_mm * 2.4
    trecho = comp * 0.36
    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"), _p(f"M0 {r:.1f} H{comp:.1f}"),
          _p(f"M0 {-r:.1f} V{r:.1f}"), _p(f"M{comp:.1f} {-r:.1f} V{r:.1f}")]
    el += _rosca(0, trecho, r)
    el += _rosca(comp, trecho, r, "saida")
    # o sextavado do meio, onde a chave pega
    el.append({"tipo": "rect", "x": comp/2 - comp*0.11, "y": -r*1.14,
               "w": comp*0.22, "h": r*2.28, "classe": "corpo"})
    el.append(_p(f"M{-comp*0.2:.1f} 0 H{comp*1.2:.1f}", "centro"))
    dn_pol = _pvc_em_polegada(dn_mm)
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol)]
    el += _dn_nas_pontas(portas[:1], (dn_mm,), comp * 0.5, r * 0.55)
    return _montar("NIPLE", f'nipe DN{dn_mm:g}', el, portas, fonte,
                   {"dn_mm": dn_mm, "junta": junta, "norma": norma})


def uniao(dn_mm, junta="ROSCA", fonte="norma", norma=""):
    """Uniao: duas meias luvas e a porca no meio que aperta uma na outra.

    A porca e a peca - e por ela que a uniao existe. Desmontar uma linha
    rosqueada sem uniao obriga a girar tudo desde a ponta; com ela, solta-se a
    porca e o trecho sai. De lado a porca aparece como a cinta gorda no meio,
    com o sextavado nas quinas.
    """
    r = dn_mm / 2
    comp = dn_mm * 1.9
    porca_l = comp * 0.34
    rp = r * 1.30
    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"), _p(f"M0 {r:.1f} H{comp:.1f}"),
          _p(f"M0 {-r:.1f} V{r:.1f}"), _p(f"M{comp:.1f} {-r:.1f} V{r:.1f}")]
    if junta == "ROSCA":
        el += _rosca(0, comp * 0.26, r)
        el += _rosca(comp, comp * 0.26, r, "saida")
    else:
        el += bolsa(0, dn_mm, dn_mm * 1.16, "entrada")
        el += bolsa(comp, dn_mm, dn_mm * 1.16, "saida")
    # a porca central, e o assento conico onde as duas metades se encostam
    el.append({"tipo": "rect", "x": comp/2 - porca_l/2, "y": -rp,
               "w": porca_l, "h": 2 * rp, "classe": "porca"})
    el.append(_p(f"M{comp/2:.1f} {-rp:.1f} V{rp:.1f}", "junta"))
    el.append(_p(f"M{-comp*0.2:.1f} 0 H{comp*1.2:.1f}", "centro"))
    dn_pol = _pvc_em_polegada(dn_mm)
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol)]
    el += _dn_nas_pontas(portas[:1], (dn_mm,), comp * 0.22, r * 0.55)
    return _montar("UNIAO", f'união DN{dn_mm:g}', el, portas, fonte,
                   {"dn_mm": dn_mm, "junta": junta, "norma": norma})


def cap_pvc(dn_mm, junta="BOLSA"):
    """Cap: a bolsa de um lado e o fundo fechado do outro.

    Nao tem cota medida - a casa nao desenhou cap solto no DXF. O que da para
    afirmar e que o cap E meia luva: uma bolsa em vez de duas, mais o fundo.
    Entao a profundidade sai da luva medida da mesma bitola e junta, e a fonte
    na tarja diz "da luva" para ninguem confundir com cota de folha.
    """
    luva = _cota_casa("LUVA", dn_mm, junta, "comprimento_mm")
    externo = _cota_casa("LUVA", dn_mm, junta, "d_externo_mm") or dn_mm * 1.18
    fundo = max(dn_mm * 0.07, 5.0)
    comp = (luva / 2 if luva else dn_mm * 0.6) + fundo
    r = externo / 2 / CINTA
    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"), _p(f"M0 {r:.1f} H{comp:.1f}"),
          _p(f"M0 {-r:.1f} V{r:.1f}"),
          # o fundo: chapa cheia, e e o que faz do cap um cap
          {"tipo": "rect", "x": comp - fundo, "y": -r, "w": fundo, "h": 2 * r,
           "classe": "corpo"}]
    if junta == "BOLSA":
        el += bolsa(0, dn_mm, externo, "entrada")
    else:
        el += [_p(f"M0 {-dn_mm/2:.1f} H{comp - fundo:.1f}", "malha"),
               _p(f"M0 {dn_mm/2:.1f} H{comp - fundo:.1f}", "malha")]
    el.append(_p(f"M{-comp*0.3:.1f} 0 H{comp:.1f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, _pvc_em_polegada(dn_mm))]
    el += _dn_nas_pontas(portas, (dn_mm,), comp * 0.42, r * 0.5)
    return _montar("CAP", f'cap {junta.lower()} DN{dn_mm:g}', el, portas,
                   "da luva", {"dn_mm": dn_mm, "junta": junta})


def colar_tomada(dn_mm, saida_pol, tipo="ROSCA", norma="NBR PN16"):
    """Colar de tomada: a sela que abraca o tubo e a derivacao que sai dela.

    E a unica peca da linha que nao entra em serie - ela monta EM CIMA do
    tubo, sem cortar nada. Por isso o desenho mostra o tubo passando reto e a
    peca por fora dele: quem olha tem de ver onde ela abraca.

    A bitola da lista aqui e o DIAMETRO EXTERNO DO TUBO em milimetro - 326 mm
    e o tubo de 12" de aco - e a saida vem em polegada, com o tipo dela na
    descricao: flange com norma, ou rosca femea BSP.

    Sem cota de folha. O que manda a forma e o tubo (que e medido) e a bitola
    da saida (que e tabelada); o resto - comprimento da sela, altura do
    pescoco - e proporcao, e a tarja diz isso.
    """
    r = dn_mm / 2
    saida_de = DE_TUBO.get(saida_pol, 60)
    rs = saida_de / 2
    sela = saida_de * 2.6                       # o comprimento da sela
    tubo_visto = sela * 1.9
    alto = saida_de * 0.42                      # quanto a sela sobe do tubo
    pescoco = saida_de * 0.9
    x0, x1 = (tubo_visto - sela) / 2, (tubo_visto + sela) / 2
    meio = tubo_visto / 2
    topo = -(r + alto)

    # o tubo passando reto, em traco de detalhe: ele nao e a peca
    el = [_p(f"M0 {-r:.1f} H{tubo_visto:.1f}", "malha"),
          _p(f"M0 {r:.1f} H{tubo_visto:.1f}", "malha")]
    # a sela, com o ombro arredondado encostando no tubo
    ombro = alto * 0.9
    el += [_polilinha([(x0, -r), (x0, topo + ombro)]
                      + arco(x0 + ombro, topo + ombro, ombro, 180, 270, 6)
                      + [(x1 - ombro, topo)]
                      + arco(x1 - ombro, topo + ombro, ombro, 270, 360, 6)
                      + [(x1, -r)])]
    # as duas cintas que passam por baixo do tubo - e o que prende
    for x in (x0 + saida_de * 0.34, x1 - saida_de * 0.34):
        el.append(_p(f"M{x:.1f} {topo + ombro:.1f} V{r * 1.22:.1f}",
                     "parafuso"))
        el.append(_p(f"M{x - saida_de*0.09:.1f} {r * 1.22:.1f} "
                     f"h{saida_de*0.18:.1f}", "parafuso"))
    # o pescoco da saida
    boca = topo - pescoco
    el += [_p(f"M{meio - rs:.1f} {topo:.1f} V{boca:.1f}"),
           _p(f"M{meio + rs:.1f} {topo:.1f} V{boca:.1f}")]
    if tipo == "FLANGE":
        chapa = placa(meio, saida_pol, boca, norma=norma, lado="saida")
        for e in chapa:
            e["girar"] = (-90, meio, boca)
        el += chapa
    else:
        # rosca femea: o filete e o que diz que a boca e rosqueada
        el.append(_p(f"M{meio - rs:.1f} {boca:.1f} H{meio + rs:.1f}"))
        passo = max(saida_de * 0.12, 4.0)
        n = int(pescoco * 0.55 / passo)
        for k in range(1, n + 1):
            y = boca + k * passo
            el.append(_p(f"M{meio - rs:.1f} {y:.1f} H{meio + rs:.1f}", "malha"))
    el.append(_p(f"M{meio:.1f} {boca - pescoco*0.3:.1f} V{-r*0.4:.1f}",
                 "centro"))
    el.append(_p(f"M0 0 H{tubo_visto:.1f}", "centro"))
    portas = [Porta("derivacao", meio, boca, -90, saida_pol)]
    el.append({"tipo": "nota", "x": meio + rs + saida_de * 0.5,
               "y": boca + pescoco * 0.5, "texto": f'{saida_pol:g}"'})
    el.append({"tipo": "nota", "x": tubo_visto * 0.14, "y": -r * 0.42,
               "texto": f"{dn_mm:g}"})
    return _montar("COLAR_TOMADA",
                   f'colar tomada {dn_mm:g} mm × {saida_pol:g}"', el, portas,
                   "proporcao", {"dn_mm": dn_mm, "saida_pol": saida_pol,
                                 "tipo": tipo, "norma": norma})


def colar_pead(dn_mm, pn=10, norma="NBR PN16"):
    """Colar de flange PEAD com a flange solta ja enfiada.

    E uma peca so no desenho porque e uma peca so na obra: a flange entra no
    tubo primeiro, o colar e soldado depois, e o ressalto do colar e que a
    prende - dai ela nao sai mais. Desenhar o colar sem a flange seria
    desenhar um estado que nao existe montado.

    O ressalto tem o diametro do ressalto da flange de aco da mesma bitola,
    que e onde a junta assenta; o comprimento do pescoco e o unico numero sem
    folha de fabricante e esta estimado - ver docs/MOTOR.md.
    """
    dn_pol = _pead_em_polegada(dn_mm)
    f = flange(dn_pol, norma)
    esp = f["espessura"]
    r = dn_mm / 2
    parede = dn_mm / SDR_POR_PN.get(pn, 17)
    ressalto = f["ressalto"]
    esp_ressalto = max(parede, 12.0)
    # o unico numero sem folha: o pescoco tem que dar espaco para a flange
    # correr e ainda sobrar tubo para a termofusao. A estimativa fica perto
    # do stub end DIN 16963-4 (DN110 da 62, DN225 da 108).
    pescoco = max(esp + 40, dn_mm * 0.40)
    comp = pescoco + esp_ressalto

    el = [
        # o pescoco: tubo de PEAD com a parede cheia, ponta lisa para fundir
        _p(f"M0 {-r:.1f} H{pescoco:.1f}"), _p(f"M0 {r:.1f} H{pescoco:.1f}"),
        _p(f"M0 {-r+parede:.1f} H{comp:.1f}", "malha"),
        _p(f"M0 {r-parede:.1f} H{comp:.1f}", "malha"),
        _p(f"M0 {-r:.1f} V{r:.1f}", "solda"),
        # o ressalto: o anel que cresce no fim do colar. E ele que segura a
        # flange, e e nele que a junta assenta - dai ter o diametro do
        # ressalto da flange de aco da mesma bitola.
        _p(f"M{pescoco:.1f} {-r:.1f} V{-ressalto/2:.1f}"),
        _p(f"M{pescoco:.1f} {r:.1f} V{ressalto/2:.1f}"),
        _p(f"M{pescoco:.1f} {-ressalto/2:.1f} H{comp:.1f}"),
        _p(f"M{pescoco:.1f} {ressalto/2:.1f} H{comp:.1f}"),
        _p(f"M{comp:.1f} {-ressalto/2:.1f} V{ressalto/2:.1f}"),
    ]
    # a flange solta, encostada por tras do ressalto. Nao solda em nada: entrou
    # pelo tubo antes de o colar existir e agora nao passa mais pelo ressalto.
    el.append({"tipo": "rect", "x": pescoco - esp, "y": -f["externo"] / 2,
               "w": esp, "h": f["externo"], "classe": "flange"})
    for sinal in (-1, 1):
        el.append(_p(f"M{pescoco-esp:.1f} {sinal*f['circulo']/2:.1f} "
                     f"h{esp:.1f}", "furo"))
        # o furo central da flange, por onde o tubo passa
        el.append(_p(f"M{pescoco-esp:.1f} {sinal*(r+2):.1f} h{esp:.1f}",
                     "malha"))
    el.append({"tipo": "texto_furos", "x": pescoco, "y": 0, "n": f["furos"],
               "furo": f["furo"]})
    el.append(_p(f"M-60 0 H{comp+50:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("COLAR_PEAD", f'colar PEAD DN{dn_mm:g} + flange solta', el,
                   portas, "netafim",
                   {"material": "PEAD", "dn_mm": dn_mm, "pn": pn,
                    "flange_solta": True, "pescoco_estimado": True})


# --------------------------------------------------------------- manifold
_manifold = None


def ficha_manifold(dn_pol, derivacao_pol=None):
    """A folha do manifold, pagina 25 do caderno."""
    global _manifold
    if _manifold is None:
        _manifold = []
        with open(f"{DADOS}/manifold_netafim.csv", encoding="utf-8") as fh:
            _manifold = list(csv.DictReader(fh))
    candidatos = [r for r in _manifold
                  if float(r["dn_pol"]) == float(dn_pol)]
    if derivacao_pol:
        exato = [r for r in candidatos
                 if float(r["derivacao_pol"]) == float(derivacao_pol)]
        if exato:
            return exato[0]
    return candidatos[0] if candidatos else None


def manifold(dn_pol, derivacao_pol=None, derivacoes=2, ponta="FLANGE"):
    """O barrilete do recalque: corpo longo, derivacoes em cima e as ventosas.

    As duas luvas de 2" BSP nao sao acessorio - sao a razao de o manifold ter
    ventosa. A folha as cota pelo topo, a 40 mm acima da geratriz do corpo, e
    esse numero fecha em todas as bitolas de 4" a 20".

    A ponta e o que a descricao chama de FL ou K: flange soldada ou anel K10
    para junta mecanica.
    """
    ficha = ficha_manifold(dn_pol, derivacao_pol) or {}
    comp = float(ficha.get("comprimento_mm") or 1500)
    der_pol = float(ficha.get("derivacao_pol") or derivacao_pol or 4)
    pescoco = float(ficha.get("derivacao_pescoco_mm") or 100)
    luva_alt = float(ficha.get("luva_altura_mm") or DE_TUBO.get(dn_pol, 200) / 2 + 40)
    r = DE_TUBO.get(dn_pol, 200) / 2
    fonte = "netafim" if ficha else None

    el = eixo(0, comp, dn_pol)
    if ponta == "FLANGE":
        el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    else:
        # anel K10: um ressalto de topo, sem furacao
        for x0, largura in ((0, 24), (comp - 24, 24)):
            el.append({"tipo": "rect", "x": x0, "y": -r - 14, "w": largura,
                       "h": 2 * r + 28, "classe": "corpo"})

    # as derivacoes, distribuidas no corpo, saindo para cima
    passo = comp / (derivacoes + 1)
    rd = DE_TUBO.get(der_pol, 100) / 2
    for i in range(derivacoes):
        x = passo * (i + 1)
        el += [_p(f"M{x-rd:.1f} {-r:.1f} V{-(r+pescoco):.1f}"),
               _p(f"M{x+rd:.1f} {-r:.1f} V{-(r+pescoco):.1f}")]
        el += placa(x, der_pol, y=-r - pescoco, direcao=-90, lado="saida")

    # as duas luvas de ventosa. A folha cota o topo (G2), nao o comprimento
    # da luva: os 30 mm da coluna F3 sao a rosca, e a luva sai da parede ate
    # os 40 mm acima dela que a cota manda.
    saliencia = luva_alt - r
    for x in (comp * 0.16, comp * 0.84):
        el += luva(x, -r, -90, LUVA_BSP["dn_pol"], comprimento=saliencia)

    el.append(_p(f"M-70 0 H{comp+70:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", comp, 0, 0, dn_pol)]
    for i in range(derivacoes):
        portas.append(Porta("derivacao", passo * (i + 1), -r - pescoco, -90,
                            der_pol))
    rot = (f'manifold {dn_pol:g}" {comp:g} mm · {derivacoes}×{der_pol:g}" '
           f'· 2 lv 2"')
    return _montar("MANIFOLD", rot, el, portas, fonte,
                   {"derivacoes": derivacoes, "derivacao_pol": der_pol,
                    "luvas_ventosa": 2, "ponta": ponta})


# ------------------------------------------------------- familias de equipamento
def volante(cx, cy, diametro, raios=3, classe="acionamento"):
    """Volante visto de frente: aro, cubo e os raios.

    O bloco da casa desenha o volante da borboleta de frente e o da gaveta de
    canto - sao dois volantes diferentes na mesma folha, e cada um mostra o
    que importa. De frente da para contar os raios; de canto da para ver que
    ele e chato.
    """
    r = diametro / 2
    el = [{"tipo": "circulo", "cx": cx, "cy": cy, "r": r, "classe": classe},
          {"tipo": "circulo", "cx": cx, "cy": cy, "r": r * 0.86,
           "classe": classe},
          {"tipo": "circulo", "cx": cx, "cy": cy, "r": r * 0.20,
           "classe": classe}]
    for k in range(raios):
        ang = math.radians(90 + k * 360 / raios)
        el.append(_p(f"M{cx + r*0.20*math.cos(ang):.1f} "
                     f"{cy - r*0.20*math.sin(ang):.1f} "
                     f"L{cx + r*0.86*math.cos(ang):.1f} "
                     f"{cy - r*0.86*math.sin(ang):.1f}", classe))
    return el


def volante_de_canto(cx, cy, diametro, espessura, classe="acionamento"):
    """Volante visto de canto: chato, com o aro nas pontas e a porca em cima."""
    r = diametro / 2
    return [{"tipo": "rect", "x": cx - r, "y": cy - espessura * 0.35,
             "w": diametro, "h": espessura * 0.7, "rx": espessura * 0.3,
             "classe": classe},
            _p(f"M{cx - r:.1f} {cy - espessura:.1f} v{2*espessura:.1f}", classe),
            _p(f"M{cx + r:.1f} {cy - espessura:.1f} v{2*espessura:.1f}", classe),
            {"tipo": "rect", "x": cx - espessura * 0.9, "y": cy - espessura * 2.1,
             "w": espessura * 1.8, "h": espessura * 1.4, "classe": classe}]


def parafusos_de_tampa(x0, x1, y, cabeca, classe="parafuso"):
    """As cabecas de parafuso nas duas pontas de uma tampa aparafusada."""
    el = []
    for x in (x0, x1):
        el.append({"tipo": "rect", "x": x - cabeca * 0.5, "y": y - cabeca,
                   "w": cabeca, "h": cabeca, "classe": classe})
    return el


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
    # as duas orelhas do wafer, onde a barra roscada passa
    for sinal in (-1, 1):
        el.append({"tipo": "rect", "x": meio - comp*0.34, "y": sinal*corpo/2
                   - (comp*0.16 if sinal > 0 else 0),
                   "w": comp*0.68, "h": comp*0.16, "classe": "corpo"})
    # flange do atuador em cima do corpo, e a haste
    topo = -corpo / 2 - comp * 0.16
    flangete = comp * 0.55
    el += caixa(meio - comp*0.7, comp*1.4, -topo + flangete, topo)
    # A folha da MP cota altura_acima_mm - do eixo ao alto do acionamento - e
    # e a versao de ALAVANCA que ela cota. Entao a alavanca fecha na cota, e a
    # haste sai da cota para tras em vez de a cota sair da haste: era isso que
    # deixava a alavanca 10% baixa em toda bitola.
    #
    # A caixa redutora nao tem cota de folha nenhuma. Ela E mais alta que a
    # alavanca - tem o redutor e o volante em cima - e aqui isso e dito de uma
    # vez: 1,15 da altura da alavanca. Deixar o volante flutuar fazia a caixa
    # crescer com a bitola sem regra, 25% acima da alavanca em 6".
    alto_alavanca = acima
    if acionamento == "ALAVANCA":
        yl = -acima + comp * 0.45
    else:
        yl = -alto_alavanca * 1.15 - comp * 0.55 + alcance / 2
    el.append(_p(f"M{meio:.1f} {topo - flangete:.1f} V{yl:.1f}", "haste"))
    if acionamento == "ALAVANCA":
        el += caixa(meio - comp*0.5, comp, -yl + comp*0.45, yl + comp*0.45,
                    classe="acionamento")
        el.append(_p(f"M{meio:.1f} {yl:.1f} h{alcance:.1f}", "acionamento"))
        el.append(_p(f"M{meio + alcance*0.15:.1f} {yl - comp*0.22:.1f} "
                     f"h{alcance*0.75:.1f}", "acionamento"))
    else:
        # caixa redutora, e o volante de FRENTE ao lado dela - e assim que o
        # bloco da casa desenha: de frente da para contar os raios
        el += caixa(meio - comp*0.9, comp*1.8, -yl, yl + comp*1.3,
                    classe="acionamento")
        el.append({"tipo": "rect", "x": meio - comp*0.45, "y": yl - comp*0.34,
                   "w": comp*0.9, "h": comp*0.34, "rx": comp*0.12,
                   "classe": "acionamento"})
        cx = meio + comp * 0.9 + alcance / 2
        cy = yl + comp * 0.55
        el.append(_p(f"M{meio + comp*0.9:.1f} {cy:.1f} H{cx - alcance/2:.1f}",
                     "acionamento"))
        el += volante(cx, cy, alcance)
    el.append(_p(f"M-40 0 H{comp+40:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    rot = f'borboleta {dn_pol:g}" {"alavanca" if acionamento == "ALAVANCA" else "caixa"}'
    return _montar("VALVULA_BORBOLETA", rot, el, portas, fonte, {"wafer": True})


def valvula_gaveta(dn_pol):
    """Corpo de fundo abaulado, castelo aparafusado, sobreposta e volante chato.

    Desenhada como o bloco da casa desenha: o volante de canto - chato, com o
    aro nas pontas e a porca da haste em cima; a sobreposta acima da flange do
    castelo; e o corpo com o fundo redondo, que e onde a cunha desce.
    """
    comp, fonte = _cota("VALVULA_GAVETA", dn_pol)
    comp = comp or 230
    alt, _ = _cota("VALVULA_GAVETA", dn_pol, "", "altura_total_mm")
    volante_d, _ = _cota("VALVULA_GAVETA", dn_pol, "", "volante_mm")
    corpo, _ = _cota("VALVULA_GAVETA", dn_pol, "", "d_corpo_mm")
    f = flange(dn_pol)
    corpo = corpo or f["externo"] * 0.62
    alt = alt or corpo * 2.4
    volante_d = volante_d or corpo
    meio = comp / 2
    bocal = DE_TUBO.get(dn_pol, 100)
    r = corpo / 2

    # o corpo: parede reta e fundo abaulado
    el = [_p(f"M0 {-bocal/2:.1f} L{comp*0.22:.1f} {-r:.1f} H{comp*0.78:.1f} "
             f"L{comp:.1f} {-bocal/2:.1f}"),
          _p(f"M0 {bocal/2:.1f} L{comp*0.22:.1f} {r*0.55:.1f} "
             f"Q{comp*0.22:.1f} {r:.1f} {meio:.1f} {r:.1f} "
             f"Q{comp*0.78:.1f} {r:.1f} {comp*0.78:.1f} {r*0.55:.1f} "
             f"L{comp:.1f} {bocal/2:.1f}")]
    # a cunha, tracejada dentro do corpo
    el.append(_p(f"M{meio - bocal*0.3:.1f} {-r*0.42:.1f} h{bocal*0.6:.1f} "
                 f"v{r*0.86:.1f} l{-bocal*0.3:.1f} {r*0.14:.1f} "
                 f"l{-bocal*0.3:.1f} {-r*0.14:.1f} Z", "oculto"))

    # a flange do castelo, com a junta, e a sobreposta em cima dela
    esp = comp * 0.07
    yf = -r
    largura_flange = comp * 0.72
    el.append({"tipo": "rect", "x": meio - largura_flange/2, "y": yf - esp,
               "w": largura_flange, "h": esp, "classe": "corpo"})
    el.append(_p(f"M{meio - largura_flange/2:.1f} {yf:.1f} h{largura_flange:.1f}",
                 "junta"))
    # sobreposta: dois degraus estreitando, e a caixa de gaxeta no topo.
    #
    # A altura dela sai do VAO disponivel - do topo do corpo ao topo do
    # volante - e nao de uma fracao da cota total. Com 44% da cota total a
    # sobreposta passava do volante em bitola grande, e o volante aparecia
    # dentro dela em vez de em cima; a casa pediu ele mais para cima, e o que
    # faltava era justamente sobrar haste livre entre os dois
    y1 = yf - esp
    vao = alt - 2 * r          # do topo do corpo ao topo do volante
    passo = vao * 0.52
    el.append({"tipo": "rect", "x": meio - comp*0.24, "y": y1 - passo*0.55,
               "w": comp*0.48, "h": passo*0.55, "classe": "corpo"})
    el.append({"tipo": "rect", "x": meio - comp*0.17, "y": y1 - passo,
               "w": comp*0.34, "h": passo*0.45, "classe": "corpo"})
    y2 = y1 - passo
    el.append({"tipo": "rect", "x": meio - comp*0.13, "y": y2 - comp*0.11,
               "w": comp*0.26, "h": comp*0.11, "classe": "corpo"})

    # a haste e o volante de canto.
    #
    # altura_total_mm e TOTAL: do fundo do corpo ao topo do volante, nao do
    # eixo para cima. Tratar como se fosse do eixo somava o corpo por baixo e
    # deixava a valvula 29% mais alta que a folha - erro que nao aparece
    # olhando, porque a torre parece proporcional em qualquer bitola.
    # o volante encosta no topo cotado: a porca da haste, que e o que fica mais
    # alto nele, termina la
    topo_volante = -(alt - r)
    yv = topo_volante + comp * 0.055 * 2.1
    el.append(_p(f"M{meio:.1f} {y2 - comp*0.11:.1f} V{yv:.1f}", "haste"))
    el += volante_de_canto(meio, yv, volante_d, comp * 0.055)

    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    el.append(_p(f"M{meio:.1f} {-alt-40:.1f} V{r+40:.1f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("VALVULA_GAVETA", f'gaveta {dn_pol:g}"', el, portas, fonte)


def valvula_hidraulica(dn_pol, serie="47"):
    """Corpo abaulado por baixo e tampa chata aparafusada em cima.

    O bloco da casa nao desenha a tampa como calota: desenha uma tampa CHATA
    e larga, com a cabeca do parafuso aparecendo nas duas pontas - que e o que
    se ve de lado numa valvula de diafragma. Dentro dela o diafragma, e a
    haste descendo ate o obturador.
    """
    comp, fonte = _cota("VALVULA_HIDRAULICA", dn_pol, serie)
    comp = comp or 462
    alt, _ = _cota("VALVULA_HIDRAULICA", dn_pol, serie, "altura_total_mm")
    r = DE_TUBO.get(dn_pol, 100) / 2
    alt = alt or r * 3
    meio = comp / 2
    corpo = r * 1.1
    # como na gaveta: a altura da folha e TOTAL, e o corpo desce abaixo do
    # eixo. Aqui o fundo e a propria parede - a casa tirou a barriga
    fundo = corpo

    # o corpo: reto em cima, abaulado embaixo - a barriga onde o obturador cai
    el = [_p(f"M0 {-corpo:.1f} H{comp:.1f}"),
          _p(f"M0 {corpo:.1f} H{comp:.1f}"),
          _p(f"M0 {-corpo:.1f} V{corpo:.1f}", "malha"),
          _p(f"M{comp:.1f} {-corpo:.1f} V{corpo:.1f}", "malha")]
    # A SEDE, em duas curvas subindo do fundo ate um pico no meio. E por cima
    # dela que a agua passa, e e nela que o obturador assenta - a peca de
    # diafragma nao tem barriga para baixo, tem sede para cima. Cada curva sai
    # do fundo quase na horizontal e chega ao pico ingreme
    pico = -corpo * 0.04
    face = comp * 0.035          # a face da sede, onde o obturador assenta
    for sinal in (-1, 1):
        pe = meio - sinal * comp * 0.31
        alto = meio - sinal * face
        controle = meio - sinal * comp * 0.13
        el.append(_p(f"M{pe:.1f} {corpo:.1f} "
                     f"Q{controle:.1f} {corpo:.1f} {alto:.1f} {pico:.1f}"))
    # as duas curvas se encontram numa FACE e nao numa ponta: e nela que o
    # obturador assenta, e uma ponta nao veda nada
    el.append(_p(f"M{meio - face:.1f} {pico:.1f} H{meio + face:.1f}"))

    # a tampa chata, larga, com o parafuso nas pontas
    tampa = comp * 0.66
    # A TAMPA e uma chapa, nao um bloco: o que e alto na peca de diafragma e a
    # TORRE embaixo dela - a camara onde o diafragma trabalha.
    #
    # E a repartição sai da BANDA LIVRE - o que existe entre o topo do corpo e
    # o topo cotado - e nao de uma fracao da altura total. Assim a torre fica
    # na mesma proporcao em toda bitola: em 3" a banda e 105 mm dos 203 de
    # altura e em 12" e 145 dos 495, e uma fracao da altura total dava torre de
    # 40% da peca em 3" contra 18% em 12". A casa apontou a de 12" como certa,
    # e 0,238 da banda para a tampa e o que a mantem igual.
    banda = max(alt - fundo - corpo, alt * 0.08)
    esp = banda * 0.238
    # -(alt - fundo) e nao -alt: o que a folha cota e a peca inteira, e a
    # barriga desce abaixo do eixo.
    #
    # E a CABECA DO PARAFUSO da tampa e que fica mais alta, nao a tampa: ela
    # sobrava acima da cota, e era so ela que fazia a peca parecer alta. Baixar
    # o conjunto pela altura da cabeca poe o ponto mais alto do desenho no
    # ponto mais alto da folha.
    cabeca = esp * 0.62
    ytampa = -(alt - fundo) + esp + cabeca
    el.append({"tipo": "rect", "x": meio - tampa/2, "y": ytampa - esp,
               "w": tampa, "h": esp, "rx": esp * 0.25, "classe": "corpo"})
    el.append({"tipo": "rect", "x": meio - tampa*0.42, "y": ytampa,
               "w": tampa*0.84, "h": -ytampa - corpo, "classe": "corpo"})
    el += parafusos_de_tampa(meio - tampa*0.45, meio + tampa*0.45,
                             ytampa - esp, esp * 0.62)
    # o diafragma, e a haste descendo ate o obturador
    el.append(_p(f"M{meio - tampa*0.40:.1f} {ytampa + esp*0.55:.1f} "
                 f"h{tampa*0.80:.1f}", "obturador"))
    el.append(_p(f"M{meio:.1f} {ytampa + esp*0.55:.1f} "
                 f"V{pico - corpo*0.22:.1f}", "haste"))
    el.append(_p(f"M{meio - r*0.52:.1f} {pico - corpo*0.22:.1f} "
                 f"h{r*1.04:.1f}", "obturador"))
    # piloto: corpo pequeno ligado a tampa por tubinho - sempre listado junto
    # o piloto fica FORA da torre, nao por cima dela: e peca pendurada na
    # tampa por um tubinho, e sobreposta a torre ele lia como parte do corpo
    px = min(meio + tampa * 0.5 + comp * 0.14, comp - comp * 0.06)
    py = ytampa + esp * 2.6
    el.append(_p(f"M{meio + tampa*0.5:.1f} {ytampa + esp*0.4:.1f} "
                 f"H{px:.1f} V{py:.1f}", "piloto"))
    el += caixa(px - comp*0.07, comp*0.14, -py + comp*0.05, py + comp*0.09,
                classe="piloto")
    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    el.append(_p(f"M{meio:.1f} {ytampa-esp-40:.1f} V{fundo+40:.1f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    return _montar("VALVULA_HIDRAULICA", f'hidráulica {serie}-{dn_pol:g}"',
                   el, portas, fonte)


def medidor(dn_pol):
    """Woltmann: corpo cilindrico, torre e o registrador de tampa articulada.

    O bloco da casa desenha o ombro do corpo entrando na flange, e o
    registrador com a tampa levantada - que e como ele fica quando alguem le,
    e diz tambem de que lado se le, o que importa quando o medidor entra
    encostado numa parede.

    Em cima e embaixo o corpo e reto. A altura sai repartida da folha da ARAD,
    que cota altura_total e altura_abaixo; ver docs/MOTOR.md 4.8 para o que
    altura_abaixo pode e nao pode dizer.
    """
    comp, fonte = _cota("MEDIDOR", dn_pol)
    comp = comp or 350
    alt, _ = _cota("MEDIDOR", dn_pol, "", "altura_total_mm")
    baixo, _ = _cota("MEDIDOR", dn_pol, "", "altura_abaixo_mm")
    largura, _ = _cota("MEDIDOR", dn_pol, "", "largura_mm")
    f = flange(dn_pol)
    bocal_de = DE_TUBO.get(dn_pol, 100)
    # o corpo tem de conter o furo: em 12" largura*0.62 da 303 e o tubo tem
    # 324 de diametro externo, e um corpo mais estreito que o furo nao existe
    corpo = max((largura or f["externo"]) * 0.62, bocal_de * 1.06)
    baixo = baixo or corpo / 2
    alt = alt or corpo * 2
    meio = comp / 2
    # altura_abaixo_mm entra como LIMITE, nao como forma. Em 3" ela vale 90 de
    # 259 e casa com meia largura do corpo; em 12" vale 330 de 505, e usar isso
    # como profundidade do corpo deixaria 13 mm acima do eixo para o
    # registrador - impossivel, porque so o furo da flange ja tem 162 de raio.
    # O que ela e de fato na folha da ARAD nao esta dito; o que se pode afirmar
    # e que o corpo nao passa dela.
    r = corpo / 2
    fundo = min(r, baixo)
    bocal = bocal_de
    # a cintura e o aperto do corpo no eixo do rotor. Ela nao pode ser menor
    # que o furo - a agua passa por ali - nem maior que o corpo. Em bitola
    # grande as duas se encostam e o corpo sai quase reto, que e o que ele e:
    # a ampulheta e feicao de bitola pequena, nao convencao de desenho
    cintura = min(bocal * 0.5, r * 0.97)

    # O corpo e um cilindro RETO de flange a flange, como a casa pediu. O
    # ombro entrando na flange era o que restava da "ampulheta" do bloco dela,
    # e em qualquer bitola ele le como defeito de traco e nao como peca.
    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"),
          _p(f"M0 {fundo:.1f} H{comp:.1f}"),
          _p(f"M0 {-r:.1f} V{fundo:.1f}", "malha"),
          _p(f"M{comp:.1f} {-r:.1f} V{fundo:.1f}", "malha")]
    # o V do fundo, que e onde a sujeira nao para
    # a tampa da camara de medicao, aparafusada no fundo chato - e por ela que
    # o rotor sai para manutencao
    tampa_baixo = comp * 0.44
    recuo_tampa = max(fundo * 0.20, 10.0)
    el += [_p(f"M{meio - tampa_baixo/2:.1f} {fundo:.1f} "
              f"V{fundo - recuo_tampa:.1f}", "malha"),
           _p(f"M{meio + tampa_baixo/2:.1f} {fundo:.1f} "
              f"V{fundo - recuo_tampa:.1f}", "malha"),
           _p(f"M{meio - tampa_baixo/2:.1f} {fundo - recuo_tampa:.1f} "
              f"H{meio + tampa_baixo/2:.1f}", "malha")]

    # A altura acima do eixo e REPARTIDA, nao empilhada: o registrador ocupa
    # o terco de cima, os dois flanges o encosto dele, e a torre o que sobra
    # ate a cintura do corpo. Empilhar cada parte com a sua propria proporcao
    # estourava a cota - o medidor saia 70% mais alto que a folha em toda
    # bitola, e ninguem via porque a torre parecia proporcional ao corpo.
    torre = comp * 0.34
    topo = -(alt - fundo)
    # A faixa livre e o que existe entre o topo do corpo e o topo cotado, e a
    # reparticao sai dela - nao de uma proporcao do comprimento. Em 12" a
    # camara desce 330 mm dos 505 de altura total, sobram 175 acima do eixo e
    # o corpo ja ocupa 162 deles: uma espessura tirada do comprimento poe o
    # flange do registrador 22 mm acima da cota.
    # a faixa livre e do TOPO DO CORPO ao topo cotado. Com o corpo reto quem
    # manda e -r, nao a cintura antiga: usar a cintura deixava a torre
    # apoiada no ar, com um vao entre o mostrador e a peca
    livre = max(-topo - r, alt * 0.10)
    # o registrador ocupa a maior parte do vao livre, e nao metade dele: com
    # metade sobrava um vao de chapa fina entre ele e o corpo, e o mostrador
    # ficava flutuando em cima da peca em vez de assentado nela
    esp = min(torre * 0.13, livre * 0.11)
    caixa_h = livre * 0.66                      # o registrador
    caixa_topo = topo
    caixa_base = topo + caixa_h
    # os dois flanges aparafusados, encostados sob o registrador
    flange_base = caixa_base + esp * 2.4
    el.append({"tipo": "rect", "x": meio - torre/2, "y": flange_base,
               "w": torre, "h": -r - flange_base, "classe": "corpo"})
    for y in (caixa_base + esp * 1.7, caixa_base):
        el.append({"tipo": "rect", "x": meio - torre*0.66, "y": y - esp,
                   "w": torre*1.32, "h": esp, "classe": "corpo"})
        el += parafusos_de_tampa(meio - torre*0.58, meio + torre*0.58,
                                 y - esp, esp*0.7)
    # o registrador, e a tampa levantada
    el.append({"tipo": "rect", "x": meio - torre*0.72, "y": caixa_topo,
               "w": torre*1.44, "h": caixa_h, "rx": esp*0.5,
               "classe": "corpo"})
    # a tampa articulada abre PARA DENTRO da altura cotada: ela levantada e o
    # estado em que alguem le, e nao pode passar da peca
    # a tampa vai da dobradica de um lado ao canto do outro, sem passar da
    # caixa: levantada e o estado em que alguem le, e o desenho nao pode
    # sugerir uma tampa maior que o registrador
    for desvio in (0.0, esp * 0.5):
        el.append(_p(f"M{meio - torre*0.66:.1f} {caixa_topo + desvio:.1f} "
                     f"L{meio + torre*0.62:.1f} "
                     f"{caixa_topo + caixa_h*0.52 + desvio:.1f}",
                     "acionamento"))

    el += placa(0, dn_pol) + placa(comp, dn_pol, lado="saida")
    el.append(_p(f"M-60 0 H{comp+60:.0f}", "centro"))
    el.append(_p(f"M{meio:.1f} {topo - 40:.1f} V{fundo+40:.1f}", "centro"))
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
    el, (sx, sy, direcao), (centro, raio), eixo_linha, paredes = giro(
        0, perna, angulo, dn_pol, sentido, gomos=gomos)
    r = DE_TUBO.get(dn_pol, 100) / 2
    rs = DE_TUBO.get(dn_saida, 60) / 2
    # O bocal sai PARALELO a perna de entrada, na parede externa do ultimo
    # gomo. Montada como o catalogo desenha - entrando por baixo e saindo de
    # lado - a saida aponta para cima, e a ventosa fica em pe sobre a curva.
    # o eixo do bocal e o proprio eixo da perna de entrada, esticado: a
    # ventosa sobe na mesma linha por onde a agua entrou. O bocal nasce onde
    # essa linha atravessa a parede externa do giro.
    parede_fora = paredes[0]
    base = (_atravessa(parede_fora, 0.0) or eixo_linha[-2][0], 0.0)
    haste = DE_TUBO.get(dn_saida, 60) * 2.2
    topo = (base[0] + haste, base[1])
    # cada parede do bocal encosta na chapa do gomo no seu proprio ponto: os
    # dois pes caem em alturas diferentes, que e o que acontece quando se
    # solda um tubo redondo num flanco inclinado
    for sinal in (-1, 1):
        pe = _atravessa(parede_fora, sinal * rs)
        el.append(_p(f"M{pe if pe is not None else base[0]:.1f} "
                     f"{sinal * rs:.1f} H{topo[0]:.1f}"))
    bocal = placa(topo[0], dn_saida, topo[1], lado="saida")
    el += bocal
    el += placa(0, dn_pol)
    saida_fl = placa(sx, dn_pol, sy, lado="saida")
    for e in saida_fl:
        e["girar"] = (direcao, sx, sy)
    el += saida_fl
    el.append(_p(eixo_de(eixo_linha), "centro"))
    el.append(_p(f"M{base[0] - 25:.1f} {base[1]:.1f} H{topo[0] + 30:.1f}",
                 "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol),
              Porta("saida", sx, sy, direcao, dn_pol),
              Porta("derivacao", topo[0], topo[1], 0, dn_saida)]
    return _montar("CURVA_SAIDA",
                   f'curva {angulo}° {dn_pol:g}" c/ saída {dn_saida:g}"',
                   el, portas, fonte)


def valvula_retencao(dn_pol):
    """Wafer de dupla portinhola: corpo estreito, as duas abas e o bujao.

    O face a face vem da ficha MP Valvulas (fig. 160/162), que ja estava em
    data/valvulas_wafer.csv - e a mesma que o motor usa para contar barra
    roscada e comprimento de parafuso.

    O bloco da casa desenha o bujao da mola em cima, e e a unica coisa que
    diferencia a retencao de um anel espacador quando se olha de lado. Fica.
    """
    from . import regras
    ficha = regras.ficha_wafer(dn_pol) or {}
    comp = ficha.get("esp_corpo_mm") or DE_TUBO.get(dn_pol, 100) * 0.6
    f = flange(dn_pol)
    # A e B saem da ficha: o corpo cabe dentro do circulo de furacao, e o
    # furo dele e maior que o do tubo - a valvula nao estrangula a linha
    corpo = ficha.get("d_externo_mm") or f["circulo"] * 0.94
    bocal = ficha.get("d_interno_mm") or DE_TUBO.get(dn_pol, 100)
    meio = comp / 2
    r = corpo / 2
    el = caixa(0, comp, r, r)
    el.append(_p(f"M0 {-bocal/2:.1f} H{comp:.1f} M0 {bocal/2:.1f} H{comp:.1f}",
                 "malha"))
    # as duas portinholas, encostadas no eixo e abrindo para a jusante
    el.append(_p(f"M{meio:.1f} 0 L{comp*0.88:.1f} {-bocal*0.42:.1f}",
                 "obturador"))
    el.append(_p(f"M{meio:.1f} 0 L{comp*0.88:.1f} {bocal*0.42:.1f}",
                 "obturador"))
    el.append(_p(f"M{meio:.1f} {-bocal*0.08:.1f} v{bocal*0.16:.1f}", "haste"))
    # o bujao da mola, no topo
    bujao = comp * 0.5
    el.append({"tipo": "rect", "x": meio - bujao/2, "y": -r - bujao*0.55,
               "w": bujao, "h": bujao*0.55, "classe": "corpo"})
    el.append({"tipo": "rect", "x": meio - bujao*0.32, "y": -r - bujao*0.85,
               "w": bujao*0.64, "h": bujao*0.30, "classe": "corpo"})
    el.append(_p(f"M-40 0 H{comp+40:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    # wafer nao tem flange: ela e abracada pelas flanges das duas pecas
    # vizinhas, e a barra roscada atravessa o conjunto inteiro
    return _montar("VALVULA_RETENCAO", f'retenção wafer {dn_pol:g}"', el, portas,
                   "MP" if ficha else None, {"wafer": True})


def valvula_pe(dn_pol):
    """Retencao de pe com crivo, MP fig. 114 - fundo de poco.

    E uma peca so: o corpo com o obturador em cima e o cesto perfurado
    embaixo. Nao confundir com o crivo AZ, que e so o cesto e vai antes de uma
    retencao separada.
    """
    alt, fonte = _cota("VALVULA_PE", dn_pol, "COM_CRIVO", "altura_total_mm")
    corpo_d, _ = _cota("VALVULA_PE", dn_pol, "COM_CRIVO", "d_corpo_mm")
    alt = alt or 330
    r = DE_TUBO.get(dn_pol, 100) / 2
    raio_corpo = (corpo_d or DE_TUBO.get(dn_pol, 100) * 1.3) / 2
    corpo = alt * 0.42
    cesto = alt - corpo
    # corpo abaulado: sai do cesto, engorda ate o diametro da ficha e fecha
    # na flange
    el = [_p(f"M0 {-r*0.95:.1f} C{corpo*0.3:.1f} {-raio_corpo:.1f} "
             f"{corpo*0.7:.1f} {-raio_corpo:.1f} {corpo:.1f} {-raio_corpo*0.72:.1f}"),
          _p(f"M0 {r*0.95:.1f} C{corpo*0.3:.1f} {raio_corpo:.1f} "
             f"{corpo*0.7:.1f} {raio_corpo:.1f} {corpo:.1f} {raio_corpo*0.72:.1f}")]
    # obturador com haste guiada, fechando contra a sede
    el.append(_p(f"M{corpo*0.34:.1f} {-r*0.62:.1f} L{corpo*0.78:.1f} "
                 f"{-r*0.22:.1f} L{corpo*0.78:.1f} {r*0.22:.1f} "
                 f"L{corpo*0.34:.1f} {r*0.62:.1f}", "obturador"))
    el.append(_p(f"M{corpo*0.78:.1f} 0 H{corpo:.1f}", "haste"))
    # cesto perfurado embaixo, com a chapa lisa no fundo
    parede_cesto = max(r * 0.05, 4.0)
    el += [_p(f"M{-cesto:.1f} {-r*0.95:.1f} H0"),
           _p(f"M{-cesto:.1f} {r*0.95:.1f} H0"),
           # V do SVG e absoluto: sair de -r*0.95 e ir para r*1.9 descia o
           # dobro e a chapa sobrava embaixo da peca. O fim e r*0.95
           _p(f"M{-cesto:.1f} {-r*0.95:.1f} V{r*0.95:.1f}", "chapa_lisa")]
    # A furacao sai do MESMO gerador do crivo AZ, com a MESMA ficha: e a mesma
    # chapa perfurada na obra, e a casa viu os dois lado a lado na folha com o
    # furo de um no dobro do outro. Passar pela ficha do crivo da bitola
    # garante que o furo e o passo sejam iguais nos dois desenhos.
    el += chapa_perfurada(-cesto + parede_cesto, 0.0, r * 0.95,
                          ficha_crivo(dn_pol))[0]
    el += placa(corpo, dn_pol, lado="saida")
    el.append(_p(f"M{-cesto-40:.0f} 0 H{corpo+60:.0f}", "centro"))
    portas = [Porta("saida", corpo, 0, 0, dn_pol)]
    return _montar("VALVULA_PE", f'válvula de pé {dn_pol:g}"', el, portas, fonte)


Posto = namedtuple("Posto", "simbolo dx dy giro entrada saida")
# a reducao chama as pontas de maior e menor; para a linha sao entrada e saida
ENTRADA = ("entrada", "maior")
SAIDA = ("saida", "menor")


# ----------------------------------------------------------------- bomba
_bombas = None


def _pol(texto):
    """2.1/2" -> 2.5"""
    texto = (texto or "").replace('"', "").strip()
    m = re.fullmatch(r"(\d+)\.(\d+)/(\d+)", texto)
    if m:
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    m = re.fullmatch(r"(\d+)/(\d+)", texto)
    if m:
        return int(m.group(1)) / int(m.group(2))
    return float(texto) if texto else None


def ficha_bomba(tamanho, polos=4, cv=None):
    """A linha da bomba na tabela de dimensoes do manual A2744.

    Aceita os dois nomes: 32-200 (dois grupos, como o folheto antigo e o
    manual da Meganorm) e 050-032-200 (tres grupos, como a lista da casa).
    A tabela cota por potencia de motor - sem cv, devolve a menor, que e a
    que o desenho usa como padrao: a cauda do motor nao e cota de tubulacao.
    """
    global _bombas
    if _bombas is None:
        _bombas = {}
        with open(f"{DADOS}/bombas_ksb_megabloc.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                for chave in (r["tamanho"], r["tamanho_folheto"]):
                    _bombas.setdefault((chave, int(r["polos"])), []).append(r)
    linhas = _bombas.get((tamanho, polos))
    if not linhas:
        return None
    if cv is None:
        return min(linhas, key=lambda r: float(r["cv"]))
    return min(linhas, key=lambda r: abs(float(r["cv"]) - cv))


# Carcaca IEC do motor por potencia, para 4 polos 60 Hz. Nao e cota de folheto
# - e a serie que a industria pratica. So serve para ESCOLHER entre as carcacas
# que o folheto lista para aquela bomba, nunca para inventar uma fora da lista.
CARCACA_POR_CV = [(1, 80), (2, 90), (3, 100), (5, 112), (10, 132), (20, 160),
                  (30, 180), (40, 200), (50, 225), (60, 250), (75, 280),
                  (150, 315), (250, 355), (400, 400)]


def carcaca_do_motor(cv):
    for limite, carcaca in CARCACA_POR_CV:
        if cv <= limite:
            return carcaca
    return CARCACA_POR_CV[-1][1]


_motores = None


def ficha_motor(carcaca):
    """As tres medidas do motor da carcaca: eixo, comprimento e corpo.

    A tabela sai de dentro do manual da Megabloc - as colunas que dependem so
    da carcaca sao do motor, e a carcaca IEC e a mesma peca nas duas linhas.
    Ver tools/motores_iec.py.

    Carcaca sem letra (a Meganorm lista '160' e nao '160M') cai na mais curta
    daquele quadro - e a escolha conservadora, porque o motor mais longo e o
    que estoura a base.
    """
    global _motores
    if _motores is None:
        _motores = {}
        with open(f"{DADOS}/motores_iec.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                _motores[r["carcaca"]] = r
    if carcaca in _motores:
        return _motores[carcaca]
    quadro = "".join(c for c in str(carcaca) if c.isdigit())
    if not quadro:
        return None
    mesmos = [f for f in _motores.values() if f["quadro"] == quadro]
    if mesmos:
        return min(mesmos, key=lambda f: float(f["comprimento_mm"]))
    # fora da tabela: o motor cresce com o quadro na mesma proporcao medida
    maior = max(_motores.values(), key=lambda f: float(f["eixo_mm"]))
    fator = float(quadro) / float(maior["eixo_mm"])
    return {"carcaca": str(carcaca), "quadro": quadro, "eixo_mm": quadro,
            "comprimento_mm": f'{float(maior["comprimento_mm"]) * fator:.0f}',
            "corpo_mm": f'{float(maior["corpo_mm"]) * fator:.0f}',
            "pe_mm": f'{float(maior["pe_mm"]) * fator:.0f}',
            "extrapolado": True}


_meganorm = None
_conjunto = None


def ficha_meganorm(tamanho):
    """A linha do tamanho na tabela de medidas da Meganorm (tabela 06)."""
    global _meganorm
    if _meganorm is None:
        with open(f"{DADOS}/bombas_ksb_meganorm.csv", encoding="utf-8") as fh:
            _meganorm = {r["tamanho"]: r for r in csv.DictReader(fh)}
    return _meganorm.get(tamanho)


def carcacas_meganorm(tamanho):
    """As carcacas de motor que o folheto monta nessa bomba, e a base."""
    global _conjunto
    if _conjunto is None:
        _conjunto = {}
        with open(f"{DADOS}/bombas_ksb_meganorm_conjunto.csv",
                  encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                _conjunto.setdefault(r["tamanho"], []).append(r)
    return _conjunto.get(tamanho, [])


def _escolher_carcaca(tamanho, cv):
    """A carcaca do folheto mais proxima da que a potencia pede.

    Se a bomba nao esta na secao 15, devolve (None, None) e quem chama usa
    proporcao - o desenho marca isso na fonte.
    """
    opcoes = carcacas_meganorm(tamanho)
    if not opcoes:
        return None, None
    def numero(texto):
        return float(re.sub(r"[^0-9]", "", texto) or 0)
    alvo = carcaca_do_motor(cv) if cv else None
    if alvo is None:
        escolhida = opcoes[len(opcoes) // 2]
    else:
        escolhida = min(opcoes, key=lambda r: abs(numero(r["carcaca_motor"]) - alvo))
    return numero(escolhida["carcaca_motor"]), escolhida


def tamanho_meganorm(nome):
    """METN 150-125-400 e o tamanho 125-400 do folheto.

    O codigo da lista tem tres grupos - succao, recalque, rotor - e o folheto
    nomeia com dois, porque a succao ja esta na tabela. Aceita os dois.
    """
    partes = nome.split("-")
    if len(partes) == 3:
        return f"{int(partes[1])}-{int(partes[2])}"
    if len(partes) == 2:
        return f"{int(partes[0])}-{partes[1]}"
    raise ValueError(f"nome de Meganorm nao reconhecido: {nome}")


def _corpo_bomba(a, b, c, rotor, dn1, dn2, dreno=True, pe_base=None,
                 largura_folha=None):
    """A parte hidraulica: bocal de succao, carcaca e pescoco da descarga.

    E a mesma nas duas linhas - Megabloc e Meganorm dividem a ponta molhada, e
    e por isso que so muda o que vem depois da carcaca: na monobloco o motor
    encosta na voluta, na mancalizada entra mancal, luva e motor sobre a base.

    Vista de lado a voluta e estreita e alta: o caracol esta no plano
    perpendicular ao eixo, entao de lado aparece de canto. O circulo grande e
    a terceira vista do folheto, olhando pelo eixo.
    """
    r1 = DE_TUBO.get(dn1, 100) / 2
    r2 = DE_TUBO.get(dn2, 80) / 2
    # O caracol e GRANDE - no desenho do fabricante ele e quase da altura do
    # motor e desce quase ate a base, com pe proprio. Em 1,15 do raio do rotor
    # ele saia um caroco no meio do conjunto. O teto e b: o caracol nao passa
    # da base, senao a peca fura o chao.
    rv = min(rotor * 0.69, b * 0.86)
    # A largura AXIAL do caracol. Em 0,42 do rotor ela saia desproporcional -
    # um caracol de 105 mm carregando uma boca de 152 de furo, com o pescoco
    # mais largo que a peca que o sustenta. O piso agora e a propria boca: o
    # caracol nao pode ser mais estreito do que ela pede. E o teto e o vao
    # ate a face de succao, senao o caracol engole o bocal de entrada.
    # A largura e o diametro do caracol saem MEDIDOS no desenho de fabrica que
    # a casa mandou (METB 125-80-315): 206 mm de largura e 435 de diametro para
    # um rotor de 315, ou 0,65 e 1,38 do rotor. Antes eram 0,95 e 1,85 - chute,
    # e o caracol saia gordo e alto demais. O piso continua sendo a boca: ela
    # nao pode ser mais larga que o caracol que a sustenta.
    # a GSD passa a largura MEDIDA na folha dela - 2 x (f1 - f2). Onde nao ha
    # folha que a cote, ela sai da proporcao do desenho de fabrica (0,65 do
    # rotor), com a boca como piso
    largura = largura_folha or max(rotor * 0.65, 2 * r2 * 0.90)
    # O caracol e CENTRADO na boca de descarga, que fica em c - o a do folheto,
    # face de succao ate o eixo da descarga. O motor comeca depois dele, e nao
    # no eixo: a casa disse, e o desenho de fabrica mostra. Ver 4.13 para o que
    # isso deixa em aberto no comprimento total.
    x0, x1 = c - largura / 2, c + largura / 2
    # A BOCA DA DESCARGA fica em c, que e onde o folheto a coloca, e nao no
    # meio do caracol. Duas medidas mandam nisso e as duas conferem:
    #
    #   c + l bate com o bloco da casa em 0,1% (951 contra 949,7), o que fixa a
    #   face de tras do caracol em c - e ali que o flange do motor aparafusa;
    #   com a boca em c a flange dela cai em 20..300 e nao avanca da face de
    #   succao, o que e o que o proprio c de 160 mm implica.
    #
    # Entao o caracol e assimetrico de proposito: a face de tras e chata,
    # porque e o flange do motor, e a boca sobe da parte da frente. Tentar
    # centrar a boca no caracol fazia a flange dela recuar 45 mm atras da face
    # de succao, o que nenhuma bomba faz.
    xd = (x0 + x1) / 2

    el = list(placa(0, dn1, lado="entrada"))
    # A SUCCAO abre em sino para dentro do caracol, e nao entra como tubo reto:
    # e fundicao, e a boca cresce do furo do flange ate a tampa do caracol.
    boca = min(rv * 0.62, r1 * 1.7)
    el += [_polilinha([(0, -r1), (x0 * 0.42, -r1), (x0, -boca)]),
           _polilinha([(0, r1), (x0 * 0.42, r1), (x0, boca)])]
    # O caracol e ARREDONDADO, como a casa pediu: peca fundida, e onde o rotor
    # gira o corpo acompanha o circulo dele. De canto isso e uma capsula - meio
    # circulo em cima, meio circulo embaixo - e nao uma caixa de quinas vivas.
    el.append({"tipo": "rect", "x": x0, "y": -rv, "w": largura, "h": 2 * rv,
               "rx": largura * 0.5, "classe": "corpo"})
    # a junta entre a tampa de succao e o corpo do caracol
    el.append(_p(f"M{x0 + largura*0.28:.1f} {-rv*0.92:.1f} V{rv*0.92:.1f}",
                 "malha"))
    # o rotor: o segundo numero do nome e o diametro nominal dele. De lado o
    # rotor e um disco de canto - uma linha, nao um circulo. O circulo so
    # aparece na vista que olha pelo eixo, que nao e esta.
    el.append(_p(f"M{xd:.1f} {-rotor/2:.1f} V{rotor/2:.1f}", "centro"))
    # O pescoco da descarga AFUNILA da flange para o caracol, e nao desce em
    # duas paredes retas. A boca de 6" tem 152 mm de furo e o caracol tem 84 de
    # largura axial: vista de lado a boca E mais larga que o caracol, e o
    # pescoco fecha nele. Duas verticais diziam que os dois tinham a mesma
    # largura, o que nao e verdade em bitola nenhuma.
    # o pescoco morre no TOPO do caracol, nao dentro dele: com o caracol na
    # altura certa, terminar em 0,72 rv punha a parede do pescoco atravessando
    # a propria peca que ela alimenta
    el += [_polilinha([(xd - r2, -a), (x0 + largura * 0.10, -rv * 0.92)]),
           _polilinha([(xd + r2, -a), (x1 - largura * 0.10, -rv * 0.92)])]
    el += placa(xd, dn2, y=-a, direcao=-90, lado="saida")
    # a junta aparafusada entre o caracol e o flange do motor: e ela que faz a
    # monobloco ser monobloco, e no desenho do fabricante ela aparece
    el.append({"tipo": "rect", "x": x1 - largura * 0.09, "y": -rv * 0.86,
               "w": largura * 0.09, "h": rv * 1.72, "classe": "flange"})
    el += parafusos_de_tampa(x1 - largura * 0.045, x1 - largura * 0.045,
                             -rv * 0.86, largura * 0.09)
    if dreno:
        # o bujao de dreno, no ponto baixo do caracol
        el.append({"tipo": "rect", "x": xd - largura * 0.10, "y": rv,
                   "w": largura * 0.20, "h": rv * 0.10, "classe": "corpo"})
    # o sentido do fluxo: entra pelo eixo, sai por cima. E a informacao que
    # decide de que lado a reducao excentrica leva o lado plano.
    # A seta da succao vai DENTRO da carcaca, nao no toco de entrada. Num
    # monobloco o toco e curto - a flange aparafusa quase direto na tampa - e
    # com o caracol na largura certa nao sobra tubo para a seta: ela acabava
    # atras da face de succao, do lado de fora da peca.
    el.append(_seta(x0 + largura * 0.30, 0, 0, min(r1 * 0.38,
                                                   largura * 0.22)))
    el.append(_seta(xd, -(rv + a) / 2, -90, r2 * 0.42))
    # O PE DO CARACOL desce ABERTO ate a base - e fundicao, e alarga para
    # apoiar. No desenho do fabricante ele e a peca que segura a bomba, e um
    # retangulo estreito nao diz isso.
    if pe_base is not None and pe_base > rv:
        topo_pe = rv * 0.94
        el.append(_polilinha([(x0 + largura * 0.30, topo_pe),
                              (x0 + largura * 0.12, pe_base),
                              (x1 - largura * 0.12, pe_base),
                              (x1 - largura * 0.30, topo_pe)]))
        el.append({"tipo": "rect", "x": x0 + largura * 0.06, "y": pe_base,
                   "w": largura * 0.88, "h": max(rv * 0.05, 8.0),
                   "classe": "corpo"})
    return el, x0, x1, rv, largura, xd


def _seta(x, y, direcao, tamanho):
    """Ponta de seta cheia, para o sentido do fluxo."""
    rad = math.radians(direcao)
    dx, dy = math.cos(rad) * tamanho, math.sin(rad) * tamanho
    nx, ny = -dy * 0.55, dx * 0.55
    return _p(f"M{x+dx:.1f} {y+dy:.1f} L{x-dx+nx:.1f} {y-dy+ny:.1f} "
              f"L{x-dx-nx:.1f} {y-dy-ny:.1f} Z", "fluxo")


def _eixo_da_bomba(x_inicio, x_fim, d_eixo, y=0.0):
    """O eixo da bomba, visto de lado: duas linhas ate a ponta."""
    r = d_eixo / 2
    return [_p(f"M{x_inicio:.1f} {-r:.1f} H{x_fim:.1f}", "malha"),
            _p(f"M{x_inicio:.1f} {r:.1f} H{x_fim:.1f}", "malha")]


def _ponta_de_eixo(x, comprimento, d1, u, t):
    """A ponta do eixo com o rasgo de chaveta, cotada na folha (d1, l, u, t).

    E o que a luva elastica aperta - a unica parte da bomba que o montador
    mede com paquimetro.
    """
    r = d1 / 2
    topo = t - d1                       # quanto a chaveta sobe acima do eixo
    return [_p(f"M{x:.1f} {-r:.1f} H{x+comprimento:.1f}"),
            _p(f"M{x:.1f} {r:.1f} H{x+comprimento:.1f}"),
            _p(f"M{x+comprimento:.1f} {-r:.1f} V{r:.1f}"),
            {"tipo": "rect", "x": x + comprimento * 0.18,
             "y": -r - topo, "w": comprimento * 0.6, "h": topo + u * 0.3,
             "classe": "corpo"}]


def _motor(x, carcaca, base_y=None, comprimento=None):
    """O motor IEC visto de lado, na medida da carcaca.

    O que faz um motor de 60 CV parecer um motor de 60 CV nao e proporcao: e
    a carcaca. A 225 tem 880 mm de corpo e 356 de diametro; a 90L tem 399 e
    140. Sao numeros da folha, e a diferenca aparece no papel.

    Quina arredondada porque carcaca de motor e fundida, nao dobrada - e o
    unico canto vivo dela e o da caixa de ligacao.

    Devolve (elementos, x do fim, ficha da carcaca).
    """
    ficha = ficha_motor(carcaca) or {}
    # comprimento entra de fora quando a folha da bomba cota o motor dela: a
    # GSD cota L2, o corpo do motor, e nao o mesmo numero que a KSB chama de l
    comp = float(comprimento or ficha.get("comprimento_mm") or 400)
    corpo = float(ficha.get("corpo_mm") or 160)
    eixo = float(ficha.get("eixo_mm") or 100)
    r = corpo / 2
    raio = corpo * 0.09                 # a quina da carcaca
    tampa = comp * 0.13                 # a tampa do ventilador
    caixa = corpo * 0.30                # a caixa de ligacao, em cima

    el = [{"tipo": "rect", "x": x, "y": -r, "w": comp - tampa, "h": corpo,
           "rx": raio, "classe": "corpo"}]
    # as aletas de refrigeracao, ao longo do corpo
    for k in range(1, 10):
        xa = x + (comp - tampa) * k / 10
        el.append(_p(f"M{xa:.1f} {-r + raio*0.5:.1f} v{corpo - raio:.1f}",
                     "malha"))
    # a caixa de ligacao e a tampa do ventilador
    el.append({"tipo": "rect", "x": x + (comp - tampa) * 0.30, "y": -r - caixa * 0.55,
               "w": caixa * 1.5, "h": caixa * 0.55, "rx": raio * 0.5,
               "classe": "corpo"})
    el.append({"tipo": "rect", "x": x + comp - tampa, "y": -r * 0.74,
               "w": tampa, "h": corpo * 0.74, "rx": raio * 0.6,
               "classe": "corpo"})
    if base_y is not None:
        # os pes: do corpo ate a base, na altura que a carcaca manda
        altura = base_y - r
        for xp in (x + (comp - tampa) * 0.16, x + (comp - tampa) * 0.68):
            el.append({"tipo": "rect", "x": xp, "y": r,
                       "w": (comp - tampa) * 0.16, "h": max(altura, 1),
                       "classe": "corpo"})
    return el, x + comp, ficha


def bomba_megabloc(tamanho, montagem="HORIZONTAL", polos=4, cv=None):
    """A KSB Megabloc (METB), monobloco, vista de lado - a ancora do desenho.

    Tres cotas do folheto colocam os dois bocais, e sao elas que a tubulacao
    precisa: a (do eixo a face do flange de descarga), b (da base ao eixo) e
    c (da face da succao ao eixo da descarga). O corpo em volta sai da
    nomenclatura - no nome 32-200 o 200 e o diametro nominal do rotor - e da
    carcaca IEC h do motor, que encosta direto na voluta: e isso que faz dela
    monobloco e nao mancalizada.

    A peca e a MESMA nas duas montagens - o que muda e a pose. Montada na
    vertical, a bomba e a mesma fundicao de pe: o motor em cima, a succao
    entrando por baixo. Aqui a vertical e so girada -90, do mesmo jeito que a
    folha desenha a curva em pe; na linha a montagem sai sozinha de onde a
    bomba cai na corrente, porque a direcao chega acumulada.
    """
    ficha = ficha_bomba(tamanho, polos, cv)
    if not ficha:
        raise ValueError(f"{tamanho} nao esta na tabela de dimensoes A2744")
    c = float(ficha["a_mm"])            # face da succao -> eixo da descarga
    a = float(ficha["h2_mm"])           # eixo -> face do flange de descarga
    b = float(ficha["h1_mm"])           # eixo -> base
    h = float(ficha["h_mm"])            # carcaca IEC do motor
    dn1 = _pol(ficha["dn_succao_pol"])
    dn2 = _pol(ficha["dn_recalque_pol"])
    rotor = float(ficha["tamanho"].split("-")[2].split(".")[0])

    el, x0, x1, rv, largura, xd = _corpo_bomba(a, b, c, rotor, dn1, dn2,
                                               pe_base=b - 22)
    # monobloco nao tem lanterna: o flange do motor aparafusa na tampa de tras
    # da voluta, e o eixo do motor E o eixo da bomba. O comprimento total sai
    # de a + l, e e isso que o DXF da casa mede - 951 contra 949,7 na
    # 150-250 de 50 CV. Eu tinha posto uma lanterna aqui, que e peca da
    # mancalizada, e a bomba saia 240 mm mais longa do que e.
    x_motor = x1
    el += _eixo_da_bomba(x1 - largura * 0.3, x_motor, h * 0.20)
    motor, fim, ficha_m = _motor(x_motor, ficha["carcaca_motor"], base_y=b - 22)
    el += motor
    el.append({"tipo": "nota", "x": (x_motor + fim) / 2,
               "y": -float(ficha_m.get("corpo_mm") or h * 2) / 2 - h * 0.40,
               "texto": f'carcaça {ficha["carcaca_motor"]} · '
                        f'{float(ficha["cv"]):g} CV'})
    # o pe da voluta e a base, no nivel que b manda. Os pes do motor ja vem
    # do proprio motor, na altura da carcaca
    el.append({"tipo": "rect", "x": x0, "y": b - 22, "w": fim - x0 + 20,
               "h": 22, "classe": "corpo"})
    el.append(_p(f"M-70 0 H{fim+40:.0f}", "centro"))
    el.append(_p(f"M{xd:.1f} {-a-40:.1f} V{rv+30:.1f}", "centro"))
    el += _letras_bomba(a, b, c, rv, x0, x_direita=x1 + h * 0.30)

    portas = [Porta("entrada", 0, 0, 180, dn1),
              Porta("saida", xd, -a, -90, dn2)]
    nome = ficha["tamanho_folheto"]
    simbolo = _montar("BOMBA", f'KSB Megabloc {nome} {dn1:g}"×{dn2:g}"',
                      el, portas, "KSB",
                      {"tamanho": nome, "montagem": montagem, "polos": polos,
                       "eixo_mm": b, "norma_flange": ficha["norma_flange"],
                       "carcaca_motor": ficha["carcaca_motor"],
                       "cv": float(ficha["cv"]), "peso_kg": ficha["peso_kg"]})
    if montagem == "VERTICAL":
        simbolo = girado(simbolo, -90)
        simbolo = simbolo._replace(
            rotulo=f'KSB Megabloc {nome} vertical {dn1:g}"×{dn2:g}"')
    return simbolo


def _letras_bomba(a, b, c, rv, x0, letras=("a", "b", "c"), x_direita=None):
    """As tres cotas escritas com a letra do folheto, so texto e em cinza.

    Sao as mesmas tres medidas nas duas linhas, com nome diferente em cada
    folha: a Megabloc chama a/b/c e a Meganorm, que segue a EN 733, chama
    h2/h1/a. O desenho escreve a letra da folha de onde a cota veio.
    """
    lado = x_direita if x_direita is not None else c + rv * 0.9
    return [{"tipo": "nota", "x": lado, "y": -(a + rv) / 2,
             "texto": f"{letras[0]} {a:.0f}"},
            {"tipo": "nota", "x": lado, "y": (b + rv) / 2,
             "texto": f"{letras[1]} {b:.0f}"},
            {"tipo": "nota", "x": c / 2, "y": -rv - 30,
             "texto": f"{letras[2]} {c:.0f}"}]


_gsd = None
_motores_gsd = None


_potencias_gsd = None


def carcaca_gsd(cv, polos=4):
    """A carcaca que a propria folha da GSD pede para essa potencia.

    Precisa dela porque a folha NOMEIA a carcaca do jeito dela - L112M, 132M,
    225S/M - e e por esse nome que a tabela de motor da mesma folha esta
    indexada. carcaca_do_motor() devolve "160" e "200", que nao casam.
    """
    global _potencias_gsd
    if _potencias_gsd is None:
        with open(f"{DADOS}/potencias_gsd.csv", encoding="utf-8") as fh:
            _potencias_gsd = [(float(r["cv"]), r["carcaca_2p"], r["carcaca_4p"])
                              for r in csv.DictReader(fh)]
    if cv is None:
        return None
    coluna = 2 if polos >= 4 else 1
    for potencia, dois, quatro in _potencias_gsd:
        if cv <= potencia:
            return (quatro if coluna == 2 else dois) or dois or quatro
    return _potencias_gsd[-1][coluna] or None


def ficha_motor_gsd(carcaca, grupo="GSD/230"):
    """O motor da GSD, com o PESCOCO que a folha cota.

    A folha da 406.1 cota o motor em duas medidas: L2 e o corpo dele e L1 e o
    total dele com o pescoco que liga no caracol. A diferenca e o pescoco - 110
    mm na carcaca 71, 134 na 90, 155 na 132, 185 no grupo /230 e 230 no /250 -
    e e por isso que o motor da GSD nao encosta na voluta como o da Megabloc
    encosta. Ele chega por um pescoco mais fino que o corpo.

    A folha da L1 em duas colunas, para os suportes 230 e 250. O grupo 240 nao
    tem coluna propria: aqui ele usa a do 230, e o params da peca marca
    pescoco_da_folha=False para quem for conferir saber.
    """
    global _motores_gsd
    if _motores_gsd is None:
        with open(f"{DADOS}/motores_gsd.csv", encoding="utf-8") as fh:
            _motores_gsd = {}
            for r in csv.DictReader(fh):
                _motores_gsd.setdefault(r["carcaca"], {}).update(
                    {k: v for k, v in r.items() if v})
    ficha = dict(_motores_gsd.get(str(carcaca)) or {})
    if not ficha:
        # a carcaca vizinha serve: o pescoco anda com o TAMANHO da carcaca e
        # com o grupo do suporte, nao com a letra dela - a 160L usa o mesmo
        # pescoco da 160M. Sem isto a 160L, a L160L e a 200M ficariam sem
        # pescoco so porque a linha delas na folha veio incompleta
        def numero(nome):
            digitos = "".join(ch for ch in nome if ch.isdigit())
            return float(digitos) if digitos else 0.0
        alvo_n = numero(str(carcaca))
        vizinhas = sorted(_motores_gsd, key=lambda n: abs(numero(n) - alvo_n))
        ficha = dict(_motores_gsd.get(vizinhas[0]) or {}) if vizinhas else {}
        if not ficha:
            return None
        ficha["carcaca_vizinha"] = vizinhas[0]
    coluna = "L1_250_mm" if grupo == "GSD/250" else "L1_230_mm"
    l2 = float(ficha.get("L2_mm") or 0)
    l1 = float(ficha.get(coluna) or ficha.get("L1_250_mm")
               or ficha.get("L1_230_mm") or 0)
    ficha["corpo_axial_mm"] = l2
    ficha["pescoco_mm"] = max(l1 - l2, 0.0)
    ficha["pescoco_da_folha"] = grupo in ("GSD/230", "GSD/250")
    return ficha


def ficha_gsd(modelo):
    """A folha dimensional da GSD - desenho 406.1 da EBARA, folha 2.

    A folha tem celula mesclada, e o que sai dela esta em data/bombas_gsd.csv
    com as guardas que tools/extrair_gsd.py aplica. Ver docs/MOTOR.md 4.14.
    """
    global _gsd
    if _gsd is None:
        with open(f"{DADOS}/bombas_gsd.csv", encoding="utf-8") as fh:
            _gsd = {r["modelo"]: r for r in csv.DictReader(fh)}
    return _gsd.get(modelo)


def gsd_para_linha(dn_pol):
    """A GSD cuja descarga tem a bitola pedida - a mesma regra da KSB.

    A folha para em DN150 de recalque; acima disso devolve a maior que existe,
    porque a linha de 12" e de 14" nao tem GSD do proprio bocal.
    """
    from .bomba import MM_PARA_POLEGADA
    ficha_gsd("32-160")
    def rotor(m):
        return float(m.split("-")[1].rstrip("L").split(".")[0])
    candidatas = [m for m, r in _gsd.items()
                  if MM_PARA_POLEGADA.get(float(r["dn2_mm"])) == dn_pol]
    if candidatas:
        # a menor de cada bitola: e a que a linha pede primeiro
        return min(candidatas, key=rotor)
    maior = max((float(r["dn2_mm"]) for r in _gsd.values()), default=0)
    acima = [m for m, r in _gsd.items() if float(r["dn2_mm"]) == maior]
    return min(acima, key=rotor, default=None)


def cv_da_gsd(modelo):
    """Uma potencia plausivel para o modelo, pela bitola de recalque dele.

    A folha dimensional nao cota potencia por modelo - a tabela de CV dela e
    por carcaca de motor, nao por bomba. Isso e proporcao, e a tarja diz.
    """
    ficha = ficha_gsd(modelo) or {}
    dn2 = float(ficha.get("dn2_mm") or 80)
    return {32: 15.0, 40: 20.0, 50: 30.0, 65: 40.0, 80: 50.0, 100: 60.0,
            125: 75.0, 150: 100.0}.get(int(dn2), 30.0)


def bomba_gsd(modelo, cv=None, montagem="HORIZONTAL"):
    """A EBARA GSD, monobloco, pela folha dimensional dela.

    E a terceira linha de bomba do desenho, e a ponta molhada e a mesma coisa
    das outras duas - por isso ela reusa _corpo_bomba inteiro. O que muda sao
    as letras da folha:

        h1  eixo -> base                (o b das KSB)
        h2  eixo -> face do flange de descarga   (o a das KSB)
        f1  face da succao -> face do flange do lado do motor
        f2  face da succao -> eixo da descarga

    As duas leem direto na folha 1, onde a linha de cota do f2 morre no eixo da
    descarga e a do f1 na face do flange de tras. Eu tinha inferido f1 - f2
    para o eixo da descarga; a folha 1 diz que e o f2 sozinho.

    Isso amarra o caracol inteiro sem chute: ele e centrado no eixo da descarga
    (f2) e a face de tras dele cai em f1, entao a largura e 2 x (f1 - f2). A
    folha se confere sozinha nisso - a frente do caracol cai em 27, 27 e 32 mm
    da face de succao nos tres grupos de suporte, que e a espessura do flange
    de succao mais uma folga. Tres grupos independentes chegando no mesmo
    numero nao e coincidencia.

    O rotor sai do nome, como nas KSB: na GSD 125-250 o 250 e o rotor.
    """
    ficha = ficha_gsd(modelo)
    if not ficha:
        raise ValueError(f"GSD {modelo} nao esta na folha dimensional 406.1")
    from .bomba import MM_PARA_POLEGADA
    dn1 = MM_PARA_POLEGADA.get(float(ficha["dn1_mm"]))
    dn2 = MM_PARA_POLEGADA.get(float(ficha["dn2_mm"]))
    if dn1 is None or dn2 is None:
        raise ValueError(f"GSD {modelo}: bocal fora da tabela de bitola")
    a = float(ficha["h2_mm"])
    b = float(ficha["h1_mm"])
    f1 = float(ficha["f1_mm"])
    c = float(ficha["f2_mm"])            # face da succao -> eixo da descarga
    rotor = float(modelo.split("-")[1].rstrip("L").split(".")[0])
    carcaca = carcaca_gsd(cv) or f"{carcaca_do_motor(cv or 30):g}"

    # o caracol da GSD tem largura de folha: 2 x (f1 - f2), com a face de tras
    # caindo em f1 - e ali que o pescoco do motor comeca
    el, x0, x1, rv, largura, xd = _corpo_bomba(
        a, b, c, rotor, dn1, dn2, pe_base=b - 22,
        largura_folha=2 * max(f1 - c, DE_TUBO.get(dn2, 80) * 0.45))
    # A GSD nao encosta o motor no caracol: entre os dois vai um PESCOCO mais
    # fino, e a folha cota ele - L1 menos L2. E o que separa esta linha das
    # duas KSB, onde o flange do motor aparafusa direto na tampa de tras.
    grupo = ficha.get("grupo_suporte") or "GSD/230"
    fm = ficha_motor_gsd(carcaca, grupo) or {}
    pescoco = float(fm.get("pescoco_mm") or 0)
    corpo_axial = float(fm.get("corpo_axial_mm") or 0) or None
    r_pescoco = rv * 0.34
    if pescoco:
        el += [_p(f"M{x1:.1f} {-r_pescoco:.1f} H{x1 + pescoco:.1f}"),
               _p(f"M{x1:.1f} {r_pescoco:.1f} H{x1 + pescoco:.1f}"),
               # a nervura do pescoco, que e onde ele agarra no flange
               _p(f"M{x1 + pescoco*0.30:.1f} {-r_pescoco:.1f} "
                  f"V{r_pescoco:.1f}", "malha")]
    x_motor = x1 + pescoco
    el += _eixo_da_bomba(x1 - largura * 0.3, x_motor, rv * 0.20)
    motor, fim, ficha_m = _motor(x_motor, carcaca, base_y=b - 22,
                                 comprimento=corpo_axial)
    el += motor
    rotulo_motor = f"carcaça {carcaca}"
    if cv:
        rotulo_motor += f" · {cv:g} CV"
    el.append({"tipo": "nota", "x": (x_motor + fim) / 2,
               "y": -float(ficha_m.get("corpo_mm") or rv * 2) / 2 - rv * 0.30,
               "texto": rotulo_motor})
    el.append({"tipo": "rect", "x": x0, "y": b - 22, "w": fim - x0 + 20,
               "h": 22, "classe": "corpo"})
    el.append(_p(f"M-70 0 H{fim+40:.0f}", "centro"))
    el.append(_p(f"M{xd:.1f} {-a-40:.1f} V{rv+30:.1f}", "centro"))
    el += _letras_bomba(a, b, c, rv, x0, letras=("h2", "h1", "f1-f2"),
                        x_direita=x1 + rv * 0.30)
    portas = [Porta("entrada", 0, 0, 180, dn1),
              Porta("saida", xd, -a, -90, dn2)]
    peca = _montar("BOMBA", f'EBARA GSD {modelo} {dn1:g}"×{dn2:g}"', el, portas,
                   "EBARA",
                   {"linha": "GSD", "modelo": modelo, "cv": cv,
                    "carcaca_motor": carcaca, "grupo_suporte":
                    ficha.get("grupo_suporte"),
                    "pescoco_mm": pescoco or None,
                    "pescoco_da_folha": fm.get("pescoco_da_folha"),
                    "norma_flange": "NBR PN16"})
    return girado(peca, -90) if montagem == "VERTICAL" else peca


def bomba_meganorm(nome, cv=None, montagem="HORIZONTAL"):
    """A KSB Meganorm (METN), mancalizada, sobre base perfilada.

    Mesma ponta molhada da Megabloc e o mesmo arranjo de bocais - succao axial,
    descarga para cima. O que muda vem depois da voluta: em vez de o motor
    encostar no corpo, entram o mancal, a luva elastica e o motor, os tres
    aparafusados numa base unica. Por isso a lista tem codigo "C/BASE
    S/MOTOR" e codigo "MANCAL" - sao pecas separadas de verdade.

    A Meganorm e normalizada (EN 733 / ISO 2858), entao as letras sao as da
    norma e nao as do fabricante. Sao as mesmas tres medidas da Megabloc com
    outro nome, e o proprio numero confirma isso em 26 dos 28 tamanhos que as
    duas linhas tem em comum:

        Meganorm a  = Megabloc c   da face da succao ao eixo da descarga
        Meganorm h1 = Megabloc b   do eixo a base
        Meganorm h2 = Megabloc a   do eixo a face do flange de descarga

    E a Meganorm cota uma quarta que a Megabloc nao tem: f, do eixo da
    descarga ao fim do mancal - o comprimento real da bomba sem o motor.
    """
    from .bomba import MM_PARA_POLEGADA
    tamanho = tamanho_meganorm(nome)
    ficha = ficha_meganorm(tamanho)
    if not ficha:
        raise ValueError(f"{tamanho} nao esta na tabela de medidas da Meganorm")
    rotor = float(ficha["rotor_mm"])
    dn1_mm, dn2_mm = float(ficha["dn1_mm"]), float(ficha["dn2_mm"])
    dn1 = MM_PARA_POLEGADA.get(dn1_mm)
    dn2 = MM_PARA_POLEGADA.get(dn2_mm)
    if dn1 is None or dn2 is None:
        raise ValueError(f"{tamanho}: bocal fora da tabela de bitola da casa")
    c = float(ficha["a_mm"])            # face da succao -> eixo da descarga
    a = float(ficha["h2_mm"])           # eixo -> face do flange de descarga
    b = float(ficha["h1_mm"])           # eixo -> base
    f = float(ficha["f_mm"])            # eixo da descarga -> fim do mancal

    carcaca, linha_conjunto = _escolher_carcaca(tamanho, cv)
    proporcao = carcaca is None
    if proporcao:
        # sem a secao 15 nao ha carcaca listada: cai na que a potencia pede
        carcaca = float(carcaca_do_motor(cv or 50))

    el, x0, x1, rv, largura, xd = _corpo_bomba(a, b, c, rotor, dn1, dn2,
                                               pe_base=b - 24)
    # o mancal: do fim da voluta ate o f do folheto, escalonado
    fim_mancal = c + f
    caixa_mancal = max(fim_mancal - x1, largura * 0.4)
    # O MANCAL tem corpo: no desenho do fabricante e uma fundicao cheia, alta
    # junto do caracol e descendo em rampa ate a ponta do eixo - nao um tubo
    # escalonado. E ele que carrega o rotor em voadico, e a massa dele e o que
    # se ve de lado.
    alto, baixo_m = rv * 0.60, rv * 0.42
    rampa = [(x1, -alto), (x1 + caixa_mancal * 0.34, -alto),
             (x1 + caixa_mancal * 0.56, -baixo_m), (fim_mancal, -baixo_m)]
    el.append(_polilinha(rampa))
    el.append(_polilinha([(x, -y) for x, y in rampa]))
    el.append(_p(f"M{fim_mancal:.1f} {-baixo_m:.1f} V{baixo_m:.1f}"))
    # a junta aparafusada com o caracol, e a tampa do rolamento na outra ponta
    el.append(_p(f"M{x1 + caixa_mancal*0.09:.1f} {-alto:.1f} V{alto:.1f}",
                 "malha"))
    el.append(_p(f"M{fim_mancal - caixa_mancal*0.10:.1f} {-baixo_m:.1f} "
                 f"V{baixo_m:.1f}", "malha"))
    # o pe: a folha cota w do eixo da descarga ate ele, e m1 entre os furos.
    # w + v = f em 43 dos 43 tamanhos, entao os dois partem o f a partir do
    # eixo da descarga - e por isso da para posicionar o pe sem inventar.
    w = float(ficha["w_mm"] or 0) or (f * 0.7)
    m1 = float(ficha["m1_mm"] or 0) or (largura * 0.9)
    g2 = float(ficha["g2_mm"] or 0) or 12.0
    s1 = float(ficha["s1_mm"] or 0) or 14.0
    x_pe = c + w
    el.append({"tipo": "rect", "x": x_pe - m1 / 2 - s1, "y": b - 24 - g2,
               "w": m1 + 2 * s1, "h": g2, "classe": "corpo"})
    el.append({"tipo": "rect", "x": x_pe - m1 * 0.34, "y": baixo_m,
               "w": m1 * 0.68, "h": b - 24 - g2 - baixo_m, "classe": "corpo"})
    for sinal in (-1, 1):
        xf = x_pe + sinal * m1 / 2
        el.append(_p(f"M{xf:.1f} {b-24-g2:.1f} v{g2:.1f}", "furo"))
    # a ponta do eixo, cotada na folha, e a luva elastica na protecao aberta
    x_luva = fim_mancal
    d1 = float(ficha["d1_mm"] or 0) or rv * 0.3
    comp_ponta = float(ficha["l_mm"] or 0) or d1 * 2
    el += _eixo_da_bomba(x1, x_luva, d1 * 1.35)
    el += _ponta_de_eixo(x_luva, comp_ponta, d1,
                         float(ficha["u_mm"] or 8), float(ficha["t_mm"] or d1 + 3))
    # a luva ocupa a ponta do eixo e mais um tanto: o total da mancalizada
    # fecha em a + f + ponta + l(carcaca). No DXF da casa, a 200-150-315 de
    # 100 CV mede 1799,5 e a soma da 1820 - 1,1% de diferenca, com todo termo
    # saindo de folha.
    folga = comp_ponta * 1.15
    # O ACOPLAMENTO e um barrilete gordo entre as duas pontas de eixo, com as
    # duas metades e a folga entre elas. No desenho do fabricante ele e a peca
    # mais cheia do vao; desenhado como tubinho, o vao entre bomba e motor
    # ficava vazio e a maquina parecia partida em duas.
    r_acopla = d1 * 0.95
    l_acopla = folga * 0.62
    x_acopla = x_luva + (folga - l_acopla) / 2
    el.append({"tipo": "rect", "x": x_acopla, "y": -r_acopla,
               "w": l_acopla, "h": 2 * r_acopla, "classe": "corpo"})
    el.append(_p(f"M{x_acopla + l_acopla/2:.1f} {-r_acopla:.1f} "
                 f"V{r_acopla:.1f}", "junta"))
    for lado in (0, l_acopla):
        el.append(_p(f"M{x_acopla + lado:.1f} {-r_acopla*0.62:.1f} "
                     f"V{r_acopla*0.62:.1f}", "malha"))
    # a protecao aberta em volta dele
    el += [_p(f"M{x_luva:.1f} {-rv*0.50:.1f} H{x_luva+folga:.1f}", "malha"),
           _p(f"M{x_luva:.1f} {rv*0.50:.1f} H{x_luva+folga:.1f}", "malha"),
           _p(f"M{x_luva:.1f} {-rv*0.50:.1f} V{-rv*0.20:.1f}", "malha"),
           _p(f"M{x_luva+folga:.1f} {-rv*0.50:.1f} V{-rv*0.20:.1f}", "malha")]
    # o motor: a carcaca sai do folheto, o comprimento e proporcao dela
    x_motor = x_luva + folga
    nome_carcaca = (linha_conjunto or {}).get("carcaca_motor") or f"{carcaca:g}"
    motor, fim, ficha_m = _motor(x_motor, nome_carcaca, base_y=b - 24)
    el += motor
    rotulo_motor = f"carcaça {nome_carcaca}"
    if cv:
        rotulo_motor += f" · {cv:g} CV"
    el.append({"tipo": "nota", "x": (x_motor + fim) / 2,
               "y": -float(ficha_m.get("corpo_mm") or carcaca * 2) / 2
                    - carcaca * 0.40,
               "texto": rotulo_motor})
    el.append({"tipo": "rect", "x": x0 - 30, "y": b - 24,
               "w": fim - x0 + 70, "h": 24, "classe": "corpo"})
    el.append(_p(f"M-70 0 H{fim+60:.0f}", "centro"))
    el.append(_p(f"M{xd:.1f} {-a-40:.1f} V{rv+30:.1f}", "centro"))
    el += _letras_bomba(a, b, c, rv, x0, letras=("h2", "h1", "a"),
                        x_direita=x1 + caixa_mancal * 0.22)
    el.append({"tipo": "nota", "x": (c + fim_mancal) / 2, "y": -rv * 0.72,
               "texto": f"f {f:.0f}"})

    portas = [Porta("entrada", 0, 0, 180, dn1),
              Porta("saida", xd, -a, -90, dn2)]
    fonte = "KSB" if not proporcao else "KSB (motor proporcao)"
    rotulo = f'KSB Meganorm {tamanho} {dn1:g}"×{dn2:g}"'
    simbolo = _montar("BOMBA", rotulo, el, portas, fonte,
                      {"tamanho": tamanho, "montagem": montagem,
                       "eixo_mm": b, "mancalizada": True, "cv": cv,
                       "carcaca_motor": (linha_conjunto or {}).get(
                           "carcaca_motor") or f"{carcaca:g}",
                       "iso_2858": ficha["iso_2858"] == "1",
                       "base": (linha_conjunto or {}).get("base"),
                       "fim_mancal_mm": fim_mancal})
    if montagem == "VERTICAL":
        simbolo = girado(simbolo, -90)
        simbolo = simbolo._replace(
            rotulo=f'KSB Meganorm {tamanho} vertical {dn1:g}"×{dn2:g}"')
    return simbolo


def bomba_para_linha(dn_succao_pol, polos=4):
    """A menor Megabloc cuja succao e a bitola pedida.

    A casa dimensiona a bomba pela vazao, nao pelo tubo - isso aqui e so para
    o desenho ter uma bomba plausivel quando ninguem escolheu o modelo.
    """
    ficha_bomba("32-200")               # garante a tabela carregada
    candidatas = [linhas[0] for (nome, pol), linhas in _bombas.items()
                  if pol == polos and "-" in nome and nome.count("-") == 2
                  and abs((_pol(linhas[0]["dn_succao_pol"]) or 0)
                          - dn_succao_pol) < 0.01]
    if not candidatas:
        return None
    return min(candidatas, key=lambda r: float(r["l_mm"]))["tamanho_folheto"]


def meganorm_para_linha(dn_succao_pol):
    """A menor Meganorm cuja succao e a bitola pedida - so para o desenho."""
    from .bomba import MM_PARA_POLEGADA
    ficha_meganorm("50-160")            # garante a tabela carregada
    candidatas = [r for r in _meganorm.values()
                  if MM_PARA_POLEGADA.get(float(r["dn1_mm"])) == dn_succao_pol]
    if not candidatas:
        return None
    return min(candidatas, key=lambda r: float(r["rotor_mm"]))["tamanho"]


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


def girado(simbolo, graus):
    """O mesmo simbolo, virado - para mostrar a peca na pose do catalogo.

    A geometria nao muda: e a folha que gira. O catalogo Irrigafour desenha a
    curva entrando por baixo, na vertical, e saindo para cima; internamente o
    motor desenha toda peca entrando pela esquerda, que e o que a montagem
    espera.
    """
    rad = math.radians(graus)
    cos, sen = math.cos(rad), math.sin(rad)

    def vira(px, py):
        return px * cos - py * sen, px * sen + py * cos

    elementos = []
    for e in simbolo.elementos:
        novo = dict(e)
        if e.get("girar"):
            # ja tem giro proprio (a flange de saida): o giro da folha entra
            # por fora, senao a peca gira mas a flange fica para tras
            novo["girar_fora"] = graus
        else:
            novo["girar"] = (graus, 0.0, 0.0)
        elementos.append(novo)
    portas = []
    for p in simbolo.portas:
        x, y = vira(p.x, p.y)
        portas.append(Porta(p.papel, x, y, p.direcao + graus, p.dn_pol))
    return Simbolo(simbolo.familia, simbolo.rotulo, elementos, portas,
                   limites(elementos), simbolo.fonte, simbolo.params)


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


def sanduiche_wafer(x_entrada, x_saida, y=0.0, direcao=0.0, dn_pol=8,
                    barras=3, norma="NBR PN16"):
    """A wafer nao tem flange: ela e abracada pelas duas flanges vizinhas.

    Entao nao ha duas juntas, ha uma so - e a barra roscada atravessa o
    conjunto inteiro, da porca de um lado ate a do outro, passando pela
    flange, pelo corpo da valvula e pela outra flange. E por isso que a lista
    conta barra roscada, e nao parafuso, nessas pecas.
    """
    f = flange(dn_pol, norma)
    esp = f["espessura"]
    raio_furo = f["circulo"] / 2
    d = f["furo"] * 0.85
    porca = d * 1.6
    x0 = x_entrada - esp - porca * 0.75
    comprimento = (x_saida - x_entrada) + 2 * esp + 2 * porca * 0.75
    el = []
    for lado, x in (("entrada", x_entrada), ("saida", x_saida)):
        el.append(_p(f"M{x:.1f} {y - f['externo']/2:.1f} "
                     f"V{y + f['externo']/2:.1f}", "junta"))
    for sinal in (-1, 1):
        yy = y + sinal * raio_furo
        el.append({"tipo": "rect", "x": x0, "y": yy - d / 2, "w": comprimento,
                   "h": d, "classe": "barra"})
        for xn in (x0, x0 + comprimento - porca * 0.75):
            el.append({"tipo": "rect", "x": xn, "y": yy - porca / 2,
                       "w": porca * 0.75, "h": porca, "classe": "porca"})
    if direcao:
        for e in el:
            e["girar"] = (direcao, x_entrada, y)
    return el


def solda_de_topo(x, y=0.0, direcao=0.0, dn_mm=225):
    """O cordao de termofusao entre duas pontas de PEAD.

    PEAD nao emenda por flange - emenda por SOLDA, topo a topo, e o que sobra
    na juncao e um cordao saliente dos dois lados da parede. Ele pertence a
    JUNCAO e nao as pecas, exatamente como a junta e o parafuso pertencem a
    junta flangeada: nenhum dos dois tubos carrega cordao antes de ser soldado.

    A flange so aparece no PEAD onde o colar entra - para casar com a linha de
    aco - e ai a peca e o colar, nao o tubo.
    """
    r = dn_mm / 2
    largura = max(dn_mm * 0.055, 6.0)
    rad = math.radians(direcao)
    ux, uy = math.cos(rad), math.sin(rad)
    nx, ny = -uy, ux
    el = []
    for lado in (-1, 1):
        # o cordao e uma lente: sai da parede, engorda e volta para ela
        base = (x + nx * r * lado, y + ny * r * lado)
        ponta = (base[0] + nx * largura * 0.62 * lado,
                 base[1] + ny * largura * 0.62 * lado)
        el.append(_polilinha(
            [(base[0] - ux * largura, base[1] - uy * largura),
             (ponta[0] - ux * largura * 0.34, ponta[1] - uy * largura * 0.34),
             (ponta[0] + ux * largura * 0.34, ponta[1] + uy * largura * 0.34),
             (base[0] + ux * largura, base[1] + uy * largura)], "solda"))
    return el


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
