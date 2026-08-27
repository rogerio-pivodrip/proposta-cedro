#!/usr/bin/env python3
"""Desenha a folha de simbolos a partir da tabela de cotas - nao a mao.

Tres camadas, como diz docs/MOTOR.md: a geometria sai em milimetro real dentro
de um <g transform="scale(...)">, o traco nao engorda (vector-effect), e a
anotacao vive fora da escala, em pixel fixo.

A folha segue duas regras que a fazem ler como um caderno e nao como uma
colecao de figuras soltas:

  o eixo de todas as pecas cai na MESMA altura da celula, entao os eixos
  vermelhos se alinham de ponta a ponta na linha inteira;

  o que e fato da peca - bitola, norma, carcaca, peso, fonte - sai do desenho
  e vai para uma tarja embaixo dele. Dentro do desenho fica so o que e cota.

Uso: python3 tools/desenhar_simbolos.py [--dn 8] > simbolos.html
"""
import argparse
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402

LARGURA = 320          # px da celula
DESENHO = 190          # px da area de desenho dentro dela
MARGEM = 14
EIXO = 0.54            # onde o eixo da peca cai, em fracao da area de desenho
DEITADA = 2.6          # acima dessa proporcao a peca ocupa duas colunas

# titulo -> (subtitulo, altura da area de desenho em px, colunas minimas).
# A altura e por secao e nao por peca: dentro de uma secao todas as celulas
# tem a mesma caixa, e e isso que mantem os eixos alinhados de ponta a ponta.
SECOES = {
    "Tubo e curva": ("o que conduz e o que vira", 190, 1),
    "Derivação e mudança de bitola": ("onde a linha se reparte ou muda", 190, 1),
    "Fecho e flange": ("o que termina a linha e o que a aperta", 150, 1),
    "Válvula e medição": ("o que controla e o que mede", 250, 1),
    "Sucção": ("o que fica dentro d'água", 170, 1),
    # o PVC injetado desenha em arco liso, sem gomo: o gomo e chapa de aco
    # soldada, e essa peca sai de molde
    "PVC e Plasson": ("o traço de molde, não de chapa", 220, 1),
    # a conexao pequena e designada em polegada, e por isso e rosqueada: a
    # soldavel e a PBA a lista chama em milimetro
    "Rosca e bitola pequena": ("o que a norma converte", 150, 1),
    "PEAD": ("depois da primeira bomba", 160, 1),
    # a bomba e a ancora do desenho: numa coluna ela virava fio de cabelo
    "Bomba": ("a âncora do desenho", 300, 2),
}


def elenco(dn):
    """Um simbolo por familia, na bitola pedida, agrupado por secao."""
    menor = {14: 12, 12: 10, 10: 8, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn, 2)
    return [
        ("Tubo e curva", [
            s.tubo(dn, 1000),
            # o catalogo desenha a curva de pe, entrando por baixo: aqui e so
            # a pose da folha, a peca e a mesma que a montagem usa deitada
            s.girado(s.curva(dn, 90, -1), -90),
            s.girado(s.curva(dn, 60, -1), -90),
            s.girado(s.curva(dn, 45, -1), -90),
            s.girado(s.curva(dn, 30, -1), -90),
            s.girado(s.curva_saida(dn, 90, 2, sentido=-1), -90),
        ]),
        ("Derivação e mudança de bitola", [
            s.te(dn, 2),
            s.manifold(dn if dn >= 4 else 4, menor),
            s.reducao(dn, menor, "CONCENTRICA"),
            s.reducao(dn, menor, "EXCENTRICA", "topo"),
            s.adaptador(dn),
        ]),
        ("Fecho e flange", [
            s.flange_cega(dn),
            s.flange_cega(dn, 2),
            s.flange_avulsa(dn),
            s.flange_avulsa(dn, "SOLTA"),
        ]),
        ("Válvula e medição", [
            s.valvula_borboleta(dn, "ALAVANCA" if dn <= 6 else "CAIXA"),
            s.valvula_gaveta(dn),
            s.valvula_hidraulica(dn, "47"),
            s.valvula_retencao(dn),
            s.medidor(dn),
        ]),
        ("Sucção", [s.crivo(dn), s.valvula_pe(dn)]),
        # o PEAD entra pela equivalencia da casa: 8" de aco vira DN225
        # o mm entra pela mesma equivalencia do PEAD: 8" de aco vira DN225.
        # A junta vem da bitola porque e assim que a casa compra: a bolsa da
        # linha de irrigacao para em DN150, acima dela a peca e soldavel
        ("PVC e Plasson", [
            s.tubo_pvc(_pead(dn), 6000, _ponta_pvc(dn)),
            s.luva_pvc(_pead(dn), _junta_pvc(dn)),
            s.luva_reducao(_pead(dn), _pead(menor), _junta_pvc(dn)),
            s.girado(s.curva_pvc(_pead(dn), 90, _junta_pvc(dn), -1), -90),
            s.girado(s.curva_pvc(_pead(dn), 45, _junta_pvc(dn), -1), -90),
            s.te_pvc(_pead(dn), junta=_junta_pvc(dn)),
            s.te_pvc(_pead(dn), _pead(menor), _junta_pvc(dn)),
            s.adaptador_flange(_pead(dn)),
            s.bucha_reducao(_pead(dn), _pead(menor)),
        ]),
        # a bitola pequena nao acompanha a da linha: ela e derivacao, e a
        # ventosa e o manometro entram em 1/2" a 2" em qualquer casa de bomba
        ("Rosca e bitola pequena", [
            _em_pol(s.niple(_rosca_mm(2)), 2),
            _em_pol(s.uniao(_rosca_mm(2)), 2),
            _em_pol(s.luva_pvc(_rosca_mm(1), "ROSCA"), 1),
            _em_pol(s.cap_pvc(_rosca_mm(1), "ROSCA"), 1),
            _em_pol(s.bucha_reducao(_rosca_mm(2), _rosca_mm(1)), 2, 1),
        ]),
        ("PEAD", [s.tubo_pead(_pead(dn), 6000), s.colar_pead(_pead(dn))]),
        ("Bomba", [
            # a mesma bomba na menor e na maior potencia do folheto: o que
            # muda de uma para a outra e o motor, e a diferenca e de folha
            s.bomba_megabloc(_megabloc(dn)),
            s.bomba_megabloc(_megabloc(dn), cv=_maior_cv(_megabloc(dn))),
            # a bomba e a mesma peca nas duas poses, como a curva
            s.bomba_megabloc(_megabloc(dn), "VERTICAL"),
            # a mancalizada: mesma ponta molhada, mancal e motor sobre a base
            s.bomba_meganorm(_meganorm(dn)),
        ]),
    ]


def _bocal(dn_linha):
    return {14: 8, 12: 8, 10: 6, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn_linha, 2)


def _megabloc(dn_linha):
    """A Megabloc cujo bocal de sucção casa com a redução que sai da linha."""
    return s.bomba_para_linha(_bocal(dn_linha)) or "80-250"


def _meganorm(dn_linha):
    return s.meganorm_para_linha(_bocal(dn_linha)) or "100-315"


def _maior_cv(tamanho):
    """A maior potência que o folheto lista para essa bomba."""
    s.ficha_bomba(tamanho)
    linhas = s._bombas.get((tamanho, 4)) or []
    return max((float(r["cv"]) for r in linhas), default=None)


def _rosca_mm(dn_pol):
    """O milímetro que a ISO 65 dá para essa polegada de rosca."""
    from motor import cotas
    return cotas.milimetro_da_serie("ROSCA", dn_pol)[0]


def _em_pol(peca, dn_pol, menor=None):
    """A peça de rosca com o rótulo na polegada da lista, como o catálogo faz."""
    from motor import desenho
    return desenho.em_polegada(peca, _rosca_mm(dn_pol), dn_pol,
                               _rosca_mm(menor) if menor else None, menor,
                               "ISO 65", "ROSCA")


def _ponta_pvc(dn_pol):
    """A barra da linha de irrigação vem com bolsa; a soldável, lisa."""
    return "BOLSA" if _junta_pvc(dn_pol) == "BOLSA" else "LISA"


def _junta_pvc(dn_pol):
    """A bolsa da linha de irrigação para em DN150; acima dela, soldável."""
    return "BOLSA" if _pead(dn_pol) <= 150 else "SOLDA"


def _pead(dn_pol):
    from motor.traducao import POLEGADA_MM
    return POLEGADA_MM.get(dn_pol) or 225


# ------------------------------------------------------------------ desenho
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
        # a quina arredondada e da carcaça fundida do motor
        raio = (f' rx="{elemento["rx"]:.1f}"' if elemento.get("rx") else "")
        corpo = (f'<rect class="{classe}" x="{elemento["x"]:.1f}" '
                 f'y="{elemento["y"]:.1f}" width="{elemento["w"]:.1f}" '
                 f'height="{elemento["h"]:.1f}"{raio}/>')
    elif elemento["tipo"] == "circulo":
        corpo = (f'<circle class="{classe}" cx="{elemento["cx"]:.1f}" '
                 f'cy="{elemento["cy"]:.1f}" r="{elemento["r"]:.1f}"/>')
    else:
        return ""
    return abre + corpo + fecha


def texto_no_eixo(x, y, texto, classe="cota", tamanho=8.0, gira=""):
    """A cota centrada NO eixo, com o eixo aparado atras dela.

    E a convencao de CAD, e a casa pediu as duas coisas juntas: a cota fica
    centrada no eixo e o eixo abre para ela passar. As duas andam juntas mesmo
    - encostada no eixo sem trim a cota fica ilegivel, e fugindo do eixo para o
    lado ela deixa de dizer a que peca pertence.

    O trim e um retangulo da cor do papel desenhado ANTES do texto: nao da para
    cortar um path em SVG, e mascara custa mais do que vale numa folha com
    trezentas pecas. Por isso o giro vai no grupo e nao no texto - o retangulo
    tem de girar com ele.
    """
    largura = len(texto) * tamanho * 0.62 + tamanho * 0.8
    altura = tamanho * 1.3
    return (f'<g{gira}><rect class="trim" x="{x - largura/2:.1f}" '
            f'y="{y - altura/2:.1f}" width="{largura:.1f}" '
            f'height="{altura:.1f}"/>'
            f'<text class="{classe}" x="{x:.1f}" y="{y:.1f}" '
            f'dominant-baseline="central">{texto}</text></g>')


def cota_escrita(simbolo):
    """A medida que manda no desenho, escrita como o projetista escreve."""
    def acha(papel):
        return next((p for p in simbolo.portas if p.papel == papel), None)
    a = acha("entrada") or acha("maior") or simbolo.portas[0]
    b = acha("saida") or acha("menor")
    if not b or abs(b.x - a.x) < 1:
        return None
    return f"{abs(b.x - a.x):.0f}"


def bitola(simbolo):
    """A bitola escrita como o projetista fala dela."""
    # a peca de rosca e montada em milimetro mas COMPRADA em polegada: quando
    # os dois estao nos params, quem manda na tarja e a lista
    if simbolo.params.get("dn_pol"):
        pass
    elif simbolo.params.get("dn_mm"):
        return f'DN{simbolo.params["dn_mm"]:g}'
    pontas = [p for p in simbolo.portas if p.papel in s.ENTRADA + s.SAIDA]
    valores = []
    for p in pontas:
        if p.dn_pol and f'{p.dn_pol:g}"' not in valores:
            valores.append(f'{p.dn_pol:g}"')
    return "×".join(valores) or "—"


def fatos(simbolo):
    """O que e fato da peca, para a tarja - fora do desenho."""
    p = simbolo.params
    saida = []
    furos = next((e for e in simbolo.elementos if e["tipo"] == "texto_furos"),
                 None)
    if furos:
        saida.append(f'{furos["n"]}×⌀{furos["furo"]:g}')
    for chave, molde in (("norma_flange", "{}"), ("carcaca_motor", "carcaça {}"),
                         ("cv", "{:g} CV"), ("peso_kg", "{} kg"),
                         ("base", "base BD-{}"), ("acionamento", "{}")):
        if p.get(chave):
            saida.append(molde.format(p[chave]))
    if p.get("wafer"):
        saida.append("wafer")
    if p.get("flange_solta"):
        saida.append("flange solta")
    if p.get("tipo") == "SOLTA":
        saida.append("corre no tubo")
    elif p.get("tipo") == "SOLDAR":
        saida.append("para soldar")
    if p.get("saida_tipo") and p.get("saida_pol"):
        saida.append(f'{p["saida_tipo"].lower()} {p["saida_pol"]:g}"')
    return saida


def colunas(simbolo, minimo=1):
    """Peca comprida ocupa duas colunas.

    Um manifold de 1,5 m ou um tubo de PEAD de 6 m numa celula de bitola nao
    cabem sem virar fio de cabelo. Como a folha e uma grade, dar duas colunas
    a eles custa nada e devolve o dobro de escala.
    """
    _, _, larg, alt = simbolo.caixa
    return max(minimo, 2 if larg / max(alt, 1) > DEITADA else 1)


def celula(simbolo, altura=DESENHO, minimo=1):
    """O desenho de uma peca, com o eixo na altura padrao da secao."""
    x0, y0, larg, alt = simbolo.caixa
    n = colunas(simbolo, minimo)
    largura = LARGURA * n
    util = altura - 2 * MARGEM
    escala = min((largura - 2 * MARGEM) / max(larg, 1), util / max(alt, 1))
    dx = (largura - larg * escala) / 2 - x0 * escala
    # o eixo da peca (y=0) cai sempre na mesma altura, mas sem deixar a peca
    # sair da celula: quem manda e o que couber
    dy = MARGEM + util * EIXO
    dy = min(max(dy, MARGEM - y0 * escala),
             altura - MARGEM - (y0 + alt) * escala)
    corpo = "".join(desenhar(e) for e in simbolo.elementos
                    if e["tipo"] not in ("texto_furos", "nota"))
    notas = [e for e in simbolo.elementos if e["tipo"] == "nota"]

    partes = [f'<svg viewBox="0 0 {largura} {altura}" role="img" '
              f'aria-label="{simbolo.rotulo}">',
              f'<g class="geo" transform="translate({dx:.2f} {dy:.2f}) '
              f'scale({escala:.5f})">{corpo}</g>', '<g class="anota">']
    # A cota fica dentro da peca, so o texto - e so quando a peca nao escreve
    # a sua propria, como a bomba faz com as letras do folheto.
    medida = cota_escrita(simbolo)
    pontas = [p for p in simbolo.portas if p.papel in s.ENTRADA + s.SAIDA]
    if medida and not notas:
        pa, pb = (pontas[0], pontas[-1]) if pontas else (simbolo.portas[0],) * 2
        xm = dx + (pa.x + pb.x) / 2 * escala
        ym = dy + (pa.y + pb.y) / 2 * escala
        partes.append(texto_no_eixo(xm, ym, medida))
    for n in notas:
        # elemento repetido, letra de folheto: o desenho mostra e a nota diz.
        # A posicao vem girada: a nota nao passa pelo transform da geometria
        nx, ny = s.posicao_da_nota(n)
        partes.append(texto_no_eixo(dx + nx * escala, dy + ny * escala,
                                    n["texto"]))
    partes.append("</g></svg>")
    return "".join(partes)


ESTILO = """
:root{--tinta:#16181d;--eixo:#c0392b;--anota:#8c9099;--linha:#e6e8ec;
  --chapa:#f4f5f7;--fundo:#fff;--papel:#fff;--titulo:#3d424d}
*{box-sizing:border-box}
body{margin:0;padding:40px 32px 64px;background:var(--fundo);color:var(--tinta);
  font:400 13px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;
  -webkit-font-smoothing:antialiased}
.papel{max-width:1320px;margin:0 auto}
header{border-bottom:1.5px solid var(--tinta);padding-bottom:14px;
  margin-bottom:8px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
h1{font-size:17px;font-weight:600;letter-spacing:-.01em;margin:0}
header .dn{font:500 13px/1 ui-monospace,SFMono-Regular,monospace;
  color:var(--eixo);letter-spacing:.02em}
header .sub{margin-left:auto;color:var(--anota);font-size:11.5px}
.legenda{display:flex;gap:22px;flex-wrap:wrap;padding:10px 0 26px;
  border-bottom:1px solid var(--linha);margin-bottom:30px}
.legenda span{display:flex;align-items:center;gap:7px;color:var(--anota);
  font-size:11px}
.legenda svg{width:26px;height:8px;overflow:visible}
h2{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
  color:var(--titulo);margin:34px 0 0;padding-bottom:6px;
  border-bottom:1px solid var(--linha)}
h2 em{font-style:normal;font-weight:400;text-transform:none;letter-spacing:0;
  color:var(--anota);margin-left:10px;font-size:11.5px}
.folha{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));
  border-left:1px solid var(--linha)}
figure{margin:0;background:var(--fundo);padding:0 0 13px;
  border-right:1px solid var(--linha);border-bottom:1px solid var(--linha)}
figure.col2{grid-column:span 2}
@media (max-width:640px){figure.col2{grid-column:span 1}}
figure svg{display:block;width:100%;height:auto}
figcaption{padding:0 14px}
.nome{font-size:12px;font-weight:500;letter-spacing:-.005em;
  display:flex;gap:8px;align-items:baseline}
.nome b{font:500 12px/1 ui-monospace,SFMono-Regular,monospace;color:var(--eixo)}
.tarja{margin-top:3px;display:flex;gap:6px;flex-wrap:wrap;align-items:baseline;
  font:400 10.5px/1.5 ui-monospace,SFMono-Regular,monospace;color:var(--anota)}
.tarja i{font-style:normal}
.tarja i+i:before{content:"·";margin-right:6px}
.tarja .fonte{margin-left:auto;letter-spacing:.07em;text-transform:uppercase;
  font-size:9px;color:#b3b7bf}
.geo *{vector-effect:non-scaling-stroke;fill:none;stroke:var(--tinta);
  stroke-width:.85;stroke-linejoin:round;stroke-linecap:round}
.geo .flange,.geo .chapa_lisa,.geo .parafuso,.geo .porca{fill:var(--chapa)}
.geo .malha,.geo .furo,.geo .solda{stroke-width:.55;stroke:#8f949c}
.geo .centro{stroke:var(--eixo);stroke-width:.65;stroke-dasharray:12 3 1.5 3}
.geo .parafuso,.geo .porca{stroke-width:.65}
.geo .junta{stroke:var(--eixo);stroke-width:.9}
.geo .fluxo{fill:#8f949c;stroke:none}
text{font-family:ui-monospace,SFMono-Regular,monospace;fill:var(--anota)}
.cota{font-size:8px;text-anchor:middle}
.marca{font-size:9px;text-anchor:middle}
/* o trim: a cota nao foge do eixo, o eixo abre para ela */
.trim{fill:var(--papel);stroke:none}
"""

LEGENDA = [
    ("corpo", "corpo", 'M0 4 H26'),
    ("centro", "eixo", 'M0 4 H26'),
    ("malha", "detalhe", 'M0 4 H26'),
    ("flange", "flange e chapa", None),
    ("fluxo", "fluxo", 'M4 0 L4 8 L14 4 Z'),
]


def legenda():
    saida = []
    for classe, nome, d in LEGENDA:
        if d:
            forma = f'<path class="{classe}" d="{d}"/>'
        else:
            forma = f'<rect class="{classe}" x="0" y="0" width="26" height="8"/>'
        saida.append(f'<span><svg class="geo" viewBox="0 0 26 8">{forma}</svg>'
                     f'{nome}</span>')
    return f'<div class="legenda">{"".join(saida)}</div>'


def figura(simbolo, altura=DESENHO, minimo=1):
    nome = simbolo.rotulo
    n = colunas(simbolo, minimo)
    classe = f' class="col{n}"' if n > 1 else ""
    return (f'<figure{classe}>{celula(simbolo, altura, minimo)}<figcaption>'
            f'<div class="nome">{nome}</div>'
            f'<div class="tarja"><i>{bitola(simbolo)}</i>'
            + "".join(f"<i>{f}</i>" for f in fatos(simbolo))
            + f'<span class="fonte">{simbolo.fonte or ""}</span></div>'
            f'</figcaption></figure>')


def fragmento(dn):
    """As secoes da folha, sem a pagina em volta - devolve (html, total).

    Serve a folha solta e a prancha: quem compoe varias bitolas numa pagina
    so precisa disto.
    """
    grupos = elenco(dn)
    corpo = []
    for titulo, pecas in grupos:
        detalhe, altura, minimo = SECOES.get(titulo, ("", DESENHO, 1))
        corpo.append(f'<h2>{titulo}<em>{detalhe}</em></h2>')
        corpo.append('<div class="folha">'
                     + "".join(figura(peca, altura, minimo) for peca in pecas)
                     + "</div>")
    return "\n".join(corpo), sum(len(pecas) for _, pecas in grupos)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    p.add_argument("--fragmento", action="store_true",
                   help="so as <figure>, sem a pagina em volta")
    args = p.parse_args()
    texto, total = fragmento(args.dn)
    corpo = [texto]
    if args.fragmento:
        print("\n".join(corpo))
    else:
        print(f'<!doctype html><meta charset="utf-8">'
              f'<title>Símbolos {args.dn:g}"</title><style>{ESTILO}</style>'
              f'<div class="papel"><header><h1>Símbolos paramétricos</h1>'
              f'<span class="dn">{args.dn:g}"</span>'
              f'<span class="sub">{total} peças · cota do fabricante · '
              f'milímetro real</span></header>{legenda()}'
              + "".join(corpo) + "</div>")
    print(f"# {total} simbolos em {args.dn:g}\"", file=sys.stderr)


if __name__ == "__main__":
    main()
