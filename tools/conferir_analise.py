#!/usr/bin/env python3
"""As tres analises de conflito que nao olham a furacao.

A furacao ja tinha conferidor proprio (tools/conferir_flanges.py) e a classe
de pressao tambem (tools/conferir_pressao.py). Faltavam as tres que ficaram
caladas por mais tempo:

  ORDEM      filtro -> valvula hidraulica -> medidor. A regra estava escrita
             em motor/hidraulica.py desde que foi confirmada nos tres
             projetos, e nao era chamada por ninguem: sabia a resposta e nunca
             era perguntada.
  SENTIDO    o crivo e a boca que fica na agua, a excentrica e peca de succao,
             a ventosa sobe de uma derivacao. Nenhum destes erros da erro - o
             desenho fecha, a lista fecha, e a linha e montada.
  COLISAO    duas pecas no mesmo lugar. So o desenho sabe: e a pose que
             colide, e a pose so existe depois de encadear os simbolos.

Cada secao faz a mesma coisa: primeiro mostra que as montagens PADRAO da casa
passam limpas - um conferidor que acusa o que a casa monta todo dia nao vale
nada - e depois monta de proposito o erro que ele existe para pegar.

Uso: python3 tools/conferir_analise.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor import catalogo as cat_mod  # noqa: E402
from motor import colisao, fluxo, hidraulica, linha as L, projeto as PJ  # noqa: E402
from motor import templates, vista  # noqa: E402

PADRAO = ("SUCCAO", "RECALQUE", "PEAD", "LIVRE")


def _montar(catalogo, chave, dn=6):
    try:
        linha, _faltando = templates.montar(catalogo, chave, dn)
    except (KeyError, ValueError):
        return None
    return linha


def secao_ordem(catalogo, problemas):
    print("\n== a ordem hidráulica")
    for chave in PADRAO:
        linha = _montar(catalogo, chave)
        if linha is None:
            continue
        familias = [p.familia for p in linha.todas_as_pecas()]
        achados = hidraulica.conferir_sequencia(familias)
        print(f"  {'ok' if not achados else ' !'} {chave:9s} "
              f"{len(familias)} peças")
        for a in achados:
            problemas.append(f"{chave}: {a}")
            print(f"       {a}")

    for rotulo, familias, espera in [
            ("filtro, válvula, medidor",
             ["FILTRO", "VALVULA_HIDRAULICA", "MEDIDOR"], 0),
            ("filtro, medidor, válvula",
             ["FILTRO", "MEDIDOR", "VALVULA_HIDRAULICA"], 1),
            ("filtro sozinho", ["FILTRO", "TUBO"], 1),
            ("sem filtro nenhum", ["TUBO", "CURVA", "MEDIDOR"], 0)]:
        achados = hidraulica.conferir_sequencia(familias)
        certo = len(achados) == espera
        print(f"  {'ok' if certo else ' !'} {rotulo:26s} -> "
              + (achados[0] if achados else "sem reparo"))
        if not certo:
            problemas.append(f"ordem '{rotulo}': esperava {espera} aviso(s), "
                             f"veio {len(achados)}")


def secao_sentido(catalogo, problemas):
    print("\n== o sentido do fluxo")
    for chave in PADRAO:
        linha = _montar(catalogo, chave)
        if linha is None:
            continue
        achados = fluxo.conferir(
            linha.pecas, [a for p in linha.pecas for a in p.acessorios])
        print(f"  {'ok' if not achados else ' !'} {chave:9s} "
              f"{len(linha.pecas)} peças na corrente")
        for a in achados:
            problemas.append(f"{chave}: {a}")
            print(f"       {a}")

    crivo = catalogo.melhor("CRIVO", 6)
    tubo = catalogo.melhor("TUBO", 6)
    bomba = next((i for i in catalogo.itens if i.get("familia") == "BOMBA"),
                 None)
    if not (crivo and tubo and bomba):
        print("  ? sem crivo, tubo ou bomba na lista - o caso montado não roda")
        return
    # o crivo no meio do caminho, e depois da bomba
    linha = L.Linha(catalogo, tipo="LIVRE")
    linha.inserir(L.Peca(tubo, comprimento_mm=1000))
    linha.inserir(L.Peca(bomba))
    linha.inserir(L.Peca(crivo))
    achados = fluxo.conferir(linha.pecas)
    print(f"  {'ok' if len(achados) == 2 else ' !'} crivo depois da bomba -> "
          f"{len(achados)} aviso(s)")
    for a in achados:
        print(f"       {a}")
    if len(achados) != 2:
        problemas.append("crivo depois da bomba: esperava 2 avisos (fora do "
                         f"começo e depois da bomba), veio {len(achados)}")


def secao_colisao(catalogo, problemas):
    print("\n== duas peças no mesmo lugar")
    for chave in PADRAO:
        linha = _montar(catalogo, chave)
        if linha is None:
            continue
        achados = vista.vista(linha)["colisoes"]
        print(f"  {'ok' if not achados else ' !'} {chave:9s} "
              f"{len(achados)} colisão(ões)")
        for a, b, fracao in achados:
            problemas.append(f"{chave}: {a} e {b} se sobrepõem ({fracao:.0%})")

    te = catalogo.melhor("TE", 6)
    tubo = catalogo.melhor("TUBO", 6)
    curva = catalogo.melhor("CURVA", 6, angulo=90)
    if not (te and tubo and curva):
        print("  ? sem tê, tubo ou curva na lista - o caso montado não roda")
        return
    # o ramo que sobe, vira duas vezes e volta por cima do tronco
    proj = PJ.Projeto(catalogo)
    tronco = proj.ativa
    tronco.inserir(L.Peca(tubo, comprimento_mm=1000))
    alvo = tronco.inserir(L.Peca(te))
    tronco.inserir(L.Peca(tubo, comprimento_mm=6000))
    ramo = proj.ramificar(alvo.id, 0, tipo="RAMO")
    for peca in (L.Peca(tubo, comprimento_mm=300),
                 L.Peca(curva, sentido=-1),
                 L.Peca(tubo, comprimento_mm=1500),
                 L.Peca(curva, sentido=-1),
                 L.Peca(tubo, comprimento_mm=4000)):
        ramo.inserir(peca)
    achados = vista.vista(tronco, projeto=proj)["colisoes"]
    print(f"  {'ok' if achados else ' !'} ramo dobrado sobre o tronco -> "
          f"{len(achados)} colisão(ões)")
    for a, b, fracao in achados:
        print(f"       {a} × {b}: {fracao:.0%} da menor")
    if not achados:
        problemas.append("o ramo dobrado sobre o tronco passou sem aviso")

    # e a geometria pura, que nao depende do catalogo
    print("\n  a conta da sobreposição, caso a caso:")
    for rotulo, a, b, espera in [
            ("caixas iguais, uma sobre a outra",
             (0, -25, 100, 50), (0, -25, 100, 50), True),
            ("face a face, encostadas",
             (0, -25, 100, 50), (100, -25, 100, 50), False),
            ("metade dentro",
             (0, -25, 100, 50), (50, -25, 100, 50), True),
            ("mordida de chapa de 16 mm entre dois tubos de 6 m",
             (0, -142, 6000, 285), (5984, -142, 6000, 285), False),
            ("dois tubos de 6 m cruzados",
             (0, -142, 6000, 285), (3000, -3142, 6000, 285), True)]:
        ca = colisao._cantos((a[0], a[1], a[2], a[3]), 0, 0, 0)
        giro = 90 if "cruzados" in rotulo else 0
        cb = colisao._cantos((0, b[1], b[2], b[3]), b[0], 0, giro)
        comum = colisao._area_comum(ca, cb)
        secao = min(min(a[2], a[3]), min(b[2], b[3])) ** 2
        acusa = comum >= colisao.MINIMO * secao
        certo = acusa == espera
        print(f"    {'ok' if certo else ' !'} {rotulo:50s} "
              f"{comum:9.0f} mm² -> {'acusa' if acusa else 'cala'}")
        if not certo:
            problemas.append(f"colisão '{rotulo}': esperava "
                             f"{'acusar' if espera else 'calar'}")


def main():
    catalogo = cat_mod.Catalogo()
    problemas = []
    secao_ordem(catalogo, problemas)
    secao_sentido(catalogo, problemas)
    secao_colisao(catalogo, problemas)
    print(f"\n{len(problemas)} problemas")
    for p in problemas:
        print(f"  ! {p}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
