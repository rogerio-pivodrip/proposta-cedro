#!/usr/bin/env python3
"""Desenha uma linha inteira encadeando os simbolos pelas portas.

Cada peca e desenhada uma vez, na origem, olhando para +x. Encaixar e uma
transformacao rigida: girar pelo angulo corrente, transladar ate o ponto
corrente. O tamanho vem da tabela de cotas, o angulo vem da curva, e a rotacao
e acumulada - a peca herda a direcao que a anterior deixou.

Uso: python3 tools/desenhar_linha.py [--dn 8] > linha.html
"""
import argparse
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402
from tools.desenhar_simbolos import desenhar, seta  # noqa: E402

MARGEM = 46


def succao(dn, menor):
    """A succao da casa: crivo, retencao, tubo, curva, reducao."""
    return [s.crivo(dn), s.valvula_pe(dn), s.tubo(dn, 1000), s.curva(dn, 90),
            s.tubo(dn, 3000), s.curva(dn, 45, -1), s.tubo(dn, 1500),
            s.reducao(dn, menor, "EXCENTRICA", "topo")]


def recalque(dn, menor):
    # a reducao entra sem dizer o sentido: orientar() vira sozinho
    return [s.reducao(dn, menor, "CONCENTRICA"), s.tubo(dn, 1000),
            s.valvula_borboleta(dn, "ALAVANCA" if dn <= 6 else "CAIXA"),
            s.tubo(dn, 500), s.medidor(dn), s.tubo(dn, 1500),
            s.valvula_hidraulica(dn, "47"), s.tubo(dn, 1000), s.curva(dn, 90, -1)]


def desenhar_linha(pecas, largura=940):
    postos, fim = s.montar(pecas)
    caixas = []
    for p in postos:
        import math
        x0, y0, w, h = p.simbolo.caixa
        rad = math.radians(p.giro)
        cos, sen = math.cos(rad), math.sin(rad)
        for cx, cy in ((x0, y0), (x0 + w, y0), (x0, y0 + h), (x0 + w, y0 + h)):
            caixas.append((p.dx + cx * cos - cy * sen, p.dy + cx * sen + cy * cos))
    minx = min(c[0] for c in caixas)
    maxx = max(c[0] for c in caixas)
    miny = min(c[1] for c in caixas)
    maxy = max(c[1] for c in caixas)
    escala = (largura - 2 * MARGEM) / max(maxx - minx, 1)
    altura = (maxy - miny) * escala + 2 * MARGEM

    partes = [f'<svg viewBox="0 0 {largura:.0f} {altura:.0f}" role="img" '
              f'aria-label="linha montada">',
              f'<g class="geo" transform="translate({MARGEM - minx*escala:.2f} '
              f'{MARGEM - miny*escala:.2f}) scale({escala:.5f})">']
    for p in postos:
        corpo = "".join(desenhar(e) for e in p.simbolo.elementos
                        if e["tipo"] != "texto_furos")
        partes.append(f'<g transform="translate({p.dx:.1f} {p.dy:.1f}) '
                      f'rotate({p.giro:g})">{corpo}</g>')
    # cada ligacao tem duas flanges encostadas e os parafusos que as fecham -
    # e a juncao que puxa a ferragem, entao e ela que desenha o parafuso
    ruins = []
    for i, p in enumerate(postos[:-1]):
        ok, motivo = s.encaixa(p.simbolo, postos[i + 1].simbolo)
        saida = s.porta(p.simbolo, s.SAIDA)
        if ok and saida is not None:
            direcao = p.giro + (saida.direcao if saida.papel != "entrada" else 0)
            ferragem = s.junta_flangeada(p.saida[0], p.saida[1], direcao,
                                         saida.dn_pol)
            partes.append("".join(desenhar(e) for e in ferragem))
        else:
            ruins.append((p, motivo))
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
        # a cota fica DENTRO da peca, na metade de cima, longe do eixo
        raio = s.DE_TUBO.get(entrada.dn_pol, 100) / 2 * escala
        recuo = max(min(raio * 0.62, 12), 6)   # longe do eixo vermelho
        vertical = abs(p.saida[1] - p.entrada[1]) > abs(p.saida[0] - p.entrada[0])
        gira = f' transform="rotate(-90 {mx:.1f} {my:.1f})"' if vertical else ""
        duas = abs((entrada.dn_pol or 0) - (saida.dn_pol or 0)) > 0.01
        rotulo = (f"{comp:.0f}" if duas
                  else f'{(entrada.dn_pol or 0):g}"  {comp:.0f}')
        partes.append(f'<text class="marca" x="{mx:.1f}" y="{my - recuo:.1f}"{gira}>'
                      f'{rotulo}</text>')
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    args = p.parse_args()
    menor = {14: 12, 12: 10, 10: 8, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(args.dn, 2)
    for nome, pecas in (("sucção", succao(args.dn, menor)),
                        ("recalque", recalque(args.dn, menor))):
        svg, postos, fim = desenhar_linha(pecas)
        print(f'<figure class="linha"><figcaption>{nome} {args.dn:g}" — '
              f'{len(postos)} peças, fecha em '
              f'{abs(fim[0])/1000:.2f} × {abs(fim[1])/1000:.2f} m</figcaption>'
              f'{svg}</figure>')
        print(f"# {nome}: {len(postos)} pecas, fim em "
              f"({fim[0]:.0f}, {fim[1]:.0f}) direcao {fim[2]:.0f}", file=sys.stderr)


if __name__ == "__main__":
    main()
