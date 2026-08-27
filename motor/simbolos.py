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
        for ang_graus, cx, cy in ([e["girar"]] if e.get("girar") else []) + \
                ([(e["girar_fora"], 0.0, 0.0)] if e.get("girar_fora") else []):
            ang = math.radians(ang_graus)
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


def crivo(dn_pol, variante=""):
    """Cesto de chapa perfurada: furo de 6 mm a cada 3, fundo fechado.

    A folha do caderno (pagina 14) cota tudo o que o desenho precisa - o
    comprimento por bitola, a parede da chapa, a margem lisa de 10 mm antes do
    primeiro furo e o passo de 3 mm entre furos. O fundo e CHAPA LISA: a agua
    entra so pela parede, e e isso que separa o crivo de um tubo aberto.

    A furacao vai desenhada no tamanho real - furo de 6 mm num cesto de 368
    e um ponto mesmo. Como um crivo de 14" tem mais de dois mil furos, o
    desenho mostra o trecho junto ao fundo e deixa o resto liso: e a convencao
    de elemento repetido, a mesma que o caderno usa no DETALHE.
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

    el = [_p(f"M0 {-r:.1f} H{comp:.1f}"), _p(f"M0 {r:.1f} H{comp:.1f}"),
          _p(f"M0 {-r+parede:.1f} H{comp:.1f}", "malha"),
          _p(f"M0 {r-parede:.1f} H{comp:.1f}", "malha"),
          # o fundo: chapa lisa fechando o cesto, com a espessura da folha
          {"tipo": "rect", "x": 0, "y": -r, "w": parede * 2, "h": 2 * r,
           "classe": "chapa_lisa"}]

    # a malha, em quincuncio, comecando depois da margem lisa e parando antes
    # dela do outro lado. Corta no meio do cesto quando a contagem explode.
    inicio = margem + parede * 2
    fim = comp - margem
    colunas = int((fim - inicio) / passo)
    fileiras = int((2 * r - 2 * margem) / passo)
    limite = 900
    mostradas = min(colunas, max(1, limite // max(fileiras, 1)))
    for i in range(mostradas):
        x = inicio + furo / 2 + passo * i
        for j in range(fileiras):
            yy = -r + margem + furo / 2 + passo * j + (passo / 2 if i % 2 else 0)
            if abs(yy) < r - margem:
                el.append({"tipo": "circulo", "cx": x, "cy": yy, "r": furo / 2,
                           "classe": "malha"})
    if mostradas < colunas:
        el.append({"tipo": "nota", "x": (inicio + fim) / 2, "y": -r * 0.55,
                   "texto": f"furo {furo:g} c/ {passo_livre:g}"})

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
    el.append(_p(f"M-40 0 H{comp+40:.0f}", "centro"))
    portas = [Porta("entrada", 0, 0, 180, dn_pol), Porta("saida", comp, 0, 0, dn_pol)]
    rot = f'borboleta {dn_pol:g}" {"alavanca" if acionamento == "ALAVANCA" else "caixa"}'
    return _montar("VALVULA_BORBOLETA", rot, el, portas, fonte, {"wafer": True})


def valvula_gaveta(dn_pol):
    """Corpo curto, castelo aparafusado, cunha emborrachada e volante fixo."""
    comp, fonte = _cota("VALVULA_GAVETA", dn_pol)
    comp = comp or 230
    alt, _ = _cota("VALVULA_GAVETA", dn_pol, "", "altura_total_mm")
    volante, _ = _cota("VALVULA_GAVETA", dn_pol, "", "volante_mm")
    corpo, _ = _cota("VALVULA_GAVETA", dn_pol, "", "d_corpo_mm")
    f = flange(dn_pol)
    corpo = corpo or f["externo"] * 0.62
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
    """Wafer de dupla portinhola: corpo estreito entre flanges, duas abas.

    O face a face vem da ficha MP Valvulas (fig. 160/162), que ja estava em
    data/valvulas_wafer.csv - e a mesma que o motor usa para contar barra
    roscada e comprimento de parafuso.
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
    el = caixa(0, comp, corpo / 2, corpo / 2)
    el.append(_p(f"M0 {-bocal/2:.1f} H{comp:.1f} M0 {bocal/2:.1f} H{comp:.1f}",
                 "oculto"))
    # as duas portinholas, encostadas no eixo e abrindo para a jusante
    el.append(_p(f"M{meio:.1f} 0 L{comp*0.95:.1f} {-bocal*0.44:.1f}",
                 "obturador"))
    el.append(_p(f"M{meio:.1f} 0 L{comp*0.95:.1f} {bocal*0.44:.1f}",
                 "obturador"))
    el.append(_p(f"M{meio:.1f} {-bocal*0.1:.1f} v{bocal*0.2:.1f}", "haste"))
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
    el += [_p(f"M{-cesto:.1f} {-r*0.95:.1f} H0"),
           _p(f"M{-cesto:.1f} {r*0.95:.1f} H0"),
           _p(f"M{-cesto:.1f} {-r*0.95:.1f} V{r*1.9:.1f}", "chapa_lisa")]
    passo = max(9.0, cesto / 14)
    for i in range(int((cesto - passo) / passo)):
        x = -cesto + passo * (i + 1)
        for j in range(int((1.9 * r - passo) / passo)):
            yy = -r * 0.95 + passo * (j + 1) + (passo / 2 if i % 2 else 0)
            if abs(yy) < r * 0.95 - passo / 6:
                el.append({"tipo": "circulo", "cx": x, "cy": yy,
                           "r": passo / 6, "classe": "malha"})
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


def ficha_bomba(tamanho, polos=4):
    """A linha da bomba na tabela de dimensoes da KSB."""
    global _bombas
    if _bombas is None:
        _bombas = {}
        with open(f"{DADOS}/bombas_ksb_megabloc.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                _bombas[(r["tamanho"], int(r["polos"]))] = r
    return _bombas.get((tamanho, polos))


def bomba_megabloc(tamanho, montagem="HORIZONTAL", polos=4):
    """A KSB Megabloc, vista de lado - a ancora do desenho.

    Tres cotas do folheto colocam os dois bocais, e sao elas que a tubulacao
    precisa: a (do eixo a face do flange de descarga), b (da base ao eixo) e
    c (da face da succao ao eixo da descarga). O corpo em volta sai da
    nomenclatura: no nome 32-200 o 200 e o diametro nominal do rotor, e a
    voluta mede cerca de 1,3 rotor. O motor sai da carcaca IEC h.

    A peca e a MESMA nas duas montagens - o que muda e a pose. Montada na
    vertical, a bomba e a mesma fundicao de pe: o motor em cima, a succao
    entrando por baixo. Aqui a vertical e so girada -90, do mesmo jeito que a
    folha desenha a curva em pe; na linha a montagem sai sozinha de onde a
    bomba cai na corrente, porque a direcao chega acumulada.
    """
    ficha = ficha_bomba(tamanho, polos)
    if not ficha or not ficha["a_mm"]:
        raise ValueError(f"{tamanho} nao tem dimensao no folheto IV polos")
    a = float(ficha["a_mm"])
    b = float(ficha["b_mm"])
    c = float(ficha["c_mm"])
    h = float(ficha["h_mm"])
    comp = float(ficha["l_mm"])
    dn1 = float(ficha["dn_succao_pol"])
    dn2 = float(ficha["dn_recalque_pol"])
    rotor = float(tamanho.split("-")[1].split(".")[0])
    r1 = DE_TUBO.get(dn1, 100) / 2
    r2 = DE_TUBO.get(dn2, 80) / 2
    # a voluta vista de lado e estreita e alta: o caracol esta no plano
    # perpendicular ao eixo, entao de lado aparece de canto. O circulo grande
    # e a terceira vista do folheto, olhando pelo eixo - nao esta.
    rv = rotor / 2 * 1.15              # meia altura da carcaca: proporcao
    largura = max(rotor * 0.42, 2 * r1 * 1.1)
    x_voluta = c - largura / 2
    x_tras = c + largura / 2
    hm = h * 0.95                      # meia altura do corpo do motor
    lanterna = h * 0.55                # o suporte que liga a voluta ao motor

    el = list(placa(0, dn1, lado="entrada"))
    el += eixo(0, x_voluta, dn1)
    # a carcaca: caixa alta e estreita, com a tampa de succao na frente
    el += [_p(f"M{x_voluta:.1f} {-rv:.1f} H{x_tras:.1f}"),
           _p(f"M{x_voluta:.1f} {rv:.1f} H{x_tras:.1f}"),
           _p(f"M{x_voluta:.1f} {-rv:.1f} V{-r1:.1f}"),
           _p(f"M{x_voluta:.1f} {r1:.1f} V{rv:.1f}"),
           _p(f"M{x_tras:.1f} {-rv:.1f} V{rv:.1f}"),
           _p(f"M{x_voluta + largura*0.28:.1f} {-rv:.1f} V{rv:.1f}", "malha")]
    # o pescoco da descarga, subindo da carcaca ate a face do flange
    el += [_p(f"M{c-r2:.1f} {-a:.1f} V{-rv:.1f}"),
           _p(f"M{c+r2:.1f} {-a:.1f} V{-rv:.1f}")]
    el += placa(c, dn2, y=-a, direcao=-90, lado="saida")
    # a lanterna e o motor, com as aletas e a tampa do ventilador
    el.append({"tipo": "rect", "x": x_tras, "y": -hm * 0.62, "w": lanterna,
               "h": 2 * hm * 0.62, "classe": "corpo"})
    x_motor = x_tras + lanterna
    corpo = max(comp - x_motor - h * 0.18, h * 0.6)
    el.append({"tipo": "rect", "x": x_motor, "y": -hm, "w": corpo, "h": 2 * hm,
               "classe": "corpo"})
    for k in range(1, 9):
        xa = x_motor + corpo * k / 9
        el.append(_p(f"M{xa:.1f} {-hm:.1f} v{2*hm:.1f}", "malha"))
    el.append({"tipo": "rect", "x": x_motor + corpo, "y": -hm * 0.72,
               "w": h * 0.18, "h": 2 * hm * 0.72, "classe": "corpo"})
    # a base e os dois pes, no nivel que a cota b manda
    fim = x_motor + corpo + h * 0.18
    el.append(_p(f"M{x_voluta:.1f} {b:.1f} H{fim:.1f}"))
    for x0, larg in ((x_voluta, largura), (fim - h * 1.1, h * 0.7)):
        el.append({"tipo": "rect", "x": x0, "y": b - 18, "w": larg, "h": 18,
                   "classe": "corpo"})
    el.append(_p(f"M-70 0 H{fim+40:.0f}", "centro"))
    el.append(_p(f"M{c:.1f} {-a-40:.1f} V{rv+30:.1f}", "centro"))

    portas = [Porta("entrada", 0, 0, 180, dn1),
              Porta("saida", c, -a, -90, dn2)]
    simbolo = _montar("BOMBA", f'KSB Megabloc {tamanho} {dn1:g}"×{dn2:g}"',
                      el, portas, "KSB",
                      {"tamanho": tamanho, "montagem": montagem,
                       "eixo_mm": b, "norma_flange": ficha["norma_flange"],
                       "rosca_possivel": ficha["rosca_possivel"] == "1"})
    if montagem == "VERTICAL":
        simbolo = girado(simbolo, -90)
        simbolo = simbolo._replace(
            rotulo=f'KSB Megabloc {tamanho} vertical {dn1:g}"×{dn2:g}"')
    return simbolo


def bomba_para_linha(dn_succao_pol, polos=4):
    """A menor Megabloc cuja succao e a bitola pedida.

    A casa dimensiona a bomba pela vazao, nao pelo tubo - isso aqui e so para
    o desenho ter uma bomba plausivel quando ninguem escolheu o modelo.
    """
    global _bombas
    ficha_bomba("32-200")               # garante a tabela carregada
    candidatas = [r for (t, p), r in _bombas.items()
                  if p == polos and r["a_mm"]
                  and abs(float(r["dn_succao_pol"]) - dn_succao_pol) < 0.01]
    if not candidatas:
        return None
    return min(candidatas, key=lambda r: float(r["l_mm"]))["tamanho"]


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
