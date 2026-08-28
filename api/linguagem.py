"""A barra de comando: de uma linha digitada para um comando do motor.

Como no AutoCAD - digita-se o verbo, os argumentos vem atras, e o prefixo
basta quando ele identifica um verbo so. `des` e `desfazer`; `gir 90` gira.

**O vocabulario mora aqui, e nao na tela.** A tela pede `vocabulario` uma vez
e usa a resposta para completar o que se digita. Se ela tivesse a propria
lista, um verbo novo no motor nao apareceria na barra, e um verbo removido
continuaria sendo oferecido - a mesma divergencia que a tela evita nao
guardando documento.

Duas decisoes que valem ser ditas:

**O argumento vai pelo TIPO, e nao pela posicao.** `montar succao 8` e
`montar 8 succao` sao a mesma coisa, e `montar 8` tambem - o numero e a
bitola, a palavra e o template, e o que falta cai no padrao. Exigir ordem
faria a barra recusar o que ela entendeu perfeitamente.

**O verbo que age sobre uma peca precisa de alvo, e o alvo e da TELA.** O
motor nao sabe o que esta selecionado - `escolhida` e o unico estado que a
tela tem. Entao ela manda junto, e o verbo que precisa e nao recebe recusa
dizendo o que fazer, em vez de agir sobre a peca errada.
"""
import unicodedata
from collections import namedtuple

Verbo = namedtuple("Verbo", "nome resumo argumentos exemplo precisa_alvo monta")
Argumento = namedtuple("Argumento", "nome tipo padrao")


class Erro(Exception):
    """A linha nao virou comando, e o motivo e para a pessoa ler."""


def _arg(nome, tipo="texto", padrao=None):
    return Argumento(nome, tipo, padrao)


def _busca(valores, sessao, campo="busca"):
    """Resolve o que se digitou num codigo SAP - por codigo ou por texto."""
    texto = (valores.get(campo) or "").strip()
    if not texto:
        raise Erro("diga o código ou o nome da peça")
    if texto in sessao.catalogo.por_sap:
        return texto
    achados = sessao.catalogo.procurar(texto, limite=4)
    if not achados:
        raise Erro(f"não achei peça para {texto!r}")
    return achados[0]["sap"]


def _prancha(valores):
    """Formato e orientacao vem em qualquer ordem - e nem sempre os dois.

    `folha a4`, `folha retrato` e `folha retrato a4` sao os tres validos, e a
    posicao nao decide qual e qual: o que estiver na lista de formatos e
    formato, o que comecar por pais/retr e orientacao. E a mesma ideia do
    argumento por tipo, um degrau mais fundo - aqui os dois sao texto, entao
    quem separa e o VALOR.

    O que nao for nem um nem outro e recusado, e nao ignorado: `folha a9`
    calada sairia em A3 sem ninguem perceber.
    """
    from motor import folha as prancha
    formato, orientacao = "A3", "paisagem"
    for termo in (valores.get("formato"), valores.get("orientacao")):
        termo = (termo or "").strip()
        if not termo:
            continue
        if termo.upper() in prancha.FORMATOS:
            formato = termo.upper()
        elif termo.lower().startswith(("pais", "retr")):
            orientacao = termo.lower()
        else:
            raise Erro(f"{termo!r} não é formato nem orientação - formatos: "
                       + ", ".join(prancha.FORMATOS).lower()
                       + "; orientação: paisagem ou retrato")
    return {"formato": formato, "orientacao": orientacao}


# como se diz "mostra" e "esconde" o balao. Fica aqui, e nao num `if` dentro
# do verbo, porque e vocabulario - e vocabulario mora neste arquivo
BALAO_LIGA = ("sim", "s", "marcar", "marca", "mostrar", "mostra", "ligar")
BALAO_DESLIGA = ("nao", "n", "desmarcar", "desmarca", "esconder", "esconde",
                 "apagar", "tirar", "sem")
BALAO_SOLTO = ("solto", "solta", "auto", "livre", "padrao")


def _balao(valores):
    """`balao`, `balao nao`, `balao 30`, `balao 30 80`, `balao solto`."""
    estado = _sem_acento((valores.get("estado") or "").strip().lower())
    pedido = {"mostrar": None, "solto": False}
    if estado in BALAO_LIGA:
        pedido["mostrar"] = True
    elif estado in BALAO_DESLIGA:
        pedido["mostrar"] = False
    elif estado in BALAO_SOLTO:
        pedido["solto"] = True
    elif estado:
        raise Erro(f"balão não entende {estado!r} - diga sim, não, solto, ou "
                   f"o ângulo em graus")
    for campo in ("angulo", "distancia"):
        pedido[campo] = valores.get(campo) if valores.get(campo) != "" else None
    return pedido


VERBOS = [
    Verbo("montar", "monta uma linha pronta",
          [_arg("template", "texto", "SUCCAO"), _arg("bitola", "numero")],
          "montar recalque 6", False,
          lambda v, alvo, s: {"nome": "template",
                              "template": (v.get("template") or "SUCCAO").upper(),
                              "dn": v.get("bitola")}),
    Verbo("inserir", "acrescenta uma peça, por código ou por nome",
          [_arg("busca", "resto")], 'inserir curva 90 8', False,
          lambda v, alvo, s: {"nome": "inserir", "sap": _busca(v, s),
                              "pos": None}),
    Verbo("substituir", "troca a peça escolhida por outra",
          [_arg("busca", "resto")], "substituir 01523-134000", True,
          lambda v, alvo, s: {"nome": "substituir", "alvo": alvo,
                              "sap": _busca(v, s)}),
    Verbo("remover", "tira a peça escolhida da linha", [], "remover", True,
          lambda v, alvo, s: {"nome": "remover", "alvo": alvo}),
    Verbo("mover", "põe a peça escolhida em outro lugar da sequência",
          [_arg("posicao", "numero")], "mover 3", True,
          # a pessoa conta a partir de 1, o motor a partir de 0
          lambda v, alvo, s: {"nome": "mover", "alvo": alvo,
                              "para": max(0, int(v.get("posicao") or 1) - 1)}),
    Verbo("esticar", "leva o tubo escolhido à próxima barra da lista",
          [_arg("passos", "numero", 1)], "esticar", True,
          lambda v, alvo, s: {"nome": "esticar", "alvo": alvo,
                              "passos": int(v.get("passos") or 1)}),
    Verbo("encolher", "leva o tubo escolhido à barra anterior",
          [_arg("passos", "numero", 1)], "encolher", True,
          lambda v, alvo, s: {"nome": "esticar", "alvo": alvo,
                              "passos": -int(v.get("passos") or 1)}),
    Verbo("comprimento", "muda o comprimento da peça escolhida, em mm",
          [_arg("mm", "numero")], "comprimento 1500", True,
          lambda v, alvo, s: {"nome": "alterar", "alvo": alvo,
                              "campos": {"comprimento_mm": v.get("mm")}}),
    Verbo("fonte", "troca a folha de onde sai a cota da peça escolhida",
          [_arg("fabricante", "texto")], "fonte netafim", True,
          lambda v, alvo, s: {"nome": "alterar", "alvo": alvo,
                              "campos": {"fonte": (v.get("fabricante") or "").upper()}}),
    Verbo("girar", "gira a linha inteira na folha",
          [_arg("graus", "numero", 90)], "girar 90", False,
          lambda v, alvo, s: {"nome": "girar",
                              "graus": v.get("graus", 90)}),
    Verbo("espelhar", "vira a peça escolhida - ou a linha, sem peça escolhida",
          [], "espelhar", False,
          lambda v, alvo, s: {"nome": "espelhar", "alvo": alvo}),
    Verbo("balao", "marca, desmarca ou move o balão da peça escolhida",
          [_arg("estado", "texto", ""), _arg("angulo", "numero", ""),
           _arg("distancia", "numero", "")],
          "balao 45", True,
          lambda v, alvo, s: {"nome": "balao", "alvo": alvo, **_balao(v)}),
    Verbo("numerar", "põe a peça escolhida em outro número de item",
          [_arg("item", "numero")], "numerar 3", True,
          lambda v, alvo, s: {"nome": "numerar", "alvo": alvo,
                              "item": v.get("item")}),
    Verbo("desfazer", "volta um comando", [], "desfazer", False,
          lambda v, alvo, s: {"nome": "desfazer"}),
    Verbo("refazer", "repete o que foi desfeito", [], "refazer", False,
          lambda v, alvo, s: {"nome": "refazer"}),
    Verbo("modo", "traço, pb ou metal", [_arg("leitura", "texto")],
          "modo metal", False,
          lambda v, alvo, s: {"nome": "modo", "modo": v.get("leitura")}),
    Verbo("exportar", "dxf, svg, xlsx ou csv", [_arg("formato", "texto")],
          "exportar dxf", False,
          lambda v, alvo, s: {"nome": "exportar", "formato": v.get("formato")}),
    Verbo("folha", "a prancha de impressão: escala, lista e carimbo",
          [_arg("formato", "texto", ""), _arg("orientacao", "texto", "")],
          "folha a3 paisagem", False,
          lambda v, alvo, s: {"nome": "folha", **_prancha(v)}),
    Verbo("procurar", "lista o que a lista tem, sem inserir nada",
          [_arg("busca", "resto")], "procurar borboleta 8", False,
          lambda v, alvo, s: {"nome": "procurar", "texto": v.get("busca")}),
]
POR_NOME = {v.nome: v for v in VERBOS}


def _sem_acento(palavra):
    """`balão` e `balao` sao a mesma palavra. Quem digita nao escolhe qual."""
    return unicodedata.normalize("NFKD", palavra).encode(
        "ascii", "ignore").decode("ascii")


def achar(palavra):
    """O verbo que a palavra nomeia. Prefixo basta, se for de um verbo so."""
    palavra = _sem_acento((palavra or "").strip().lower())
    if not palavra:
        raise Erro("digite um comando")
    if palavra in POR_NOME:
        return POR_NOME[palavra]
    candidatos = [v for v in VERBOS if v.nome.startswith(palavra)]
    if len(candidatos) == 1:
        return candidatos[0]
    if not candidatos:
        raise Erro(f"não conheço {palavra!r} - digite ? para ver os comandos")
    raise Erro(f"{palavra!r} serve para " +
               ", ".join(v.nome for v in candidatos) + " - falta uma letra")


def _numero(termo):
    try:
        return float(termo.replace(",", "."))
    except ValueError:
        return None


def interpretar(texto, alvo, sessao):
    """A linha digitada vira (comando, entendido). Erro é resposta, não crash."""
    partes = (texto or "").strip().split()
    if not partes:
        raise Erro("digite um comando")
    verbo = achar(partes[0])
    if verbo.precisa_alvo and not alvo:
        raise Erro(f"{verbo.nome} age sobre uma peça - escolha uma antes, "
                   f"no desenho ou na lista")
    valores = {a.nome: a.padrao for a in verbo.argumentos}
    sobra = list(partes[1:])
    # `resto` engole tudo o que sobrou: é o argumento de busca, e peça tem
    # nome de várias palavras
    resto = next((a for a in verbo.argumentos if a.tipo == "resto"), None)
    if resto:
        valores[resto.nome] = " ".join(sobra)
        sobra = []
    for termo in sobra:
        valor = _numero(termo)
        tipo = "numero" if valor is not None else "texto"
        # a primeira vaga do tipo que ainda esta no padrao - e por isso que
        # `montar succao 8` e `montar 8 succao` dao no mesmo
        vaga = next((a for a in verbo.argumentos
                     if a.tipo == tipo and valores.get(a.nome) == a.padrao),
                    None)
        if vaga is None:
            raise Erro(f"{verbo.nome} não usa {termo!r} - {verbo.exemplo}")
        valores[vaga.nome] = valor if valor is not None else termo
    faltando = [a.nome for a in verbo.argumentos
                if a.padrao is None and valores.get(a.nome) in (None, "")]
    if faltando:
        raise Erro(f"{verbo.nome} precisa de {', '.join(faltando)} - "
                   f"{verbo.exemplo}")
    return verbo.monta(valores, alvo, sessao), {"verbo": verbo.nome,
                                                "valores": valores}


def vocabulario():
    """O que a barra oferece - a tela pede uma vez e completa sozinha."""
    return [{"nome": v.nome, "resumo": v.resumo, "exemplo": v.exemplo,
             "precisa_alvo": v.precisa_alvo,
             "argumentos": [{"nome": a.nome, "tipo": a.tipo,
                             "padrao": a.padrao} for a in v.argumentos]}
            for v in VERBOS]
