"""A classe de pressao da peca, lida da descricao - e o que ela quer dizer.

**O mesmo "PN" quer dizer tres coisas nesta lista**, e por isso ele nao pode
ser lido como numero solto:

    aco e PEAD      PN 16   = 16 bar          (NBR / EN 1092)
    plastico de     PN 80   = 80 mca ~ 8 bar  (a classe brasileira de
    irrigacao                                  irrigacao e em metro de
                                               coluna d'agua)
    PVC-U de ISO    PN 10   = 10 bar          (ISO 1452 / ISO 2536 - o
                                               MESMO material, outra escala)
    aco americano   150 LB  = classe 150      (ASME B16.5 - nao e bar)

Ler "PN 80" de um tubo de PVC como 80 bar seria dar a ele cinco vezes a
pressao que ele aguenta. E a armadilha vizinha ja estava documentada: no PEAD
o `PE80` e a RESINA, e nao a pressao - por isso este arquivo so aceita o
prefixo PN, nunca PE.

**Classe de familias diferentes nao se compara por conta propria.** PN e bar,
LB e classe ASME, e a equivalencia entre as duas depende de material e
temperatura - esta na folha do fabricante, e nao aqui. Quando as duas pontas
falam linguas diferentes, o programa diz isso e manda conferir, em vez de
inventar um numero que pareceria resposta.
"""
import re

# Nos plasticos as duas escalas convivem, e o material sozinho nao separa: a
# lista tem "TUBO IRRIGA PVC 100 DEFOFO JEI PN125" (125 mca = 12,3 bar, linha
# brasileira) e "FL PVC 110MM ISO 2536 PN16" (16 bar, linha ISO), o mesmo PVC
# nas duas. Quem separa e a serie de numeros, e ela nao se sobrepoe: em bar o
# plastico vai ate PN 25 (6, 8, 10, 12,5, 16, 20, 25) e a linha em mca comeca
# em PN 40 (40, 60, 80, 125, 145, 160, 180). Ler um PN 16 de ISO como mca
# daria 1,6 bar a uma flange de 16 - dez vezes menos do que ela vale, e a peca
# seria trocada por engano.
#
# No aco isto NAO vale: PN 40 de aco e 40 bar de verdade (NBR 7675 vai ate
# PN 40, a EN 1092 vai muito acima), e aplicar a regra ali rebaixaria uma
# flange boa a 3,9 bar.
# Em bar so existem estas classes - sao as da NBR 7675 e da EN 1092, e nao ha
# outras. Um PN 60, 80, 125, 145, 160 ou 180 nao e classe de bar de norma
# nenhuma: e mca, venha de que material vier. Por isso o material so precisa
# decidir na FAIXA EM QUE AS DUAS SERIES SE CRUZAM - o PN 40, que e 40 bar no
# aco e 4 bar (40 mca) no plastico de irrigacao. Foi o que salvou as luvas
# "IRR JIR PN125" e os tubos "PRFV PN160", que a lista escreve sem dizer de
# que material sao: pelo numero ja se sabe que a escala e mca.
PN_EM_BAR = (4, 6, 8, 10, 12.5, 16, 20, 25, 40, 63, 100)
MAIOR_PN_SO_EM_BAR = 25
EM_MCA = ("PVC", "PVC_PLASSON", "PVC_O", "CPVC", "PEAD")
MCA_POR_BAR = 10.197

# Classe ASME so existe nesta serie. Sem isto o "140LB" de um pressostato de
# compressor de ar (que e libra por polegada quadrada, e nem peca de linha e)
# entrava na lista como se fosse classe de flange.
CLASSES_ASME = (125, 150, 250, 300, 400, 600, 900, 1500, 2500)

RX_PN = re.compile(r"\bPN\s?(\d{1,3})(?:[,.](\d))?\b")
RX_LB = re.compile(r"\b(\d{3})\s?LBS?\b|\bANSI\s?(\d{3})\b|\bASME\s?(\d{3})\b")
RX_CL = re.compile(r"\bCL(?:ASSE)?\s?(\d{3})\b")


def _em_mca(valor, material):
    """Se este PN esta escrito em metro de coluna d'agua, e nao em bar."""
    if valor <= MAIOR_PN_SO_EM_BAR:
        return False          # 6, 10, 16, 25: bar em qualquer material
    if valor not in PN_EM_BAR:
        return True           # 60, 80, 125, 145, 160, 180: so existem em mca
    return (material or "").upper() in EM_MCA   # 40, 63, 100: o material diz


def da_descricao(descricao, material=None):
    """A classe desta peca, ou None quando a descricao nao declara.

    Devolve familia ("PN" ou "ASME"), o valor como esta escrito, o
    equivalente em bar quando ele existe, e o rotulo para mostrar.
    """
    texto = (descricao or "").upper()
    for rx in (RX_LB, RX_CL):
        for achado in rx.finditer(texto):
            valor = float(next(g for g in achado.groups() if g))
            if int(valor) not in CLASSES_ASME:
                continue
            return {"familia": "ASME", "valor": valor, "bar": None,
                    "rotulo": f"classe {valor:.0f}"}
    achado = RX_PN.search(texto)
    if achado:
        inteiro, decimo = achado.group(1), achado.group(2)
        valor = float(inteiro) + (float(decimo) / 10 if decimo else 0.0)
        if _em_mca(valor, material):
            return {"familia": "PN", "valor": valor,
                    "bar": round(valor / MCA_POR_BAR, 1),
                    "rotulo": f"PN {valor:g} ({valor / MCA_POR_BAR:.1f} bar)"}
        return {"familia": "PN", "valor": valor, "bar": valor,
                "rotulo": f"PN {valor:g}"}
    return None


def da_norma(norma):
    """A classe embutida no nome da norma da flange: NBR PN16, ANSI 150."""
    return da_descricao(norma or "")


def comparar(peca, linha):
    """Como a classe da PECA se compara com a da LINHA. (veredito, frase)

    veredito: "igual" | "acima" | "abaixo" | "outra familia" | None
    """
    if not peca or not linha:
        return None, ""
    if peca["familia"] != linha["familia"]:
        return ("outra familia",
                f'{peca["rotulo"]} contra {linha["rotulo"]} - classes de '
                f"normas diferentes, e a equivalência depende do material e "
                f"da temperatura: conferir na folha")
    if abs(peca["valor"] - linha["valor"]) < 0.05:
        return "igual", ""
    if peca["valor"] < linha["valor"]:
        return ("abaixo",
                f'{peca["rotulo"]} numa linha {linha["rotulo"]} - a peça '
                f"aguenta MENOS que a linha")
    return ("acima",
            f'{peca["rotulo"]} numa linha {linha["rotulo"]} - a peça é mais '
            f"pesada que a linha pede")


def todas_da_descricao(descricao, material=None):
    """Todas as classes que a descricao declara, na ordem em que aparecem.

    Uma peca de duas faces declara duas: 'ADAPT AZ 6" FL NBR PN16 X 6" FL NBR
    PN25' e PN16 de um lado e PN25 do outro. Um tubo de PEAD flangeado tambem:
    'TUBO PE100 PN10 110MM ... FL PN16' - PN10 e o corpo, PN16 e a flange.
    """
    texto = (descricao or "").upper()
    achados = []
    for rx in (RX_LB, RX_CL, RX_PN):
        for m in rx.finditer(texto):
            classe = da_descricao(m.group(0), material)
            if classe:
                achados.append((m.start(), classe))
    achados.sort(key=lambda par: par[0])
    saida = []
    for _, classe in achados:
        if not any(c["familia"] == classe["familia"]
                   and abs(c["valor"] - classe["valor"]) < 0.05 for c in saida):
            saida.append(classe)
    return saida


def da_peca(descricao, material=None):
    """A classe que vale para a PECA inteira - a menor que ela declara.

    Quem manda no que a peca aguenta e a face mais fraca: um tubo de PEAD PN10
    com flange PN16 nas pontas continua sendo um tubo de 10 bar. Quando as
    classes declaradas sao de familias diferentes (PN de um lado, ASME do
    outro) nao ha menor que se possa apontar sem arbitrar equivalencia, e a
    peca fica sem classe unica - cada boca responde pela norma dela.
    """
    achados = todas_da_descricao(descricao, material)
    if not achados:
        return None
    if len({c["familia"] for c in achados}) > 1:
        return None
    return min(achados, key=lambda c: c["valor"])


# Pecas que nao conduzem pressao - elas APERTAM a peca que conduz. A classe
# delas ser mais alta que a do tubo e o par normal, e nao um conflito.
SO_APERTAM = ("FLANGE", "COLAR_PEAD", "JUNTA_PLANA", "COLAR_TOMADA")


def na_juncao(a, b):
    """As duas classes que se encontram numa junta. (veredito, frase)

    A junta nao vale a media nem a maior: vale a MENOR das duas. Um tubo de
    PN 10 aparafusado numa linha de PN 16 nao vira PN 16 por estar preso nela
    - a linha inteira passa a valer 10 bar naquele ponto, e quem dimensionou
    para 16 nao sabe disso. Por isso a frase diz o numero que sobrou.

    veredito: "igual" | "menor" | "outra familia" | None
    """
    if not a or not b:
        return None, ""       # sem as duas nao ha o que comparar, e chutar
                              # seria pior que calar
    if a["familia"] != b["familia"]:
        return ("outra familia",
                f'{a["rotulo"]} contra {b["rotulo"]} - classes de normas '
                f"diferentes, e a equivalência depende do material e da "
                f"temperatura: conferir na folha")
    if abs(a["valor"] - b["valor"]) < 0.05:
        return "igual", ""
    fraca = a if a["valor"] < b["valor"] else b
    return ("menor",
            f'{a["rotulo"]} contra {b["rotulo"]} - a junta só vale a menor '
            f'das duas: {fraca["rotulo"]}')
