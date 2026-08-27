#!/usr/bin/env python3
"""Extrai a FORMA do motor dos DXF da W22 que a casa mandou.

Isto fecha uma pergunta que estava aberta desde que o motor entrou no desenho:
qual e o diametro do corpo. A tabela da Megabloc nao tem essa coluna. O que ela
tem e r1 e n5, e eu usava o r1 como diametro - errado. Cruzando as duas folhas
que a casa mandou, r1 e n5 batem EXATO com o A e o AB do IEC nos seis quadros
que as duas compartilham:

    quadro   r1 (KSB)   A (EBARA)      n5 (KSB)   AB (EBARA)
    90         140        140            164        164
    100        160        160            188        188
    112        190        190            220        220
    200        318        318            385        385
    225        356        356            436        436

A e AB sao medidas de LARGURA - vao entre os furos dos pes e largura total
sobre os pes. Elas se veem de frente, e o desenho aqui e de lado. Ou seja: o
corpo do motor estava desenhado com uma medida que nao aparece nesta vista.

O DXF da W22 resolve, e resolve melhor do que uma tabela: ele tem CAMADA. A
folha da EBARA e vetorial mas nao expoe camada por entidade, e por isso o
tracado automatico do perfil dela vinha com as linhas de cota dentro. Aqui as
camadas separam o que e peca do que e cota:

    MOTOR        o contorno, as aletas, a caixa, os olhais, os pes
    EIXO         a ponta de eixo e a chaveta
    COTAS        L, E, C, B, H, HD, OAC, OD - com o valor medido no proprio DXF
    DETALHE      os eixos dos furos do pe
    EIXO_CENTRO  a linha de centro

Tres coisas que so o desenho contava, e que nenhuma tabela conta:

**As aletas sao radiais, e o passo delas e angular.** No perfil elas caem em
R sen(k 15) - 52,3 / 100,5 / 140,7 / 174,9 num raio de 201. Desenhar a
mesma distancia entre elas e o que fazia o motor parecer um radiador.

**O corpo pode passar do plano do pe.** No quadro 132 o raio e 136 e a altura
do eixo e 132: a fundicao e achatada nos 4 mm que sobram. Nao e erro de
desenho, e como carcaca IEC e feita - o pe quase encosta no chao, e nao ha
perna nenhuma embaixo do motor.

**A caixa de ligacao tem chanfro na frente**, tampa, flange de assento no
corpo, e dois olhais de suspensao, um de cada lado dela.

Uso: python3 tools/extrair_weg.py > data/motores_weg.csv
"""
import csv
import glob
import math
import os
import re
import sys

import ezdxf

PASTA = "data/fichas/weg"
FONTE = "WEG W22 IR3 Premium, DXF individual 4 polos (desenho da casa)"
# o que a folha cota, com o nome que ela usa
COTAS = ("L", "E", "C", "B", "H", "HD", "ØAC", "ØD")


def _numero(txt):
    achado = re.search(r"-?\d+(?:[.,]\d+)?", txt or "")
    return float(achado.group().replace(",", ".")) if achado else None


def _do_arquivo(caminho):
    """Uma linha por DXF: as cotas que a folha diz e a forma que ela desenha."""
    msp = ezdxf.readfile(caminho).modelspace()
    cotas, texto = {}, []
    polys, linhas, circulos, eixo, furos = [], [], [], [], []
    for e in msp:
        tipo, camada = e.dxftype(), e.dxf.layer
        if tipo == "DIMENSION":
            nome = re.sub(r"\s*=.*", "", e.dxf.get("text", "")).replace("%%c", "Ø")
            cotas[nome] = round(e.get_measurement(), 1)
        elif tipo == "TEXT":
            texto.append(e.dxf.text)
        elif camada == "MOTOR" and tipo == "LWPOLYLINE":
            polys.append([(x, y) for x, y, *_ in e.get_points()])
        elif camada == "MOTOR" and tipo == "LINE":
            linhas.append(((e.dxf.start.x, e.dxf.start.y),
                           (e.dxf.end.x, e.dxf.end.y)))
        elif camada == "MOTOR" and tipo == "CIRCLE":
            circulos.append((e.dxf.center.x, e.dxf.center.y, e.dxf.radius))
        elif camada == "EIXO" and tipo == "LWPOLYLINE":
            eixo.append([(x, y) for x, y, *_ in e.get_points()])
        elif camada == "DETALHE" and tipo == "LINE":
            furos.append(e.dxf.start.x)

    faltando = [c for c in COTAS if c not in cotas]
    if faltando:
        raise ValueError(f"{os.path.basename(caminho)}: sem as cotas {faltando}")

    # o contorno e a poly mais longa; ela vai da face do corpo ao fim do
    # defletor, e o chanfro do defletor esta nela
    corpo = max(polys, key=lambda p: max(x for x, y in p) - min(x for x, y in p))
    face = min(x for x, y in corpo)
    fim = max(x for x, y in corpo)
    raio = max(y for x, y in corpo)
    # onde o raio deixa de ser cheio: comeca o cone do defletor
    cheio = max(x for x, y in corpo if abs(y - raio) < 0.2)
    raio_fim = min(abs(y) for x, y in corpo if abs(x - fim) < 0.2)

    # as tres verticais: fim da tampa dianteira, fim das aletas, inicio do
    # defletor. Sao as juntas fundidas do corpo
    juntas = sorted(round(a[0], 1) for a, b in linhas
                    if abs(a[0] - b[0]) < 0.1 and abs(a[1] - b[1]) > raio)

    # as aletas: y = raio sen(k passo). O passo sai do arco-seno do primeiro
    aletas = sorted({round(a[1], 1) for a, b in linhas
                     if abs(a[1] - b[1]) < 0.1 and a[1] > 1})
    passo = math.degrees(math.asin(min(aletas) / raio)) if aletas else 0.0
    horizontais = [(min(a[0], b[0]), max(a[0], b[0])) for a, b in linhas
                   if abs(a[1] - b[1]) < 0.1 and a[1] > 1]
    aleta_x0 = min(x for x, _ in horizontais)
    aleta_x1 = max(x for _, x in horizontais)

    # a caixa de ligacao: a poly de 5 pontos, que e a que tem chanfro
    caixa = max((p for p in polys if len(p) == 5),
                key=lambda p: max(y for x, y in p))
    cx = [x for x, y in caixa]
    caixa_topo = max(y for x, y in caixa)
    chanfro = min(y for x, y in caixa if abs(y - caixa_topo) > 0.2 and y > raio)

    # o flange de assento da caixa: a poly rasa que morre no topo do corpo, e
    # mais larga que a caixa - e por ela que a caixa aparafusa na carcaca
    assento = next((p for p in polys if len(p) == 4
                    and abs(max(y for x, y in p) - raio) < 0.3
                    and max(x for x, y in p) - min(x for x, y in p)
                    > (max(cx) - min(cx))), None)

    # os olhais: dois pares de circulos concentricos acima do corpo
    grandes = sorted((c for c in circulos if c[2] > raio * 0.05),
                     key=lambda c: c[0])
    pequenos = sorted((c for c in circulos if c[2] <= raio * 0.05),
                      key=lambda c: c[0])

    # o pedestal do olhal: a poly quadrada que sobe do topo do corpo, do
    # tamanho do olhal - e o pescoco fundido em que ele e rosqueado
    pedestais = [p for p in polys if len(p) == 4
                 and abs(min(y for x, y in p) - raio) < 0.3
                 and max(x for x, y in p) - min(x for x, y in p)
                 < (max(cx) - min(cx))]
    pedestal = (max(x for x, y in pedestais[0]) - min(x for x, y in pedestais[0])
                if pedestais else None)

    # o pe: a banda achatada embaixo, e nela os dois calcos do furo
    embaixo = [p for p in polys if p is not corpo
               and max(y for x, y in p) < 0]
    banda = max(embaixo, key=lambda p: max(x for x, y in p) - min(x for x, y in p))
    calcos = [p for p in embaixo if p is not banda]
    # a banda liga o fundo do corpo ao plano do pe, e faz os dois papeis: e
    # relevo quando o raio passa do plano (quadro 132: R 136, H 132) e e calco
    # quando o raio nao chega nele (quadro 225: R 201,5, H 225). O plano e o y
    # da banda que NAO e o fundo do corpo
    plano = min((y for x, y in banda), key=lambda y: -abs(y + raio))
    calco_alto = (max(max(y for x, y in p) for p in calcos) - plano
                  if calcos else 0.0)
    calco_larg = (sum(max(x for x, y in p) - min(x for x, y in p)
                      for p in calcos) / len(calcos)) if calcos else 0.0

    # a ponta de eixo e o cubo do mancal dianteiro
    ponta = max(eixo, key=lambda p: max(x for x, y in p) - min(x for x, y in p))
    cubo = min((p for p in polys if len(p) == 4 and min(x for x, y in p) <= face + 0.2),
               key=lambda p: max(y for x, y in p), default=None)

    nome = os.path.basename(caminho)
    # a potencia e a carcaca saem do TEXTO do desenho e nao do nome do arquivo:
    # o arquivo 012cv e um motor de 12,5 cv, e so o texto diz isso
    titulo = next((t for t in texto if "cv" in t), "")
    cv = _numero(titulo.split("cv")[0].split("-")[-1]) or _numero(
        nome.split("_")[1])
    carcaca = (titulo.split("CARCACA")[-1].strip() if "CARCACA" in titulo
               else nome.split("_")[3].split(".")[0].replace("-", "/"))
    return {
        "carcaca": carcaca,
        "quadro": int(cotas["H"]),
        "cv": f"{cv:g}",
        "polos": 4,
        # as cotas, do jeito que a folha as chama
        "L_mm": cotas["L"], "E_mm": cotas["E"], "C_mm": cotas["C"],
        "B_mm": cotas["B"], "H_mm": cotas["H"], "HD_mm": cotas["HD"],
        "AC_mm": cotas["ØAC"], "D_mm": cotas["ØD"],
        "K_mm": _numero(next((t.replace("%%c", "Ø").split("ØK")[1]
                              for t in texto
                              if "ØK" in t.replace("%%c", "Ø")), "")),
        # a forma, medida no proprio desenho (x a partir da ponta do eixo)
        "corpo_x0_mm": round(face, 1), "corpo_x1_mm": round(fim, 1),
        "raio_mm": round(raio, 1),
        "junta1_mm": round(juntas[0], 1) if juntas else None,
        "junta2_mm": round(juntas[1], 1) if len(juntas) > 1 else None,
        "junta3_mm": round(juntas[2], 1) if len(juntas) > 2 else None,
        "tampa1_mm": round(juntas[0] - face, 1) if juntas else None,
        "tampa2_mm": round(juntas[-1] - juntas[-2], 1) if len(juntas) > 2 else None,
        "defletor_x_mm": round(cheio, 1), "defletor_r_mm": round(raio_fim, 1),
        "aleta_x0_mm": round(aleta_x0, 1), "aleta_x1_mm": round(aleta_x1, 1),
        "aleta_passo_grau": round(passo, 1), "aletas": len(aletas),
        "caixa_x0_mm": round(min(cx), 1), "caixa_x1_mm": round(max(cx), 1),
        "caixa_topo_mm": round(caixa_topo, 1),
        "caixa_chanfro_mm": round(chanfro, 1),
        "caixa_chanfro_x_mm": round(min(x for x, y in caixa
                                        if abs(y - caixa_topo) < 0.2), 1),
        "caixa_pe_x0_mm": round(min(x for x, y in assento), 1) if assento else None,
        "caixa_pe_x1_mm": round(max(x for x, y in assento), 1) if assento else None,
        "caixa_pe_esp_mm": round(raio - min(y for x, y in assento), 1) if assento else None,
        "olhal_x_mm": round(grandes[0][0], 1) if grandes else None,
        "olhal_r_mm": round(grandes[0][2], 1) if grandes else None,
        "olhal_ri_mm": round(pequenos[0][2], 1) if pequenos else None,
        "olhal_y_mm": round(grandes[0][1], 1) if grandes else None,
        "olhal_x2_mm": round(grandes[-1][0], 1) if len(grandes) > 1 else None,
        "olhal_pe_mm": round(pedestal, 1) if pedestal else None,
        "olhais": len(grandes),
        "pe_x0_mm": round(min(x for x, y in banda), 1),
        "pe_x1_mm": round(max(x for x, y in banda), 1),
        "pe_plano_mm": round(plano, 1),
        "calco_alto_mm": round(calco_alto, 1),
        "calco_larg_mm": round(calco_larg, 1),
        "furo1_mm": round(min(furos), 1) if furos else None,
        "furo2_mm": round(max(furos), 1) if furos else None,
        "eixo_comp_mm": round(max(x for x, y in ponta), 1),
        "cubo_x_mm": round(max(x for x, y in cubo), 1) if cubo else None,
        "cubo_r_mm": round(max(y for x, y in cubo), 1) if cubo else None,
        "fonte": FONTE,
    }


def conferir(f):
    """O que o desenho tem de dizer de si mesmo, ou a linha nao vale."""
    problemas = []
    if abs(f["raio_mm"] * 2 - f["AC_mm"]) > 1.5:
        problemas.append(f'raio do contorno {f["raio_mm"]*2:g} != ØAC {f["AC_mm"]:g}')
    if abs(-f["pe_plano_mm"] - f["H_mm"]) > 1.5:
        problemas.append(f'plano do pe {-f["pe_plano_mm"]:g} != H {f["H_mm"]:g}')
    if f["furo1_mm"] and abs(f["furo1_mm"] - f["corpo_x0_mm"] - f["C_mm"]) > 1.5:
        problemas.append(f'primeiro furo a {f["furo1_mm"]-f["corpo_x0_mm"]:g} '
                         f'da face != C {f["C_mm"]:g}')
    if f["furo1_mm"] and abs(f["furo2_mm"] - f["furo1_mm"] - f["B_mm"]) > 1.5:
        problemas.append(f'vao dos furos {f["furo2_mm"]-f["furo1_mm"]:g} '
                         f'!= B {f["B_mm"]:g}')
    if abs(f["corpo_x1_mm"] - f["L_mm"]) > 1.5:
        problemas.append(f'fim do corpo {f["corpo_x1_mm"]:g} != L {f["L_mm"]:g}')
    if abs(f["caixa_topo_mm"] + f["H_mm"] - f["HD_mm"]) > 1.5:
        problemas.append(f'topo da caixa {f["caixa_topo_mm"]+f["H_mm"]:g} '
                         f'!= HD {f["HD_mm"]:g}')
    if abs(f["corpo_x0_mm"] - f["E_mm"]) > 1.5:
        problemas.append(f'face do corpo {f["corpo_x0_mm"]:g} != E {f["E_mm"]:g}')
    return problemas


def main():
    fichas = []
    for caminho in sorted(glob.glob(f"{PASTA}/*.dxf")):
        try:
            f = _do_arquivo(caminho)
        except Exception as erro:                       # noqa: BLE001
            print(f"# {os.path.basename(caminho)}: {erro}", file=sys.stderr)
            continue
        ruim = conferir(f)
        for p in ruim:
            print(f'# {f["carcaca"]} {f["cv"]}cv: {p}', file=sys.stderr)
        fichas.append(f)

    campos = list(fichas[0])
    campos.remove("aletas")
    escritor = csv.DictWriter(sys.stdout, campos, extrasaction="ignore")
    escritor.writeheader()
    for f in sorted(fichas, key=lambda f: (f["quadro"], float(f["cv"]))):
        escritor.writerow(f)

    print(f"# {len(fichas)} desenhos, "
          f"{len({f['carcaca'] for f in fichas})} carcacas", file=sys.stderr)
    # as fracoes servem de reserva para quadro fora desta pasta (a GSD pequena
    # monta 71 a 112, e a W22 individual comeca no 132)
    def med(nome, f):
        return sum(nome(x) for x in fichas) / len(fichas)
    print("# fracoes medias, para quadro fora da pasta:", file=sys.stderr)
    for rotulo, conta in (
            ("tampa1/L", lambda f: f["tampa1_mm"] / f["L_mm"]),
            ("tampa2/L", lambda f: (f["tampa2_mm"] or 0) / f["L_mm"]),
            ("defletor/L", lambda f: (f["L_mm"] - f["defletor_x_mm"]) / f["L_mm"]),
            ("r_defletor/R", lambda f: f["defletor_r_mm"] / f["raio_mm"]),
            ("caixa_comp/L", lambda f: (f["caixa_x1_mm"] - f["caixa_x0_mm"]) / f["L_mm"]),
            ("caixa_alt/R", lambda f: (f["caixa_topo_mm"] - f["raio_mm"]) / f["raio_mm"]),
            ("chanfro/alt", lambda f: (f["caixa_chanfro_mm"] - f["raio_mm"])
             / (f["caixa_topo_mm"] - f["raio_mm"])),
            ("olhal_r/R", lambda f: f["olhal_r_mm"] / f["raio_mm"]),
            ("calco_alto/H", lambda f: f["calco_alto_mm"] / f["H_mm"]),
            ("calco_larg/B", lambda f: f["calco_larg_mm"] / f["B_mm"]),
            ("cubo_r/R", lambda f: (f["cubo_r_mm"] or 0) / f["raio_mm"]),
            ("passo_aleta", lambda f: f["aleta_passo_grau"]),
            ("E/H", lambda f: f["E_mm"] / f["H_mm"]),
            ("L/H", lambda f: f["L_mm"] / f["H_mm"]),
            ("AC/2H", lambda f: f["AC_mm"] / 2 / f["H_mm"])):
        vs = [conta(f) for f in fichas]
        print(f"#   {rotulo:14} {sum(vs)/len(vs):7.3f}   "
              f"({min(vs):.3f} a {max(vs):.3f})", file=sys.stderr)


if __name__ == "__main__":
    main()
