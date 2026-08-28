#!/usr/bin/env python3
"""A classe de pressao: se o programa esta lendo a escala certa.

O mesmo "PN" quer dizer tres coisas nesta lista - bar no aco e no PEAD, metro
de coluna d'agua no plastico de irrigacao brasileiro, e classe ASME quando
vem escrito em libra. Ler a escala errada nao da erro nenhum: da um numero
plausivel e errado por um fator de dez, e o engano so aparece na pressao de
teste, com a linha ja montada.

Este conferidor faz tres coisas:

  1. os casos que ja enganaram, um a um, com a resposta certa ao lado;
  2. varre o catalogo e denuncia leitura fora das series conhecidas - PN de
     plastico que caiu entre 25 e 40, classe ASME que nao existe;
  3. mostra a junta de classes diferentes que o motor passa a avisar.

Uso: python3 tools/conferir_pressao.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor import pressao  # noqa: E402

CATALOGO = "data/catalogo.json"

# (descricao, material, rotulo esperado). Cada linha e uma armadilha real da
# lista, e nao um caso inventado para o teste passar.
CASOS = [
    # o aco e o PEAD falam bar, e e o caso facil
    ('TUBO AZ 6" NBR PN16 X 6M', "ACO_ZINCADO", "PN 16"),
    ("TUBO PEAD PE100 PN08 355MMX16,9MMX6M", "PEAD", "PN 8"),
    ("TUBO PEAD PE100 PN12,5 280MMX20,6MMX6M", "PEAD", "PN 12.5"),
    # o PVC de irrigacao fala metro de coluna d'agua
    ("TUBO IRRIGA PVC 100 DEFOFO JEI PN125-6M", "PVC", "PN 125 (12.3 bar)"),
    ("TUBO IRRIGA PVC 75 PB PN80-6M", "PVC", "PN 80 (7.8 bar)"),
    # ...e o MESMO PVC fala bar quando e da linha ISO. So a serie separa
    ("FL PVC 110MM ISO 2536 PN16", "PVC", "PN 16"),
    ("AQUAPLASTIC TUBO PVC-U PP 110 PN10 - 6M", "PVC", "PN 10"),
    # PN 40 de aco e 40 bar de verdade: a regra do plastico nao vale aqui
    ('ADAPT AZ 6" FL NBR PN40 X 6" K10', "ACO_ZINCADO", "PN 40"),
    # libra e classe ASME, e nao bar
    ('UNIFLAP 6" 150LB', "FOFO", "classe 150"),
    ('VALV RETENCAO 4" ANSI 300', "ACO_ZINCADO", "classe 300"),
    # ...mas so na serie ASME. "140LB" de pressostato de compressor nao e
    # classe de flange nenhuma, e entrava na conta
    ("COM.SUPER AR 10/175V 140LB 2CV 220/380-T", None, None),
    ("FILTRO REG PRESSAO DE AR C/2S 1/4\" 120LB", None, None),
    # PE80 e a RESINA, e nao a pressao - o tubo abaixo e PN 10
    ("TUBO PEAD PE80 PN10 110MMX6,6MMX6M", "PEAD", "PN 10"),
    # duas classes na mesma peca: vale a menor, que e a face mais fraca
    ("TUBO PE100 PN10 110MMX6,6MMX50M FL PN16", "PEAD", "PN 10"),
    ('ADAPT AZ 6" FL NBR PN16 X 6" FL NBR PN25', "ACO_ZINCADO", "PN 16"),
    # sem classe declarada o programa cala, e nao chuta
    ('CURVA 90 AZ 6" FL NBR', "ACO_ZINCADO", None),
]

# A serie em bar e a do motor - conferir contra uma copia daqui nao conferiria
# nada. A serie em mca so existe aqui: e a das classes brasileiras de
# irrigacao, e serve para apontar leitura fora de qualquer serie conhecida.
PN_EM_BAR = pressao.PN_EM_BAR
PN_EM_MCA = (40, 60, 80, 100, 125, 145, 160, 180, 200)


def main():
    problemas = []

    print("== os casos que ja enganaram")
    for desc, material, esperado in CASOS:
        classe = pressao.da_peca(desc, material)
        veio = classe["rotulo"] if classe else None
        marca = "ok" if veio == esperado else " !"
        print(f"  {marca} {desc[:52]:52s} -> {veio or 'sem classe'}")
        if veio != esperado:
            problemas.append(f"{desc}: esperava {esperado or 'sem classe'}, "
                             f"veio {veio or 'sem classe'}")

    print("\n== o catálogo inteiro")
    catalogo = json.load(open(CATALOGO, encoding="utf-8"))
    com, contagem = 0, {}
    for item in catalogo:
        classe = item.get("classe_pressao")
        if not classe:
            continue
        com += 1
        contagem[classe["rotulo"]] = contagem.get(classe["rotulo"], 0) + 1
        if classe["familia"] == "ASME":
            if int(classe["valor"]) not in pressao.CLASSES_ASME:
                problemas.append(f'{item["descricao"]}: classe ASME '
                                 f'{classe["valor"]:g} não existe')
            continue
        serie = PN_EM_MCA if classe["bar"] != classe["valor"] else PN_EM_BAR
        if classe["valor"] not in serie:
            escala = "mca" if serie is PN_EM_MCA else "bar"
            problemas.append(f'{item["descricao"]}: PN {classe["valor"]:g} '
                             f"lido em {escala} não está na série")
    print(f"  {com} de {len(catalogo)} peças declaram classe")
    for rotulo, quantas in sorted(contagem.items(), key=lambda p: -p[1])[:12]:
        print(f"    {quantas:5d}  {rotulo}")

    print("\n== a junta de classes diferentes")
    for a, ma, b, mb in [("TUBO PEAD PE100 PN08 355MM", "PEAD",
                          'TUBO AZ 14" NBR PN16', "ACO_ZINCADO"),
                         ('UNIFLAP 6" 150LB', "FOFO",
                          'TUBO AZ 6" NBR PN16', "ACO_ZINCADO"),
                         ('TUBO AZ 6" NBR PN16', "ACO_ZINCADO",
                          'CURVA 90 AZ 6" FL NBR PN16', "ACO_ZINCADO")]:
        veredito, frase = pressao.na_juncao(pressao.da_peca(a, ma),
                                            pressao.da_peca(b, mb))
        print(f"  {veredito or 'sem classe nos dois':16s} {frase or '—'}")

    print(f"\n{len(problemas)} problemas")
    for p in problemas:
        print(f"  ! {p}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
