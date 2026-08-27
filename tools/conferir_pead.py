#!/usr/bin/env python3
"""Confere a tabela de SDR contra a parede que a descricao do tubo PEAD diz.

No PEAD o desenho depende de dois numeros e os dois estao no codigo: o DN, que
E o diametro externo, e a parede, que sai da razao DN/SDR fixada pela pressao.
Se a tabela de SDR estiver certa, o calculo tem que reproduzir a parede que a
descricao ja carrega - TUBO PEAD PE100 PN08 355MMX16,9MMX6M da 355/21 = 16,9.

Uso: python3 tools/conferir_pead.py
"""
import json
import re
import sys

sys.path.insert(0, ".")
from motor.simbolos import SDR_POR_PN  # noqa: E402

CATALOGO = "data/catalogo.json"
# PN08 225MMX10,8MMX6M -> pressao, diametro, parede
RX = re.compile(r"PN\s?0?(\d+(?:[,.]\d+)?).*?(\d{2,3})MM\s?X\s?(\d+(?:,\d+)?)MM",
                re.I)
FOLGA_MM = 0.35        # a norma arredonda a parede para cima


def num(t):
    return float(t.replace(",", "."))


def main():
    batem = fora = sem_parede = 0
    achados = []
    for item in json.load(open(CATALOGO, encoding="utf-8")):
        if item["familia"] != "TUBO" or item["material"] != "PEAD":
            continue
        m = RX.search(item["descricao"])
        if not m:
            sem_parede += 1
            continue
        pn, dn, parede = num(m.group(1)), num(m.group(2)), num(m.group(3))
        sdr = SDR_POR_PN.get(pn)
        if not sdr:
            fora += 1
            achados.append((item["descricao"], f"PN {pn:g} nao esta na tabela"))
            continue
        calculada = dn / sdr
        if abs(calculada - parede) <= FOLGA_MM:
            batem += 1
        else:
            fora += 1
            achados.append((item["descricao"],
                            f"tabela {calculada:.1f} x descricao {parede:.1f}"))

    print(f"{batem} tubos conferem, {fora} nao, {sem_parede} sem parede na "
          f"descricao")
    for descricao, motivo in achados:
        print(f"  {descricao:44} {motivo}")
    if fora:
        print("\nO PN80 nao e pressao, e a resina PE80 - o codigo antigo nao "
              "separa os dois.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
