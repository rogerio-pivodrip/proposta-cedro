#!/usr/bin/env python3
"""Normaliza descricoes do catalogo em pecas parametricas.

Transforma texto livre ("REDCON AZ 12\" FL NBRPN16X8\" FL NBRPN40") em um
registro estruturado com familia, material, DNs, conexoes e geometria, que e o
que o motor de desenho e o gerador de lista consomem.

Uso: python3 tools/normalizar.py [entrada.json] [saida.json]
"""
import json
import os
import re
import sys
import unicodedata
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor import manifold  # noqa: E402

PADRAO_ENTRADA = "data/catalogo_bruto.json"
PADRAO_SAIDA = "data/catalogo.json"

# --------------------------------------------------------------------------
# Familias: (regex no inicio da descricao, familia canonica, angulo opcional)
# A ordem importa - o primeiro padrao que casar vence.
# --------------------------------------------------------------------------
FAMILIAS = [
    (r"^TUBO\s?AZ\b|^TUBOAZ\b|^TUBO\s?INOX\b|^TUBO\b", "TUBO", None),
    (r"^MNFD\s?AZ\s?D\s?\d+|^MNFDAZ\s?D\s?\d+|^MFD\s?AZ", "MANIFOLD", None),
    (r"^REDCON\b|^RED\s?CON\b|^RC\s+INOX", "REDUCAO_CONCENTRICA", None),
    (r"^REDEXC\b|^RED\s?EXC\b|^RE\s+INOX", "REDUCAO_EXCENTRICA", None),
    (r"^BUCHA\s?RED", "BUCHA_REDUCAO", None),
    (r"^ADAPT", "ADAPTADOR", None),
    (r"^CURVA\s?90", "CURVA", 90),
    (r"^CURVA\s?45", "CURVA", 45),
    (r"^CURVA\s?30", "CURVA", 30),
    (r"^CURVA\s?22", "CURVA", 22.5),
    (r"^CURVA\b|^COTOVELO\b|^JOELHO\b", "CURVA", None),
    (r"^Y\s?45", "Y", 45),
    (r"^TE\s?RED\b", "TE_REDUZIDO", None),
    (r"^TE\b", "TE", None),
    (r"^FL\s?CEGA\b|^FL\.\s?CEGA\b", "FLANGE_CEGA", None),
    (r"^FLANGE\b|^FL\b|^FL\.", "FLANGE", None),
    (r"^CRIVO\b|^JACOBUCCI\s?CRIVO", "CRIVO", None),
    (r"^ARTICULADOR\b", "ARTICULADOR", None),
    (r"^FLUTUADOR\b|^FLUTUANTE\b", "FLUTUADOR", None),
    (r"^UNIAO\b", "UNIAO", None),
    (r"^LUVA\b", "LUVA", None),
    (r"^CAP\b|^TAMPAO\b", "CAP", None),
    (r"^COLAR\.?\s?P/\s?FL\b.*PEAD|^COLAR\.?\s?P/\s?\s?FL\b", "COLAR_PEAD", None),
    (r"^COLAR\s?TOMADA\b|^COLAR\b", "COLAR_TOMADA", None),
    (r"^JUNTA\s?PLANA\b", "JUNTA_PLANA", None),
    (r"^JUNTA\s?DE\s?EXPANSAO\b", "JUNTA_EXPANSAO", None),
    (r"^JUNTA\s?MEC\b", "JUNTA_MECANICA", None),
    (r"^PARAFUSO\b", "PARAFUSO", None),
    (r"^PORCA\b", "PORCA", None),
    (r"^ARRUELA\b", "ARRUELA", None),
    (r"^BARRA\s?ROSC", "BARRA_ROSCADA", None),
    (r"^NIPLE\b|^NIPEL\b", "NIPLE", None),
    (r"VALV\w*\s*(?:DE\s*)?RETENCAO|VALV\.?\s*RETENCAO|\bUNIFLAP\b", "VALVULA_RETENCAO", None),
    (r"VALV\w*\s*(?:DE\s*)?PE\b", "VALVULA_PE", None),
    # "VALV.BORB. ... CX.-DN 8"" e borboleta com caixa redutora - o ponto da
    # abreviacao deixava 35 itens invisiveis.
    (r"VALV\w*\.?\s*BORBOLETA|VALV\.?\s*BORB\.?|^BORBOLETA\b",
     "VALVULA_BORBOLETA", None),
    # "REG. GAVETA" e "VALV. GAVETA" - o ponto da abreviacao ficava de fora, e
    # era por isso que a gaveta flangeada da GAER nao entrava.
    (r"VALV\w*\.?\s*GAVETA|REG(?:ISTRO|\.)?\s*GAVETA", "VALVULA_GAVETA", None),


    # Ordem importa: ventosa e alivio ganham da hidraulica, senao uma
    # "BERMAD VALV AR ANTIVACUO" seria lida como valvula de controle.
    (r"ANTI-?VACUO|\bVENTOSA\b|\bVALV\w*\s*(?:DE\s*)?AR\b", "VENTOSA", None),
    (r"\bALIVIO\b", "VALVULA_ALIVIO", None),
    # Peca de reposicao de valvula ou piloto - nao e a valvula.
    (r"\b(MOLA|ASSENTO|TACA|BOIA|REPARO|DIAFRAGMA|HASTE|PISTAO|LACRE|"
     r"TURBINA|SUP\.?\s?P/\s?PILOTO)\b.*\b(DOROT|BERMAD|PILOTO|VALV)"
     r"|\b(DOROT|BERMAD)\b.*\b(MOLA|ASSENTO|TACA|BOIA|REPARO|DIAFRAGMA|"
     r"HASTE|PISTAO|LACRE|TURBINA)\b", "PECA_REPOSICAO", None),
    (r"\bPILOTO\b|\bPILOT\b", "PILOTO", None),
    # Corpo de valvula de controle hidraulico: marca + VALV + serie
    (r"VALV\w*\s*HIDRAULICA"
     r"|\b(?:DOROT|BERMAD)\b.*\bVALV\w*\b.*\b\d{2,3}\s?[-/]?\s?\w"
     r"|\bVALV\w*\b.*\b(?:DOROT|BERMAD)\b", "VALVULA_HIDRAULICA", None),
    (r"^MANOVACUOMETRO|^MANOMETRO", "MANOMETRO", None),
    (r"^FILTRO\b|\bESPELHO\b|^ALPHADISC|^ARKAL|^SANDSTORM", "FILTRO", None),
    (r"^RETROLAVAGEM\b", "RETROLAVAGEM", None),
    (r"MEDIDOR\s*(?:DE\s*)?AGUA|^HIDROMETRO|^HYDROMETRO", "MEDIDOR", None),
    (r"^EXTREMIDADE\b", "EXTREMIDADE", None),
    (r"^CASA\s?DE\s?MAQUINAS", "CASA_MAQUINAS", None),
    (r"^CHAVE\s?DE\s?PARTIDA|^QUADRO\b|^SOFT\s?START|^INVERSOR\b", "QUADRO", None),
    (r"^MOTOBOMBA\b|^BOMBA\b|^METB\b|^ETB\b|^KSB\b", "BOMBA", None),
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
    (r"\bPEAD\b|\bPE\s?100\b|^TUBO\s?PE\b", "PEAD"),
]

# Tipos de conexao. tipo = como acopla; norma = furacao/padrao dimensional.
CONEXOES = [
    # NBR 7675 e a norma dos flanges: "FL NBR7675 PN16" e o mesmo que
    # "FL NBR PN16", so escrito com o numero da norma.
    (r"FL\.?\s?NBR\s?7675\s?PN\s?(\d+)", "FLANGE", "NBR PN{0}"),
    (r"\bNBR\s?7675\s?PN\s?(\d+)", "FLANGE", "NBR PN{0}"),
    (r"FL\.?\s?ABNT\s?PN\s?(\d+)|FL\.?\s?ABNT\s?(\d+)", "FLANGE", "NBR PN{0}"),
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
# "C/ESC.2"" e o escape de 2 polegadas da curva, por onde entra a ventosa
RX_SERIE = re.compile(r"\b(\d{2,3})[A-Z]?\s?-\s?\d{1,2}(?:[.,]\d)?\s?[\"']")
RX_ESCAPE = re.compile(r"C/\s*ESC\.?\s*(\d+(?:\s?\d/\d)?)\s*\"?", re.I)
# O lookbehind impede ler o denominador de uma fracao como diametro: em
# 'QC 3/4"' o que vale e 3/4, nao 4.
RX_DN = re.compile(
    r"(?<![\d/])(\d+\s?\d/\d|\d+/\d+|\d+(?:[.,]\d+)?)\s*\"")
RX_DN_MM = re.compile(
    r"\b(\d{2,3})\s*MM(?:\b|(?=X))|\((\d{2,3})\)|\b(\d{2,3})\s*(?:PLASSON|$)"
    r"|\b(\d{2,3})M(?=X)|X\s?(\d{2,3})F\b|\bDN\s?(\d{2,3})\b")
# Serie comercial de PVC/PEAD/Plasson em mm. Um numero solto so vira DN se for
# um desses - evita ler "CL 10" ou "PN 10" como diametro.
SERIE_MM = {20, 25, 32, 40, 50, 63, 75, 90, 100, 110, 125, 140, 160, 180, 200,
            225, 250, 280, 300, 315, 350, 355, 400, 450, 500, 600}
RX_PAR_MM = re.compile(r"\b(\d{2,3})\s*X\s*(\d{2,3})\s*MM\b")
RX_GSD = re.compile(r"\bGSD\s+(\d{2,3}-\d{3}[A-Z]?(?:\.\d)?)\b", re.I)
RX_MNFD = re.compile(r"\bD\s?(\d{2})\b")
RX_GEOM = re.compile(
    r"(\d+\s?\d/\d|\d+)\s*\"?\s*X\s*([\d,.]+)\s*(?:MM)?\s*X\s*([\d,.]+)\s*(MM|M)\b"
)


def sem_acento(txt):
    """'Retenção' -> 'RETENCAO'. As descricoes do CAD vem acentuadas, as do SAP nao."""
    # NFD, nao NFKD: NFKD transformaria o grau ordinal de "90º" em "90o"
    normal = unicodedata.normalize("NFD", txt)
    return "".join(c for c in normal if not unicodedata.combining(c))


def para_float(txt):
    """Converte '2,65', '1 1/2', '11/2' em float."""
    txt = txt.strip()
    m = re.fullmatch(r"(\d+)\s?(\d)/(\d)", txt)
    if m:  # 11/2 -> 1 1/2 -> 1.5
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    m = re.fullmatch(r"(\d+)/(\d+)", txt)   # 3/4, 9/16, 15/16
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
    """Aceita um registro do catalogo ou uma descricao solta (nome de peca do CAD)."""
    if isinstance(item, str):
        item = {"sap": None, "descricao": item, "un": None, "grupo": None,
                "procedencia": None}
    desc = sem_acento(item["descricao"]).upper().replace("\xa0", " ")
    # O CAD escreve 1.1/4" e as vezes a barra vira ponto: 1".1.4". Normaliza as
    # duas formas para "1 1/4" antes de qualquer leitura de diametro.
    desc = re.sub(r'(\d)"?\.(\d)[./](\d)"', r'\1 \2/\3"', desc)
    desc = re.sub(r'(\d)\.(\d)/(\d)', r'\1 \2/\3', desc)
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
    peca["bocais"] = []
    peca["luvas"] = []
    peca["manifold"] = None
    peca["saida_pol"] = None
    peca["acionamento"] = None
    peca["serie"] = None
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
        if not mm and peca["material"] in ("PVC", "PVC_PLASSON", "PEAD"):
            mm = [int(t) for t in re.findall(r"\b(\d{2,3})\b", desc)
                  if int(t) in SERIE_MM]
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
        # '-6M', '-1.00m', '- 0,50 M' -> milimetros
        m = re.search(r"[-\s](\d+(?:[.,]\d+)?)\s*M\b", desc)
        if m:
            peca["comprimento_mm"] = round(para_float(m.group(1)) * 1000)

    # Par em milimetro com a unidade dita uma vez so no fim: 'BUCHA RED CURTA
    # PVC S 32 X 25 MM' sao duas bitolas, 32 e 25, e nao so a 25. Sem isto a
    # reducao perde a bitola maior - que e justamente a que da o tamanho dela.
    if peca["unidade_dn"] == "mm":
        m = RX_PAR_MM.search(desc)
        if m:
            peca["dn"] = [int(m.group(1)), int(m.group(2))]
            dns_pos = [(v, m.start()) for v in peca["dn"]]

    # A GSD da EBARA e bomba, e a lista nao diz "bomba" no nome dela: diz
    # "EBARA GSD 125-200 30CV". Sem esta regra as 14 GSD do catalogo ficam sem
    # familia e nao desenham.
    m = RX_GSD.search(desc)
    if m:
        peca["familia"] = "BOMBA"
        peca["serie"] = "GSD"
        peca["manifold"] = None
        peca["dn"] = []
        peca["unidade_dn"] = None

    # Colar de tomada: '160X2"' e '125 X 2"' sao tubo em milimetro e saida em
    # polegada. Sem isso o 160 se perde e o colar fica sem diametro de tubo.
    if peca["familia"] == "COLAR_TOMADA":
        # "326MM X", "326M X" e "326 X" - a lista escreve dos tres jeitos
        m = re.search(r"(\d{2,3})\s*M?M?\s*X\s*(\d+(?:\s?\d/\d)?)\s*\"",
                      desc)
        if m:
            peca["dn"] = [int(m.group(1))]
            peca["unidade_dn"] = "mm"
            peca["saida_pol"] = para_float(m.group(2))

    # Alavanca ou volante: a casa prefere alavanca na borboleta.
    if re.search(r"ALAVANCA", desc):
        peca["acionamento"] = "ALAVANCA"
    elif re.search(r"VOLANTE", desc):
        peca["acionamento"] = "VOLANTE"
    elif re.search(r"\bCX\.?\b|CAIXA\s?RED|REDUTOR", desc):
        peca["acionamento"] = "CAIXA"      # caixa redutora, o "gear"
    elif re.search(r"CABECOTE", desc):
        peca["acionamento"] = "CABECOTE"

    # Serie da valvula hidraulica: o "47" de "DOROT VALV MET 47-8" BASICA".
    # E parametro, nao nome - a cota do corpo sai da serie, nao do codigo.
    if peca["familia"] in ("VALVULA_HIDRAULICA", "PECA_REPOSICAO", "PILOTO"):
        m = RX_SERIE.search(desc)
        if m:
            peca["serie"] = m.group(1)

    peca["conexoes"] = extrair_conexoes(desc, dns_pos)

    # O manifold e a peca com mais variacao de FORMA e nenhuma cota nova: o
    # que muda e o que ha em cima dele, e isso esta escrito no nome. Ver
    # motor/manifold.py - sem isto o desenho teria de inventar quantos bocais
    # existem, que foi o erro que a casa apontou
    if peca["familia"] == "MANIFOLD":
        peca["bocais"], peca["luvas"] = manifold.topologia(desc)

    for m in RX_ESCAPE.finditer(desc):
        peca["derivacoes"].append(
            {"qtd": 1, "dn": para_float(m.group(1)), "tipo": "ESCAPE"})
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
