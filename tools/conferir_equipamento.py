#!/usr/bin/env python3
"""Confere se o equipamento volta na altura e no comprimento que a folha cota.

A peca de tubulacao e simples de conferir: comeca numa flange e acaba na
outra, e a caixa dela E a cota. O equipamento nao - ele tem uma parte que
SOBE: volante, caixa redutora, tampa, registrador. Essa parte nao entra em
face a face, entra em altura total, e e ai que o desenho escapa sem ninguem
ver: numa bitola grande a torre parece proporcional, e na pequena ela come a
peca.

Foi assim que o medidor passou 70% da propria altura em todas as bitolas
sem que a folha de simbolos denunciasse - o olho compara a torre com o corpo,
nao com a cota.

Uso: python3 tools/conferir_equipamento.py [--limite 3.0]
"""
import argparse
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402

# O que a cota H da folha NAO cobre, e que por isso sai da comparacao de
# altura: a flange (o disco dela e mais largo que o corpo em bitola pequena -
# uma hidraulica de 3" tem 203 mm de altura e 200 mm de disco de flange) e o
# piloto, que e peca pendurada e vem listado junto. Comparar a caixa cheia
# contra H seria cobrar da folha uma medida que ela nao deu.
SEM_CORPO = {"centro"}
# O parafuso ENTRA na altura: numa tampa aparafusada a cabeca dele e o ponto
# mais alto da peca, e e ate ela que a folha cota. Sai da conta so o que a folha
# de fato nao cobre - a flange do tubo, que em bitola pequena e mais larga que a
# peca inteira, e o piloto, que vem pendurado e listado a parte.
FORA_DA_ALTURA = {"flange", "furo", "piloto"}
BITOLAS = (3, 4, 5, 6, 8, 10, 12, 14)

# familia -> (como montar, cota de comprimento, cota de altura)
#
# A altura de cada uma sai de onde a folha dela cota:
#   altura_total_mm       do eixo para cima mais o que desce - gaveta,
#                         hidraulica, medidor (que tambem cota o abaixo)
#   acima + abaixo        a borboleta cota as duas metades separadas, porque
#                         a haste sobe muito mais do que o corpo desce
FEITIO = {
    "MEDIDOR": (lambda dn: s.medidor(dn), "face_a_face_mm", "altura_total_mm",
                ""),
    # a hidraulica cota por SERIE, nao so por bitola: a 47 e a 77 tem corpo
    # diferente na mesma bitola, e pedir a cota sem a serie nao acha nada
    "VALVULA_HIDRAULICA": (lambda dn: s.valvula_hidraulica(dn, "47"),
                           "face_a_face_mm", "altura_total_mm", "47"),
    # na gaveta o comprimento nao entra: o volante de canto tem 500 mm numa
    # valvula de 290 de face a face, e passa dos dois lados de proposito
    "VALVULA_GAVETA": (lambda dn: s.valvula_gaveta(dn), None,
                       "altura_total_mm", ""),
    "VALVULA_PE": (lambda dn: s.valvula_pe(dn), None, "altura_total_mm", ""),
}


def confere_borboleta(limite):
    """A borboleta e o caso extremo do que sobe: numa de 3" o wafer tem 46 mm
    e o acionamento sobe 159, tres vezes e meia o corpo. A folha da MP cota
    altura_acima_mm - do eixo para cima - e nao a altura total, entao aqui se
    compara so o que fica acima do eixo.
    """
    print(f"\n{'peça':30} {'acima do eixo (mm)':>22} {'folha':>8} {'Δ':>8}")
    piores, fora = [], 0
    for dn in BITOLAS:
        acima, _ = s._cota("VALVULA_BORBOLETA", dn, "", "altura_acima_mm")
        if not acima:
            continue
        for acionamento in ("ALAVANCA", "CAIXA"):
            peca = s.valvula_borboleta(dn, acionamento)
            _, y, _, _ = corpo(peca, SEM_CORPO | FORA_DA_ALTURA)
            obtido = -y
            # a caixa redutora nao tem cota de folha: ela e desenhada em 1,15
            # da alavanca, e e contra isso que se confere - senao a conferencia
            # cobraria da MP uma medida que a MP nao deu
            esperado = acima * (1.15 if acionamento == "CAIXA" else 1.0)
            delta = 100 * (obtido - esperado) / esperado
            marca = ""
            if abs(delta) > limite:
                marca, fora = "  <<", fora + 1
            print(f'{"BORBOLETA " + f"{dn:g}" + chr(34) + " " + acionamento:30} '
                  f"{obtido:22.0f} {esperado:8.0f} {delta:+7.1f}%" + marca)
            piores.append(abs(delta))
    return piores, fora


def corpo(simbolo, sem=SEM_CORPO):
    uteis = [e for e in simbolo.elementos
             if e.get("classe") not in sem
             and e["tipo"] not in ("nota", "texto_furos")]
    return s.limites(uteis)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=float, default=3.0,
                    help="acima dessa diferenca em %% a linha e destacada")
    arg = ap.parse_args()

    print(f"{'peça':30} {'motor (mm)':>17} {'folha (mm)':>17} "
          f"{'Δ comp':>8} {'Δ alt':>8}")
    piores, fora = [], 0
    for familia in list(FEITIO):
        for dn in BITOLAS:
            if False:
                pass
            else:
                monta, sig_c, sig_a, variante = FEITIO[familia]
                comp = (s._cota(familia, dn, variante, sig_c)[0]
                        if sig_c else None)
                alto = (s._cota(familia, dn, variante, sig_a)[0]
                        if sig_a else None)
            if not comp and not alto:
                continue
            try:
                peca = monta(dn)
            except Exception as erro:                    # noqa: BLE001
                print(f'{familia} {dn:g}"  não montou: {erro}')
                continue
            _, _, largura, _ = corpo(peca)
            _, _, _, altura = corpo(peca, SEM_CORPO | FORA_DA_ALTURA)
            deltas = []
            for obtido, folha in ((largura, comp), (altura, alto)):
                deltas.append(100 * (obtido - folha) / folha if folha else None)
            marca = ""
            if any(d is not None and abs(d) > arg.limite for d in deltas):
                marca, fora = "  <<", fora + 1
            print(f'{familia + " " + f"{dn:g}" + chr(34):30} '
                  f"{largura:7.0f} × {altura:7.0f} "
                  f"{comp or 0:7.0f} × {alto or 0:7.0f} "
                  + " ".join(f"{d:+7.1f}%" if d is not None else f"{'-':>8}"
                             for d in deltas) + marca)
            piores += [abs(d) for d in deltas if d is not None]

    mais, fora_b = confere_borboleta(arg.limite)
    piores += mais
    fora += fora_b

    print(f"\n{len(piores)} cotas comparadas · {fora} peças fora de "
          f"{arg.limite:g}%")
    if piores:
        print(f"|Δ| médio {sum(piores)/len(piores):5.2f}%  ·  "
              f"pior {max(piores):5.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
