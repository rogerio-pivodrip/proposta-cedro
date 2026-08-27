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
import re
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402
from motor.svg import (DEFS, ESTILO, cor_de, desenhar,  # noqa: E402,F401
                       texto_no_eixo)
from motor.vista import MODOS  # noqa: E402

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


ACO = ("ACO_ZINCADO", "ACO_CARBONO", "INOX", None)
PLASTICO = ("PVC", "PVC_PLASSON")


def _catalogo():
    global _cat
    if _cat is None:
        from motor.catalogo import Catalogo
        _cat = Catalogo()
    return _cat


_cat = None


def _escolher(familia, dn, materiais=None, texto=None, sem=None, **filtros):
    """O item da LISTA que representa essa familia nessa bitola.

    A folha nao desenha mais peca parametrica solta: cada celula sai de um
    item do catalogo, com codigo SAP. A casa pediu assim - "use apenas as
    pecas que temos na LM com codigo" - e ela esta certa por um motivo que ja
    tinha aparecido duas vezes nesta semana: peca inventada nao se compra. A
    curva de 60 graus estava na folha em oito bitolas e nao existe na lista; a
    valvula de pe em aco tambem nao - o que a lista tem e o CRIVO para valvula
    de pe.
    """
    cat = _catalogo()
    cand = cat.buscar(familia, dn, material=None, **filtros)
    if materiais:
        cand = [i for i in cand if i["material"] in materiais]
    if texto:
        cand = [i for i in cand if re.search(texto, i["descricao"], re.I)]
    if sem:
        cand = [i for i in cand if not re.search(sem, i["descricao"], re.I)]
    return cand[0] if cand else None


def pedidos(dn):
    """O que a folha PEDE ao catalogo nesta bitola, secao por secao.

    Cada pedido e (rotulo, familia, bitola, filtros). O rotulo so aparece
    quando a lista NAO tem a peca - e o que a secao mostra no lugar dela.
    """
    menor = {14: 12, 12: 10, 10: 8, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn, 2)
    mm = _plasson(dn)
    mm_menor = _plasson(menor) or (_abaixo_plasson(mm) if mm else None)
    junta = _junta_pvc(dn)
    # o catalogo desenha a curva de pe, entrando por baixo: e so a pose da
    # folha, a peca e a mesma que a montagem usa deitada
    de_pe = {"pose": -90}
    return [
        ("Tubo e curva", [
            ("tubo", "TUBO", dn, {"materiais": ACO, "comprimento_mm": 1000}),
            ("curva 90°", "CURVA", dn, {"materiais": ACO, "angulo": 90, **de_pe}),
            ("curva 60°", "CURVA", dn, {"materiais": ACO, "angulo": 60, **de_pe}),
            ("curva 45°", "CURVA", dn, {"materiais": ACO, "angulo": 45, **de_pe}),
            ("curva 30°", "CURVA", dn, {"materiais": ACO, "angulo": 30, **de_pe}),
            ('curva 90° c/ escape 2"', "CURVA", dn,
             {"materiais": ACO, "angulo": 90, "dn_saida": 2, **de_pe}),
        ]),
        ("Derivação e mudança de bitola", [
            ("tê", "TE", dn, {"materiais": ACO}),
            ("manifold", "MANIFOLD", dn, {"materiais": ACO}),
            (f'redução concêntrica {dn:g}"×{menor:g}"', "REDUCAO_CONCENTRICA",
             dn, {"materiais": ACO, "dn_saida": menor}),
            (f'redução excêntrica {dn:g}"×{menor:g}"', "REDUCAO_EXCENTRICA",
             dn, {"materiais": ACO, "dn_saida": menor}),
            ("adaptador", "ADAPTADOR", dn, {"materiais": ACO}),
        ]),
        ("Fecho e flange", [
            ("flange cega", "FLANGE_CEGA", dn,
             {"materiais": ACO, "sem": r"C/\s*(LG|FL)"}),
            ('flange cega c/ luva 2"', "FLANGE_CEGA", dn,
             {"materiais": ACO, "dn_saida": 2}),
            ("flange", "FLANGE", dn,
             {"materiais": ACO, "sem": r"P/\s*COLAR|SEXTAVADO|CPVC"}),
        ]),
        ("Válvula e medição", [
            # o acionamento nao entra como filtro e sim como PREFERENCIA: o
            # catalogo ja ordena alavanca, caixa e volante nessa ordem, e
            # exigir alavanca deixava a borboleta de 3" fora da folha porque a
            # lista so tem caixa e volante nessa bitola
            ("válvula borboleta", "VALVULA_BORBOLETA", dn, {}),
            ("registro de gaveta", "VALVULA_GAVETA", dn, {}),
            ("válvula hidráulica", "VALVULA_HIDRAULICA", dn, {}),
            ("válvula de retenção", "VALVULA_RETENCAO", dn, {}),
            ("medidor", "MEDIDOR", dn, {}),
        ]),
        ("Sucção", [
            ("crivo", "CRIVO", dn, {"materiais": ACO}),
            ("válvula de pé", "VALVULA_PE", dn, {}),
        ]),
        # o mm entra pela equivalencia da casa: 8" de aco vira DN225. A junta
        # vem da bitola porque e assim que a casa compra: a bolsa da linha de
        # irrigacao para em DN150, acima dela a peca e soldavel
        ("PVC e Plasson", [] if not mm else [
            ("tubo", "TUBO", mm, {"materiais": PLASTICO}),
            ("luva", "LUVA", mm, {"materiais": PLASTICO}),
            ("luva de redução", "LUVA", mm,
             {"materiais": PLASTICO, "dn_saida": mm_menor}),
            ("curva 90°", "CURVA", mm,
             {"materiais": PLASTICO, "angulo": 90, **de_pe}),
            ("curva 45°", "CURVA", mm,
             {"materiais": PLASTICO, "angulo": 45, **de_pe}),
            ("tê", "TE", mm, {"materiais": PLASTICO}),
            ("tê de redução", "TE_REDUZIDO", mm,
             {"materiais": PLASTICO, "dn_saida": mm_menor}),
            # o adaptador p/ flange da lista nao declara material na
            # descricao - "ADAPTADOR P/FL 225MM SOLDA" - entao quem o
            # identifica e o texto, nao o material
            ("adaptador p/ flange", "ADAPTADOR", mm, {"texto": r"P/\s*FL"}),
            ("bucha de redução", "BUCHA_REDUCAO", mm,
             {"materiais": PLASTICO, "dn_saida": mm_menor}),
        ]),
        # a bitola pequena nao acompanha a da linha: ela e derivacao, e a
        # ventosa e o manometro entram em 1/2" a 2" em qualquer casa de bomba
        ("Rosca e bitola pequena", [
            ('niple 2"', "NIPLE", 2, {}),
            ('união 2"', "UNIAO", 2, {}),
            ('luva 1"', "LUVA", 1, {}),
            ('cap 1"', "CAP", 1, {}),
            ('bucha de redução 2"×1"', "BUCHA_REDUCAO", 2, {"dn_saida": 1}),
            ('ventosa 2"', "VENTOSA", 2, {}),
        ]),
        ("PEAD", [
            ("tubo PEAD", "TUBO", _pead(dn), {"materiais": ("PEAD",)}),
            ("colar de PEAD", "COLAR_PEAD", _pead(dn), {}),
            # a flange SOLTA da lista e a do colar de PEAD, designada em DN
            # milimetro: "FL P/COLAR. PEAD DN225 NBR PN16". Ela nao existe na
            # secao de aco, e por isso mora aqui
            ("flange p/ colar", "FLANGE", _pead(dn), {"texto": r"P/\s*COLAR"}),
        ]),
    ]


def vazia(titulo, dn):
    """Por que a secao saiu vazia nesta bitola - a folha diz, nao esconde."""
    if titulo != "PVC e Plasson":
        return ""
    if _plasson(dn) is None:
        return ("A linha Plasson do catálogo acaba em DN225 — acima disso a "
                "linha segue em aço ou em PEAD.")
    return (f"A lista não tem conexão de PVC em DN{_plasson(dn):g}. A série "
            f"Plasson existe nessa bitola, mas a casa não compra peça dela.")


def elenco(dn):
    """Um simbolo por familia, na bitola pedida, agrupado por secao.

    Devolve (titulo, pecas, faltam): o que a lista tem desenhado, e o nome do
    que ela NAO tem nesta bitola. A folha mostra os dois - peca que falta
    calada faz supor que faltou desenhar, e o que falta e informacao.
    """
    from motor import desenho
    grupos = []
    for titulo, lista in pedidos(dn):
        pecas, faltam = [], []
        for rotulo, familia, bitola, filtros in lista:
            filtros = dict(filtros)
            pose = filtros.pop("pose", 0)
            item = _escolher(familia, bitola, **filtros)
            if item is None:
                faltam.append(rotulo)
                continue
            try:
                peca = desenho.de_item(item)
            except Exception as erro:                   # noqa: BLE001
                faltam.append(f"{rotulo} — {type(erro).__name__}: {erro}")
                continue
            pecas.append(s.girado(peca, pose) if pose else peca)
        grupos.append((titulo, pecas, faltam))
    grupos.append(("Bomba", _bombas(dn), []))
    return grupos


_desenhadas = None


def _bombas(dn):
    """As bombas da LISTA cujo bocal de recalque casa com esta linha.

    As tres linhas que a casa compra - Megabloc, Meganorm e GSD - e todas
    saem de item com codigo. O folheto entra so para dar a cota; quem escolhe
    o modelo e a lista, e por isso a potencia da tarja e a que se compra e nao
    uma proporcao.

    A bitola do recalque nao sai do nome sem desenhar: cada linha nomeia de um
    jeito. Entao desenha e le a porta de saida, que e onde as tres concordam.
    """
    global _desenhadas
    from motor import desenho
    if _desenhadas is None:
        _desenhadas = []
        for item in _catalogo().itens:
            if item.get("familia") != "BOMBA":
                continue
            try:
                peca = desenho.de_item(item)
            except Exception:                           # noqa: BLE001
                continue
            saida = s.porta(peca, s.SAIDA)
            if saida and saida.dn_pol:
                _desenhadas.append((saida.dn_pol, peca))
    alvo = _bocal(dn)
    saida, vistas = [], set()
    for dn_saida, peca in _desenhadas:
        linha = (peca.params.get("linha")
                 or ("METN" if "meganorm" in peca.rotulo.lower() else None)
                 or ("METB" if "megabloc" in peca.rotulo.lower() else "?"))
        if dn_saida != alvo or linha in vistas:
            continue
        vistas.add(linha)
        saida.append(peca)
    return saida


def _bocal(dn_linha):
    return {14: 8, 12: 8, 10: 6, 8: 6, 6: 4, 5: 4, 4: 3, 3: 2}.get(dn_linha, 2)





def _rosca_mm(dn_pol):
    """O milímetro que a ISO 65 dá para essa polegada de rosca."""
    from motor import cotas
    return cotas.milimetro_da_serie("ROSCA", dn_pol)[0]



def _abaixo_plasson(mm):
    """A bitola Plasson imediatamente abaixo - quando a menor da linha de aco
    nao tem correspondente na serie do Plasson."""
    menores = [d for d in PLASSON if d < mm]
    return menores[-1] if menores else mm



def _junta_pvc(dn_pol):
    """A bolsa da linha de irrigação para em DN150; acima dela, soldável."""
    return "BOLSA" if _pead(dn_pol) <= 150 else "SOLDA"


def _pead(dn_pol):
    from motor.traducao import POLEGADA_MM
    return POLEGADA_MM.get(dn_pol) or 225


# A linha Plasson do catalogo existe em 25, 32, 40, 50, 63, 75, 90, 110, 125,
# 140, 160 e 225 - e acaba ai. Acima de 225 a folha desenhava luva, curva, te
# e bucha de DN280, 315 e 355, que sao 27 pecas que a lista nao tem: o PEAD
# sobe ate 355, o PVC/Plasson nao. Peca que nao existe nao entra na folha.
PLASSON = (25, 32, 40, 50, 63, 75, 90, 110, 125, 140, 160, 225)


def _plasson(dn_pol):
    """O DN da linha Plasson para essa bitola, ou None se ela nao vai ate la."""
    mm = _pead(dn_pol)
    return mm if mm in PLASSON else None


# ------------------------------------------------------------------ desenho
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

    # o mesmo grupo `peca` da vista montada, com a mesma librea: a folha e a
    # linha tem de mostrar a valvula da mesma cor, senao a folha vira uma
    # segunda opiniao sobre como a peca e
    cor = cor_de(simbolo)
    pintura = f' data-cor="{cor}"' if cor else ""
    partes = [f'<svg viewBox="0 0 {largura} {altura}" role="img" '
              f'aria-label="{simbolo.rotulo}">',
              f'<g class="geo" transform="translate({dx:.2f} {dy:.2f}) '
              f'scale({escala:.5f})"><g class="peca"{pintura} '
              f'data-familia="{simbolo.familia}">{corpo}</g></g>',
              '<g class="anota">']
    # A cota fica dentro da peca, so o texto - e so quando a peca nao escreve
    # a sua propria, como a bomba faz com as letras do folheto.
    medida = cota_escrita(simbolo)
    pontas = [p for p in simbolo.portas if p.papel in s.ENTRADA + s.SAIDA]
    if medida and not notas:
        # a cota cai no MEIO DO EIXO, nao no meio entre as portas: na curva o
        # meio entre as portas fica na corda, fora do tubo
        meio = s.meio_do_eixo(simbolo)
        if meio is None:
            pa, pb = ((pontas[0], pontas[-1]) if pontas
                      else (simbolo.portas[0],) * 2)
            meio = ((pa.x + pb.x) / 2, (pa.y + pb.y) / 2)
        partes.append(texto_no_eixo(dx + meio[0] * escala,
                                    dy + meio[1] * escala, medida))
    for n in notas:
        # elemento repetido, letra de folheto: o desenho mostra e a nota diz.
        # A posicao vem girada: a nota nao passa pelo transform da geometria
        nx, ny = s.posicao_da_nota(n)
        partes.append(texto_no_eixo(dx + nx * escala, dy + ny * escala,
                                    n["texto"]))
    partes.append("</g></svg>")
    return "".join(partes)


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
    # o codigo SAP e a descricao da LISTA vem primeiro na tarja: a folha
    # desenha o que se compra, e o codigo e o nome de compra da peca
    sap = simbolo.params.get("sap")
    descricao = simbolo.params.get("descricao")
    codigo = f'<b class="sap">{sap}</b>' if sap else ""
    lista = (f'<div class="lista">{codigo}<span>{descricao}</span></div>'
             if sap or descricao else "")
    return (f'<figure{classe}>{celula(simbolo, altura, minimo)}<figcaption>'
            f'<div class="nome">{nome}</div>{lista}'
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
    for titulo, pecas, faltam in grupos:
        detalhe, altura, minimo = SECOES.get(titulo, ("", DESENHO, 1))
        corpo.append(f'<h2>{titulo}<em>{detalhe}</em></h2>')
        if pecas:
            corpo.append('<div class="folha">'
                         + "".join(figura(peca, altura, minimo)
                                   for peca in pecas)
                         + "</div>")
        elif vazia(titulo, dn):
            # secao vazia diz POR QUE esta vazia: some sem explicacao e o
            # leitor supoe que faltou desenhar
            corpo.append(f'<p class="vazia">{vazia(titulo, dn)}</p>')
        if faltam:
            # o que a LISTA nao tem nesta bitola. Aparece porque e informacao:
            # nao ha curva de 60 graus no catalogo, em bitola nenhuma, e quem
            # projeta precisa saber disso antes de especificar uma
            corpo.append('<p class="falta">a lista não tem nesta bitola: '
                         + ", ".join(faltam) + "</p>")
    return "\n".join(corpo), sum(len(pecas) for _, pecas, _ in grupos)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8)
    p.add_argument("--fragmento", action="store_true",
                   help="so as <figure>, sem a pagina em volta")
    p.add_argument("--modo", default="traco", choices=list(MODOS),
                   help="traco (projeto), pb (para plotar), metal (colorido)")
    args = p.parse_args()
    texto, total = fragmento(args.dn)
    corpo = [texto]
    # os degrades ficam num <svg> escondido no topo: gradiente tem de morar
    # dentro de um SVG, e uma vez na pagina serve a todas as celulas
    defs = f'<svg width="0" height="0" style="position:absolute">{DEFS}</svg>'
    if args.fragmento:
        print(defs + "\n".join(corpo))
    else:
        print(f'<!doctype html><meta charset="utf-8">'
              f'<title>Símbolos {args.dn:g}"</title><style>{ESTILO}</style>'
              f'{defs}<div class="papel modo-{args.modo}">'
              f'<header><h1>Símbolos paramétricos</h1>'
              f'<span class="dn">{args.dn:g}"</span>'
              f'<span class="sub">{total} peças · cota do fabricante · '
              f'milímetro real</span></header>{legenda()}'
              + "".join(corpo) + "</div>")
    print(f"# {total} simbolos em {args.dn:g}\"", file=sys.stderr)


if __name__ == "__main__":
    main()
