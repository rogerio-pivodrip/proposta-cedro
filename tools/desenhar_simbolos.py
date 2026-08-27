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
        s.crivo(dn),
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
    # A cota fica dentro da peca, so o texto. Peca de duas bitolas leva a
    # medida em cada flange - a reducao diz 8" numa ponta e 6" na outra - e o
    # comprimento no meio do corpo.
    import motor.simbolos as ms
    medida = cota_escrita(simbolo)
    pontas = [p for p in simbolo.portas if p.papel in ms.ENTRADA + ms.SAIDA]
    bitolas = {p.dn_pol for p in pontas}
    partes.append('<g class="anota">')
    if len(bitolas) > 1:
        for porta in pontas:
            # a bitola vai acima da flange: nunca esbarra no corpo nem no eixo
            px = dx + porta.x * escala
            py = dy + porta.y * escala
            meia = ms.flange(porta.dn_pol)["externo"] / 2 * escala
            partes.append(f'<text class="marca" x="{px:.1f}" '
                          f'y="{py - meia - 4:.1f}">{porta.dn_pol:g}"</text>')
    if medida:
        pa = pontas[0] if pontas else simbolo.portas[0]
        pb = pontas[-1] if pontas else pa
        xm = dx + (pa.x + pb.x) / 2 * escala
        ym = dy + (pa.y + pb.y) / 2 * escala
        raio = ms.DE_TUBO.get(pa.dn_pol, 100) / 2 * escala
        recuo = max(min(raio * 0.62, 13), 7)
        rotulo = medida if len(bitolas) > 1 else f'{pa.dn_pol:g}"  {medida}'
        partes.append(f'<text class="marca" x="{xm:.1f}" '
                      f'y="{ym - recuo:.1f}">{rotulo}</text>')
    partes.append("</g>")
    if furos:
        partes.append(f'<text class="furos" x="{LARGURA-MARGEM}" y="{MARGEM+4}">'
                      f'{furos["n"]}×⌀{furos["furo"]:g}</text>')
    # o diametro, so o texto, na margem
    entrada = next((p for p in simbolo.portas if p.papel == "entrada"),
                   None) or next((p for p in simbolo.portas
                                  if p.papel in ("maior", "saida")), None)
    if entrada:
        import motor.simbolos as ms
        de = ms.flange(entrada.dn_pol)["externo"]
        ym = dy + entrada.y * escala
        partes.append(f'<g class="anota"><text class="cota vertical" '
                      f'transform="rotate(-90 12 {ym:.1f})" x="12" '
                      f'y="{ym:.1f}">⌀{de:g}</text></g>')
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
