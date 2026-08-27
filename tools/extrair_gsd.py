#!/usr/bin/env python3
"""Extrai o dimensional da serie GSD e a base viga da serie GS.

Duas folhas, dois feitios de tabela e dois problemas diferentes.

A GSD (desenho 406.1) tem CELULA MESCLADA: bombas do mesmo grupo dividem o
diametro nominal, o f2, o b, o m1, o m2 e o s1, e o valor aparece uma vez so
na primeira linha do grupo. Ler linha a linha perde a maioria dos numeros, e
por isso aqui cada coluna e lida pela POSICAO x dela e o que falta desce da
linha anterior - do mesmo jeito que quem le a folha no papel faz.

A base viga da GS e texto corrido e limpo: uma linha por combinacao de bomba e
potencia.

Uso: python3 tools/extrair_gsd.py folha_gsd.pdf folha_base.pdf
"""
import csv
import re
import sys
import types

for _m in ("cryptography", "cryptography.hazmat", "cryptography.hazmat.primitives",
           "cryptography.hazmat.primitives.ciphers", "cryptography.hazmat.backends",
           "cryptography.hazmat.primitives.ciphers.algorithms",
           "cryptography.hazmat.primitives.ciphers.modes"):
    sys.modules[_m] = types.ModuleType(_m)
sys.modules["cryptography.hazmat.primitives.ciphers"].Cipher = object
sys.modules["cryptography.hazmat.primitives.ciphers"].algorithms = object
sys.modules["cryptography.hazmat.primitives.ciphers"].modes = object
sys.modules["cryptography.hazmat.backends"].default_backend = lambda: None
import pdfplumber  # noqa: E402

# coluna -> x do centro dela na folha 406.1, folha 2
COLUNAS = [("dn1_mm", 231), ("dn2_mm", 265), ("f2_mm", 288), ("h1_mm", 305),
           ("h2_mm", 322), ("b_mm", 341), ("m1_mm", 356), ("m2_mm", 375),
           ("n1_mm", 389), ("n2_mm", 406), ("s1_mm", 423), ("xd_mm", 435),
           ("xc_mm", 452), ("f1_mm", 469)]
# as que MESCLAM: valem para o grupo inteiro e descem de linha
MESCLADAS = {"dn1_mm", "dn2_mm", "f2_mm", "b_mm", "m1_mm", "m2_mm", "s1_mm",
             "f1_mm", "grupo_suporte"}
RX_MODELO = re.compile(r"^\d{2,3}-\d{3}[A-Z]?(?:\.\d)?$")
RX_GRUPO = re.compile(r"^GSD/\d{3}$")
TOLERANCIA = 7.0        # quanto o numero pode fugir do centro da coluna
# a tabela vive nesta faixa da folha. Sem isso o "1 2 3 4 5 6" do quadro cai
# dentro dela: o "3" fica na coluna do b e vira uma bomba com 3 mm de pe
FAIXA_Y = (20, 155)
# faixa plausivel de cada cota, em mm. Serve para pegar numero colado - a
# folha tem "21215" onde estao 212 e 15 grudados, e um n2 de 21 metros nao e
# cota, e leitura errada
LIMITES = {"dn1_mm": (25, 400), "dn2_mm": (25, 400), "f2_mm": (50, 400),
           "h1_mm": (80, 500), "h2_mm": (100, 600), "b_mm": (30, 250),
           "m1_mm": (50, 400), "m2_mm": (40, 300), "n1_mm": (150, 800),
           "n2_mm": (100, 700), "s1_mm": (8, 40), "xd_mm": (80, 500),
           "xc_mm": (80, 500), "f1_mm": (100, 400)}


def _numero(txt):
    txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


def dimensional(caminho, recusados=None):
    """Uma linha por modelo GSD, com o que mescla ja preenchido."""
    recusados = recusados if recusados is not None else []
    pg = pdfplumber.open(caminho).pages[1]
    palavras = pg.extract_words()
    # y -> palavras, com a mesma granularidade grossa que a folha usa
    filas = {}
    for w in palavras:
        y = round(w["top"] / 3.2)
        if FAIXA_Y[0] <= y <= FAIXA_Y[1]:
            filas.setdefault(y, []).append(w)

    linhas = []
    for y in sorted(filas):
        fila = sorted(filas[y], key=lambda w: w["x0"])
        modelo = next((w["text"] for w in fila
                       if w["x0"] < 165 and RX_MODELO.match(w["text"])), None)
        grupo = next((w["text"] for w in fila if RX_GRUPO.match(w["text"])), None)
        valores = {}
        for w in fila:
            valor = _numero(w["text"])
            if valor is None:
                continue
            for nome, x in COLUNAS:
                if abs(w["x0"] - x) > TOLERANCIA:
                    continue
                lo, hi = LIMITES[nome]
                if lo <= valor <= hi:
                    valores[nome] = valor
                else:
                    recusados.append((nome, w["text"]))
                break
        if modelo or grupo or valores:
            linhas.append({"y": y, "modelo": modelo, "grupo_suporte": grupo,
                           **valores})

    # 1. o modelo pega o que esta na sua propria fila e nas vizinhas sem modelo
    saida, i = [], 0
    while i < len(linhas):
        if not linhas[i]["modelo"]:
            i += 1
            continue
        peca = dict(linhas[i])
        for j in (i - 1, i + 1):
            if 0 <= j < len(linhas) and not linhas[j]["modelo"]:
                for k, v in linhas[j].items():
                    if k not in ("y", "modelo") and v is not None:
                        peca.setdefault(k, v)
                        if peca.get(k) is None:
                            peca[k] = v
        saida.append(peca)
        i += 1

    # 2. o que mescla desce: quem nao trouxe o proprio valor herda do de cima
    for n, peca in enumerate(saida):
        for chave in MESCLADAS:
            if peca.get(chave) is None and n:
                peca[chave] = saida[n - 1].get(chave)

    # 3. duas guardas, porque descer valor erra em celula mesclada e a folha
    #    tem como se conferir sozinha:
    #
    #    o NOME diz o DN2 - "125-250" e uma bomba de recalque 125 e rotor 250,
    #    a mesma regra que o folheto da KSB usa e que ja foi homologada aqui.
    #    Onde a tabela discorda do nome, quem manda e o nome;
    #    f1 e f2 pertencem ao GRUPO DO SUPORTE e nao a bomba - por isso valem
    #    o mesmo em todo o grupo. A moda do grupo corrige quem herdou do
    #    vizinho de cima em vez do proprio grupo.
    for peca in saida:
        nome = (peca.get("modelo") or "").split("-")[0]
        if nome.isdigit():
            peca["dn2_mm"] = float(nome)
    for chave in ("f1_mm", "f2_mm"):
        por_grupo = {}
        for peca in saida:
            if peca.get("grupo_suporte") and peca.get(chave):
                por_grupo.setdefault(peca["grupo_suporte"], []).append(
                    peca[chave])
        moda = {g: max(set(v), key=v.count) for g, v in por_grupo.items()}
        for peca in saida:
            if peca.get("grupo_suporte") in moda:
                peca[chave] = moda[peca["grupo_suporte"]]
    # dn1 tem de ser maior que dn2: a succao e sempre uma bitola acima
    ACIMA = {32: 50, 40: 65, 50: 65, 65: 80, 80: 100, 100: 125, 125: 150,
             150: 200, 200: 250}
    for peca in saida:
        dn2 = peca.get("dn2_mm")
        if dn2 and (not peca.get("dn1_mm") or peca["dn1_mm"] <= dn2):
            peca["dn1_mm"] = ACIMA.get(int(dn2))
    return saida


# a tabela de motor da mesma folha, do lado direito dela
MOTOR = [("A_mm", 534), ("AB_mm", 551), ("AD_mm", 568), ("AC_mm", 586),
         ("B_mm", 613), ("BB_mm", 641), ("C_mm", 663), ("K_mm", 680),
         ("H_mm", 698), ("L2_mm", 714), ("L1_230_mm", 744), ("L1_250_mm", 787)]
LIMITES_MOTOR = {"A_mm": (90, 700), "AB_mm": (100, 800), "AD_mm": (100, 600),
                 "AC_mm": (60, 500), "B_mm": (60, 600), "BB_mm": (80, 700),
                 "C_mm": (30, 300), "K_mm": (5, 40), "H_mm": (60, 400),
                 "L2_mm": (150, 1200), "L1_230_mm": (200, 1400),
                 "L1_250_mm": (200, 1400)}
RX_CARCACA = re.compile(r"^L?\d{2,3}[SML]?(?:/[SML])?$|^L\d{2,3}[SML]$")


def motores(caminho):
    """A tabela de motor da folha da GSD - e ela que explica o pescoco.

    L2 e o corpo do motor e L1 e o total dele com o PESCOCO que liga no
    caracol. A diferenca entre os dois e o pescoco, e ela muda com o grupo do
    suporte: na carcaca 160M sao 185 mm no GSDB/230 e 230 no GSDB/250. E por
    isso que o motor da GSD nao encosta na voluta como o da Megabloc encosta.
    """
    pg = pdfplumber.open(caminho).pages[1]
    filas = {}
    for w in pg.extract_words():
        if w["x0"] > 495:
            filas.setdefault(round(w["top"] / 3.2), []).append(w)

    linhas = []
    for y in sorted(filas):
        fila = sorted(filas[y], key=lambda w: w["x0"])
        carcaca = next((w["text"] for w in fila
                        if w["x0"] < 533 and RX_CARCACA.match(w["text"])), None)
        valores = {}
        for w in fila:
            valor = _numero(w["text"])
            if valor is None:
                continue
            for nome, x in MOTOR:
                if abs(w["x0"] - x) > 8:
                    continue
                lo, hi = LIMITES_MOTOR[nome]
                if lo <= valor <= hi:
                    valores[nome] = valor
                break
        if carcaca or valores:
            linhas.append({"carcaca": carcaca, **valores})

    saida = []
    for i, linha in enumerate(linhas):
        if not linha["carcaca"]:
            continue
        peca = dict(linha)
        for j in (i - 1, i + 1):
            if 0 <= j < len(linhas) and not linhas[j]["carcaca"]:
                for k, v in linhas[j].items():
                    if k != "carcaca" and v is not None:
                        peca.setdefault(k, v)
        saida.append(peca)
    return saida


def potencias(caminho):
    """A tabela CV -> carcaca da propria folha da GSD, em 2 e 4 polos.

    Precisa dela porque a folha NOMEIA a carcaca do jeito dela - L112M, 132M,
    225S/M - e e por esse nome que a tabela de motor da mesma folha esta
    indexada. A tabela IEC generica do motor devolve "160" e "200", que nao
    casam com "160M" e "200L".
    """
    pg = pdfplumber.open(caminho).pages[1]
    filas = {}
    for w in pg.extract_words():
        if w["x0"] < 120:
            filas.setdefault(round(w["top"] / 3.2), []).append(w)
    saida = []
    for y in sorted(filas):
        fila = sorted(filas[y], key=lambda w: w["x0"])
        cv = next((_numero(w["text"]) for w in fila
                   if w["x0"] < 56 and _numero(w["text"]) is not None), None)
        if cv is None or not 0.5 <= cv <= 400:
            continue
        dois = next((w["text"] for w in fila if 60 <= w["x0"] < 90
                     and RX_CARCACA.match(w["text"])), None)
        quatro = next((w["text"] for w in fila if 90 <= w["x0"] < 120
                       and RX_CARCACA.match(w["text"])), None)
        if dois or quatro:
            saida.append({"cv": cv, "carcaca_2p": dois or "",
                          "carcaca_4p": quatro or dois or ""})
    return saida


def base_viga(caminho):
    """A base viga da GS: uma linha por bomba e potencia."""
    pdf = pdfplumber.open(caminho)
    rx = re.compile(
        r"GS\s+(\d{2,3}-\d{3}[A-Z]?)\s+(\d+)\s+(\d+)\s+([\w/]+)\s+"
        r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
        r"(\d+)\s+(\d+)")
    saida = []
    for pagina in pdf.pages:
        for linha in (pagina.extract_text() or "").splitlines():
            m = rx.match(linha.strip())
            if m:
                saida.append({
                    "bomba": m.group(1), "cv": m.group(2), "rpm": m.group(3),
                    "carcaca_motor": m.group(4), "c_mm": m.group(5),
                    "A_mm": m.group(6), "B_mm": m.group(7), "Y_mm": m.group(8),
                    "V_mm": m.group(9), "E_mm": m.group(10),
                    "H_mm": m.group(11), "s_mm": m.group(12),
                    "T_mm": m.group(13), "peso_kg": m.group(14)})
    return saida


def main():
    recusados = []
    gsd = dimensional(sys.argv[1], recusados)
    # a folha diz quais cotas fazem a bomba: sem bitola e sem as duas alturas
    # nao ha desenho, e a linha nao sai
    # f1 e f2 entram nas essenciais porque a diferenca entre as duas E a cota
    # que posiciona os dois bocais: face de succao ate o eixo da descarga
    essenciais = ("dn1_mm", "dn2_mm", "h1_mm", "h2_mm", "f1_mm", "f2_mm")
    completas = [p for p in gsd if all(p.get(k) for k in essenciais)]
    faltando = [p["modelo"] for p in gsd if p not in completas]
    campos = ["modelo", "grupo_suporte"] + [n for n, _ in COLUNAS]
    with open("data/bombas_gsd.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, campos + ["fonte"], extrasaction="ignore")
        w.writeheader()
        for p in completas:
            w.writerow({**p, "fonte": "GSD desenho 406.1 folha 2 (rev. 10)"})
    print(f"{len(completas)} modelos GSD de {len(gsd)} lidos "
          f"-> data/bombas_gsd.csv")
    if faltando:
        print(f"  sem cota essencial, fora: {', '.join(faltando)}")
    if recusados:
        print(f"  numeros recusados por estarem fora de faixa: "
              f"{', '.join(f'{n}={v}' for n, v in recusados)}")

    mot = [m for m in motores(sys.argv[1])
           if m.get("L2_mm") and (m.get("L1_230_mm") or m.get("L1_250_mm"))]
    campos_m = ["carcaca"] + [n for n, _ in MOTOR]
    with open("data/motores_gsd.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, campos_m + ["fonte"], extrasaction="ignore")
        w.writeheader()
        for m in mot:
            w.writerow({**m, "fonte": "GSD desenho 406.1 folha 2 (rev. 10)"})
    print(f"{len(mot)} carcacas de motor -> data/motores_gsd.csv")

    pot = potencias(sys.argv[1])
    with open("data/potencias_gsd.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, ["cv", "carcaca_2p", "carcaca_4p", "fonte"])
        w.writeheader()
        for r in pot:
            w.writerow({**r, "fonte": "GSD desenho 406.1 folha 2 (rev. 10)"})
    print(f"{len(pot)} potencias -> data/potencias_gsd.csv")

    base = base_viga(sys.argv[2])
    with open("data/bases_gs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(base[0]) + ["fonte"])
        w.writeheader()
        for r in base:
            w.writerow({**r, "fonte": "Tabela dimensional base viga bombas GS"})
    print(f"{len(base)} linhas de base viga -> data/bases_gs.csv")


if __name__ == "__main__":
    main()
