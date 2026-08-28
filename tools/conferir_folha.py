#!/usr/bin/env python3
"""Confere a prancha de impressao: escala, formato e lista.

A folha e o unico formato de saida que alguem ASSINA, e o unico que sai do
programa em papel. Tres coisas tem de ser verdade nela, e nenhuma e "o HTML
gera":

  **A escala e a maior da NORMA em que o desenho cabe.** Nao "o que couber":
  um dos numeros da NBR 8196, para que quem mede com escalimetro ache a cota.
  Entao cobra-se as duas metades - que o desenho CABE na escala escolhida, e
  que na escala imediatamente maior ele NAO caberia. Sem a segunda metade,
  1:1000 passaria em todo teste.

  **A folha mede o que o formato diz.** A4 e 210 x 297, e a impressao tem de
  sair no tamanho de verdade - senao a escala escrita no carimbo e mentira, e
  uma escala mentirosa e pior que escala nenhuma.

  **A lista da folha e a mesma da planilha.** Sao duas saidas do mesmo
  documento; se divergissem, a obra receberia um desenho e o comercial
  compraria outro.

Uso: python3 tools/conferir_folha.py
"""
import re
import sys

sys.path.insert(0, ".")
from api.nucleo import Sessao, executar                # noqa: E402
from motor import folha, vista                         # noqa: E402
from motor.catalogo import Catalogo                    # noqa: E402
from motor import templates                            # noqa: E402


def main():
    problemas = []

    def conferir(caso, condicao, detalhe=""):
        if condicao:
            print(f"  ok {caso}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}" + (f": {detalhe}" if detalhe else ""))

    catalogo = Catalogo()

    print("== a escala é a maior da norma em que o desenho cabe")
    for dn, curva, formato, orientacao in ((8, 90, "A3", "paisagem"),
                                           (8, None, "A4", "retrato"),
                                           (14, 90, "A2", "paisagem"),
                                           (4, 45, "A1", "paisagem")):
        linha, _r, _f = templates.succao(catalogo, dn, curva=curva)
        html, ficha = folha.montar(linha, formato, orientacao)
        postos, _ = vista.postos_da_linha(linha)
        ext_x, ext_y = vista.extensao(postos)
        largura, altura = folha.medidas(formato, orientacao)
        esq, fora = folha.margens(formato)
        util_x = (largura - esq - fora) - min(folha.CARIMBO[0],
                                              (largura - esq - fora) * 0.34) - 4
        util_y = (altura - 2 * fora) - folha.CARIMBO[1] - 4
        folga = 2 * vista.MARGEM * folha.ANOTA
        d = ficha["divisor"]
        cabe = (ext_x / d <= util_x - folga + .01 and
                ext_y / d <= util_y - folga + .01)
        anterior = [e for e in vista.ESCALAS if e < d]
        estoura = True
        if anterior:
            a = anterior[-1]
            estoura = not (ext_x / a <= util_x - folga and
                           ext_y / a <= util_y - folga)
        conferir(f'{dn:g}" em {formato} {orientacao} → {ficha["escala"]} cabe',
                 cabe, f'{ext_x/d:.0f}x{ext_y/d:.0f} em {util_x:.0f}x{util_y:.0f}')
        conferir(f'  e é a maior: a próxima estouraria', estoura)
        conferir("  a escala escrita no carimbo é a usada",
                 f'>{ficha["escala"]}<' in html.replace("</span>", "<")
                 or ficha["escala"] in html)

    print("\n== a folha mede o que o formato diz")
    for formato, orientacao, espera in (("A4", "retrato", (210, 297)),
                                        ("A3", "paisagem", (420, 297)),
                                        ("A1", "paisagem", (841, 594))):
        linha, _r, _f = templates.succao(catalogo, 8)
        html, _ficha = folha.montar(linha, formato, orientacao)
        pagina = re.search(r"@page \{ size: ([\d.]+)mm ([\d.]+)mm", html)
        prancha = re.search(r"\.prancha \{\s*width:\s*([\d.]+)mm;\s*"
                            r"height:\s*([\d.]+)mm", html)
        medido = tuple(float(v) for v in pagina.groups()) if pagina else None
        conferir(f"{formato} {orientacao} = {espera[0]}x{espera[1]} mm",
                 medido == tuple(float(v) for v in espera), str(medido))
        conferir("  a página e a prancha têm a mesma medida",
                 prancha and prancha.groups() == pagina.groups())

    print("\n== a lista da folha é a mesma da planilha")
    linha, _r, _f = templates.succao(catalogo, 8, curva=90)
    html, ficha = folha.montar(linha, "A3", "paisagem")
    itens, _avisos = linha.lista_materiais()
    na_folha = re.findall(r'<td class="q">(\d+)</td><td class="c">([\w-]*)</td>'
                          r"<td>([^<]*)</td>", html)
    conferir("uma linha por item", len(na_folha) == len(itens),
             f"{len(na_folha)} contra {len(itens)}")
    conferir("mesmo código e mesma quantidade, na mesma ordem",
             [(q, s) for q, s, _d in na_folha] ==
             [(str(r["qtd"]), r["sap"]) for r in itens])
    conferir("o carimbo conta os mesmos itens", ficha["itens"] == len(itens))

    print("\n== a cota cai no eixo da peça, e não na corda")
    # Numa curva o meio entre as duas portas cai na CORDA, que passa por fora
    # do tubo - a cota ia parar no ar ao lado da peca. E o defeito que
    # meio_do_eixo existe para nao ter.
    from motor import simbolos as s                    # noqa: E402
    curva = s.curva(8, 90)
    entrada, saida = s.porta(curva, s.ENTRADA), s.porta(curva, s.SAIDA)
    corda = ((entrada.x + saida.x) / 2, (entrada.y + saida.y) / 2)
    eixo = s.meio_do_eixo(curva)
    raio = s.DE_TUBO[8] / 2
    conferir("na curva o meio do eixo não é o meio da corda",
             ((eixo[0] - corda[0]) ** 2 + (eixo[1] - corda[1]) ** 2) ** .5 > raio,
             f"eixo {eixo[:2]} · corda {corda}")
    reto = s.meio_do_eixo(s.tubo(8, 1000))
    conferir("no tubo reto os dois coincidem", abs(reto[0] - 500) < 1
             and abs(reto[1]) < 1, str(reto))
    conferir("e o eixo diz a direção dele ali, para a cota deitar junto",
             abs(eixo[2] + 30) < 1 and abs(reto[2]) < 1,
             f"curva {eixo[2]:.1f}° · tubo {reto[2]:.1f}°")

    linha, _r, _f = templates.succao(catalogo, 8, curva=90)
    html, _ficha = folha.montar(linha, "A3", "paisagem")
    conferir("a cota não leva mais tarja atrás dela", "trim" not in html)
    # a medida vai so no TUBO: e a unica peca que se corta, e por isso a unica
    # cujo comprimento e decisao de projeto. O resto vem preso ao codigo SAP
    escrito = re.findall(r'class="marca"[^>]*>([^<]+)</text>', html)
    tubos = [p for p in linha.pecas if p.familia == "TUBO"]
    conferir("uma cota por tubo, e nenhuma nas outras peças",
             len(escrito) == len(tubos),
             f"{escrito} para {len(tubos)} tubo(s) em "
             f"{[p.familia for p in linha.pecas]}")
    conferir("ela abre o eixo por um halo na letra",
             "paint-order:stroke" in html and "stroke-width:" in html)

    print("\n== a prancha recusa o que não dá para desenhar")
    sessao = Sessao()
    vazia = executar(sessao, {"nome": "folha"})
    conferir("linha vazia recusa com motivo",
             not vazia["ok"] and "vazia" in (vazia["erro"] or ""),
             vazia.get("erro", "passou"))
    executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
    ruim = executar(sessao, {"nome": "folha", "formato": "A9"})
    conferir("formato que não existe recusa dizendo quais existem",
             not ruim["ok"] and "A4" in (ruim["erro"] or ""),
             ruim.get("erro", "passou"))

    print("\n== a folha segue o modo em que se está vendo")
    sessao = Sessao()
    executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
    executar(sessao, {"nome": "modo", "modo": "metal"})
    saida = executar(sessao, {"nome": "folha"})
    conferir("modo metal na tela, modo metal na folha",
             'class="modo-metal"' in saida.get("html", ""))

    print(f"\n{len(problemas)} problemas")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
