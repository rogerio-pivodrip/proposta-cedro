#!/usr/bin/env python3
"""Confere a regra do bocal da bomba contra a tabela de dimensoes da KSB.

A regra ENTRADA_PELA_SAIDA saiu de medir a lista da Netafim: uma bomba que
declara so a saida tem a entrada uma bitola acima. O catalogo do fabricante e
uma fonte independente - e diz o DN dos dois bocais em texto, sem inferencia.

Uso: python3 tools/conferir_bomba_ksb.py
"""
import csv
import json
import re
import sys

sys.path.insert(0, ".")
from motor import bomba, regras  # noqa: E402

MANUAL = "data/bombas_ksb_megabloc.csv"          # extraido do A2744
FOLHETO = "data/bombas_ksb_megabloc_folheto.csv"  # transcrito a mao, mais antigo
MEGANORM = "data/bombas_ksb_meganorm.csv"         # extraido do A2742
TABELA = MANUAL


def mm(polegada):
    for pol, dn in regras.POLEGADA_PARA_DN.items():
        if abs(pol - polegada) < 0.01:
            return dn
    return None


def pol(texto):
    texto = (texto or "").replace('"', "").strip()
    m = re.fullmatch(r"(\d+)\.(\d+)/(\d+)", texto)
    if m:
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    m = re.fullmatch(r"(\d+)/(\d+)", texto)
    if m:
        return int(m.group(1)) / int(m.group(2))
    return float(texto) if texto else None


def main():
    tres_fontes()
    pares = {}
    for r in csv.DictReader(open(TABELA, encoding="utf-8")):
        s = mm(pol(r["dn_recalque_pol"]))     # o nome da bomba e a saida
        e = mm(pol(r["dn_succao_pol"]))
        if s and e:
            pares.setdefault(s, set()).add(e)

    print("== bocal da bomba: regra da casa x catalogo KSB Megabloc")
    bate = falta = diverge = 0
    for saida in sorted(pares):
        nossa, quantas = bomba.entrada_presumida(saida)
        ksb = sorted(pares[saida])
        if nossa is None:
            print(f"  saida {saida:>3}mm  regra nao tem       KSB {ksb}")
            falta += 1
        elif [nossa] == ksb:
            print(f"  saida {saida:>3}mm  entrada {nossa:>3}mm "
                  f"({quantas} bombas na lista)   KSB confirma")
            bate += 1
        else:
            print(f"  saida {saida:>3}mm  regra diz {nossa}   KSB diz {ksb}   DIVERGE")
            diverge += 1
    print(f"  -> {bate} confirmadas, {diverge} divergentes, {falta} sem regra")
    nome_x_recalque()

    vistos = set()
    faixa = []
    for r in csv.DictReader(open(TABELA, encoding="utf-8")):
        chave = r["tamanho_folheto"]
        if r["polos"] != "4" or (pol(r["dn_succao_pol"]) or 0) < 3 \
                or chave in vistos:
            continue
        vistos.add(chave)
        faixa.append(r)
    print(f"\n== ancora do desenho: {len(faixa)} tamanhos com succao de 3\" ou mais")
    print(f"  {'tamanho':10} {'succao':>7} {'recalque':>9} {'eixo h1':>8} "
          f"{'h2':>5} {'a':>5}  flange")
    for r in faixa:
        print(f"  {r['tamanho_folheto']:10} {r['dn_succao_pol']:>7} "
              f"{r['dn_recalque_pol']:>9} {r['h1_mm']:>8} "
              f"{r['h2_mm']:>5} {r['a_mm']:>5}  {r['norma_flange']}")
    casar_com_a_lista()


def tres_fontes():
    """As tres medidas que posicionam os bocais, nas tres folhas que as tem.

    O folheto antigo da Megabloc chama a/b/c; o manual A2744 e o manual da
    Meganorm A2742 chamam h2/h1/a, que sao as letras da EN 733. Sao as mesmas
    tres medidas, e conferir uma contra a outra e o que decide quando duas
    folhas divergem: vence a que tem companhia.
    """
    def linhas(caminho, filtro=None):
        return [r for r in csv.DictReader(open(caminho, encoding="utf-8"))
                if not filtro or filtro(r)]
    manual = {}
    for r in linhas(MANUAL, lambda r: r["polos"] == "4"):
        manual.setdefault(r["tamanho_folheto"],
                          (r["h2_mm"], r["h1_mm"], r["a_mm"]))
    folheto = {r["tamanho"]: (r["a_mm"], r["b_mm"], r["c_mm"])
               for r in linhas(FOLHETO, lambda r: r["polos"] == "4" and r["a_mm"])}
    meganorm = {r["tamanho"]: (r["h2_mm"], r["h1_mm"], r["a_mm"])
                for r in linhas(MEGANORM)}

    print("== as tres medidas do bocal, nas tres folhas")
    iguais = 0
    divergem = []
    comuns = sorted(set(manual) & set(folheto),
                    key=lambda t: (int(t.split("-")[0]), float(t.split("-")[1])))
    for tamanho in comuns:
        trio = {"manual A2744": manual[tamanho], "folheto": folheto[tamanho]}
        if tamanho in meganorm:
            trio["Meganorm A2742"] = meganorm[tamanho]
        if len(set(trio.values())) == 1:
            iguais += 1
        else:
            divergem.append((tamanho, trio))
    print(f"  {iguais} de {len(comuns)} tamanhos com as tres folhas iguais")
    for tamanho, trio in divergem:
        print(f"    {tamanho}:")
        for fonte, valores in trio.items():
            print(f"      {fonte:16} h2/h1/a = {'/'.join(valores)}")
        vencedor = max(set(trio.values()), key=list(trio.values()).count)
        quantas = list(trio.values()).count(vencedor)
        print(f"      -> {quantas} de {len(trio)} dizem {'/'.join(vencedor)}")
    print("  O desenho de cada linha usa a folha da sua linha - nao mistura.")


def nome_x_recalque():
    """O primeiro numero do nome e o DN de recalque em milimetro.

    EN 733 nomeia a bomba por (DN de descarga) x (rotor nominal): 32-200 e
    descarga DN32 com rotor de 200. Se isso vale, o primeiro numero do nome
    tem que reproduzir a coluna DN2 do folheto sem consultar nada.
    """
    print("\n== nome da bomba x DN de recalque")
    bate = diverge = fora = 0
    ruins = []
    vistos = set()
    for r in csv.DictReader(open(TABELA, encoding="utf-8")):
        if r["tamanho_folheto"] in vistos:
            continue
        vistos.add(r["tamanho_folheto"])
        nome = int(r["tamanho_folheto"].split("-")[0])
        dn2 = mm(pol(r["dn_recalque_pol"]))
        if dn2 is None:
            # 1", 1.1/4" e 1.1/2" nao estao na tabela de DN da casa - a casa
            # nao usa esse tamanho de bomba, e nao ha o que conferir
            fora += 1
        elif dn2 == nome:
            bate += 1
        else:
            diverge += 1
            ruins.append(f'{r["tamanho_folheto"]} diz {nome} mm, '
                         f'folha diz {dn2}')
    print(f"  {bate} de {bate + diverge} confirmam: o nome da bomba E o DN2")
    for ruim in ruins:
        print(f"    {ruim}")
    print(f"  {fora} tamanhos com recalque abaixo de 2\" ficam fora - a tabela "
          f"de DN da casa\n  comeca em 2\" e a casa nao usa bomba desse porte.")
    print("  A succao sobe uma ou duas bitolas e nao tem regra - fica a tabela.")


def casar_com_a_lista():
    """Liga os codigos METB da lista aos tamanhos do catalogo.

    O nome na lista tem tres grupos - entrada, saida, rotor - e o catalogo
    nomeia com dois, saida e rotor, deixando a entrada implicita. Entao
    METB 150-125-200 e o tamanho 125-200 do catalogo, com succao de 150.
    """
    tabela = {r["tamanho_folheto"]: r
              for r in csv.DictReader(open(TABELA, encoding="utf-8"))
              if r["polos"] == "4"}
    catalogo = json.load(open("data/catalogo.json", encoding="utf-8"))
    metb = [i for i in catalogo if i.get("familia") == "BOMBA"
            and re.search(r"\bMETB\b", i["descricao"])]
    achou = perdeu = 0
    faltando = set()
    for item in metb:
        m = re.search(r"(\d{2,3})-(\d{2,3})-(\d{2,4})", item["descricao"])
        if not m:
            m2 = re.search(r"(\d{2,3})-(\d{2,4})(?!\d)", item["descricao"])
            chave = (f"{int(m2.group(1))}-{int(m2.group(2))}") if m2 else None
        else:
            chave = f"{int(m.group(2))}-{int(m.group(3))}"
        if chave and chave in tabela:
            achou += 1
        else:
            perdeu += 1
            if chave:
                faltando.add(chave)
    print(f"\n== lista x catalogo: {len(metb)} codigos METB")
    print(f"  {achou} tem dimensao na tabela, {perdeu} nao")
    if faltando:
        print(f"  tamanhos citados na lista e ausentes do folheto: "
              f"{', '.join(sorted(faltando))}")


if __name__ == "__main__":
    main()
