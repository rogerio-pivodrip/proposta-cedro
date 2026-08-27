#!/usr/bin/env python3
"""Confere a flange que o programa DESENHA contra as folhas que ele tem.

A flange e a peca mais repetida do desenho - cada junta tem duas - e e a que
tem menos margem para errar: o externo decide a altura de quase toda peca na
vista lateral, e a espessura decide o comprimento do parafuso que entra na
lista de materiais. Errar 10% no externo nao aparece olhando; errar a
espessura aparece na obra.

Tres perguntas, e cada uma tem uma resposta separada:

  **De onde veio o externo?** Folha de fabricante, catalogo, ou estimativa. A
  estimativa e `DE_TUBO * 1,7`, um chute que serve para nao deixar buraco no
  desenho - e a coluna diz onde ele ainda esta em uso.

  **A espessura bate com a folha?** A folha Netafim cota a chapa: 16 mm ate
  10", 21 ate 16", 27,5 acima. A tabela da MP cota outra coisa - a flange
  INTEGRAL de uma valvula de ferro fundido, que e mais grossa. Sao duas pecas
  diferentes com o mesmo nome, e misturar as duas engorda a flange solta.

  **A furacao bate com a norma?** Circulo, quantidade e diametro do furo.
  Aqui a folha Netafim e a NBR da casa DISCORDAM de 10" para cima - o caderno
  desenha EN PN16 e a tabela e NBR. Isso nao e defeito deste programa e nao se
  conserta aqui: quem compra pela NBR e monta contra peca Netafim nao fecha o
  parafuso. Ver tools/conferir_flanges_netafim.py.

Uso: python3 tools/conferir_flanges.py
"""
import csv
import sys

sys.path.insert(0, ".")
from motor import simbolos as s                      # noqa: E402

BITOLAS = (2, 2.5, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 24)
TOLERANCIA = 0.6            # mm: a folha cota em milimetro inteiro


def folhas():
    netafim, irrigafour = {}, {}
    with open("data/flanges_netafim.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["tipo"] == "SOLDAR":
                netafim[float(r["dn_pol"])] = r
    with open("data/flanges_irrigafour.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["norma"] == "DIN 2533 PN 16":
                irrigafour[float(r["dn_pol"])] = r
    return netafim, irrigafour


def main():
    netafim, irrigafour = folhas()
    problemas, estimadas, divergem = [], [], []

    print("== o que o programa desenha, e de onde veio")
    print(f'{"pol":>5}  {"externo":>7} {"folha":>6} {"cat.":>6}  '
          f'{"esp":>5} {"folha":>6}  {"circulo":>7} {"furos":>7}  fonte')
    for dn in BITOLAS:
        f = s.flange(dn)
        n, i = netafim.get(dn), irrigafour.get(dn)
        e_folha = float(n["d_externo_mm"]) if n else None
        e_cat = float(i["d_externo_mm"]) if i else None
        t_folha = float(n["esp_mm"]) if n else None
        print(f'{dn:>5g}  {f["externo"]:>7.0f} '
              f'{e_folha if e_folha else 0:>6.0f} {e_cat if e_cat else 0:>6.0f}  '
              f'{f["espessura"]:>5.1f} {t_folha if t_folha else 0:>6.1f}  '
              f'{f["circulo"]:>7.0f} {f["furos"]:>3g}x{f["furo"]:>3.0f}  '
              f'{f["fonte"]}')
        if f["fonte"] == "estimativa":
            estimadas.append(dn)
        if e_folha and abs(f["externo"] - e_folha) > TOLERANCIA:
            problemas.append(f'{dn:g}" externo {f["externo"]:.0f} '
                             f'contra {e_folha:.0f} da folha')
        if t_folha and abs(f["espessura"] - t_folha) > TOLERANCIA:
            problemas.append(f'{dn:g}" espessura {f["espessura"]:.1f} '
                             f'contra {t_folha:.1f} da folha')
        if e_folha and e_cat and abs(e_folha - e_cat) > TOLERANCIA:
            divergem.append((dn, e_folha, e_cat))

    print("\n== a norma pedida e a norma entregue")
    # o cache era um so, montado com a norma da PRIMEIRA chamada. Este caso
    # cobra que pedir ANSI nao envenene a NBR seguinte
    ansi = s.flange(8, "ANSI 150")
    nbr = s.flange(8, "NBR PN16")
    if ansi["furos"] == nbr["furos"] and ansi["circulo"] == nbr["circulo"]:
        problemas.append("ANSI 150 e NBR PN16 devolvem a MESMA furação em 8\" "
                         "- o cache está compartilhado entre normas")
        print("  ! ANSI 150 e NBR PN16 dão a mesma furação em 8\"")
    else:
        print(f'  ok 8" ANSI 150 = {ansi["furos"]}x{ansi["furo"]:.0f} em '
              f'{ansi["circulo"]:.1f} · NBR PN16 = {nbr["furos"]}x'
              f'{nbr["furo"]:.0f} em {nbr["circulo"]:.0f}')

    print("\n== a junta desenhada e a chapa da folha")
    # a junta flangeada desenha DUAS chapas encostadas: o vao entre as faces
    # das duas pecas tem de ser duas espessuras, nem mais nem menos
    for dn in (3, 8, 14):
        f = s.flange(dn)
        placa = s.placa(0, dn)
        alto = max(e["h"] for e in placa if e["tipo"] == "rect")
        largo = max(e["w"] for e in placa if e["tipo"] == "rect")
        ok_alto = abs(alto - f["externo"]) < TOLERANCIA
        ok_largo = abs(largo - f["espessura"]) < TOLERANCIA
        marca = "ok" if ok_alto and ok_largo else " !"
        print(f'  {marca} {dn:g}" a chapa desenhada mede '
              f'{largo:.1f} x {alto:.0f} mm '
              f'(folha: {f["espessura"]:.1f} x {f["externo"]:.0f})')
        if not (ok_alto and ok_largo):
            problemas.append(f'{dn:g}" a chapa desenhada não é a da ficha')

    if divergem:
        print("\n== onde a folha e o catálogo discordam")
        for dn, e_folha, e_cat in divergem:
            print(f'  · {dn:g}"  folha Netafim {e_folha:.0f}  ·  '
                  f'catálogo Irrigafour {e_cat:.0f}  → o desenho usa a folha')

    if estimadas:
        print(f'\n{len(estimadas)} bitolas sem folha, no chute de DE_TUBO*1,7: '
              + ", ".join(f'{d:g}"' for d in estimadas))

    print(f"\n{len(problemas)} problemas")
    for p in problemas:
        print(f"  ! {p}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
