#!/usr/bin/env python3
"""Normaliza descricoes do catalogo em pecas parametricas.

Transforma texto livre ("REDCON AZ 12\" FL NBRPN16X8\" FL NBRPN40") em um
registro estruturado com familia, material, DNs, conexoes e geometria, que e o
que o motor de desenho e o gerador de lista consomem.

Uso: python3 tools/normalizar.py [entrada.json] [saida.json]
"""
import json
import re
import sys
from collections import Counter

PADRAO_ENTRADA = "data/catalogo_bruto.json"
PADRAO_SAIDA = "data/catalogo.json"

# --------------------------------------------------------------------------
# Familias: (regex no inicio da descricao, familia canonica, angulo opcional)
# A ordem importa - o primeiro padrao que casar vence.
# --------------------------------------------------------------------------
FAMILIAS = [
    (r"^TUBO\s?AZ\b|^TUBOAZ\b", "TUBO", None),
    (r"^TUBO\s?INOX\b", "TUBO", None),
    (r"^TUBO\b", "TUBO", None),
    (r"^MNFD\s?AZ\s?D\s?\d+|^MNFDAZ\s?D\s?\d+|^MFD\s?AZ", "MANIFOLD", None),
    (r"^REDCON\b|^RED\s?CON\b|^RC\s+INOX", "REDUCAO_CONCENTRICA", None),
    (r"^REDEXC\b|^RED\s?EXC\b|^RE\s+INOX", "REDUCAO_EXCENTRICA", None),
    (r"^ADAPT\b", "ADAPTADOR", None),
    (r"^CURVA\s?90", "CURVA", 90),
    (r"^CURVA\s?45", "CURVA", 45),
    (r"^CURVA\s?30", "CURVA", 30),
    (r"^CURVA\s?22", "CURVA", 22.5),
    (r"^CURVA\b", "CURVA", None),
    (r"^Y\s?45", "Y", 45),
    (r"^TE\s?RED\b", "TE_REDUZIDO", None),
    (r"^TE\b", "TE", None),
    (r"^FL\s?CEGA\b|^FL\.\s?CEGA\b", "FLANGE_CEGA", None),
    (r"^FLANGE\b|^FL\b|^FL\.", "FLANGE", None),
    (r"^CRIVO\b|^JACOBUCCI\s?CRIVO", "CRIVO", None),
    (r"^ARTICULADOR\b", "ARTICULADOR", None),
    (r"^UNIAO\b", "UNIAO", None),
    (r"^LUVA\b", "LUVA", None),
    (r"^CAP\b|^TAMPAO\b", "CAP", None),
    (r"^JUNTA\s?PLANA\b", "JUNTA_PLANA", None),
    (r"^JUNTA\s?DE\s?EXPANSAO\b", "JUNTA_EXPANSAO", None),
    (r"^JUNTA\s?MEC\b", "JUNTA_MECANICA", None),
    (r"^PARAFUSO\b", "PARAFUSO", None),
    (r"^PORCA\b", "PORCA", None),
    (r"^ARRUELA\b", "ARRUELA", None),
    (r"^NIPLE\b", "NIPLE", None),
    (r"^VALV\.?\s?RETENCAO|^VALVULA\s?RETENCAO", "VALVULA_RETENCAO", None),
    (r"^VALV\.?\s?GAVETA|^REGISTRO\s?GAVETA", "VALVULA_GAVETA", None),
    (r"^VALVULA\s?ANTI-?VACUO|^DOROT\s?ANTIVACUO|^NAVC\s?VENTOSA|^VENTOSA", "VENTOSA", None),
    (r"^MANOVACUOMETRO|^MANOMETRO", "MANOMETRO", None),
]

# Materiais, na ordem de especificidade
MATERIAIS = [
    (r"\bPLASSON\b|\bFIP\b", "PVC_PLASSON"),
    (r"\bINOX\s?30?4?\b|\bINOX\b", "INOX"),
    (r"\bAZ\b|AÇO ZINCADO|\bZB\b", "ACO_ZINCADO"),
    (r"\bPVC\b", "PVC"),
    (r"\bFOFO\b|FERRO FUNDIDO", "FOFO"),
    (r"\bFG\b", "FERRO_GALV"),
    (r"\bBRONZE\b", "BRONZE"),
    (r"\bPEAD\b|\bPE\b", "PEAD"),
]

# Tipos de conexao. tipo = como acopla; norma = furacao/padrao dimensional.
CONEXOES = [
    (r"FL\.?\s?NBR\s?PN\s?(\d+)", "FLANGE", "NBR PN{0}"),
    (r"FL\.?\s?EN\s?PN\s?(\d+)", "FLANGE", "EN PN{0}"),
    (r"FL\.?\s?ANSI\s?(\d+)", "FLANGE", "ANSI {0}"),
    (r"\bANSI\s?(\d+)", "FLANGE", "ANSI {0}"),
    (r"\bNBR\s?PN\s?(\d+)", "FLANGE", "NBR PN{0}"),
    (r"\bEN\s?PN\s?(\d+)", "FLANGE", "EN PN{0}"),
    (r"\bFLK\b", "FLANGE_K", "K"),          # flange + engate rapido K
    (r"\bKFL\b", "FLANGE_K", "K"),
    (r"\bK\s?(\d+)\b", "ENGATE_K", "K{0}"),  # engate rapido Netafim K6/K8/K10/K12
    (r"\bRANHURA\b|\bVICTAULIC\b", "RANHURADA", "RANHURA"),
    (r"\bRM\b", "ROSCA_MACHO", "BSP"),
    (r"\bRF\b", "ROSCA_FEMEA", "BSP"),
    (r"\bSOLDA\w*\b|\bSOLDAVEL\b", "SOLDA", "PVC SOLDAVEL"),
    (r"\bPL\b|PONTA LISA", "PONTA_LISA", None),
    (r"\bFL\b|\bFLANGE\b", "FLANGE", None),  # flange sem norma explicita
]

# Derivacoes auxiliares: LG 2" = luva galvanizada, LV = luva, L2 = luva 2"
RX_DERIV = re.compile(r"\b(?:C/\s*)?(\d)?\s*(LG|LV|L)\s*(\d+(?:\s?\d/\d)?)\s*\"?", re.I)
RX_DN = re.compile(r"(\d+\s?\d/\d|\d+(?:[.,]\d+)?)\s*\"")
RX_DN_MM = re.compile(r"\b(\d{2,3})\s*MM\b|\((\d{2,3})\)|\b(\d{2,3})\s*(?:PLASSON|$)")
RX_MNFD = re.compile(r"\bD\s?(\d{2})\b")
RX_GEOM = re.compile(
    r"(\d+\s?\d/\d|\d+)\s*\"?\s*X\s*([\d,.]+)\s*(?:MM)?\s*X\s*([\d,.]+)\s*(MM|M)\b"
)


def para_float(txt):
    """Converte '2,65', '1 1/2', '11/2' em float."""
    txt = txt.strip()
    m = re.fullmatch(r"(\d+)\s?(\d)/(\d)", txt)
    if m:  # 11/2 -> 1 1/2 -> 1.5
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    m = re.fullmatch(r"(\d)/(\d)", txt)
    if m:
        return int(m.group(1)) / int(m.group(2))
    return float(txt.replace(",", "."))


def detectar(regras, texto):
    for padrao, *resto in regras:
        if re.search(padrao, texto):
            return resto
    return None


def extrair_conexoes(texto, dns):
    """Associa cada token de conexao ao DN mais proximo a esquerda."""
    achados = []
    for padrao, tipo, molde in CONEXOES:
        for m in re.finditer(padrao, texto):
            norma = None
            if molde:
                norma = molde.format(*m.groups()) if m.groups() and m.group(1) else molde
                norma = norma.replace("{0}", "")
            achados.append({"pos": m.start(), "fim": m.end(), "tipo": tipo,
                            "norma": norma})
    # o primeiro padrao da lista e o mais especifico ("FL NBR PN16" antes de
    # "NBR PN16"); mantendo essa ordem e descartando qualquer casamento que
    # sobreponha um ja aceito, cada trecho do texto vira uma unica conexao.
    limpos = []
    for a in achados:
        if any(a["pos"] < b["fim"] and b["pos"] < a["fim"] for b in limpos):
            continue
        limpos.append(a)
    limpos.sort(key=lambda a: a["pos"])
    conexoes = []
    for a in limpos:
        dn = None
        for valor, pos in dns:
            if pos <= a["pos"]:
                dn = valor
            else:
                break
        conexoes.append({"dn": dn, "tipo": a["tipo"], "norma": a["norma"]})
    return conexoes


def normalizar_item(item):
    desc = item["descricao"].upper().replace("\xa0", " ")
    peca = dict(item)
    peca["familia"] = None
    peca["material"] = None
    peca["dn"] = []
    peca["unidade_dn"] = None
    peca["angulo"] = None
    peca["espessura_mm"] = None
    peca["comprimento_mm"] = None
    peca["conexoes"] = []
    peca["derivacoes"] = []
    peca["manifold"] = None
    peca["confianca"] = 0.0

    fam = detectar(FAMILIAS, desc)
    if fam:
        peca["familia"], peca["angulo"] = fam[0], fam[1]
    mat = detectar(MATERIAIS, desc)
    if mat:
        peca["material"] = mat[0]

    if peca["familia"] == "MANIFOLD":
        m = RX_MNFD.search(desc)
        if m:
            peca["manifold"] = "D" + m.group(1)

    # angulo explicito quando nao veio do prefixo
    if peca["angulo"] is None:
        m = re.search(r"\b(90|45|30|22,5|22)\s*[°º.]", desc)
        if m:
            peca["angulo"] = para_float(m.group(1))

    # DNs em polegada (com posicao) - base para associar conexoes
    dns_pos = [(para_float(m.group(1)), m.start()) for m in RX_DN.finditer(desc)]
    if dns_pos:
        peca["unidade_dn"] = "in"
        peca["dn"] = [d for d, _ in dns_pos]
    else:
        mm = [int(g) for m in RX_DN_MM.finditer(desc) for g in m.groups() if g]
        if mm:
            peca["unidade_dn"] = "mm"
            peca["dn"] = mm
            dns_pos = [(v, 0) for v in mm]

    # geometria de tubo/manifold: DN x espessura x comprimento
    g = RX_GEOM.search(desc)
    if g:
        peca["espessura_mm"] = para_float(g.group(2))
        comp = para_float(g.group(3))
        peca["comprimento_mm"] = comp if g.group(4) == "MM" else comp * 1000
    elif peca["familia"] == "TUBO":
        m = re.search(r"-(\d+)M\b", desc)
        if m:
            peca["comprimento_mm"] = int(m.group(1)) * 1000

    peca["conexoes"] = extrair_conexoes(desc, dns_pos)

    for m in RX_DERIV.finditer(desc):
        peca["derivacoes"].append(
            {"qtd": int(m.group(1) or 1), "dn": para_float(m.group(3)), "tipo": "LUVA"}
        )

    # confianca: quanto do registro ficou preenchido
    pontos = sum(
        [
            2 if peca["familia"] else 0,
            1 if peca["material"] else 0,
            2 if peca["dn"] else 0,
            2 if peca["conexoes"] else 0,
        ]
    )
    peca["confianca"] = round(pontos / 7, 2)
    return peca


def main():
    entrada = sys.argv[1] if len(sys.argv) > 1 else PADRAO_ENTRADA
    saida = sys.argv[2] if len(sys.argv) > 2 else PADRAO_SAIDA
    with open(entrada, encoding="utf-8") as fh:
        itens = json.load(fh)
    pecas = [normalizar_item(i) for i in itens]
    with open(saida, "w", encoding="utf-8") as fh:
        json.dump(pecas, fh, ensure_ascii=False, indent=1)

    alvo = [p for p in pecas if p["grupo"] in ("AÇO ZINCADO", "PVC (CONEXÃO E TUBO IMPORTADO)")]
    fam = Counter(p["familia"] for p in alvo)
    print(f"{len(pecas)} pecas -> {saida}")
    print(f"escopo succao/recalque: {len(alvo)} itens")
    print(f"  com familia:  {sum(1 for p in alvo if p['familia']):4d}")
    print(f"  com DN:       {sum(1 for p in alvo if p['dn']):4d}")
    print(f"  com conexoes: {sum(1 for p in alvo if p['conexoes']):4d}")
    print("  familias:", ", ".join(f"{k or 'SEM'}={v}" for k, v in fam.most_common(12)))


if __name__ == "__main__":
    main()
