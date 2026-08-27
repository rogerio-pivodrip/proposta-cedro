#!/usr/bin/env python3
"""Roda o template de succao e confere contra os dois projetos reais.

Uso: python3 tools/demo_template.py
"""
import sys

sys.path.insert(0, ".")
from motor.bomba import HORIZONTAL, VERTICAL
from motor.catalogo import Catalogo
from motor.templates import succao

CASOS = [
    {
        "projeto": "Marcelo Amorim 1855NN",
        "dn": 4.0, "bomba": "METB 050-32-200", "orientacao": HORIZONTAL,
        "curva": 90,
        "desenho": ["CRIVO FOFO 4\" FL P/ VALVULA PE",
                    "Ari Valvula de Retencao de 4\"",
                    "Tubo AZ 4\" -1.00m",
                    "Curva AZ 4\" - 90o",
                    "Red Exc AZ 4\"x 2\""],
    },
    {
        "projeto": "Lincoln Junqueira 2040/25NN",
        "dn": 8.0, "bomba": "METB 125-80-315", "orientacao": VERTICAL,
        "curva": None,
        "desenho": ["Crivo 8\" p/ Valvula de Pe",
                    "Ari Valvula de Retencao de 8\"",
                    "Tubo AZ 8\" -1m",
                    "Red Con AZ 8\" x 5\""],
    },
]


def main():
    cat = Catalogo()
    for caso in CASOS:
        linha, _reducao, faltando = succao(
            cat, caso["dn"], caso["bomba"], caso["orientacao"], caso["curva"])
        print(f'\n== {caso["projeto"]} - succao {caso["dn"]:g}", '
              f'bomba {caso["orientacao"].lower()} ==')
        print(f'{"template":48s} | desenho')
        print("-" * 100)
        for i in range(max(len(linha.pecas), len(caso["desenho"]))):
            gerado = (f'{linha.pecas[i].sap} {linha.pecas[i].descricao[:32]}'
                      if i < len(linha.pecas) else "")
            desenho = caso["desenho"][i] if i < len(caso["desenho"]) else ""
            print(f"{gerado:48s} | {desenho}")
        if faltando:
            print("  nao encontrado:", faltando)
        bom, avisos = linha.lista_materiais()
        derivados = [r for r in bom if r["origem"] != "linha"]
        print(f'  {len(linha.pecas)} pecas na linha + {len(derivados)} '
              "codigos derivados (ferragem e tirante)")


if __name__ == "__main__":
    main()
