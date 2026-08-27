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

Tres letras bastam para desenhar o motor, e as tres se confirmam entre si:

  h   altura do eixo do motor - e o proprio numero da carcaca IEC
  l   comprimento do motor
  r1  diametro do corpo. h - r1/2 da a altura do pe do motor, e ela sobe de
      20 mm na carcaca 90 para 47 na 225 - que e como motor IEC e mesmo.

n5 e maior que r1 em toda a tabela e fica gravado, mas nao entra no desenho:
sem a figura em resolucao maior nao da para dizer se e a largura com aletas,
com caixa de ligacao, ou outra coisa.

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
            "corpo_mm": r["r1_mm"], "n5_mm": r["n5_mm"], "cv": set(),
            "fonte": FONTE})
        ficha["cv"].add(float(r["cv"]))
        for campo, coluna in (("eixo_mm", "h_mm"), ("comprimento_mm", "l_mm"),
                              ("corpo_mm", "r1_mm")):
            if r[coluna] and ficha[campo] != r[coluna]:
                print(f"# {carcaca}: {coluna} tem dois valores "
                      f"({ficha[campo]} e {r[coluna]})", file=sys.stderr)

    campos = ["carcaca", "quadro", "eixo_mm", "comprimento_mm", "corpo_mm",
              "pe_mm", "n5_mm", "cv_min", "cv_max", "fonte"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    for ficha in sorted(motores.values(),
                        key=lambda f: (float(f["eixo_mm"]), f["carcaca"])):
        eixo, corpo = float(ficha["eixo_mm"]), float(ficha["corpo_mm"])
        escritor.writerow({
            "carcaca": ficha["carcaca"],
            "quadro": int(float(ficha["eixo_mm"])),
            "eixo_mm": ficha["eixo_mm"],
            "comprimento_mm": ficha["comprimento_mm"],
            "corpo_mm": ficha["corpo_mm"],
            "pe_mm": round(eixo - corpo / 2, 1),
            "n5_mm": ficha["n5_mm"],
            "cv_min": f'{min(ficha["cv"]):g}', "cv_max": f'{max(ficha["cv"]):g}',
            "fonte": ficha["fonte"]})
    print(f"# {len(motores)} carcacas", file=sys.stderr)


if __name__ == "__main__":
    main()
