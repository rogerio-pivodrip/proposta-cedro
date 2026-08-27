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

Uso: python3 tools/fichas_equipamento.py > data/cotas_equipamento.csv
"""
import csv
import sys

POLEGADA = {50: 2, 65: 2.5, 80: 3, 100: 4, 125: 5, 150: 6,
            200: 8, 250: 10, 300: 12, 350: 14, 400: 16, 500: 20, 600: 24,
            32: 1, 40: 1.5}

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
    bitolas = sum(len(t) for t in DOROT.values())
    print(f"# {n} cotas de equipamento: borboleta {len(BORBOLETA)} bitolas, "
          f"medidor {len(MEDIDOR)}, dorot {bitolas} em "
          f"{sum(len(s) for s in DOROT)} series", file=sys.stderr)


if __name__ == "__main__":
    main()
