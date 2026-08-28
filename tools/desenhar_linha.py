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
from motor.vista import MARGEM, desenhar_linha  # noqa: E402,F401
from tools.desenhar_simbolos import ESTILO, legenda  # noqa: E402
from tools.desenhar_simbolos import texto_no_eixo  # noqa: E402
from tools.desenhar_simbolos import desenhar  # noqa: E402

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
    # os dois colares olham para FORA: a flange na ponta do trecho e a solda
    # para dentro. O da esquerda e o mesmo desenho espelhado
    return ([s.colar_pead(dn_mm, lado="entrada")] + [s.tubo_pead(dn_mm)] * tubos
            + [s.colar_pead(dn_mm)])


def manifold_ventosas(dn, bocais=()):
    """O barrilete do recalque, com as duas luvas de ventosa e a flange cega
    fechando a ponta - a cega leva a terceira luva de 2\".

    Sem bocal por padrao: e o D12 da lista, o liso com as duas luvas. Bocal em
    cima e o que a descricao do item pedir, e nao um numero que este desenho
    escolha - ver motor/manifold.py.
    """
    return [s.manifold(dn, bocais), s.flange_cega(dn, 2)]


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
        svg, postos, fim, _colisoes = desenhar_linha(pecas, giro=giro)
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
