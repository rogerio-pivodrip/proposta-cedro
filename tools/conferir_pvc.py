#!/usr/bin/env python3
"""Confere se a peca de PVC/Plasson volta na medida que a casa mediu.

As pecas de aco saem de folha de fabricante; as de mm saem do DXF da casa,
que e a unica fonte que temos para elas. Entao o teste aqui e o inverso do
conferir_cad.py: la a folha manda e a comparacao e informativa; aqui a medida
da casa E a cota, e o desenho tem de voltar nela.

Nao volta exato de proposito em dois casos, e os dois estao no relatorio:

  a curva  o que a casa mede e o ENVELOPE, e a perna que produz aquele
           envelope e resolvida por iteracao - para quando erra menos de
           meio milimetro, e em bitola grande isso ja e menos de 0,2%;
  a bitola sem medida  cai na estimativa, e ai a diferenca e contra nada.

Uso: python3 tools/conferir_pvc.py [--limite 2.0]
"""
import argparse
import collections
import sys

sys.path.insert(0, ".")
from motor import cotas, simbolos as s  # noqa: E402

SEM_CORPO = {"centro"}

# familia -> (como pedir a peca, cota de largura, cota de altura)
FEITIO = {
    "LUVA": (lambda dn, menor, var: s.luva_pvc(dn, var or "BOLSA"),
             "comprimento_mm", "d_externo_mm"),
    "LUVA_REDUCAO": (lambda dn, menor, var: s.luva_reducao(
        dn, menor or _abaixo(dn), var or "BOLSA"),
        "comprimento_mm", "d_externo_mm"),
    "CURVA": (lambda dn, menor, var: s.curva_pvc(
        dn, int(var.split("/")[0]), var.split("/")[1] or "BOLSA"),
        "envelope_x_mm", "envelope_y_mm"),
    "TE": (lambda dn, menor, var: s.te_pvc(dn, None, var or "BOLSA"),
           "face_a_face_mm", "altura_total_mm"),
    "TE_REDUZIDO": (lambda dn, menor, var: s.te_pvc(
        dn, menor or _abaixo(dn), var or "BOLSA"),
        "face_a_face_mm", "altura_total_mm"),
    "ADAPTADOR_FLANGE": (lambda dn, menor, var: s.adaptador_flange(dn),
                         "comprimento_mm", "d_externo_mm"),
    "BUCHA_REDUCAO": (lambda dn, menor, var: s.bucha_reducao(
        dn, menor or _abaixo(dn)), "comprimento_mm", "d_externo_mm"),
}
SERIE = (25, 32, 35, 40, 50, 63, 75, 90, 100, 110, 125, 140, 150, 160, 180,
         200, 225, 250, 280, 315, 355)


def _abaixo(dn):
    """A bitola imediatamente menor da serie - quando a medida nao diz o par."""
    menores = [d for d in SERIE if d < dn]
    return menores[-1] if menores else dn


def corpo(simbolo):
    """A caixa da peca sem o eixo: o eixo sobra dos dois lados e sobra
    diferente em cada peca, e nao e material."""
    uteis = [e for e in simbolo.elementos
             if e.get("classe") not in SEM_CORPO and e["tipo"] != "nota"]
    return s.limites(uteis)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=float, default=2.0,
                    help="acima dessa diferenca em %% a linha e destacada")
    arg = ap.parse_args()

    # a medida da casa, agrupada por peca: (familia, variante, dn, menor)
    pedidos = collections.defaultdict(dict)
    for chave, v in cotas.leituras_da_casa().items():
        familia, variante, dn, menor, significado = chave
        if familia not in FEITIO or not v["confiavel"]:
            continue
        # curva sem junta no nome nao da para pedir ao motor: a bolsa e a
        # soldavel da mesma bitola tem envelope diferente, e a chave "90/"
        # ficou com as duas leituras misturadas
        if familia == "CURVA" and not (variante or "").split("/")[1]:
            continue
        pedidos[(familia, variante, dn, menor)][significado] = v["valor"]

    print(f"{'peça':38} {'motor (mm)':>17} {'casa (mm)':>17} "
          f"{'Δ larg':>8} {'Δ alt':>8}")
    piores = []
    falhas = []
    for chave in sorted(pedidos, key=lambda k: (k[0], str(k[1]), k[2])):
        familia, variante, dn, menor = chave
        medido = pedidos[chave]
        monta, sig_l, sig_a = FEITIO[familia]
        try:
            peca = monta(dn, menor, variante or "")
        except Exception as erro:                       # noqa: BLE001
            falhas.append((chave, f"{type(erro).__name__}: {erro}"))
            continue
        _, _, largura, altura = corpo(peca)   # limites() devolve x, y, w, h
        obtido = {sig_l: largura, sig_a: altura}
        if familia == "CURVA":
            # a curva nao tem pose canonica: a de 45 da casa esta de pe, a
            # minha entra pela horizontal, e cada uma cai num x/y diferente.
            # O que se compara e o PAR de envelopes, nao o eixo em que caiu
            maior, menor_lado = max(largura, altura), min(largura, altura)
            casa = sorted(v for v in (medido.get(sig_l), medido.get(sig_a)) if v)
            if len(casa) == 2:
                medido = {sig_l: casa[1], sig_a: casa[0]}
                obtido = {sig_l: maior, sig_a: menor_lado}
        deltas = []
        for sig in (sig_l, sig_a):
            if sig in medido and medido[sig]:
                deltas.append(100 * (obtido[sig] - medido[sig]) / medido[sig])
            else:
                deltas.append(None)
        marca = "  <<" if any(d is not None and abs(d) > arg.limite
                             for d in deltas) else ""
        nome = f"{familia} {variante or '-'} DN{dn:g}"
        if menor:
            nome += f"×{menor:g}"
        print(f"{nome:38} "
              f"{obtido[sig_l]:7.1f} × {obtido[sig_a]:7.1f} "
              f"{medido.get(sig_l, 0):7.1f} × {medido.get(sig_a, 0):7.1f} "
              + " ".join(f"{d:+7.1f}%" if d is not None else f"{'-':>8}"
                         for d in deltas) + marca)
        for d in deltas:
            if d is not None:
                piores.append(abs(d))

    print(f"\n{len(pedidos)} peças medidas · {len(piores)} cotas comparadas")
    if piores:
        print(f"|Δ| médio {sum(piores)/len(piores):5.2f}%  ·  "
              f"pior {max(piores):5.2f}%  ·  "
              f"{sum(1 for d in piores if d <= arg.limite)} dentro de "
              f"{arg.limite:g}%")
    if falhas:
        print(f"\n== não montou")
        for chave, erro in falhas:
            print(f"  {chave}  {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
