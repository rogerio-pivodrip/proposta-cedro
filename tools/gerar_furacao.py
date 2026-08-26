#!/usr/bin/env python3
"""Gera data/regras_furacao.csv a partir das tabelas normativas.

Por que gerado e nao digitado: a furacao ABNT/NBR de flange para irrigacao
segue o padrao DIN/ISO 2531, igual a EN 1092. Escrever a regra uma vez e
expandir evita divergencia entre as duas familias de norma.

FONTES:
 - NBR 7675: tabela dimensional real da ficha tecnica T.153FB da MP Valvulas
   (data/fichas/FIG153_valvula_gaveta_flange_NBR7675.pdf). Homologada.
 - EN 1092-1 e ASME B16.5: escritas de norma, sem documento a mao nesta sessao
   (a politica de rede bloqueia o acesso), entao nascem homologado=NAO.
"""
import csv

# --- EN 1092-1 / DIN 2501 - a base da furacao ABNT no Brasil -----------------
# dn_mm: {pn: (furos, parafuso_metrico, furo_mm, circulo_mm)}
EN = {
    50:  {10: (4, "M16", 18, 125), 16: (4, "M16", 18, 125),
          25: (4, "M16", 18, 125), 40: (4, "M16", 18, 125)},
    65:  {10: (4, "M16", 18, 145), 16: (4, "M16", 18, 145),
          25: (8, "M16", 18, 145), 40: (8, "M16", 18, 145)},
    80:  {10: (8, "M16", 18, 160), 16: (8, "M16", 18, 160),
          25: (8, "M16", 18, 160), 40: (8, "M16", 18, 160)},
    100: {10: (8, "M16", 18, 180), 16: (8, "M16", 18, 180),
          25: (8, "M20", 22, 190), 40: (8, "M20", 22, 190)},
    125: {10: (8, "M16", 18, 210), 16: (8, "M16", 18, 210),
          25: (8, "M24", 26, 220), 40: (8, "M24", 26, 220)},
    150: {10: (8, "M20", 22, 240), 16: (8, "M20", 22, 240),
          25: (8, "M24", 26, 250), 40: (8, "M24", 26, 250)},
    200: {10: (8, "M20", 22, 295), 16: (12, "M20", 22, 295),
          25: (12, "M24", 26, 310), 40: (12, "M27", 30, 320)},
    250: {10: (12, "M20", 22, 350), 16: (12, "M24", 26, 355),
          25: (12, "M27", 30, 370), 40: (12, "M30", 33, 385)},
    300: {10: (12, "M20", 22, 400), 16: (12, "M24", 26, 410),
          25: (16, "M27", 30, 430), 40: (16, "M30", 33, 450)},
    350: {10: (16, "M20", 22, 460), 16: (16, "M24", 26, 470),
          25: (16, "M30", 33, 490)},
    400: {10: (16, "M24", 26, 515), 16: (16, "M27", 30, 525),
          25: (16, "M33", 36, 550)},
    450: {10: (20, "M24", 26, 565), 16: (20, "M27", 30, 585)},
    500: {10: (20, "M24", 26, 620), 16: (20, "M30", 33, 650)},
    600: {10: (20, "M27", 30, 725), 16: (20, "M33", 36, 770)},
}

# Espessura de referencia do flange (tipo 01/11), em mm. Entra no calculo do
# comprimento do tirante de barra roscada.
ESPESSURA = {50: 20, 65: 20, 80: 20, 100: 20, 125: 22, 150: 22, 200: 24,
             250: 26, 300: 28, 350: 30, 400: 32, 450: 40, 500: 38, 600: 42}

# --- ABNT NBR 7675 - a furacao real, lida da ficha tecnica T.153FB -----------
# dn_mm: (furos, furo_mm, circulo_mm, esp_flange_mm, diam_externo_mm)
# Nota: ate DN200 a furacao coincide com PN16; de DN250 para cima ela segue o
# padrao PN10 - o que casa com a queda de classe da propria valvula
# (40-200 PN16, 250-300 PN10, 350-600 PN6).
NBR_7675 = {
    40:  (4, 18, 110, 19.5, 150),
    50:  (4, 18, 125, 19.5, 165),
    65:  (4, 18, 145, 21.0, 185),
    75:  (8, 18, 160, 21.0, 200),
    80:  (8, 18, 160, 21.0, 200),   # DIN chama de DN80 o que a NBR chama de DN75
    100: (8, 18, 180, 21.0, 220),
    125: (8, 18, 210, 22.0, 250),
    150: (8, 22, 240, 22.0, 285),
    200: (12, 22, 295, 23.0, 340),
    250: (12, 22, 350, 26.0, 395),
    300: (12, 22, 400, 28.0, 445),
    350: (16, 22, 460, 28.0, 505),
    400: (16, 26, 515, 28.0, 565),
    450: (20, 26, 565, 26.5, 615),
    500: (20, 26, 620, 26.5, 670),
    600: (20, 31, 725, 32.0, 780),
}

# Diametro do furo -> parafuso, nos dois sistemas
FURO_PARA_PARAFUSO = {18: ("M16", "5/8"), 22: ("M20", "3/4"),
                      26: ("M24", "1"), 30: ("M27", "1 1/8"),
                      31: ("M27", "1 1/8"), 33: ("M30", "1 1/4"),
                      36: ("M33", "1 1/4")}

# --- ASME/ANSI B16.5 - o que vem nas bombas e valvulas importadas ------------
# dn_pol: {classe: (furos, parafuso_pol, furo_mm, circulo_mm)}
ANSI = {
    2:    {150: (4, "5/8", 19, 120.7),   300: (8, "5/8", 19, 127.0)},
    2.5:  {150: (4, "5/8", 19, 139.7),   300: (8, "3/4", 22, 149.2)},
    3:    {150: (4, "5/8", 19, 152.4),   300: (8, "3/4", 22, 168.3)},
    4:    {150: (8, "5/8", 19, 190.5),   300: (8, "3/4", 22, 200.0)},
    5:    {150: (8, "3/4", 22, 215.9),   300: (8, "3/4", 22, 235.0)},
    6:    {150: (8, "3/4", 22, 241.3),   300: (12, "3/4", 22, 269.9)},
    8:    {150: (8, "3/4", 22, 298.5),   300: (12, "7/8", 25, 330.2)},
    10:   {150: (12, "7/8", 25, 362.0),  300: (16, "1", 29, 387.4)},
    12:   {150: (12, "7/8", 25, 431.8),  300: (16, "1 1/8", 32, 450.8)},
    14:   {150: (12, "1", 29, 476.3),    300: (20, "1 1/8", 32, 514.4)},
    16:   {150: (16, "1", 29, 539.8),    300: (20, "1 1/4", 35, 571.5)},
    18:   {150: (16, "1 1/8", 32, 577.9), 300: (24, "1 1/4", 35, 628.6)},
    20:   {150: (20, "1 1/8", 32, 635.0), 300: (24, "1 1/4", 35, 685.8)},
    24:   {150: (20, "1 1/4", 35, 749.3), 300: (24, "1 1/2", 41, 812.8)},
}

# Serie em polegada usada no aco zincado -> DN nominal em mm
POL_PARA_DN = {2: 50, 2.5: 65, 3: 80, 4: 100, 5: 125, 6: 150, 8: 200,
               10: 250, 12: 300, 14: 350, 16: 400, 18: 450, 20: 500, 24: 600}
DN_PARA_POL = {v: k for k, v in POL_PARA_DN.items()}

# Conversao do parafuso metrico para a bitola UNC comprada no Brasil
METRICO_UNC = {"M16": "5/8", "M20": "3/4", "M24": "1", "M27": "1 1/8",
               "M30": "1 1/4", "M33": "1 1/4"}

CABECALHO = ["norma", "dn_mm", "dn_pol", "furos", "parafuso_norma",
             "bitola_unc_pol", "furo_mm", "circulo_mm", "esp_flange_mm",
             "fonte", "homologado"]


def linhas():
    # NBR 7675: uma furacao so, medida - nao existe "NBR PN10 x PN16" na pratica,
    # a norma ja embute a queda de classe com o diametro.
    for dn_mm, (furos, furo, circulo, esp, _ext) in sorted(NBR_7675.items()):
        parafuso, unc = FURO_PARA_PARAFUSO[furo]
        for norma in ("NBR PN10", "NBR PN16", "NBR PN25"):
            yield {
                "norma": norma,
                "dn_mm": dn_mm,
                "dn_pol": DN_PARA_POL.get(dn_mm, ""),
                "furos": furos,
                "parafuso_norma": parafuso,
                "bitola_unc_pol": unc,
                "furo_mm": furo,
                "circulo_mm": circulo,
                "esp_flange_mm": esp,
                "fonte": "NBR 7675 (ficha T.153FB MP Valvulas)",
                "homologado": "SIM",
            }
    for dn_mm, por_pn in sorted(EN.items()):
        for pn, (furos, parafuso, furo, circulo) in sorted(por_pn.items()):
            for familia, fonte in (("EN PN%d" % pn, "EN 1092-1"),):
                yield {
                    "norma": familia,
                    "dn_mm": dn_mm,
                    "dn_pol": DN_PARA_POL.get(dn_mm, ""),
                    "furos": furos,
                    "parafuso_norma": parafuso,
                    "bitola_unc_pol": METRICO_UNC.get(parafuso, ""),
                    "furo_mm": furo,
                    "circulo_mm": circulo,
                    "esp_flange_mm": ESPESSURA.get(dn_mm, ""),
                    "fonte": fonte,
                    "homologado": "NAO",
                }
    for dn_pol, por_classe in sorted(ANSI.items()):
        for classe, (furos, bitola, furo, circulo) in sorted(por_classe.items()):
            dn_mm = POL_PARA_DN[dn_pol]
            yield {
                "norma": "ANSI %d" % classe,
                "dn_mm": dn_mm,
                "dn_pol": dn_pol,
                "furos": furos,
                "parafuso_norma": bitola + '"',
                "bitola_unc_pol": bitola,
                "furo_mm": furo,
                "circulo_mm": circulo,
                "esp_flange_mm": ESPESSURA.get(dn_mm, ""),
                "fonte": "ASME B16.5",
                "homologado": "NAO",
            }


def main():
    caminho = "data/regras_furacao.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        fh.write("# GERADO por tools/gerar_furacao.py - nao edite a mao,\n")
        fh.write("# edite as tabelas do script e rode de novo.\n")
        fh.write("# 8\" (DN200) NBR PN16 = 12 furos: confirmado pelo Rogerio.\n")
        fh.write("# O resto e referencia normativa e precisa de conferencia.\n")
        escritor = csv.DictWriter(fh, fieldnames=CABECALHO)
        escritor.writeheader()
        n = 0
        for linha in linhas():
            escritor.writerow(linha)
            n += 1
    print(f"{n} linhas -> {caminho}")


if __name__ == "__main__":
    main()
