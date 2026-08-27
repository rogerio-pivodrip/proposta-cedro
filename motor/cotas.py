"""Quanto uma peca mede - a unica porta por onde o motor pergunta isso.

A cota nao esta no codigo SAP: esta numa tabela por (fabricante, familia,
variante, bitola). A casa compra dos dois fornecedores e a furacao dos dois
bate, entao qualquer peca de um monta na outra - mas nenhuma tem a mesma cota,
e cota diferente muda o desenho. Por isso o fabricante e parametro, com um
padrao declarado.

  cota("REDUCAO_CONCENTRICA", 8)              -> 150.0   (Irrigafour, o padrao)
  cota("REDUCAO_CONCENTRICA", 8, fonte="NETAFIM") -> 300.0
  cota("CURVA", 8, variante="90", significado="perna_mm") -> 335.0
"""
import csv
import os

PADRAO = "IRRIGAFOUR"
# Conexao vem do Irrigafour; equipamento vem de quem a casa ja compra.
# A MP Valvulas ja fornece a gaveta e a retencao (fichas 153, 160 e 162), entao
# a borboleta dela e a escolha coerente - a Saint-Gobain fica como alternativa.
PREFERIDA_POR_FAMILIA = {
    "VALVULA_BORBOLETA": "MP",
    "VALVULA_GAVETA": "MP",
    "VALVULA_RETENCAO": "MP",
    "VALVULA_PE": "MP",
    "VALVULA_HIDRAULICA": "DOROT",
    "MEDIDOR": "ARAD",
}
TABELA = os.path.join(os.path.dirname(__file__), "..", "data", "cotas.csv")
# A cota do PVC, do Plasson e do PEAD soldavel nao esta em folha de fabricante
# nenhuma - esta medida no DXF da casa. Fica numa tabela separada porque a
# chave e outra: DN em milimetro, que no PVC e no PEAD E o diametro externo.
TABELA_CASA = os.path.join(os.path.dirname(__file__), "..", "data",
                           "cotas_casa.csv")

_indice = None
_casa = None


def _carregar():
    global _indice
    if _indice is not None:
        return _indice
    _indice = {}
    with open(TABELA, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            chave = (r["fonte"], r["familia"], r["variante"],
                     float(r["dn_pol"]),
                     float(r["dn_menor_pol"]) if r["dn_menor_pol"] else None,
                     r["significado"])
            _indice[chave] = float(r["valor_mm"])
    return _indice


def fontes():
    return sorted({k[0] for k in _carregar()})


def _carregar_casa():
    global _casa
    if _casa is not None:
        return _casa
    # A mesma peca aparece mais de uma vez nos arquivos, e as vezes com uma
    # leitura fora da serie - o rotulo de uma vizinha que grudou na peca
    # errada. A mediana descarta a leitura solitaria sem descartar a peca.
    bruto = {}
    for r in csv.DictReader(open(TABELA_CASA, encoding="utf-8")):
        chave = (r["familia"], r["variante"], float(r["dn"]),
                 float(r["dn_menor"]) if r["dn_menor"] else None,
                 r["significado"])
        bruto.setdefault(chave, []).append((float(r["valor_mm"]),
                                            r["confiavel"] == "1"))
    _casa = {}
    for chave, leituras in bruto.items():
        valores = sorted(v for v, _ in leituras)
        meio = valores[(len(valores) - 1) // 2]
        # Cota medida duas vezes com duas respostas nao e cota. Acontece quando
        # um rotulo grudou na peca errada, e o jeito de nao propagar isso e
        # recusar a chave inteira em vez de escolher uma das duas leituras.
        concorda = not valores or (valores[-1] - valores[0]) <= 0.10 * meio
        confiavel = any(c for _, c in leituras) and concorda
        _casa[chave] = (meio, confiavel, len(valores), valores[0], valores[-1],
                        concorda)
    return _casa


def cota_da_casa(familia, dn_mm, variante="", significado="comprimento_mm",
                 dn_menor=None, aceitar_suspeita=False):
    """A cota medida no DXF da casa, em milimetro. None se nao houver.

    Medida em desenho de projeto, nao em folha - e a casa declarou uma excecao:
    os registros de gaveta podem ter entrado fora de escala. Eles estao na
    tabela com confiavel=0 e so saem daqui se alguem pedir explicitamente, o
    que forca quem usa a saber o que esta usando.
    """
    indice = _carregar_casa()
    for chave in ((familia, variante, float(dn_mm), dn_menor, significado),
                  (familia, variante, float(dn_mm), None, significado),
                  (familia, "", float(dn_mm), None, significado)):
        achado = indice.get(chave)
        if achado is None:
            continue
        valor, confiavel = achado[0], achado[1]
        if confiavel or aceitar_suspeita:
            return valor
    return None


def leituras_da_casa():
    """Cada cota medida, com quantas leituras e a faixa entre elas.

    Serve para achar a peca que foi medida duas vezes com resultado diferente
    - sinal de rotulo grudado na peca errada, nao de peca com duas medidas.
    """
    return {chave: {"valor": v, "confiavel": c, "leituras": n,
                    "minimo": lo, "maximo": hi, "concorda": ok}
            for chave, (v, c, n, lo, hi, ok) in _carregar_casa().items()}


def cota_com_fonte(familia, dn_pol, variante="", significado="face_a_face_mm",
                   fonte=None, dn_menor_pol=None):
    """Devolve (valor, fonte_usada). Cai para o outro fabricante se o padrao
    nao tiver a peca - e diz de quem veio, para o desenho poder avisar.

    dn_menor_pol so importa na reducao, onde a cota depende do par: a
    excentrica de 8" mede 200 contra 6" e 300 contra 3".
    """
    indice = _carregar()
    if dn_pol is None:
        return None, None
    preferida = fonte or PREFERIDA_POR_FAMILIA.get(familia, PADRAO)
    ordem = [preferida] + [f for f in fontes() if f != preferida]
    menores = [dn_menor_pol, None] if dn_menor_pol is not None else [None]
    # a variante afina a busca; quem nao separa por variante responde no ""
    variantes = [variante, ""] if variante else [""]
    for f in ordem:
        for var in variantes:
            for menor in menores:
                chave = (f, familia, var, float(dn_pol),
                         float(menor) if menor is not None else None, significado)
                valor = indice.get(chave)
                if valor is not None:
                    return valor, f
    return None, None


def cota(familia, dn_pol, variante="", significado="face_a_face_mm", fonte=None,
         dn_menor_pol=None):
    return cota_com_fonte(familia, dn_pol, variante, significado, fonte,
                          dn_menor_pol)[0]
