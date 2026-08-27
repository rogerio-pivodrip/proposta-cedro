#!/usr/bin/env python3
"""Confere o desenho do motor contra o DXF da casa.

O DXF da casa e a quarta fonte de cota, e a unica desenhada por quem monta.
Mas nao e folha de fabricante: e desenho de projeto, onde uma peca ou outra
pode ter entrado fora de escala. Entao aqui nada e importado - o que sai e
uma comparacao, peca a peca, com a diferenca em porcento.

A comparacao e do CORPO, nao da caixa cheia: o eixo sobra dos dois lados da
peca e sobra diferente em cada desenho. Sem tirar o eixo, uma bomba de 950 mm
parece 35% maior do lado do motor so por causa do traco-e-ponto.

Uso: python3 tools/conferir_cad.py [data/cad/*.dxf]
"""
import csv
import glob
import re
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402

MEDIDAS = "data/cotas_cad.csv"
# o eixo e a seta de fluxo nao sao material: os dois dizem algo SOBRE a peca,
# como a cota diz, e nenhum dos dois tem chapa. A seta ja foi o que fez a bomba
# parecer 32 mm mais larga do que e.
SEM_CORPO = {"centro", "fluxo"}
# o que da para casar: o nome no DXF -> como pedir a peca ao motor
RX_METB = re.compile(r"\bMETB\s+(\d{2,3})-(\d{2,3})-(\d{2,4})\D+(\d+)\s*cv", re.I)
RX_METN = re.compile(r"\bKSB\s+(\d{2,3})-(\d{2,3})-(\d{2,4})\D+(\d+)\s*cv", re.I)
RX_CURVA_AZ = re.compile(r'^(\d+)"$')


def corpo(simbolo):
    """A caixa da peca sem o eixo - so o que e material."""
    uteis = [e for e in simbolo.elementos
             if e.get("classe") not in SEM_CORPO and e["tipo"] not in ("nota",)]
    return s.limites(uteis)


def do_nome(nome):
    """O simbolo que o motor faz para o que o DXF chama assim, ou None."""
    m = RX_METB.search(nome)
    if m:
        return s.bomba_megabloc(f"{int(m.group(2))}-{int(m.group(3))}",
                                cv=float(m.group(4)))
    m = RX_METN.search(nome)
    if m:
        return s.bomba_meganorm(f"{int(m.group(1))}-{int(m.group(2))}-"
                                f"{int(m.group(3))}", cv=float(m.group(4)))
    return None


def main():
    linhas = list(csv.DictReader(open(MEDIDAS, encoding="utf-8")))
    print(f'{"peça":34} {"motor (mm)":>17} {"casa (mm)":>17}   Δ larg   Δ alt')
    casados = 0
    for linha in linhas:
        simbolo = None
        try:
            simbolo = do_nome(linha["nome"])
        except Exception:
            continue
        if simbolo is None:
            continue
        _, _, larg, alt = corpo(simbolo)
        lc, ac = float(linha["largura_mm"]), float(linha["altura_mm"])
        casados += 1
        print(f'{linha["nome"][:34]:34} {larg:8.0f} × {alt:6.0f} '
              f'{lc:8.1f} × {ac:6.1f}   {(larg-lc)/lc*100:+6.1f}% '
              f'{(alt-ac)/ac*100:+6.1f}%')
    print(f"\n{casados} peças casadas de {len(linhas)} medidas.")
    print("O DXF da casa é desenho de projeto, não folha de fabricante: onde\n"
          "diverge, a folha manda. O que a comparação mostra é onde olhar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
