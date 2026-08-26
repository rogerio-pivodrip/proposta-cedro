#!/usr/bin/env python3
"""Demonstracao ponta a ponta: monta uma succao padrao e emite a lista.

Uso: python3 tools/demo_succao.py [DN_POLEGADAS]
"""
import sys

sys.path.insert(0, ".")
from motor.catalogo import Catalogo
from motor.linha import Linha, Peca

NORMA = "NBR PN16"


def montar_succao(cat, dn):
    """Template 'SUCCAO CANAL PADRAO' resolvido para um DN."""
    linha = Linha(cat, tipo="SUCCAO")
    receita = [
        ("CRIVO", {}),
        ("TUBO", {"comprimento_mm": 1000}),
        ("CURVA", {"angulo": 90}),
        ("TUBO", {"comprimento_mm": 3000}),
        ("CURVA", {"angulo": 45}),
        ("TUBO", {"comprimento_mm": 1500}),
        ("REDUCAO_EXCENTRICA", {"dn_saida": dn - 2}),
    ]
    faltando = []
    for familia, extra in receita:
        item = cat.melhor(familia, dn, norma=NORMA, **extra)
        if not item:
            faltando.append((familia, dn, extra))
            continue
        linha.inserir(Peca(item, comprimento_mm=extra.get("comprimento_mm")))
    return linha, faltando


def main():
    dn = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    cat = Catalogo()
    linha, faltando = montar_succao(cat, dn)

    print(f'== SUCCAO {dn:g}" {NORMA} - {len(linha.pecas)} pecas na linha ==')
    for i, p in enumerate(linha.pecas):
        print(f'  {i}. {p.sap}  {p.descricao}')
    if faltando:
        print("  nao encontrado no catalogo:", faltando)

    print("\n== juncoes ==")
    for j in linha.juncoes():
        print(f"  {j['pos']}: {j['acao']:10s} {j['dados']}")

    print("\n== geometria (mm) ==")
    for g in linha.geometria():
        de, para = g["de"], g["para"]
        print(f"  {g['peca'].familia:22s} ({de[0]:8.0f},{de[1]:8.0f}) -> "
              f"({para[0]:8.0f},{para[1]:8.0f})  dir={g['direcao']:.0f}deg")

    bom, avisos = linha.lista_materiais()
    print(f"\n== LISTA DE MATERIAIS ({len(bom)} codigos) ==")
    print(f"{'Area':5s} {'Cod. SAP':14s} {'Qtd':>5s}  Descricao")
    for reg in bom:
        print(f"{linha.area:5s} {reg['sap']:14s} {reg['qtd']:5g}  {reg['descricao']}")
    if avisos:
        print("\n== avisos ==")
        for a in avisos:
            print("  !", a)


if __name__ == "__main__":
    main()
