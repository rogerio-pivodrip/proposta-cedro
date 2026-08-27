#!/usr/bin/env python3
"""Confere se todo codigo SAP citado nas tabelas ainda existe no catalogo.

O esquema do fabricante avisa em rodape que "codigos e produtos poderao ser
substituidos ou desativados". As tabelas deste repositorio apontam para codigos
fixos - kit de flange PVC, piloto, barra roscada, de-para. Este script varre
todas elas e acusa o que nao esta mais na lista.

Uso: python3 tools/conferir_codigos.py
"""
import glob
import json
import os
import re
import sys

RX_SAP = re.compile(r"\b\d{5}-\d{6}\b")
CATALOGO = "data/catalogo.json"


def main():
    detalhar = "-v" in sys.argv
    with open(CATALOGO, encoding="utf-8") as fh:
        catalogo = {i["sap"]: i for i in json.load(fh)}

    total = achados = perdidos = 0
    fontes = (glob.glob("data/*.csv") + glob.glob("docs/*.md")
              + glob.glob("*.md"))
    for caminho in sorted(fontes):
        nome = os.path.basename(caminho)
        if nome.startswith("exemplo"):
            continue
        # O caderno de desenhos cita codigos que a LM ainda nao tem - e o
        # achado, nao um erro. Quem cuida disso e tools/conferir_desenhos.py.
        if nome == "desenhos_netafim.csv":
            continue
        with open(caminho, encoding="utf-8") as fh:
            texto = fh.read()
        codigos = sorted(set(RX_SAP.findall(texto)))
        if not codigos:
            continue
        total += len(codigos)
        faltando = [c for c in codigos if c not in catalogo]
        achados += len(codigos) - len(faltando)
        perdidos += len(faltando)
        marca = "ok" if not faltando else f"{len(faltando)} fora do catalogo"
        print(f'{os.path.basename(caminho):26s} {len(codigos):3d} codigos  {marca}')
        for c in faltando:
            print(f"    ! {c} nao existe na lista atual")
        if detalhar:
            for c in codigos:
                if c in catalogo:
                    print(f"      {c}  {catalogo[c]['descricao'][:54]}")

    print(f"\n{total} codigos citados: {achados} conferem, {perdidos} nao existem")
    return 1 if perdidos else 0


if __name__ == "__main__":
    sys.exit(main())
