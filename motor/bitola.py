"""Bitola e identidade, nao numero.

Tres bugs desta semana vieram de tratar bitola como numero, e todos os tres
sao a mesma coisa: um numero nao sabe de que serie ele e.

    3/4"  lido como 4"        o denominador da fracao casou com o padrao
    90    de PVC comparado    milimetro contra grau
          com 90 de curva
    225 mm e 8" tratados      quando sao a MESMA flange de 12 furos
    como coisas diferentes

E os tres apareceram de novo em outra roupa, nas correcoes desta semana: o
manifold com dois bocais que a lista nao tem, o PVC desenhado em DN280 onde a
linha Plasson acaba em 225. Peca inventada e sempre a mesma raiz - o programa
nao sabia a que serie o numero pertencia.

**A identidade e o DN nominal em milimetro**, e as representacoes sao
apresentacao. Por que o DN nominal e nao a polegada: e ele a chave da tabela de
furacao, e furacao e a prova fisica de que duas bitolas sao a mesma - 225 mm de
Plasson e 8" de aco tomam a mesma flange, com os mesmos 12 furos, no mesmo
circulo. Ver tools/conferir_bitola.py, que confere isso peca por peca.

**A conversao e tabelada e depende do material**, nao e aritmetica. E as series
nao sao a mesma coisa:

    linha em aco     3" 4" 6" 8" 10" 12" 14"     trecho de tubulacao
    bocal de bomba   inclui 5"                   entrada e saida da bomba
    metrica          63 75 90 110 140 160 225    PEAD e Plasson (diametro
                     280 315 355                 EXTERNO, nao nominal)
    soldavel         20 25 32 40 50 60 75 85     NBR 5648
                     110
    bolsa (PBA)      50 75 100 125 150           NBR 5647
    rosca            ISO 65

**5" prova a regra:** existe como bocal, nao existe como linha. Nao ha crivo,
valvula, tubo, te nem manifold em 5" - a folha de simbolos, quando passou a
sair da lista, caiu de 38 pecas para 13 nessa bitola. Uma `Bitola` sem serie
nao tem como saber disso; com serie, o motor recusa 5" como diametro de trecho
e aceita como diametro de transicao.

Este modulo e a UNICA tabela de conversao do programa. Ela estava copiada em
quatro lugares - traducao.POLEGADA_MM, regras.POLEGADA_PARA_DN,
regras.PVC_PARA_DN e simbolos.PEAD_POL - e copia e onde a divergencia mora.
"""
import csv
import os
import re

DADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data")

# polegada -> DN nominal em milimetro. E a identidade da bitola, e e a chave da
# tabela de furacao (data/regras_furacao.csv).
NOMINAL = {
    0.125: 6, 0.25: 8, 0.375: 10, 0.5: 15, 0.75: 20, 1: 25, 1.25: 32, 1.5: 40,
    2: 50, 2.5: 65, 3: 80, 4: 100, 5: 125, 6: 150, 8: 200, 10: 250, 12: 300,
    14: 350, 16: 400, 18: 450, 20: 500, 24: 600, 28: 700, 30: 750, 32: 800,
    36: 900, 40: 1000, 48: 1200,
}
POLEGADA = {dn: pol for pol, dn in NOMINAL.items()}

# DN nominal -> diametro EXTERNO na serie metrica. E como o PEAD e o Plasson se
# chamam: um tubo "DN225" de PEAD tem 225 mm de diametro externo e DN nominal
# 200 - e por isso ele usa a flange de 8".
METRICO = {50: 63, 65: 75, 80: 90, 100: 110, 125: 140, 150: 160, 200: 225,
           250: 280, 300: 315, 350: 355, 400: 400, 450: 450, 500: 500,
           # PEAD grande, serie ISO 161-1: a lista tem colar e flange ate 630
           560: 560, 600: 630, 700: 710}

# DN nominal -> diametro externo na serie DEFOFO (NBR 7665), que e o PVC de
# ponta e bolsa das bitolas grandes. E outra serie: o mesmo DN150 e 160 mm no
# metrico e 170 mm no DEFOFO, e comprar por uma tabela e receber da outra nao
# encaixa. A lista tem 118, 170, 222, 274, 326 e 378.
DEFOFO = {100: 118, 150: 170, 200: 222, 250: 274, 300: 326, 350: 378,
          400: 429, 500: 532, 600: 635}

# DN nominal -> diametro externo do TUBO DE ACO, que e como a lista escreve a
# flange: FL 8" (203MM). Nao e o nominal nem o metrico - e a terceira serie de
# milimetro que aparece na mesma lista.
ACO_EXTERNO = {80: 89, 100: 102, 125: 141, 150: 152, 200: 203, 250: 261,
               300: 318, 350: 368, 400: 419, 450: 470, 500: 521, 600: 622,
               700: 711}

# as series que a casa compra, em DN nominal
LINHA_ACO = (80, 100, 150, 200, 250, 300, 350)
BOCAL_BOMBA = (25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250)
LINHA_PLASSON = (65, 80, 100, 125, 150, 200)      # 75 a 225 mm de externo
LINHA_PEAD = (80, 100, 150, 200, 250, 300, 350)   # 90 a 355 mm de externo

_series = None


def _carregar_series():
    """A equivalencia polegada <-> milimetro de cada serie nominal, por norma.

    Sai de data/series_nominais.csv, que e NORMA e nao folha de fabricante: a
    mesma polegada cai em milimetro diferente em cada serie - 2" e 60 mm na
    soldavel e 50 mm na PBA, e comprar pela tabela errada nao encaixa.
    """
    global _series
    if _series is None:
        _series = {}
        with open(os.path.join(DADOS, "series_nominais.csv"),
                  encoding="utf-8") as fh:
            linhas = [ln for ln in fh if not ln.startswith("#")]
        for r in csv.DictReader(linhas):
            serie = _series.setdefault(r["serie"], {"norma": r["norma"],
                                                    "por_pol": {}, "por_mm": {}})
            pol, mm = float(r["dn_pol"]), float(r["dn_mm"])
            serie["por_pol"][pol] = mm
            serie["por_mm"][mm] = pol
    return _series


class Bitola:
    """Uma bitola: DN nominal em milimetro, mais a serie de onde ela veio.

    Igualdade e por DN nominal, nunca pelo numero exibido. E o que faz
    Bitola.de_mm(225, "METRICO") == Bitola.de_polegada(8) ser verdadeiro, que e
    a realidade fisica: as duas tomam a mesma flange.
    """

    __slots__ = ("dn_mm", "serie")

    def __init__(self, dn_nominal_mm, serie="ACO"):
        self.dn_mm = float(dn_nominal_mm)
        self.serie = serie

    # ------------------------------------------------------------ construir
    @classmethod
    def de_polegada(cls, pol, serie="ACO"):
        """A bitola de uma medida em polegada. None se nao esta na tabela."""
        if pol is None:
            return None
        dn = NOMINAL.get(_talvez_numero(pol))
        return cls(dn, serie) if dn else None

    @classmethod
    def de_mm(cls, mm, serie="METRICO"):
        """A bitola de uma medida em milimetro, na serie dita.

        A serie importa: 90 e DN80 no metrico (externo 90) e nao existe como
        nominal. Sem a serie o numero nao decide nada - e por isso que ela nao
        tem valor padrao adivinhado.
        """
        mm = _talvez_numero(mm)
        if mm is None:
            return None
        externos = {"METRICO": METRICO, "DEFOFO": DEFOFO,
                    "ACO_EXTERNO": ACO_EXTERNO}.get(serie)
        if externos:
            for dn, externo in externos.items():
                if abs(externo - mm) < 0.6:
                    return cls(dn, serie)
            return None
        if serie == "NOMINAL":
            return cls(mm, serie) if mm in POLEGADA else None
        tabela = _carregar_series().get(serie)
        if tabela and mm in tabela["por_mm"]:
            return cls.de_polegada(tabela["por_mm"][mm], serie)
        return None

    @classmethod
    def de_texto(cls, texto, serie="ACO"):
        r'''A bitola escrita como a lista escreve.

        Trata a fracao, que e o bug do 3/4": `de_texto('3/4"')` tem de dar
        DN20 e nunca DN100. O padrao le a fracao INTEIRA - inteiro e fracao,
        ou fracao sozinha - e nao o denominador solto.
        '''
        if not texto:
            return None
        achado = re.search(r'(\d+)\s+(\d+)/(\d+)\s*"|(\d+)/(\d+)\s*"'
                           r'|(\d+(?:[.,]\d+)?)\s*"', str(texto))
        if not achado:
            return None
        g = achado.groups()
        if g[0]:
            pol = float(g[0]) + float(g[1]) / float(g[2])
        elif g[3]:
            pol = float(g[3]) / float(g[4])
        else:
            pol = float(g[5].replace(",", "."))
        return cls.de_polegada(pol, serie)

    # ---------------------------------------------------------- apresentar
    def em_polegada(self):
        """Como o aco se chama: 8"."""
        return POLEGADA.get(self.dn_mm)

    def em_mm_externo(self):
        """Como o plastico se chama: 225 mm."""
        return METRICO.get(self.dn_mm)

    def em_serie(self, serie):
        """O numero desta bitola na serie pedida, ou None se ela nao existe la.

        E aqui que o programa descobre que nao ha peca: uma bitola que nao
        aparece na serie nao e um numero que da errado, e uma peca que nao
        existe para comprar.
        """
        if serie in ("METRICO", "DEFOFO", "ACO_EXTERNO"):
            return {"METRICO": METRICO, "DEFOFO": DEFOFO,
                    "ACO_EXTERNO": ACO_EXTERNO}[serie].get(self.dn_mm)
        if serie in ("ACO", "NOMINAL", "BOCAL"):
            return self.em_polegada() if serie != "NOMINAL" else self.dn_mm
        tabela = _carregar_series().get(serie)
        pol = self.em_polegada()
        return tabela["por_pol"].get(pol) if tabela and pol else None

    def norma_da_serie(self, serie=None):
        tabela = _carregar_series().get(serie or self.serie)
        return tabela["norma"] if tabela else None

    # -------------------------------------------------------------- validar
    def na_linha(self, material="ACO"):
        """Esta bitola existe como TRECHO de linha nesse material?

        O 5" e o caso: existe como bocal de bomba e nao existe como linha.
        """
        return self.dn_mm in {"ACO": LINHA_ACO, "PEAD": LINHA_PEAD,
                              "PLASSON": LINHA_PLASSON,
                              "BOCAL": BOCAL_BOMBA}.get(material, LINHA_ACO)

    def no_bocal(self):
        return self.dn_mm in BOCAL_BOMBA

    # -------------------------------------------------------- comportamento
    def __eq__(self, outra):
        # comparar com numero e o bug que este objeto existe para impedir:
        # 90 de PVC contra 90 de grau passava calado
        if not isinstance(outra, Bitola):
            return NotImplemented
        return self.dn_mm == outra.dn_mm

    def __hash__(self):
        return hash(self.dn_mm)

    def __lt__(self, outra):
        if not isinstance(outra, Bitola):
            return NotImplemented
        return self.dn_mm < outra.dn_mm

    def __repr__(self):
        pol = self.em_polegada()
        como = f'{pol:g}"' if pol else f"DN{self.dn_mm:g}"
        return f"<Bitola {como} DN{self.dn_mm:g} {self.serie}>"

    def __str__(self):
        pol = self.em_polegada()
        return f'{pol:g}"' if pol else f"DN{self.dn_mm:g}"


def _talvez_numero(valor):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------- atalhos
# A ordem em que se tenta reconhecer um milimetro solto. Nao e arbitraria: a
# metrica e a serie da linha (PEAD e Plasson), o DEFOFO e o PVC grande, o
# nominal e o que a bomba usa, e o externo de aco e como a flange e escrita. A
# soldavel, a PBA e a rosca vem depois porque a lista as escreve com a palavra
# junto - SOLD, BS, R.
SERIES_MM = ("METRICO", "DEFOFO", "NOMINAL", "ACO_EXTERNO", "SOLDA", "BOLSA",
             "ROSCA")


def qualquer_mm(medida):
    """A bitola de um milimetro solto, tentando as series na ordem de uso."""
    for serie in SERIES_MM:
        achada = Bitola.de_mm(medida, serie)
        if achada:
            return achada
    return None


def nominal(medida, unidade="in", material=None):
    """A medida do desenho -> DN nominal em milimetro.

    E o que regras.dn_nominal fazia com tres dicionarios soltos. Aqui a serie
    entra explicita, e a do plastico e a METRICA - o DN que a lista escreve e o
    diametro externo.
    """
    if unidade == "mm":
        b = Bitola.de_mm(medida, "METRICO") or Bitola.de_mm(medida, "NOMINAL")
        return b.dn_mm if b else None
    b = Bitola.de_polegada(medida)
    return b.dn_mm if b else None


def em_polegada(medida, unidade="in"):
    """A medida do desenho -> polegada, que e como a flange se chama."""
    if unidade == "mm":
        b = Bitola.de_mm(medida, "METRICO") or Bitola.de_mm(medida, "NOMINAL")
        return b.em_polegada() if b else None
    return _talvez_numero(medida)


def em_mm(pol):
    """A polegada -> milimetro externo da serie metrica (PEAD e Plasson)."""
    b = Bitola.de_polegada(pol)
    return b.em_mm_externo() if b else None
