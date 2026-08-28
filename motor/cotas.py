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
# A folha da PLASSON, que a casa mandou: dez desenhos da linha soldavel. E
# folha de fabricante, entao ela vem ANTES da medida do DXF na ordem de fonte.
TABELA_PLASSON = os.path.join(os.path.dirname(__file__), "..", "data",
                              "plasson_soldavel.csv")

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


TABELA_SERIE = f"{DADOS}/series_nominais.csv" if "DADOS" in dir() else \
    "data/series_nominais.csv"
_series = None


def _carregar_series():
    global _series
    if _series is not None:
        return _series
    _series = {}
    with open(TABELA_SERIE, encoding="utf-8") as fh:
        for r in csv.DictReader(l for l in fh if not l.startswith("#")):
            _series[(r["serie"], float(r["dn_pol"]))] = (float(r["dn_mm"]),
                                                         r["norma"])
    return _series


def milimetro_da_serie(serie, dn_pol):
    """O diametro em milimetro que a norma da para essa polegada, e qual norma.

    Devolve (dn_mm, norma) ou (None, None). A serie importa: 2" e 60 mm na
    soldavel (NBR 5648) e 50 mm na PBA (NBR 5647), e a peca comprada pela
    tabela errada nao encaixa. Por isso quem chama tem de dizer a serie, que
    sai da descricao, e a norma volta para aparecer na tarja.
    """
    achado = _carregar_series().get((serie, float(dn_pol)))
    return achado if achado else (None, None)


def cota_da_casa(familia, dn_mm, variante="", significado="comprimento_mm",
                 dn_menor=None, aceitar_suspeita=False):
    """A cota medida no DXF da casa, em milimetro. None se nao houver.

    Medida em desenho de projeto, nao em folha - e a casa declarou uma excecao:
    os registros de gaveta podem ter entrado fora de escala. Eles estao na
    tabela com confiavel=0 e so saem daqui se alguem pedir explicitamente, o
    que forca quem usa a saber o que esta usando.
    """
    indice = _carregar_casa()
    # do mais especifico ao mais geral. A variante e o par de bitolas soltam
    # em ordens diferentes: a bucha foi medida com o par mas SEM junta no
    # nome, e sem a terceira chave dessa lista ela caia na estimativa
    for chave in ((familia, variante, float(dn_mm), dn_menor, significado),
                  (familia, variante, float(dn_mm), None, significado),
                  (familia, "", float(dn_mm), dn_menor, significado),
                  (familia, "", float(dn_mm), None, significado)):
        achado = indice.get(chave)
        if achado is None:
            continue
        valor, confiavel = achado[0], achado[1]
        if confiavel or aceitar_suspeita:
            return valor
    return None


_plasson = None


def _carregar_plasson():
    """A folha da Plasson, indexada por (familia, d, d_menor)."""
    global _plasson
    if _plasson is None:
        _plasson = {}
        with open(TABELA_PLASSON, encoding="utf-8") as fh:
            linhas = [ln for ln in fh if not ln.startswith("#")]
        for r in csv.DictReader(linhas):
            def num(campo):
                return float(r[campo]) if r.get(campo) else None
            chave = (r["familia"], num("d_mm"), num("d_menor_mm"))
            _plasson.setdefault(chave, {k: num(k) for k in
                                        ("E_mm", "E1_mm", "H_mm", "I_mm",
                                         "Z_mm", "B_mm", "C_mm", "Lt_mm",
                                         "L_mm", "Dp_mm", "S_mm", "furos",
                                         "peso_g")})
            _plasson[chave]["codigo"] = r["codigo"]
    return _plasson


def cota_plasson(familia, dn_mm, significado, dn_menor=None, variante=""):
    """A cota da FOLHA da Plasson - a fonte mais forte que temos em milimetro.

    A ordem de fonte deste projeto poe folha de fabricante acima de desenho de
    projeto, e por isso ela vem antes da medida da casa. As duas se confirmam
    onde existem juntas: o te soldavel de 160 e de 225 bate exato nas duas, e o
    E1 do colar 5510 bate nas cinco bitolas que a casa mediu.

    A folha nomeia as cotas com as letras dela, e a traducao para o que o
    desenho pede e o que esta aqui:

        luva          comprimento = H          externo = E
        te            face a face = H          altura total = Z + I + E/2
        curva 90      envelope    = H (nos dois eixos)
        bucha         comprimento = H          externo = o proprio d
        colar 5510    comprimento = H          externo = E1 (o ressalto)
        flange        espessura   = H          externo = E1 (solta) ou E (cega)

    A curva 45 fica de fora: a folha 5450 cota a PERNA (E) e nao o envelope, e
    inventar o envelope a partir dela seria estimar com cara de folha.
    """
    tabela = _carregar_plasson()
    fam = familia
    if familia in ("TE_REDUZIDO",):
        fam = "TE"
    if familia == "CURVA":
        angulo = (variante or "").split("/")[0]
        if angulo != "90":
            return None
        fam = "CURVA_90"
    linha = (tabela.get((fam, float(dn_mm), float(dn_menor) if dn_menor else None))
             or tabela.get((fam, float(dn_mm), None)))
    if not linha:
        return None
    E, H, I, Z, E1 = (linha["E_mm"], linha["H_mm"], linha["I_mm"],
                      linha["Z_mm"], linha["E1_mm"])
    if significado in ("comprimento_mm", "face_a_face_mm", "espessura_mm"):
        return H
    if significado == "altura_total_mm" and None not in (E, H, I, Z):
        return Z + I + E / 2
    if significado in ("envelope_x_mm", "envelope_y_mm"):
        return H if fam == "CURVA_90" else None
    if significado == "d_externo_mm":
        if fam in ("ADAPTADOR_FLANGE", "FLANGE"):
            return E1
        if fam == "BUCHA_REDUCAO":
            return float(dn_mm)
        return E
    if significado == "circulo_mm":
        return linha["Dp_mm"]
    if significado == "furo_mm":
        return linha["S_mm"]
    if significado == "furos":
        return linha["furos"]
    return None


def par_flangeado_plasson(dn_mm):
    """As DUAS pecas que fazem uma ponta flangeada Plasson, numa ficha so.

    A ponta Plasson nao e uma peca, sao duas, e e isso que muda o parafuso: o
    COLAR (desenho 5510) e soldado no tubo e tem um ressalto de espessura `B`;
    a FLANGE SOLTA (5900) corre por tras dele e tem espessura `H`. O parafuso
    nao aperta uma chapa, aperta o par - e num encontro Plasson-Plasson ele
    atravessa quatro camadas, e nao duas.

    Era esse numero que faltava para medir o parafuso fora do aco. Sem ele o
    programa media as juntas Plasson com a espessura da chapa de aco dos dois
    lados e dava um veredito sobre um sanduiche que nao existe.

    Devolve None quando a folha nao tem a bitola. O `d` e o EXTERNO do tubo em
    milimetro, que e como a Plasson nomeia a bitola.
    """
    tabela = _carregar_plasson()
    flange = tabela.get(("FLANGE", float(dn_mm), None))
    colar = tabela.get(("ADAPTADOR_FLANGE", float(dn_mm), None))
    if not flange:
        return None
    return {
        "d_mm": float(dn_mm),
        "externo": flange["E1_mm"],
        "espessura": flange["H_mm"],          # H da flange solta
        "furo_flange": flange["E_mm"],        # por onde o colar passa
        "circulo": flange["Dp_mm"],
        "furo": flange["S_mm"],
        "furos": int(flange["furos"]),
        # o colar existe de 20 a 225; a flange comeca em 32. Onde faltar o
        # colar, so a flange responde, e o aperto sai incompleto - por isso
        # o campo pode vir None e quem chama tem de olhar
        "ressalto": colar["B_mm"] if colar else None,
        "ressalto_externo": colar["E1_mm"] if colar else None,
        "codigo_flange": "5900",
        "codigo_colar": "5510" if colar else None,
        "fonte": "plasson",
    }


def bitolas_flangeadas_plasson():
    """Todo `d` que a folha cota com flange solta, do menor para o maior."""
    return sorted(d for fam, d, _menor in _carregar_plasson()
                  if fam == "FLANGE")


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
