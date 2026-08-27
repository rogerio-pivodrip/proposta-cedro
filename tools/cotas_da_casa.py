#!/usr/bin/env python3
"""Le o que foi medido no DXF da casa e transforma em tabela de cota.

O medidor devolve nome e caixa. Aqui o nome e lido: "CURVA 90. SOLDA 225MM
PLASSON/FIP" vira (CURVA, PEAD_SOLDA, DN225, angulo 90), e a caixa vira as
cotas que aquela familia usa. E a unica fonte de cota que cobre PVC, Plasson e
PEAD soldavel - nenhuma tabela de fabricante do motor alcanca essas familias.

Uma coluna diz se a medida e para usar. A casa confia nas medidas do arquivo
com uma excecao declarada: os REGISTROS DE GAVETA podem ter entrado fora de
escala. Eles ficam na tabela com confiavel=0, para nao virarem cota por
distracao - e para nao desaparecerem, que e pior.

Uso: python3 tools/cotas_da_casa.py > data/cotas_casa.csv
"""
import csv
import re
import sys

MEDIDAS = "data/cotas_cad.csv"
FONTE = "DXF da casa"
# A casa confia no arquivo, menos nestes
SUSPEITAS = (re.compile(r"REG\.?\s*GAVETA", re.I),)
# A bomba nao entra: ela tem folha de fabricante, e o DXF dela serve para
# conferir contra a folha (tools/conferir_cad.py), nao para virar cota.
IGNORAR = (re.compile(r"\b(?:METB|METN|KSB)\b", re.I),)

N = r"(\d+(?:[,.]\d+)?)"
POL = r'(\d+(?:\s*\d*/\d+)?)\s*"'
# ordem importa: a primeira regra que casa manda
REGRAS = [
    # familia, significado da largura, significado da altura, regex
    # na curva nem a largura nem a altura sao a perna: o que se mede e o
    # envelope da peca em pe. Para 90 graus os dois valem a perna; para 45 e
    # 60, nao - entao a medida vai com o nome do que ela e.
    ("CURVA", "envelope_x_mm", "envelope_y_mm",
     re.compile(rf"CURVA\s*(?P<ang>\d+)\D*SOLDA\s*{N}\s*MM", re.I)),
    ("CURVA", "envelope_x_mm", "envelope_y_mm",
     re.compile(rf"CURVA\s*(?P<ang>\d+)\s*PVC.*?{N}\s*MM", re.I)),
    ("CURVA", "envelope_x_mm", "envelope_y_mm",
     re.compile(rf"JOELHO.*?(?P<ang>\d+)\s*-\s*{N}\s*MM", re.I)),
    ("ADAPTADOR_FLANGE", "comprimento_mm", "d_externo_mm",
     re.compile(rf"ADAPTADOR\s*P/\s*FL\s*{N}\s*MM", re.I)),
    ("FLANGE", "espessura_mm", "d_externo_mm",
     re.compile(rf"^FL\s*{N}\s*MM", re.I)),
    ("TE_REDUZIDO", "face_a_face_mm", "altura_total_mm",
     re.compile(rf"TE\s*RED.*?{N}\s*X\s*{N}\s*MM", re.I)),
    ("TE", "face_a_face_mm", "altura_total_mm",
     re.compile(rf"TE\s+PVC.*?{N}\s*MM", re.I)),
    ("LUVA_REDUCAO", "comprimento_mm", "d_externo_mm",
     re.compile(rf"LUVA\s*RED.*?{N}\s*X\s*{N}\s*MM", re.I)),
    ("LUVA_CORRER", "comprimento_mm", "d_externo_mm",
     re.compile(rf"LUVA\s*(?:DE\s*)?CORRER.*?{N}\s*MM", re.I)),
    ("LUVA", "comprimento_mm", "d_externo_mm",
     re.compile(rf"LUVA.*?{N}\s*MM", re.I)),
    ("BUCHA_REDUCAO", "comprimento_mm", "d_externo_mm",
     re.compile(rf"BUCHA\s*RED\.?\s*{N}\s*X\s*{N}", re.I)),
    ("ADAPTADOR", "comprimento_mm", "d_externo_mm",
     re.compile(rf"ADAP\.?\s*(?:PVC\s*)?(?:PBS|MACHO|FEMEA)?\s*{N}\s*X\s*{N}",
                re.I)),
    ("ADAPTADOR", "comprimento_mm", "d_externo_mm",
     re.compile(rf"ADAP\.?\s*BS\s*X\s*RM\s*{N}\s*X\s*{POL}", re.I)),
    ("VALVULA_GAVETA", "face_a_face_mm", "altura_total_mm",
     re.compile(rf"REG\.?\s*GAVETA\s*{POL}", re.I)),
    ("VALVULA_HIDRAULICA", "face_a_face_mm", "altura_total_mm",
     re.compile(rf"VALV\.?\s*PLASTICA.*?{N}\s*X", re.I)),
    ("VENTOSA", "largura_mm", "altura_total_mm",
     re.compile(rf"(?:VALV\.?\s*)?(?:VENTOSA|ANTI-VACUO)\D*{POL}", re.I)),
]
RX_POL = re.compile(r'(\d+)(?:\s*(\d+)/(\d+))?')
# A junta faz parte da identidade da peca, nao e detalhe: a curva de 90 de
# DN110 soldavel mede 203 e a de bolsa mede 186. Sao duas pecas. Sem separar,
# as duas caem na mesma chave e a tabela recusa as duas por discordancia.
JUNTAS = ((re.compile(r"SOLDA|SOLDAVEL", re.I), "SOLDA"),
          (re.compile(r"\bCORRER\b", re.I), "CORRER"),
          (re.compile(r"\bR(?:M|F)?\b|ROSCA", re.I), "ROSCA"),
          (re.compile(r"\bPBS\b|\bBS\b|IRRI\s*LF", re.I), "BOLSA"))
COM_JUNTA = {"CURVA", "TE", "TE_REDUZIDO", "LUVA", "LUVA_REDUCAO",
             "ADAPTADOR", "BUCHA_REDUCAO"}


def junta_de(nome):
    for rx, junta in JUNTAS:
        if rx.search(nome):
            return junta
    return ""


def polegada(texto):
    m = RX_POL.match(texto.strip())
    if not m:
        return None
    valor = float(m.group(1))
    if m.group(2):
        valor += float(m.group(2)) / float(m.group(3))
    return valor


def numero(texto):
    return float(texto.replace(",", "."))


def ler(nome):
    """(familia, dn, dn2, variante, unidade, sig_larg, sig_alt) ou None."""
    for familia, sig_l, sig_a, rx in REGRAS:
        m = rx.search(nome)
        if not m:
            continue
        variante = (m.groupdict().get("ang") or "").strip()
        # o grupo nomeado sai da lista de bitolas pelo INDICE dele: "45" de
        # angulo e "45" de bitola sao a mesma string, e comparar por valor
        # fazia o angulo virar DN menor.
        fora = {rx.groupindex[nome] for nome in rx.groupindex}
        grupos = [g for i, g in enumerate(m.groups(), start=1)
                  if g and g.strip() and i not in fora]
        unidade = "in" if '"' in nome and familia in (
            "VALVULA_GAVETA", "VENTOSA") else "mm"
        converter = polegada if unidade == "in" else numero
        dn = converter(grupos[0]) if grupos else None
        dn2 = converter(grupos[1]) if len(grupos) > 1 else None
        if dn is None:
            return None
        if dn2 and dn2 > dn:
            dn, dn2 = dn2, dn
        if familia in COM_JUNTA:
            junta = junta_de(nome)
            variante = f"{variante}/{junta}" if variante else junta
        return familia, dn, dn2, variante, unidade, sig_l, sig_a
    return None


def main():
    campos = ["familia", "dn", "dn_menor", "unidade_dn", "variante",
              "significado", "valor_mm", "confiavel", "nome_no_dxf",
              "arquivo", "fonte"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    lidas = perdidas = 0
    nao_lidos = []
    for linha in csv.DictReader(open(MEDIDAS, encoding="utf-8")):
        nome = linha["nome"]
        if not nome or any(rx.search(nome) for rx in IGNORAR):
            continue
        lido = ler(nome)
        if not lido:
            perdidas += 1
            nao_lidos.append(nome)
            continue
        familia, dn, dn2, variante, unidade, sig_l, sig_a = lido
        confiavel = 0 if any(rx.search(nome) for rx in SUSPEITAS) else 1
        lidas += 1
        for significado, valor in ((sig_l, linha["largura_mm"]),
                                   (sig_a, linha["altura_mm"])):
            if significado is None:
                continue
            escritor.writerow({
                "familia": familia, "dn": f"{dn:g}",
                "dn_menor": f"{dn2:g}" if dn2 else "",
                "unidade_dn": unidade, "variante": variante,
                "significado": significado, "valor_mm": valor,
                "confiavel": confiavel, "nome_no_dxf": nome,
                "arquivo": linha["arquivo"], "fonte": FONTE})
    print(f"# {lidas} pecas lidas, {perdidas} sem regra", file=sys.stderr)
    for nome in nao_lidos[:12]:
        print(f"#   sem regra: {nome[:60]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
