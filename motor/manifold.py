"""A topologia do manifold sai da descricao, e nao de um padrao.

O manifold e a peca da lista com mais variacao de FORMA e nenhuma cota nova:
todos sao um tubo reto de 1 a 6 m. O que muda e o que ha em cima dele, e isso
esta escrito no nome:

    MNFD AZ D06 14" FL NBR PN16 C/ L2        liso, duas luvas de 2"
    MNFD AZ D09 12"X2,65X2100MM FL E 2 FL8"  dois bocais de 8" flangeados
    MNFD AZ D10 12"X2,65X3260MM FL E 3 K8"   tres bocais de 8" com anel K
    MNFD AZ D12 8" FL C/ 2 LG2"              liso, duas luvas
    MNFD AZ D20 20" FL X 1FL14" X 2FL12"     um bocal de 14 e dois de 12

O codigo D e o DESENHO do barrilete - e ele que fixa quantos bocais existem -
e a descricao diz o tamanho de cada um. Ver tools/gabarito_manifold.py, que
levanta a tabela codigo -> topologia a partir do proprio catalogo e denuncia
quem discorda do proprio codigo.

**Nao ha bocal por padrao.** O desenho antes punha dois sempre, e a casa
apontou o erro num manifold que nao os tem. Inventar topologia e o mesmo erro
de inventar cota.

O que separa bocal de PONTA e o que vem antes dele:

    FLK 2K10"      o 2 e contagem  -> dois bocais de 10"
    FLK14" 2K10"   o 14" nao tem contagem nem C/ -> e a ponta, e repete o DN
    FL C/ FL6"     o C/ apresenta um bocal
    FL X 1FL14"    o X separa os bocais na familia D20

Entao bocal e o que vem com contagem, com `C/` ou depois de um separador. Sem
nenhum dos tres, o que esta escrito e a ponta do proprio manifold.
"""
import re

# bocal escrito depois do tipo: '2 FL8"', '1FL3"', '2K10"', 'C/ FL 3"'
RX_BOCAL = re.compile(
    r'(?:(?P<qtd>\d)\s*|(?P<cbarra>C/\s*)|(?P<sep>[XE]\s+))'
    r'(?P<tipo>FL|K)\s*(?:NBR\s*PN\d+\s*)?(?P<dn>\d{1,2}(?:[.,]\d+)?)'
    # a aspa fica opcional QUANDO ha contagem: '2 FL10' e '2FL8 2FL6' sao
    # bocais tanto quanto '2 FL10"'. Sem contagem ela e obrigatoria, porque e
    # ela que separa o bocal de 10" da ponta K10
    r'(?(qtd)\s*"?|\s*")')
# bocal escrito antes do tipo: 'C/4"FL NBRPN16'
RX_BOCAL_ANTES = re.compile(r'C/\s*(\d{1,2}(?:[.,]\d+)?)\s*"\s*(FL|K)')
# a luva de ventosa: 'C/ 2 LG2"', 'C/ L2', 'C/ LG 3', '2LG2"'
RX_LUVA = re.compile(r'\b(?:C/\s*)?(\d)?\s*L[GV]?\s*(\d(?:\s?\d/\d)?)\s*"?')
# a geometria - '12"X2,65X2100MM' - nao e bocal nenhum
RX_GEOMETRIA = re.compile(r'\d{1,2}(?:[.,]\d+)?\s*"?\s*X\s*\d[.,]?\d*\s*X\s*'
                          r'\d+\s*MM')
RX_CABECA = re.compile(r'^\s*M[NF]*D\s*AZ\s*D?\d*\s*')


def _numero(txt):
    return float(txt.replace(",", "."))


def topologia(descricao):
    """(bocais, luvas) do manifold, lidos da descricao.

    bocais: [{"qtd", "dn_pol", "tipo"}] - tipo FL (flange) ou K (anel)
    luvas:  [{"qtd", "dn_pol"}]         - a luva roscada da ventosa
    """
    d = RX_CABECA.sub(" ", (descricao or "").upper())
    d = RX_GEOMETRIA.sub(" ", d)
    # tira a bitola do proprio manifold, que abre a descricao
    d = re.sub(r'^\s*\d{1,2}(?:[.,]\d+)?\s*"', " ", d)

    bocais = []
    for m in RX_BOCAL.finditer(d):
        bocais.append({"qtd": int(m.group("qtd") or 1),
                       "dn_pol": _numero(m.group("dn")),
                       "tipo": m.group("tipo")})
    for m in RX_BOCAL_ANTES.finditer(d):
        bocais.append({"qtd": 1, "dn_pol": _numero(m.group(1)),
                       "tipo": m.group(2)})

    luvas = []
    for m in RX_LUVA.finditer(d):
        luvas.append({"qtd": int(m.group(1) or 1),
                      "dn_pol": _numero(m.group(2))})
    return bocais, luvas


def quantos(bocais):
    return sum(b["qtd"] for b in bocais)
