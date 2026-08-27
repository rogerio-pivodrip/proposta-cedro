#!/usr/bin/env python3
"""Junta as cotas dos dois fabricantes numa tabela so, com o Irrigafour como padrao.

O motor pergunta "quanto mede uma reducao de 8 polegadas" e recebe uma resposta,
nao duas. A escolha da casa e o Irrigafour; a Netafim fica como alternativa
declarada, para quando a peca comprada for dela.

Entradas: data/cotas_irrigafour.csv, data/cotas_por_familia.csv
Saida:    data/cotas.csv

Uso: python3 tools/consolidar_cotas.py > data/cotas.csv
"""
import collections
import csv
import sys

IRRIGAFOUR = "data/cotas_irrigafour.csv"
EQUIPAMENTO = "data/cotas_equipamento.csv"
NETAFIM = "data/cotas_por_familia.csv"

# familia Irrigafour -> [(letra da cota, familia do motor, variante, significado)]
# variante None = usa a variante que veio da pagina (o angulo da curva)
DO_IRRIGAFOUR = {
    "REDUCAO_CONCENTRICA":   [("E", "REDUCAO_CONCENTRICA", "", "face_a_face_mm")],
    "REDUCAO_EXCENTRICA":    [("E", "REDUCAO_EXCENTRICA", "", "face_a_face_mm")],
    "CURVA":                 [("C", "CURVA", None, "perna_mm")],
    "CURVA_SAIDA":           [("C", "CURVA_SAIDA", None, "perna_mm")],
    "CURVA_DUPLA":           [("C", "CURVA_DUPLA", None, "face_a_face_mm")],
    "CRIVO":                 [("C", "CRIVO", "cesto", "comprimento_mm")],
    "TE":                    [("E", "TE", "", "face_a_face_mm"),
                              ("F", "TE", "", "derivacao_mm")],
    "TE_45":                 [("C", "TE_45", "", "face_a_face_mm"),
                              ("D", "TE_45", "", "derivacao_mm")],
    "Y":                     [("E", "Y", "", "face_a_face_mm"),
                              ("F", "Y", "", "derivacao_mm")],
    "Y_45":                  [("C", "Y_45", "", "face_a_face_mm"),
                              ("D", "Y_45", "", "derivacao_mm")],
    "CRUZETA":               [("C", "CRUZETA", "", "face_a_face_mm"),
                              ("D", "CRUZETA", "", "derivacao_mm")],
    "MANIFOLD":              [("C", "MANIFOLD", "", "comprimento_mm")],
    "ARTICULADOR":           [("D_conjunto", "ARTICULADOR", "", "comprimento_mm")],
    "ADAPTADOR_ESPIGAO":     [("C", "ADAPTADOR_ESPIGAO", "", "face_a_face_mm")],
    "PECA_TRANSICAO_NIPLE":  [("C", "PECA_TRANSICAO_NIPLE", "", "face_a_face_mm")],
    "PECA_TRANSICAO_LUVA":   [("C", "PECA_TRANSICAO_LUVA", "", "face_a_face_mm")],
    "ANCORAGEM":             [("C", "ANCORAGEM", "", "comprimento_mm")],
    "ANCORAGEM_MEIA_LUA":    [("C_altura", "ANCORAGEM_MEIA_LUA", "", "altura_mm")],
}
# familia da tabela Netafim -> [(familia do motor, significado)]
DO_NETAFIM = {
    "REDUCAO":  [("REDUCAO_CONCENTRICA", "face_a_face_mm"),
                 ("REDUCAO_EXCENTRICA", "face_a_face_mm")],
    "CURVA":    [("CURVA", "perna_mm")],
    "CRIVO":    [("CRIVO", "comprimento_mm")],
    "MANIFOLD": [("MANIFOLD", "comprimento_mm")],
    "TE":       [("TE", "perna_mm")],
    "ADAPTADOR": [("ADAPTADOR", "face_a_face_mm")],
}
# o caderno Netafim so desenha o crivo conico
VARIANTE_NETAFIM = {"CRIVO": "cone"}
# o angulo sai da variante do catalogo: "90/4gomos" -> "90". Gomo nao muda cota.
def angulo(variante):
    return variante.split("/")[0] if variante else ""


def main():
    linhas = []

    # ---- Irrigafour: cota por (familia, variante, DN maior) e, na reducao,
    # tambem por par de bitolas: a excentrica de 8" mede 200 contra 6" e 300
    # contra 3" - o cone mais fechado precisa de corpo mais longo.
    bruto = collections.defaultdict(list)
    par = {}
    for r in csv.DictReader(open(IRRIGAFOUR, encoding="utf-8")):
        regras = DO_IRRIGAFOUR.get(r["familia"])
        if not regras:
            continue
        for letra, familia, variante, significado in regras:
            if r["cota"] != letra:
                continue
            a, c = float(r["dn_a_pol"]), float(r["dn_c_pol"] or 0)
            dn, menor = max(a, c), min(a, c)
            var = angulo(r["variante"]) if variante is None else variante
            valor = int(r["valor_mm"])
            bruto[("IRRIGAFOUR", familia, var, dn, significado)].append(valor)
            if familia.startswith("REDUCAO") and menor:
                par[("IRRIGAFOUR", familia, var, dn, menor, significado)] = valor
    for (fonte, familia, var, dn, sig), valores in bruto.items():
        valor, _ = collections.Counter(valores).most_common(1)[0]
        linhas.append([fonte, familia, var, f"{dn:g}", "", sig, valor,
                       len(valores), len(set(valores)) - 1])
    for (fonte, familia, var, dn, menor, sig), valor in par.items():
        linhas.append([fonte, familia, var, f"{dn:g}", f"{menor:g}", sig, valor, 1, 0])

    # ---- Netafim: alternativa declarada
    for r in csv.DictReader(open(NETAFIM, encoding="utf-8")):
        for familia, significado in DO_NETAFIM.get(r["familia"], []):
            var = VARIANTE_NETAFIM.get(r["familia"], r["variante"])
            linhas.append(["NETAFIM", familia, var, f"{float(r['dn_pol']):g}", "",
                           significado, f"{float(r['cota_mm']):g}",
                           r["amostras"], r["divergentes"]])

    # ---- equipamento: cada familia tem um fabricante so, entao a fonte e ele
    for r in csv.DictReader(open(EQUIPAMENTO, encoding="utf-8")):
        # cotas.csv guarda so milimetro: peso e bitola de tirante ficam na
        # tabela de equipamento, que e onde a ficha inteira vive
        try:
            float(r["valor_mm"])
        except ValueError:
            continue
        if r["significado"].endswith("_kg"):
            continue
        linhas.append([r["fabricante"], r["familia"], r["variante"], r["dn_pol"],
                       "", r["significado"], r["valor_mm"], 1, 0])

    escritor = csv.writer(sys.stdout)
    escritor.writerow(["fonte", "familia", "variante", "dn_pol", "dn_menor_pol",
                       "significado", "valor_mm", "amostras", "divergentes"])
    escritor.writerows(sorted(linhas, key=lambda l: (l[0], l[1], l[2], float(l[3]),
                                                     float(l[4] or 0))))

    por_fonte = collections.Counter(l[0] for l in linhas)
    print(f"# {len(linhas)} cotas: " +
          ", ".join(f"{k} {v}" for k, v in por_fonte.most_common()), file=sys.stderr)


if __name__ == "__main__":
    main()
