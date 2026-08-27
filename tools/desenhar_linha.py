#!/usr/bin/env python3
"""Desenha uma linha inteira encadeando os simbolos pelas portas.

Cada peca e desenhada uma vez, na origem, olhando para +x. Encaixar e uma
transformacao rigida: girar pelo angulo corrente, transladar ate o ponto
corrente. O tamanho vem da tabela de cotas, o angulo vem da curva, e a rotacao
e acumulada - a peca herda a direcao que a anterior deixou.

Uso: python3 tools/desenhar_linha.py [--dn 8] > linha.html
"""
import argparse
import math
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402
from tools.desenhar_simbolos import ESTILO, legenda  # noqa: E402
from tools.desenhar_simbolos import texto_no_eixo  # noqa: E402
from tools.desenhar_simbolos import desenhar  # noqa: E402

MARGEM = 46


# Bocal de entrada da bomba para cada bitola de linha, pela tabela KSB
# Megabloc: uma linha de 6" entra numa bomba de 4" (tamanho 65-xxx) e uma de
# 12" na maior do folheto, que tem sucção de 8" (150-xxx).
BOCAL_BOMBA = {3: 2, 4: 3, 5: 4, 6: 4, 8: 6, 10: 6, 12: 8, 14: 8}


def _bomba(bocal_pol, linha="METB"):
    """A bomba cuja sucção tem a bitola que a redução entrega.

    A peça é a mesma nas duas montagens: a direção chega acumulada pela
    corrente, então na sucção vertical ela recebe por baixo e na horizontal
    recebe deitada, sem parâmetro nenhum dizendo isso.
    """
    if linha == "METN":
        tamanho = s.meganorm_para_linha(bocal_pol)
        return s.bomba_meganorm(tamanho) if tamanho else None
    tamanho = s.bomba_para_linha(bocal_pol)
    return s.bomba_megabloc(tamanho) if tamanho else None


def succao_vertical(dn):
    """Bomba vertical: a linha sobe direto da água até o bocal.

    Sem curva - o eixo da bomba é o eixo da sucção - e a redução é
    concêntrica, porque não há lado de cima onde o ar possa ficar preso.
    """
    bocal = BOCAL_BOMBA.get(dn, 2)
    return [s.crivo(dn), s.valvula_retencao(dn), s.tubo(dn, 1000),
            s.reducao(dn, bocal, "CONCENTRICA"), _bomba(bocal)]


def succao_mancalizada(dn):
    """Mesma sucção horizontal, com bomba mancalizada em vez de monobloco.

    A tubulação não muda nada: os dois bocais estão no mesmo lugar e na mesma
    bitola. O que muda é o que vem depois da voluta - e isso é problema da
    base, não da linha.
    """
    bocal = BOCAL_BOMBA.get(dn, 2)
    return [s.crivo(dn), s.valvula_retencao(dn), s.tubo(dn, 1000),
            s.curva(dn, 90, -1), s.tubo(dn, 500),
            s.reducao(dn, bocal, "EXCENTRICA", "topo"),
            _bomba(bocal, "METN")]


def succao_horizontal(dn):
    """Bomba horizontal: a linha sobe, vira 90° e entra deitada.

    A redução é excêntrica com o lado plano em cima: deitada, uma concêntrica
    deixaria uma bolsa de ar no topo, bem na boca do rotor.
    """
    bocal = BOCAL_BOMBA.get(dn, 2)
    return [s.crivo(dn), s.valvula_retencao(dn), s.tubo(dn, 1000),
            s.curva(dn, 90, -1), s.tubo(dn, 500),
            s.reducao(dn, bocal, "EXCENTRICA", "topo"), _bomba(bocal)]


def recalque(dn, menor):
    # a reducao entra sem dizer o sentido: orientar() vira sozinho
    return [s.reducao(dn, menor, "CONCENTRICA"), s.tubo(dn, 1000),
            s.valvula_borboleta(dn, "ALAVANCA" if dn <= 6 else "CAIXA"),
            s.tubo(dn, 500), s.medidor(dn), s.tubo(dn, 1500),
            s.valvula_hidraulica(dn, "47"), s.tubo(dn, 1000), s.curva(dn, 90, -1)]


def trecho_pead(dn, tubos=4):
    """Depois da primeira bomba a linha vira PEAD.

    O trecho e sempre o mesmo: N barras de 6 m fundidas topo a topo e, em cada
    ponta, um colar com a flange solta ja presa pelo ressalto. E por isso que a
    lista pede colar e flange sempre aos pares - motor/templates.trecho_pead.
    """
    from motor.traducao import POLEGADA_MM
    dn_mm = POLEGADA_MM.get(dn) or 225
    return ([s.colar_pead(dn_mm)] + [s.tubo_pead(dn_mm)] * tubos
            + [s.colar_pead(dn_mm)])


def manifold_ventosas(dn, derivacao=None):
    """O barrilete do recalque, com as duas luvas de ventosa e a flange cega
    fechando a ponta - a cega leva a terceira luva de 2\"."""
    menor = derivacao or {14: 8, 12: 6, 10: 6, 8: 6, 6: 4, 4: 3}.get(dn, 4)
    return [s.manifold(dn, menor), s.flange_cega(dn, 2)]


def _os_dois_pead(a, b):
    """A juncao e soldada quando as duas pontas que se encontram sao de PEAD.

    O colar conta: ele solda no tubo por termofusao e leva a flange do outro
    lado - a flange dele nao esta nesta juncao, esta na ponta que vai para o
    aco.
    """
    return all(p.params.get("material") == "PEAD" for p in (a, b))


def desenhar_linha(pecas, largura=940, giro=0.0, altura_max=620):
    postos, fim = s.montar(pecas)
    if giro:
        # a sucção nasce no poço e sobe: a linha inteira gira para ficar de pé
        rad = math.radians(giro)
        cos, sen = math.cos(rad), math.sin(rad)
        vira = lambda x, y: (x * cos - y * sen, x * sen + y * cos)
        postos = [p._replace(dx=vira(p.dx, p.dy)[0], dy=vira(p.dx, p.dy)[1],
                             giro=p.giro + giro,
                             entrada=vira(*p.entrada), saida=vira(*p.saida))
                  for p in postos]
        fim = (*vira(fim[0], fim[1]), fim[2] + giro)
    caixas = []
    for p in postos:
        x0, y0, w, h = p.simbolo.caixa
        rad = math.radians(p.giro)
        cos, sen = math.cos(rad), math.sin(rad)
        for cx, cy in ((x0, y0), (x0 + w, y0), (x0, y0 + h), (x0 + w, y0 + h)):
            caixas.append((p.dx + cx * cos - cy * sen, p.dy + cx * sen + cy * cos))
    minx = min(c[0] for c in caixas)
    maxx = max(c[0] for c in caixas)
    miny = min(c[1] for c in caixas)
    maxy = max(c[1] for c in caixas)
    # cabe na largura E na altura: a sucção de bomba vertical é alta e
    # estreita, e escalando só pela largura ela virava um poster
    escala = min((largura - 2 * MARGEM) / max(maxx - minx, 1),
                 (altura_max - 2 * MARGEM) / max(maxy - miny, 1))
    largura = (maxx - minx) * escala + 2 * MARGEM
    altura = (maxy - miny) * escala + 2 * MARGEM

    partes = [f'<svg viewBox="0 0 {largura:.0f} {altura:.0f}" '
              f'style="max-width:{largura:.0f}px" role="img" '
              f'aria-label="linha montada">',
              f'<g class="geo" transform="translate({MARGEM - minx*escala:.2f} '
              f'{MARGEM - miny*escala:.2f}) scale({escala:.5f})">']
    for p in postos:
        corpo = "".join(desenhar(e) for e in p.simbolo.elementos
                        if e["tipo"] != "texto_furos")
        partes.append(f'<g transform="translate({p.dx:.1f} {p.dy:.1f}) '
                      f'rotate({p.giro:g})">{corpo}</g>')
    # cada ligacao tem duas flanges encostadas e os parafusos que as fecham -
    # e a juncao que puxa a ferragem, entao e ela que desenha o parafuso.
    # A wafer e a excecao: ela nao tem flange, e abracada pelas duas vizinhas,
    # e entao as duas juncoes viram uma so, com barra roscada de ponta a ponta.
    wafer = {i for i, p in enumerate(postos) if p.simbolo.params.get("wafer")}
    ruins = []
    for i, p in enumerate(postos[:-1]):
        if i in wafer or (i + 1) in wafer:
            continue
        ok, motivo = s.encaixa(p.simbolo, postos[i + 1].simbolo)
        saida = s.porta(p.simbolo, s.SAIDA)
        if ok and saida is not None:
            direcao = p.giro + (saida.direcao if saida.papel != "entrada" else 0)
            vizinho = postos[i + 1].simbolo
            # PEAD com PEAD e SOLDA e nao flange: nenhuma das duas pontas tem
            # chapa, e o que sobra na juncao e o cordao de termofusao. A flange
            # do PEAD aparece so onde o colar casa com a linha de aco
            if _os_dois_pead(p.simbolo, vizinho):
                ferragem = s.solda_de_topo(
                    p.saida[0], p.saida[1], direcao,
                    p.simbolo.params.get("dn_mm") or 225)
            else:
                ferragem = s.junta_flangeada(p.saida[0], p.saida[1], direcao,
                                             saida.dn_pol)
            partes.append("".join(desenhar(e) for e in ferragem))
        else:
            ruins.append((p, motivo))
    for i in sorted(wafer):
        p = postos[i]
        entrada = s.porta(p.simbolo, s.ENTRADA)
        comp = abs(s.porta(p.simbolo, s.SAIDA).x - entrada.x)
        # a ferragem sai no eixo da propria peca e viaja com ela, no mesmo
        # grupo de transformacao que o corpo - senao ela fica solta na folha
        ferragem = s.sanduiche_wafer(0.0, comp, 0.0, 0.0, entrada.dn_pol)
        partes.append(f'<g transform="translate({p.dx:.1f} {p.dy:.1f}) '
                      f'rotate({p.giro:g})">'
                      + "".join(desenhar(e) for e in ferragem) + "</g>")
    partes.append("</g>")
    # cada peca leva a bitola e a medida, em cinza claro, fora da escala
    partes.append('<g class="anota">')
    for p in postos:
        entrada, saida = s.porta(p.simbolo, s.ENTRADA), s.porta(p.simbolo, s.SAIDA)
        if entrada is None or saida is None:
            entrada = entrada or saida
            saida = saida or entrada
        comp = ((saida.x - entrada.x) ** 2 + (saida.y - entrada.y) ** 2) ** 0.5
        vao = comp * escala
        if vao < 44:                 # peca curta: a cota nao cabe dentro dela
            continue
        mx = MARGEM + ((p.entrada[0] + p.saida[0]) / 2 - minx) * escala
        my = MARGEM + ((p.entrada[1] + p.saida[1]) / 2 - miny) * escala
        # a cota fica NO eixo da peca, com o eixo aparado atras dela
        vertical = abs(p.saida[1] - p.entrada[1]) > abs(p.saida[0] - p.entrada[0])
        gira = f' transform="rotate(-90 {mx:.1f} {my:.1f})"' if vertical else ""
        duas = abs((entrada.dn_pol or 0) - (saida.dn_pol or 0)) > 0.01
        # no PEAD a bitola do papel e o DN em milimetro, que E o externo
        bitola = (f'DN{p.simbolo.params["dn_mm"]:g}'
                  if p.simbolo.params.get("dn_mm")
                  else f'{(entrada.dn_pol or 0):g}"')
        rotulo = f"{comp:.0f}" if duas else f"{bitola}  {comp:.0f}"
        partes.append(texto_no_eixo(mx, my, rotulo, "marca", 9.0, gira))
        if duas:
            # a bitola de cada flange, na sua ponta
            for porta, ponto in ((entrada, p.entrada), (saida, p.saida)):
                meia = s.flange(porta.dn_pol)["externo"] / 2 * escala
                px = MARGEM + (ponto[0] - minx) * escala
                py = MARGEM + (ponto[1] - miny) * escala - meia - 4
                partes.append(f'<text class="marca" x="{px:.1f}" y="{py:.1f}">'
                              f'{porta.dn_pol:g}"</text>')
    for p, motivo in ruins:
        px = MARGEM + (p.saida[0] - minx) * escala
        py = MARGEM + (p.saida[1] - miny) * escala
        partes.append(f'<circle class="juncao ruim" cx="{px:.1f}" cy="{py:.1f}" r="4"/>')
    partes.append("</g></svg>")
    return "".join(partes), postos, fim


def fragmento(dn):
    """As montagens, sem a pagina em volta - devolve (html, quantas).

    Serve a folha solta e a prancha, como em desenhar_simbolos.fragmento.
    """
    menor = {14: 12, 12: 10, 10: 8, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn, 2)
    args = argparse.Namespace(dn=dn)
    linhas = [("sucção · bomba vertical",
               "sobe reta e entra por baixo da bomba",
               succao_vertical(args.dn), -90),
              ("sucção · bomba horizontal",
               "curva de 90° antes da bomba, redução excêntrica com o lado "
               "plano em cima",
               succao_horizontal(args.dn), -90),
              ("sucção · bomba mancalizada",
               "a mesma tubulação, com Meganorm sobre base",
               succao_mancalizada(args.dn), -90),
              ("recalque", "da bomba ao manifold", recalque(args.dn, menor), 0),
              ("manifold c/ ventosas",
               "as duas luvas de 2\" e a flange cega fechando",
               manifold_ventosas(args.dn), 0),
              ("trecho de PEAD", "quatro barras de 6 m e um colar em cada ponta",
               trecho_pead(args.dn), 0)]

    figuras = []
    for nome, detalhe, pecas, giro in linhas:
        svg, postos, fim = desenhar_linha(pecas, giro=giro)
        figuras.append(
            f'<figure class="linha"><figcaption><b>{nome}</b>'
            f'<em>{detalhe}</em><span>{len(postos)} peças · fecha em '
            f'{abs(fim[0])/1000:.2f} × {abs(fim[1])/1000:.2f} m</span>'
            f'</figcaption>{svg}</figure>')
        print(f"# {nome}: {len(postos)} pecas, fim em "
              f"({fim[0]:.0f}, {fim[1]:.0f}) direcao {fim[2]:.0f}",
              file=sys.stderr)
    return "\n".join(figuras), len(linhas)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    p.add_argument("--fragmento", action="store_true",
                   help="só as <figure>, sem a página em volta")
    args = p.parse_args()
    figuras, quantas = fragmento(args.dn)
    if args.fragmento:
        print(figuras)
        return
    linhas = range(quantas)
    print(f'<!doctype html><meta charset="utf-8">'
          f'<title>Linhas {args.dn:g}"</title>'
          f'<style>{ESTILO}{ESTILO_LINHA}</style>'
          f'<div class="papel"><header><h1>Linhas montadas</h1>'
          f'<span class="dn">{args.dn:g}"</span>'
          f'<span class="sub">{len(linhas)} montagens · a mesma peça, '
          f'a direção acumulada pela corrente</span></header>'
          f'{legenda()}' + figuras + "</div>")


ESTILO_LINHA = """
.linha{border:1px solid var(--linha);margin:0 0 22px;padding:18px 20px 8px}
.linha figcaption{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
  margin-bottom:10px}
.linha figcaption b{font-size:13px;font-weight:600;letter-spacing:-.005em}
.linha figcaption em{font-style:normal;color:var(--anota);font-size:11.5px}
.linha figcaption span{margin-left:auto;color:var(--anota);
  font:400 10.5px/1 ui-monospace,SFMono-Regular,monospace}
.linha svg{width:100%;height:auto;display:block;margin:0 auto}
.geo .juncao{fill:none}
.geo .juncao.ruim{fill:var(--eixo);stroke:none}
"""


if __name__ == "__main__":
    main()
