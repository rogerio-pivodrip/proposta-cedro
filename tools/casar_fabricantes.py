#!/usr/bin/env python3
"""Casa as pecas de conexao entre Netafim e Irrigafour.

A furacao das duas bate (tools/conferir_irrigafour.py: 10 de 10 bitolas), entao
toda peca flangeada AZ de uma monta na outra. O que muda e a COTA - e cota
diferente muda o desenho e a cota geral do conjunto, nao a lista.

Vereditos:
  IDENTICA          mesma cota: troca livre, nem o desenho muda
  TROCA_REDESENHA   monta igual, mas a peca tem outro comprimento
  PECA_DIFERENTE    mesmo nome, geometria outra (crivo cone x cesto)
  SO_NETAFIM        so um fornecedor tem
  SO_IRRIGAFOUR     idem, e e onde o Irrigafour cobre lacuna de cadastro

Uso: python3 tools/casar_fabricantes.py > data/depara_fabricantes.csv
"""
import collections
import csv
import json
import sys

COTAS_IRRI = "data/cotas_irrigafour.csv"
COTAS_NETA = "data/cotas_por_familia.csv"
CATALOGO = "data/catalogo.json"
CASA = [3, 4, 5, 6, 8, 10, 12, 14]

# familia Irrigafour -> (familia na tabela Netafim, variante, cota que compara)
PAREADAS = {
    ("REDUCAO_CONCENTRICA", ""): ("REDUCAO", "", "E"),
    ("REDUCAO_EXCENTRICA", ""):  ("REDUCAO", "", "E"),
    ("CURVA", "90/4gomos"):      ("CURVA", "90", "C"),
    ("CURVA", "45/3gomos"):      ("CURVA", "45", "C"),
    ("CRIVO", ""):               ("CRIVO", "", "C"),
    ("TE", ""):                  ("TE", "", "E"),
}
# fator sobre a cota Netafim para chegar a mesma medida do Irrigafour.
# O caderno tabula o raio R de cada perna do te; o corpo corrido e 2R.
FATOR_NETAFIM = {"TE": 2.0}
# o que foi comparado, e sobre que base - conferido no desenho do fabricante
BASE = {
    "REDUCAO_CONCENTRICA": "L do caderno x E do catalogo, os dois face a face "
                           "entre flanges (desenho 01528 e pagina 23)",
    "REDUCAO_EXCENTRICA": "mesma tabela da concentrica nos dois fabricantes",
    "CURVA": "R do caderno x C do catalogo, os dois a perna da curva "
             "(desenho 01523 e pagina 13)",
    "CRIVO": "altura do corpo nos dois",
    "TE": "2R do caderno (corpo corrido) x E do catalogo",
}
# mesmo nome, peca diferente - a comparacao de numero nao quer dizer nada
DIFERENTES = {
    "CRIVO": "Netafim e cone e cresce com a bitola; Irrigafour e cesto "
             "cilindrico de 300mm fixo",
    "TE": "te compacto (2R) contra derivado de corpo corrido de 1m - "
          "nao sao a mesma peca",
}
# familia Irrigafour -> familia do catalogo Netafim, para contar codigos
NO_CATALOGO = {
    "REDUCAO_CONCENTRICA": "REDUCAO_CONCENTRICA",
    "REDUCAO_EXCENTRICA": "REDUCAO_EXCENTRICA",
    "CURVA": "CURVA", "CRIVO": "CRIVO", "TE": "TE",
    "MANIFOLD": "MANIFOLD", "ARTICULADOR": "ARTICULADOR",
    "CRUZETA": None, "Y": None, "Y_45": None, "TE_45": None,
    "CURVA_DUPLA": None, "ANCORAGEM": None, "ANCORAGEM_MEIA_LUA": None,
    "ADAPTADOR_ESPIGAO": "ADAPTADOR", "CURVA_SAIDA": "CURVA",
    "PECA_TRANSICAO_NIPLE": "ADAPTADOR", "PECA_TRANSICAO_LUVA": "LUVA",
}


def dn_maximo(item):
    valores = [d for d in (item.get("dn") or []) if isinstance(d, (int, float))]
    return max(valores) if valores else None


def main():
    irri = list(csv.DictReader(open(COTAS_IRRI, encoding="utf-8")))
    neta = {(r["familia"], r["variante"], float(r["dn_pol"])): float(r["cota_mm"])
            for r in csv.DictReader(open(COTAS_NETA, encoding="utf-8"))}
    catalogo = json.load(open(CATALOGO, encoding="utf-8"))

    codigos = collections.defaultdict(list)
    for item in catalogo:
        dn = dn_maximo(item)
        if item.get("familia") and dn and item.get("material") in (None, "ACO_ZINCADO"):
            codigos[(item["familia"], dn)].append(item["sap"])

    # cota Irrigafour por (familia, variante, dn) - a maior bitola manda
    cota_irri = {}
    for r in irri:
        dn = max(float(r["dn_a_pol"]), float(r["dn_c_pol"] or 0))
        chave = (r["familia"], r["variante"], dn, r["cota"])
        cota_irri.setdefault(chave, set()).add(int(r["valor_mm"]))

    escritor = csv.writer(sys.stdout)
    escritor.writerow(["familia", "variante", "dn_pol", "cota_netafim_mm",
                       "cota_irrigafour_mm", "delta_mm", "codigos_az_netafim",
                       "veredito", "observacao", "base_da_comparacao"])

    vistos, resumo = set(), collections.Counter()
    for (fam_i, var_i), (fam_n, var_n, letra) in PAREADAS.items():
        for dn in CASA:
            valores = cota_irri.get((fam_i, var_i, float(dn), letra))
            cn = neta.get((fam_n, var_n, float(dn)))
            if cn is not None:
                cn *= FATOR_NETAFIM.get(fam_i, 1.0)
            ci = min(valores) if valores else None
            fam_cat = NO_CATALOGO.get(fam_i)
            n_cod = len(codigos.get((fam_cat, dn), [])) if fam_cat else 0

            if fam_i in DIFERENTES and cn and ci:
                veredito, obs, delta = "PECA_DIFERENTE", DIFERENTES[fam_i], ""
            elif cn and ci:
                delta = ci - cn
                veredito = "IDENTICA" if abs(delta) < 1 else "TROCA_REDESENHA"
                obs = "" if veredito == "IDENTICA" else \
                    f"o conjunto muda {delta:+.0f}mm por peca"
                delta = f"{delta:+.0f}"
            elif ci:
                veredito, obs, delta = "SO_IRRIGAFOUR", "sem cota no caderno Netafim", ""
            elif cn:
                veredito, obs, delta = "SO_NETAFIM", "nao ofertada no catalogo", ""
            else:
                continue

            escritor.writerow([fam_i, var_i, dn,
                               f"{cn:g}" if cn else "", f"{ci:g}" if ci else "",
                               delta, n_cod, veredito, obs, BASE.get(fam_i, "")])
            resumo[veredito] += 1
            vistos.add(fam_i)

    # familias que so o Irrigafour tem
    for fam in sorted({r["familia"] for r in irri} - vistos):
        fam_cat = NO_CATALOGO.get(fam)
        bitolas = sorted({max(float(r["dn_a_pol"]), float(r["dn_c_pol"] or 0))
                          for r in irri if r["familia"] == fam})
        na_casa = [b for b in bitolas if 3 <= b <= 14]
        if not na_casa:
            continue
        n_cod = sum(len(codigos.get((fam_cat, b), [])) for b in na_casa) if fam_cat else 0
        escritor.writerow([fam, "", f"{na_casa[0]:g}-{na_casa[-1]:g}", "", "", "",
                           n_cod, "SO_IRRIGAFOUR" if not n_cod else "CONFERIR",
                           f"{len(na_casa)} bitolas na casa"
                           + ("" if n_cod else "; sem familia equivalente no catalogo"),
                           "sem cota tabelada dos dois lados"])
        resumo["SO_IRRIGAFOUR" if not n_cod else "CONFERIR"] += 1

    for k, v in resumo.most_common():
        print(f"# {k}: {v}", file=sys.stderr)


if __name__ == "__main__":
    main()
