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
         "VALVULA_HIDRAULICA": "L", "MEDIDOR": "L", "VALVULA_PE": "H", "BOMBA": "c"}


def elenco(dn):
    """Um simbolo por familia, na bitola pedida."""
    menor = {14: 12, 12: 10, 10: 8, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn, 2)
    return [
        s.tubo(dn, 1000),
        # o catalogo desenha a curva de pe, entrando por baixo: aqui e so a
        # pose da folha, a peca e a mesma que a montagem usa deitada
        s.girado(s.curva(dn, 90, -1), -90),
        s.girado(s.curva(dn, 60, -1), -90),
        s.girado(s.curva(dn, 45, -1), -90),
        s.girado(s.curva(dn, 30, -1), -90),
        s.girado(s.curva_saida(dn, 90, 2, sentido=-1), -90),
        s.te(dn, 2),
        s.reducao(dn, menor, "CONCENTRICA"),
        s.reducao(dn, menor, "EXCENTRICA", "topo"),
        s.adaptador(dn),
        s.crivo(dn),
        s.valvula_pe(dn),
        s.flange_cega(dn),
        s.flange_cega(dn, 2),
        s.flange_avulsa(dn),
        s.flange_avulsa(dn, "SOLTA"),
        s.manifold(dn if dn >= 4 else 4, menor),
        s.valvula_borboleta(dn, "ALAVANCA" if dn <= 6 else "CAIXA"),
        s.valvula_gaveta(dn),
        s.valvula_hidraulica(dn, "47"),
        s.medidor(dn),
        # o PEAD entra pela equivalencia da casa: 8" de aco vira DN225
        s.tubo_pead(_pead(dn), 6000),
        s.colar_pead(_pead(dn)),
        # a bomba: a mesma peça nas duas poses, como a curva
        s.bomba_megabloc(_megabloc(dn)),
        s.bomba_megabloc(_megabloc(dn), "VERTICAL"),
        # a mancalizada: mesma ponta molhada, mancal e motor sobre a base
        s.bomba_meganorm(_meganorm(dn)),
    ]


def _bocal(dn_linha):
    return {14: 8, 12: 8, 10: 6, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn_linha, 2)


def _megabloc(dn_linha):
    """A Megabloc cujo bocal de sucção casa com a redução que sai da linha."""
    return s.bomba_para_linha(_bocal(dn_linha)) or "80-250"


def _meganorm(dn_linha):
    return s.meganorm_para_linha(_bocal(dn_linha)) or "100-315"


def _pead(dn_pol):
    from motor.traducao import POLEGADA_MM
    return POLEGADA_MM.get(dn_pol) or 225


def desenhar(elemento):
    abre = fecha = ""
    fora = elemento.get("girar_fora")
    if fora:
        abre += f'<g transform="rotate({fora:g})">'
        fecha += "</g>"
    girar = elemento.get("girar")
    if girar:
        abre += f'<g transform="rotate({girar[0]:g} {girar[1]:.1f} {girar[2]:.1f})">'
        fecha = "</g>" + fecha
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
    # Celula uniforme. A borboleta de 8" mede 60 mm de corpo e sobe 480 com o
    # acionamento: no papel ela e um fio alto mesmo, e essa e a informacao.
    altura = ALTURA
    escala = min((LARGURA - 2 * MARGEM) / max(larg, 1),
                 (altura - 2 * MARGEM - 50) / max(alt, 1))
    dx = (LARGURA - larg * escala) / 2 - x0 * escala
    dy = (altura - 50 - alt * escala) / 2 - y0 * escala
    corpo = "".join(desenhar(e) for e in simbolo.elementos
                    if e["tipo"] not in ("texto_furos", "nota"))
    notas = [e for e in simbolo.elementos if e["tipo"] == "nota"]
    furos = next((e for e in simbolo.elementos if e["tipo"] == "texto_furos"), None)

    partes = [f'<svg viewBox="0 0 {LARGURA} {altura:.0f}" role="img" '
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
    # a bomba ja escreve as cotas com a letra do folheto (a/b/c ou h2/h1/a):
    # a medida genérica seria a mesma coisa duas vezes, uma sem letra
    if medida and not notas:
        pa = pontas[0] if pontas else simbolo.portas[0]
        pb = pontas[-1] if pontas else pa
        xm = dx + (pa.x + pb.x) / 2 * escala
        ym = dy + (pa.y + pb.y) / 2 * escala
        raio = ms.DE_TUBO.get(pa.dn_pol, 100) / 2 * escala
        recuo = max(min(raio * 0.62, 13), 7)
        bitola = (f'DN{simbolo.params["dn_mm"]:g}'
                  if simbolo.params.get("dn_mm") else f'{pa.dn_pol:g}"')
        rotulo = medida if len(bitolas) > 1 else f'{bitola}  {medida}'
        partes.append(f'<text class="marca" x="{xm:.1f}" '
                      f'y="{ym - recuo:.1f}">{rotulo}</text>')
    for n in notas:
        # elemento repetido: o desenho mostra um trecho e a nota diz o resto
        partes.append(f'<text class="marca" x="{dx + n["x"] * escala:.1f}" '
                      f'y="{dy + n["y"] * escala + 3:.1f}">{n["texto"]}</text>')
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
        # no PEAD o que manda no papel e o tubo, nao a flange: o DN E o
        # diametro externo, e e ele que a folha cota
        de = (simbolo.params.get("dn_mm")
              or ms.flange(entrada.dn_pol)["externo"])
        ym = dy + entrada.y * escala
        partes.append(f'<g class="anota"><text class="cota vertical" '
                      f'transform="rotate(-90 12 {ym:.1f})" x="12" '
                      f'y="{ym:.1f}">⌀{de:g}</text></g>')
    partes.append(f'<text class="rotulo" x="{LARGURA/2:.0f}" y="{altura-14:.0f}">'
                  f'{simbolo.rotulo}</text>')
    partes.append(f'<text class="fonte" x="{LARGURA/2:.0f}" y="{altura-2:.0f}">'
                  f'{simbolo.fonte or ""}</text>')
    partes.append("</svg>")
    return "".join(partes), altura > ALTURA


# Traco fino e preto, eixo vermelho traco-ponto, anotacao em cinza claro - o
# estilo pedido para a folha. Fica no gerador e nao numa folha solta para a
# folha sair sempre igual, sem ninguem remontar o HTML na mao.
ESTILO = """
:root{--tinta:#111;--eixo:#c0392b;--anota:#8a8a8a;--chapa:#f2f2f2}
body{margin:0;padding:24px;background:#fff;color:var(--tinta);
  font:13px/1.5 ui-sans-serif,system-ui,sans-serif}
h1{font-size:15px;font-weight:600;margin:0 0 4px}
p.sub{margin:0 0 20px;color:var(--anota);font-size:12px}
.folha{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
figure{margin:0;border:1px solid #e4e4e4;border-radius:3px;overflow:hidden}
figure svg{display:block;width:100%;height:auto}
.geo *{vector-effect:non-scaling-stroke;fill:none;stroke:var(--tinta);
  stroke-width:.9;stroke-linejoin:round}
.geo .flange{fill:var(--chapa)}
.geo .chapa_lisa{fill:var(--chapa)}
.geo .malha,.geo .furo,.geo .solda{stroke-width:.6;stroke:#666}
.geo .centro{stroke:var(--eixo);stroke-width:.7;
  stroke-dasharray:14 4 2 4;fill:none}
.geo .parafuso,.geo .porca{fill:var(--chapa);stroke-width:.7}
.geo .junta{stroke:var(--eixo);stroke-width:.9}
text{font-family:ui-monospace,SFMono-Regular,monospace;fill:var(--anota)}
.marca{font-size:8px;text-anchor:middle}
.cota{font-size:8px;text-anchor:middle}
.furos{font-size:7.5px;text-anchor:end}
.rotulo{font-size:9.5px;text-anchor:middle;fill:var(--tinta)}
.fonte{font-size:7px;text-anchor:middle;letter-spacing:.08em}
.anota .seta{fill:var(--anota);stroke:none}
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    p.add_argument("--fragmento", action="store_true",
                   help="so as <figure>, sem a pagina em volta")
    args = p.parse_args()
    lista = elenco(args.dn)
    figuras = []
    for simbolo in lista:
        svg, alto = celula(simbolo)
        figuras.append(f'<figure class="simbolo{" alto" if alto else ""}">'
                       f'{svg}</figure>')
    if args.fragmento:
        print("\n".join(figuras))
    else:
        print(f'<!doctype html><meta charset="utf-8">'
              f'<title>Simbolos {args.dn:g}"</title><style>{ESTILO}</style>'
              f'<h1>Simbolos parametricos &mdash; {args.dn:g}"</h1>'
              f'<p class="sub">{len(lista)} familias, cota do fabricante, '
              f'milimetro real</p><div class="folha">'
              + "\n".join(figuras) + "</div>")
    print(f"# {len(lista)} simbolos em {args.dn:g}\"", file=sys.stderr)


if __name__ == "__main__":
    main()
