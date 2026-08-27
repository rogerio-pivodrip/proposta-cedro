#!/usr/bin/env python3
"""Confere o motor: o desenho contra o DXF, e as tres folhas entre si.

O motor era a peca menos conferida do caderno. Ele nao tem flange, entao a
conferencia de face a face nao o alcanca, e nao tem torre, entao a de altura
total nao o alcanca tambem. Ficou anos desenhado com uma medida errada - o r1
do manual da Megabloc, que e o A do IEC, uma largura de vista de frente - e
nenhum teste tinha como reclamar.

Este confere duas coisas diferentes:

**O desenho contra o DXF.** Monta o motor sozinho e mede a caixa dele: o
comprimento tem de dar L - E, o raio tem de dar OAC/2, o plano do pe tem de
dar H, o topo tem de dar o olhal.

**As tres folhas entre si.** Sao tres fontes independentes com a mesma
carcaca IEC dentro, e por isso elas TEM de concordar:

    KSB A2744    r1, n5, l          (manual da Megabloc)
    EBARA 406.1  A, AB, L2          (dimensional da GSD)
    WEG W22      OAC, L, E, H, B, C (DXF individual)

Quando concordam, uma confirma a leitura da outra. Foi assim que r1 = A e
n5 = AB apareceram, e foi assim que L2 = L - E se confirmou.

Uso: python3 tools/conferir_motor.py [--limite 1.0]
"""
import argparse
import csv
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402

DADOS = "data"


def _por_carcaca(caminho, chave="carcaca"):
    with open(f"{DADOS}/{caminho}", encoding="utf-8") as fh:
        fichas = {}
        for r in csv.DictReader(fh):
            fichas.setdefault(r[chave], r)
        return fichas


def desenho_contra_dxf(limite):
    """O motor montado sozinho, medido, contra o que o DXF dele cota."""
    print("== o desenho contra o DXF\n")
    print(f'{"carcaça":10}{"cv":>6}  {"cota":18}{"desenho":>9}{"folha":>9}{"Δ":>8}')
    fora, cotas = [], 0
    with open(f"{DADOS}/motores_weg.csv", encoding="utf-8") as fh:
        linhas = list(csv.DictReader(fh))
    for f in linhas:
        cv = float(f["cv"])
        # o comprimento entra explicito para que este teste confira a
        # TRANSCRICAO do DXF. Na bomba de verdade quem manda no comprimento e o
        # manual dela - ver a tabela do l mais abaixo
        el, fim, ficha = s._motor(
            0.0, f["carcaca"], base_y=None, cv=cv,
            comprimento=float(f["L_mm"]) - float(f["E_mm"]))
        x, y, largura, altura = s.limites(el)
        R = float(f["raio_mm"])
        # o corpo e o primeiro elemento: a poly fechada do contorno. Medir ele
        # e a unica forma de conferir o RAIO - a caixa envolve a caixa de
        # ligacao e o olhal, e nao diz nada do corpo
        pontos = [p for linha in s.pontos_do_path(el[0]["d"]) for p in linha]
        raio = max(abs(py) for _, py in pontos)
        topo = max(float(f["caixa_topo_mm"]),
                   float(f["olhal_y_mm"] or 0) + float(f["olhal_r_mm"] or 0))
        medido = {
            "comprimento (L-E)": (largura, float(f["L_mm"]) - float(f["E_mm"])),
            "raio do corpo": (raio, R),
            # embaixo manda quem descer mais: o corpo quando o raio passa do
            # plano do pe, e o plano do pe quando nao passa
            "fundo": (y + altura, max(float(f["H_mm"]), R)),
            "topo": (-y, topo),
        }
        for nome, (nosso, folha) in medido.items():
            cotas += 1
            d = (nosso - folha) / folha * 100 if folha else 0.0
            if abs(d) > limite:
                fora.append((f["carcaca"], cv, nome, nosso, folha, d))
            print(f'{f["carcaca"]:10}{cv:6g}  {nome:18}{nosso:9.1f}{folha:9.1f}'
                  f'{d:+7.1f}%')
    print(f"\n{cotas} cotas comparadas · {len(fora)} fora de {limite:g}%")
    return fora


def as_tres_folhas():
    """Onde as tres se cruzam elas tem de dizer o mesmo numero."""
    print("\n== as tres folhas, no que elas compartilham\n")
    ksb = _por_carcaca("motores_iec.csv")
    ebara = _por_carcaca("motores_gsd.csv")
    weg = _por_carcaca("motores_weg.csv")

    def quadro(nome):
        return "".join(c for c in nome if c.isdigit())

    def acha(tabela, nome):
        if nome in tabela:
            return tabela[nome]
        return next((f for n, f in tabela.items()
                     if quadro(n) == quadro(nome)), None)

    problemas = []
    print(f'{"quadro":8}{"r1=A":>14}{"n5=AB":>14}{"L2=L-E":>16}{"AC/2 vs H":>14}')
    for nome, k in sorted(ksb.items(), key=lambda kv: float(kv[1]["eixo_mm"])):
        e = acha(ebara, nome)
        w = acha(weg, nome)
        linha = [f'{quadro(nome):8}']

        def par(a, b, rotulo, tol=1.0):
            if a is None or b is None:
                return f'{"—":>14}'
            if abs(a - b) > tol:
                problemas.append(f"{nome}: {rotulo} {a:g} != {b:g}")
                return f'{f"{a:g}≠{b:g}":>14}'
            return f'{f"{a:g}":>14}'

        linha.append(par(float(k["largura_pes_mm"]),
                         float(e["A_mm"]) if e and e["A_mm"] else None, "r1/A"))
        linha.append(par(float(k["largura_total_mm"]),
                         float(e["AB_mm"]) if e and e["AB_mm"] else None,
                         "n5/AB"))
        # L2 so se compara com a MESMA carcaca: a 200M e mais curta que a
        # 200L, e as duas sao quadro 200. Comparar por quadro cobraria das duas
        # folhas um numero que elas nao dizem da mesma peca
        exata = (e and w and e is ebara.get(nome) and w is weg.get(nome))
        l2 = float(e["L2_mm"]) if exata and e["L2_mm"] else None
        corpo = (float(w["L_mm"]) - float(w["E_mm"])) if exata else None
        linha.append(par(l2, corpo, "L2/(L-E)", 2.0).rjust(16))
        # o AC do dimensional da EBARA e RAIO, e nao diametro: e por isso que
        # ele bate com a metade do OAC do DXF, e nao com ele inteiro
        ac = float(e["AC_mm"]) if e and e["AC_mm"] else None
        acw = float(w["AC_mm"]) / 2 if w else None
        linha.append(par(ac, acw, "AC(EBARA)/OAC(WEG)/2",
                         (acw or 0) * 0.05 + 2))
        print("".join(linha))
    for p in problemas:
        print(f"  ! {p}")
    print(f"\n{len(problemas)} discordancias entre folhas")
    return problemas


def o_l_contra_o_L():
    """O l do manual da bomba contra o L do DXF do motor - dois motores.

    Nao e erro um nao ser o outro: o l e o motor que a KSB monta e o L e o
    motor que a WEG faz. Eles ficam a 3 a 6% um do outro, e e por isso que o
    comprimento sai do manual da bomba e a forma sai do desenho do motor.
    """
    print("\n== o l do manual contra o L do DXF\n")
    ksb = _por_carcaca("motores_iec.csv")
    weg = _por_carcaca("motores_weg.csv")
    print(f'{"carcaça":10}{"l (KSB)":>9}{"L (WEG)":>9}{"l/L":>8}')
    for nome, k in sorted(ksb.items(), key=lambda kv: float(kv[1]["eixo_mm"])):
        w = weg.get(nome)
        if not w:
            continue
        l, L = float(k["comprimento_mm"]), float(w["L_mm"])
        print(f'{nome:10}{l:9g}{L:9g}{l/L:8.3f}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limite", type=float, default=1.0)
    args = p.parse_args()
    fora = desenho_contra_dxf(args.limite)
    ruins = as_tres_folhas()
    o_l_contra_o_L()
    for carcaca, cv, nome, nosso, folha, d in fora:
        print(f"  ! {carcaca} {cv:g}cv {nome}: {nosso:.1f} contra {folha:.1f} "
              f"({d:+.1f}%)")
    print(f"\n{len(fora) + len(ruins)} problemas")


if __name__ == "__main__":
    main()
