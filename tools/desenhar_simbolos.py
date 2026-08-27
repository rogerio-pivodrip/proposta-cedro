#!/usr/bin/env python3
"""Desenha os simbolos a partir da tabela de cotas - nao a mao.

Tres camadas, como diz docs/MOTOR.md: a geometria sai em milimetro real dentro
de um <g transform="scale(...)">, o traco nao engorda (vector-effect), e a
anotacao - rotulo, cota escrita, fonte - vive fora da escala, em pixel fixo.

Uso: python3 tools/desenhar_simbolos.py [--dn 8] > simbolos.html
"""
import argparse
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402

LARGURA = 300          # px da celula
ALTURA = 200
MARGEM = 16
# a letra com que o catalogo chama a cota principal de cada familia
LETRA = {"CURVA": "C", "REDUCAO_CONCENTRICA": "E", "REDUCAO_EXCENTRICA": "E",
         "TE": "E", "MANIFOLD": "C", "CRIVO": "C", "ADAPTADOR": "C",
         "TUBO": "L", "VALVULA_BORBOLETA": "A", "VALVULA_GAVETA": "L",
         "VALVULA_HIDRAULICA": "L", "MEDIDOR": "L", "VALVULA_PE": "H"}


def elenco(dn):
    """Um simbolo por familia, na bitola pedida."""
    menor = {14: 12, 12: 10, 10: 8, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn, 2)
    return [
        s.tubo(dn, 1000),
        s.curva(dn, 90),
        s.curva(dn, 45),
        s.te(dn, 2),
        s.reducao(dn, menor, "CONCENTRICA"),
        s.reducao(dn, menor, "EXCENTRICA", "topo"),
        s.adaptador(dn),
        s.crivo(dn, "cesto"),
        s.crivo(dn, "cone"),
        s.valvula_pe(dn),
        s.flange_cega(dn),
        s.valvula_borboleta(dn, "ALAVANCA" if dn <= 6 else "CAIXA"),
        s.valvula_gaveta(dn),
        s.valvula_hidraulica(dn, "47"),
        s.medidor(dn),
    ]


def desenhar(elemento):
    girar = elemento.get("girar")
    abre = fecha = ""
    if girar:
        abre = f'<g transform="rotate({girar[0]:g} {girar[1]:.1f} {girar[2]:.1f})">'
        fecha = "</g>"
    classe = elemento.get("classe", "corpo")
    if elemento["tipo"] == "path":
        corpo = f'<path class="{classe}" d="{elemento["d"]}"/>'
    elif elemento["tipo"] == "rect":
        corpo = (f'<rect class="{classe}" x="{elemento["x"]:.1f}" '
                 f'y="{elemento["y"]:.1f}" width="{elemento["w"]:.1f}" '
                 f'height="{elemento["h"]:.1f}"/>')
    elif elemento["tipo"] == "circulo":
        corpo = (f'<circle class="{classe}" cx="{elemento["cx"]:.1f}" '
                 f'cy="{elemento["cy"]:.1f}" r="{elemento["r"]:.1f}"/>')
    else:
        return ""
    return abre + corpo + fecha


def cota_escrita(simbolo):
    """A medida que manda no desenho, escrita como o projetista escreve."""
    def acha(papel):
        return next((p for p in simbolo.portas if p.papel == papel), None)
    a = acha("entrada") or acha("maior") or simbolo.portas[0]
    b = acha("saida") or acha("menor")
    if not b or abs(b.x - a.x) < 1:
        return None
    return f"{abs(b.x - a.x):.0f}"


def seta(x, y, sentido, tamanho=4.5, vertical=False):
    """Ponta de seta da linha de cota, como o catalogo desenha."""
    if vertical:
        return (f'<path class="seta" d="M{x:.1f} {y:.1f} '
                f'l{-tamanho*0.42:.1f} {sentido*tamanho:.1f} '
                f'l{tamanho*0.84:.1f} 0 Z"/>')
    return (f'<path class="seta" d="M{x:.1f} {y:.1f} '
            f'l{sentido*tamanho:.1f} {-tamanho*0.42:.1f} '
            f'l0 {tamanho*0.84:.1f} Z"/>')


def celula(simbolo):
    x0, y0, larg, alt = simbolo.caixa
    escala = min((LARGURA - 2 * MARGEM) / max(larg, 1),
                 (ALTURA - 2 * MARGEM - 50) / max(alt, 1))
    dx = (LARGURA - larg * escala) / 2 - x0 * escala
    dy = (ALTURA - 50 - alt * escala) / 2 - y0 * escala
    corpo = "".join(desenhar(e) for e in simbolo.elementos
                    if e["tipo"] != "texto_furos")
    furos = next((e for e in simbolo.elementos if e["tipo"] == "texto_furos"), None)

    partes = [f'<svg viewBox="0 0 {LARGURA} {ALTURA}" role="img" '
              f'aria-label="{simbolo.rotulo}">',
              f'<g class="geo" transform="translate({dx:.2f} {dy:.2f}) '
              f'scale({escala:.5f})">{corpo}</g>']
    medida = cota_escrita(simbolo)
    y_base = dy + (y0 + alt) * escala
    y_cota = min(y_base + 16, ALTURA - 38)
    if medida:
        def acha(papel):
            return next((p for p in simbolo.portas if p.papel == papel), None)
        pa = acha("entrada") or acha("maior") or simbolo.portas[0]
        pb = acha("saida") or acha("menor")
        xa = dx + pa.x * escala
        xb = dx + pb.x * escala
        letra = LETRA.get(simbolo.familia, "")
        partes.append(
            f'<g class="anota">'
            f'<path class="chamada" d="M{xa:.1f} {y_base + 3:.1f} V{y_cota+4:.1f} '
            f'M{xb:.1f} {y_base + 3:.1f} V{y_cota+4:.1f}"/>'
            f'<path class="linha-cota" d="M{xa:.1f} {y_cota:.1f} H{xb:.1f}"/>'
            + seta(xa, y_cota, 1) + seta(xb, y_cota, -1) +
            f'<text class="cota" x="{(xa+xb)/2:.1f}" y="{y_cota-5:.1f}">'
            f'<tspan class="letra">{letra}</tspan> {medida}</text>'
            f'</g>')
    if furos:
        partes.append(f'<text class="furos" x="{LARGURA-MARGEM}" y="{MARGEM+4}">'
                      f'{furos["n"]}×⌀{furos["furo"]:g}</text>')
    # cota vertical: o diametro externo da flange de entrada
    entrada = next((p for p in simbolo.portas if p.papel == "entrada"),
                   None) or next((p for p in simbolo.portas
                                  if p.papel in ("maior", "saida")), None)
    if entrada:
        import motor.simbolos as ms
        de = ms.flange(entrada.dn_pol)["externo"]
        xv = 12          # sempre na margem, nunca em cima do desenho
        ya = dy + (entrada.y - de / 2) * escala
        yb = dy + (entrada.y + de / 2) * escala
        if yb - ya > 26:
            partes.append(
                f'<g class="anota">'
                f'<path class="linha-cota" d="M{xv:.1f} {ya:.1f} V{yb:.1f}"/>'
                + seta(xv, ya, 1, 4.2, vertical=True)
                + seta(xv, yb, -1, 4.2, vertical=True) +
                f'<text class="cota vertical" transform="rotate(-90 {xv-4:.1f} '
                f'{(ya+yb)/2:.1f})" x="{xv-4:.1f}" y="{(ya+yb)/2:.1f}">'
                f'<tspan class="letra">⌀</tspan>{de:g}</text></g>')
    partes.append(f'<text class="rotulo" x="{LARGURA/2:.0f}" y="{ALTURA-14}">'
                  f'{simbolo.rotulo}</text>')
    partes.append(f'<text class="fonte" x="{LARGURA/2:.0f}" y="{ALTURA-2}">'
                  f'{simbolo.fonte or ""}</text>')
    partes.append("</svg>")
    return "".join(partes)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    args = p.parse_args()
    for simbolo in elenco(args.dn):
        print(f'<figure class="simbolo">{celula(simbolo)}</figure>')
    print(f"# {len(elenco(args.dn))} simbolos em {args.dn:g}\"", file=sys.stderr)


if __name__ == "__main__":
    main()
