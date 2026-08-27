#!/usr/bin/env python3
"""Cotas de equipamento, transcritas das fichas do fabricante.

O caderno de conexoes nao mede valvula, filtro nem medidor - essas cotas vem da
ficha de quem fabrica. Aqui elas viram tabela, no mesmo formato das conexoes,
para o motor perguntar por uma porta so.

Fontes (data/fichas/):
  SAINT-GOBAIN PAM  FTSG 0406 rev01, 09/09/2024 - borboleta wafer semi lug,
                    face a face API 609, flange EN1092-2 PN10/PN16 e ANSI 150
  ARAD              ING23008 WSTsb Bayonet, set/24 rev3 - medidor Woltmann
  DOROT             secao A, valvulas metalicas basicas - series 47/77/87, 67,
                    82/91, 84 e 94; L = face a face, H = altura do corpo
  RAN               Fig. 37 gaveta cunha emborrachada corpo curto (ISO 5752
                    serie 14, flange NBR 7675) e Fig. 39 retencao de
                    fechamento rapido wafer
  MP VALVULAS       Fig. 140 borboleta wafer (API 609, alavanca de 10 posicoes
                    ou caixa redutora - a tabela e a mesma), Fig. 114 valvula
                    de pe com crivo, Fig. 153 gaveta haste fixa

Uso: python3 tools/fichas_equipamento.py > data/cotas_equipamento.csv
"""
import csv
import sys

POLEGADA = {50: 2, 65: 2.5, 80: 3, 100: 4, 125: 5, 150: 6,
            200: 8, 250: 10, 300: 12, 350: 14, 400: 16, 500: 20, 600: 24,
            32: 1, 40: 1.5, 75: 3}

# ---- borboleta Saint-Gobain PAM, disco em ferro fundido -------------------
# A = face a face | H1 = altura acima do eixo | H2 = abaixo
# alcance = G, o comprimento da alavanca; nos DNs de redutor, o diametro do
# volante. E o alcance que diz se a valvula cabe onde foi posta.
BORBOLETA = [
    # dn_mm, acionamento, A,    H1,    H2,    alcance, peso
    (50,  "ALAVANCA", 42.0, 141.2,  68.6, 195.0,  2.4),
    (65,  "ALAVANCA", 44.5, 150.4,  76.0, 195.0,  2.7),
    (80,  "ALAVANCA", 44.5, 156.4,  95.0, 195.0,  3.3),
    (100, "ALAVANCA", 51.0, 167.9, 110.0, 266.0,  4.5),
    (125, "ALAVANCA", 54.5, 186.5, 129.4, 266.0,  7.2),
    (150, "ALAVANCA", 54.5, 205.7, 142.0, 328.0,  7.9),
    (200, "CAIXA",    59.6, 230.6, 176.0, 185.0, 19.7),
    (250, "CAIXA",    67.0, 269.9, 212.0, 280.0, 27.0),
    (300, "CAIXA",    75.5, 327.8, 248.5, 280.0, 39.0),
    (350, "CAIXA",    75.5, 368.0, 272.0, 280.0, 50.5),
]
# ---- medidor ARAD WSTsb (bayonet) ----------------------------------------
# L = comprimento entre faces | W = largura | H = altura total | h = do eixo
# para baixo. Trecho reto do fabricante: 5 DN antes, 3 DN depois (a casa usa
# 10 e 5, mais folgado - ver docs/LOGICA.md).
MEDIDOR = [
    # dn_mm,  L,   W,   H,   h,  peso
    (50,  200, 165, 239,  70, 12.0),
    (65,  200, 185, 254,  84, 15.0),
    (80,  230, 200, 259,  90, 15.5),
    (100, 250, 220, 275, 106, 19.0),
    (150, 300, 285, 344, 130, 35.0),
    (200, 350, 340, 377, 158, 47.0),
    (250, 450, 405, 463, 258, 75.0),
    (300, 500, 489, 505, 330, 95.0),
]
# ---- valvula hidraulica Dorot ---------------------------------------------
# L = face a face | H = altura total do corpo. As series 47, 77 e 87 partilham
# a mesma tabela. As linhas "323" e "868" do catalogo sao corpo reduzido -
# flange maior que o corpo (3"x2" e 8"x6") - e ficam de fora ate confirmacao.
DOROT = {
    ("47", "77", "87"): [
        # dn_mm, L,   H
        (50,  203, 169), (65,  214, 188), (80,  285, 203), (100, 307, 232),
        (150, 390, 360), (200, 462, 381), (250, 540, 458), (300, 587, 495),
        (350, 580, 495), (400, 755, 830), (500, 900, 970), (600, 900, 970),
    ],
    ("67",): [
        (50,  233, 175), (80,  310, 237), (100, 356, 265), (150, 436, 378),
        (200, 530, 481), (250, 636, 546), (400, 755, 830), (500, 900, 970),
        (600, 900, 970),
    ],
    ("82", "91"): [
        (32,   73, 110), (40,   73, 110), (50,   93, 131), (80,  177, 278),
        (100, 183, 293), (150, 230, 380),
    ],
    ("84",): [(80, 145, 239)],
    ("94",): [(50, 251, 121)],
}
# ---- gaveta RAN Fig. 37, corpo curto ISO 5752 serie 14 --------------------
# L = face a face | H = altura total com volante | V = diametro do volante.
# O face a face bate com data/valvulas_gaveta.csv em todos os DN - e norma,
# nao escolha do fabricante.
GAVETA = [
    # dn_mm,  L,   H,   V,  peso
    (50,  150, 220, 200,  11),
    (75,  180, 270, 250,  18),
    (80,  180, 270, 250,  18),
    (100, 190, 320, 300,  26),
    (125, 200, 410, 300,  40),
    (150, 210, 410, 300,  47),
    (200, 230, 510, 500,  90),
    (250, 250, 610, 500, 110),
    (300, 270, 735, 500, 171),
    (350, 290, 867, 585, 233),
    (400, 310, 850, 585, 233),
]
# ---- retencao de fechamento rapido RAN Fig. 39 ---------------------------
# Valvula diferente da portinhola das fichas MP Valvulas: tem by-pass e mola.
# H e L estao na tabela do catalogo mas o desenho nao deixa claro qual e o face
# a face - por isso saem marcados para conferencia e NAO entram na geometria.
RETENCAO_RAN = [
    # dn_mm, og, og_linha, H,  by_pass, L,  peso
    (100, 156, 140, 100, '1/2"', 130,   6.0),
    (125, 180, 160, 138, '1/2"', 145,   8.5),
    (150, 211, 194, 150, '3/4"', 180,  15.0),
    (200, 266, 258, 128, '3/4"', 180,  20.0),
    (250, 319, 311, 146, '1"',   257,  35.0),
    (300, 370, 360, 181, '1"',   260,  45.0),
    (350, 429, 413, 223, '1"',   286,  75.0),
    (400, 485, 475, 235, '1"',   215, 104.0),
]
# ---- borboleta MP Valvulas Fig. 140, wafer ANSI ou DIN 150 LBS -----------
# B = face a face | D = altura do centro ate o topo | A = diametro do disco.
# E e a bitola do tirante na ficha - fica marcada para conferencia porque
# diverge da regra da casa acima de 6" (ver docs/LOGICA.md).
# Alavanca de 10 posicoes e caixa redutora com volante lateral partilham a
# mesma tabela: o acionamento nao muda o corpo nesta linha.
BORBOLETA_MP = [
    # dn_pol,  A,     B,   D,     tirante
    (1.5,   45.5,  30, 100,   '3/8"'),
    (2,     51,    43, 140,   '9/16"'),
    (2.5,   65.5,  46, 152,   '9/16"'),
    (3,     76,    46, 159,   '9/16"'),
    (4,    101,    52, 178,   '5/8"'),
    (5,    127,    56, 190,   '3/4"'),
    (6,    146.5,  56, 202,   '3/4"'),
    (8,    194,    60, 242.5, '7/8"'),
    (10,   247,    68, 278,   '1"'),
    (12,   301,    78, 310,   '1.1/8"'),
    (14,   337,    78, 340,   '1.3/8"'),
    (16,   384,   102, 365,   '1.5/8"'),
    (18,   438,   114, 415,   '1.3/4"'),
    (20,   491,   127, 450,   '1.3/4"'),
    (24,   614,   154, 500,   '2.1/4"'),
]
# ---- valvula de pe com crivo MP Fig. 114, fundo de poco ------------------
# H = altura total do conjunto. E outra peca que o crivo conico do caderno
# Netafim e que o cesto do Irrigafour: aqui a retencao vem junto.
VALVULA_PE = [
    # dn_mm, H
    (50, 152), (65, 167), (75, 195), (80, 195), (100, 206), (125, 237),
    (150, 328), (200, 330), (250, 382), (300, 417), (350, 435), (400, 686),
]
# ---- gaveta MP Fig. 153: o que faltava era altura e volante --------------
# L (face a face) ja estava em data/valvulas_gaveta.csv e bate com o RAN.
GAVETA_MP = [
    # dn_mm,  L,   V volante
    (50,  150, 200), (65,  170, 200), (75,  180, 200), (100, 190, 200),
    (125, 200, 250), (150, 210, 300), (200, 230, 350), (250, 250, 350),
    (300, 270, 400), (350, 290, 500), (400, 310, 500),
]
FONTE_MP = "MP Valvulas fichas T.140, T.114 e T.153"
FONTE_RAN = "RAN Valvulas Fig. 37 (gaveta) e Fig. 39 (retencao)"
FONTE_DOROT = "DOROT secao A - valvulas metalicas basicas"
FONTE_BORB = "SAINT-GOBAIN PAM FTSG 0406 rev01"
FONTE_MED = "ARAD ING23008 WSTsb Bayonet set/24 rev3"


def main():
    escritor = csv.writer(sys.stdout)
    escritor.writerow(["fabricante", "familia", "variante", "dn_pol", "dn_mm",
                       "significado", "valor_mm", "ficha"])
    n = 0
    for dn_mm, acionamento, face, h1, h2, alcance, peso in BORBOLETA:
        for significado, valor in (("face_a_face_mm", face),
                                   ("altura_acima_mm", h1),
                                   ("altura_abaixo_mm", h2),
                                   ("alcance_acionamento_mm", alcance),
                                   ("peso_kg", peso)):
            escritor.writerow(["SAINT-GOBAIN", "VALVULA_BORBOLETA", acionamento,
                               f"{POLEGADA[dn_mm]:g}", dn_mm, significado,
                               f"{valor:g}", FONTE_BORB])
            n += 1
    for dn_mm, comp, larg, alt, h, peso in MEDIDOR:
        for significado, valor in (("face_a_face_mm", comp),
                                   ("largura_mm", larg),
                                   ("altura_total_mm", alt),
                                   ("altura_abaixo_mm", h),
                                   ("peso_kg", peso)):
            escritor.writerow(["ARAD", "MEDIDOR", "", f"{POLEGADA[dn_mm]:g}",
                               dn_mm, significado, f"{valor:g}", FONTE_MED])
            n += 1
    for series, tabela in DOROT.items():
        for dn_mm, comp, altura in tabela:
            for serie in series:
                for significado, valor in (("face_a_face_mm", comp),
                                           ("altura_total_mm", altura)):
                    escritor.writerow(["DOROT", "VALVULA_HIDRAULICA", serie,
                                       f"{POLEGADA[dn_mm]:g}", dn_mm,
                                       significado, f"{valor:g}", FONTE_DOROT])
                    n += 1
    for dn_mm, comp, altura, volante, peso in GAVETA:
        for significado, valor in (("face_a_face_mm", comp),
                                   ("altura_total_mm", altura),
                                   ("volante_mm", volante),
                                   ("peso_kg", peso)):
            escritor.writerow(["RAN", "VALVULA_GAVETA", "", f"{POLEGADA[dn_mm]:g}",
                               dn_mm, significado, f"{valor:g}", FONTE_RAN])
            n += 1
    for dn_mm, og, og2, h, by_pass, comp, peso in RETENCAO_RAN:
        for significado, valor in (("diametro_corpo_mm", og),
                                   ("H_conferir_mm", h),
                                   ("L_conferir_mm", comp),
                                   ("peso_kg", peso)):
            escritor.writerow(["RAN", "VALVULA_RETENCAO", "FECHAMENTO_RAPIDO",
                               f"{POLEGADA[dn_mm]:g}", dn_mm, significado,
                               f"{valor:g}", FONTE_RAN])
            n += 1
    for dn_pol, a, b, d, tirante in BORBOLETA_MP:
        for significado, valor in (("face_a_face_mm", b),
                                   ("altura_acima_mm", d),
                                   ("diametro_disco_mm", a)):
            escritor.writerow(["MP", "VALVULA_BORBOLETA", "", f"{dn_pol:g}", "",
                               significado, f"{valor:g}", FONTE_MP])
            n += 1
        escritor.writerow(["MP", "VALVULA_BORBOLETA", "", f"{dn_pol:g}", "",
                           "tirante_conferir_pol", tirante, FONTE_MP])
        n += 1
    for dn_mm, altura in VALVULA_PE:
        escritor.writerow(["MP", "VALVULA_PE", "COM_CRIVO", f"{POLEGADA[dn_mm]:g}",
                           dn_mm, "altura_total_mm", altura, FONTE_MP])
        n += 1
    for dn_mm, comp, volante in GAVETA_MP:
        for significado, valor in (("face_a_face_mm", comp),
                                   ("volante_mm", volante)):
            escritor.writerow(["MP", "VALVULA_GAVETA", "", f"{POLEGADA[dn_mm]:g}",
                               dn_mm, significado, f"{valor:g}", FONTE_MP])
            n += 1
    bitolas = sum(len(t) for t in DOROT.values())
    print(f"# {n} cotas de equipamento: borboleta {len(BORBOLETA)} bitolas, "
          f"medidor {len(MEDIDOR)}, dorot {bitolas} em "
          f"{sum(len(s) for s in DOROT)} series", file=sys.stderr)


if __name__ == "__main__":
    main()
