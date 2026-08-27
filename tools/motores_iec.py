#!/usr/bin/env python3
"""Extrai a tabela do MOTOR de dentro da tabela da Megabloc.

Descoberto ao separar as colunas do manual A2744 por quem as faz variar: elas
se partem em duas metades limpas, e nenhuma coluna fica no meio.

  dependem do TAMANHO da bomba   h1 h2 a b m1 m2 n1 n2 n3 s1
  dependem da CARCACA do motor   h l m3 m4 n4 n5 r1 s2 t1 w

Ou seja: o l do manual NAO e o comprimento do conjunto - e o comprimento do
MOTOR. Um l so por carcaca, em 22 de 22 carcacas, nas duas rotacoes. E isso
resolve o que o desenho nao tinha: um motor de 60 CV e uma carcaca 225 com
880 mm de comprimento, um de 3 CV e uma 90L com 399. A diferenca aparece.

Duas letras bastam para o tamanho do motor:

  h   altura do eixo do motor - e o proprio numero da carcaca IEC
  l   comprimento do motor

**r1 e n5 nao sao o corpo.** Eu li o r1 como diametro do corpo e desenhei
motor com ele por um tempo. Errado: cruzando esta tabela com a folha da EBARA,
r1 bate EXATO com o A do IEC e n5 com o AB, nos seis quadros que as duas
compartilham (90, 100, 112, 200, 225 e o 132 pela vizinha):

  quadro   r1 (KSB)   A (EBARA)      n5 (KSB)   AB (EBARA)
  90         140        140            164        164
  100        160        160            188        188
  112        190        190            220        220
  200        318        318            385        385
  225        356        356            436        436

A e AB sao medidas de LARGURA - vao entre os furos dos pes e largura sobre os
pes. Elas se veem de FRENTE, e o desenho da casa e de lado. Numa carcaca 90 o
r1 da 140 onde o corpo tem 180.

O diametro do corpo e o OAC, e ele nao esta neste manual. Ele esta no DXF da
W22 que a casa mandou: ver tools/extrair_weg.py e data/motores_weg.csv. Por
isso as colunas aqui tem o nome do que elas medem, e nao "corpo".

A Meganorm nao repete essas medidas - a secao 15 dela so diz QUAL carcaca
monta em cada bomba. Como a carcaca IEC e a mesma peca nas duas linhas, esta
tabela serve as duas.

Uso: python3 tools/motores_iec.py > data/motores_iec.csv
"""
import csv
import sys

MEGABLOC = "data/bombas_ksb_megabloc.csv"
FONTE = ("KSB Megabloc manual tecnico A2744.0.3P/2 - colunas que dependem so "
         "da carcaca")


def main():
    motores = {}
    for r in csv.DictReader(open(MEGABLOC, encoding="utf-8")):
        carcaca = r["carcaca_motor"]
        ficha = motores.setdefault(carcaca, {
            "carcaca": carcaca, "eixo_mm": r["h_mm"], "comprimento_mm": r["l_mm"],
            "largura_pes_mm": r["r1_mm"], "largura_total_mm": r["n5_mm"],
            "cv": set(), "fonte": FONTE})
        ficha["cv"].add(float(r["cv"]))
        for campo, coluna in (("eixo_mm", "h_mm"), ("comprimento_mm", "l_mm"),
                              ("largura_pes_mm", "r1_mm")):
            if r[coluna] and ficha[campo] != r[coluna]:
                print(f"# {carcaca}: {coluna} tem dois valores "
                      f"({ficha[campo]} e {r[coluna]})", file=sys.stderr)

    campos = ["carcaca", "quadro", "eixo_mm", "comprimento_mm",
              "largura_pes_mm", "largura_total_mm", "cv_min", "cv_max", "fonte"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    for ficha in sorted(motores.values(),
                        key=lambda f: (float(f["eixo_mm"]), f["carcaca"])):
        escritor.writerow({
            "carcaca": ficha["carcaca"],
            "quadro": int(float(ficha["eixo_mm"])),
            "eixo_mm": ficha["eixo_mm"],
            "comprimento_mm": ficha["comprimento_mm"],
            "largura_pes_mm": ficha["largura_pes_mm"],
            "largura_total_mm": ficha["largura_total_mm"],
            "cv_min": f'{min(ficha["cv"]):g}', "cv_max": f'{max(ficha["cv"]):g}',
            "fonte": ficha["fonte"]})
    print(f"# {len(motores)} carcacas", file=sys.stderr)


if __name__ == "__main__":
    main()
