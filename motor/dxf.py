"""Escreve os simbolos em DXF, como bloco - que e como a casa ja desenha.

A casa tem biblioteca de bloco em DWG: um bloco por peca, desenhado a mao,
uma vez por bitola. Esta camada nao concorre com isso - ela PRODUZ o mesmo
tipo de coisa. Cada simbolo vira um BLOCK com o nome da peca, e a linha vira
um INSERT por peca, com a rotacao acumulada da corrente. Quem abre no CAD ve
blocos, explode se quiser, e a cota esta em milimetro real.

As camadas seguem a convencao do desenho: o eixo vermelho traco-ponto numa
camada so, o corpo em preto, a chapa e a ferragem separadas. E isso que deixa
apagar todos os eixos de uma vez, ou plotar so o corpo.

    from motor import dxf
    dxf.escrever_pecas("simbolos.dxf", [tubo(8, 1000), curva(8, 90)])
    dxf.escrever_linha("succao.dxf", postos)
"""
import math
import re
import unicodedata

from .simbolos import pontos_do_path


def _ezdxf():
    """A biblioteca de CAD, carregada so quando alguem exporta.

    Importar no topo obrigaria a instalar ezdxf para DESENHAR, e desenhar nao
    precisa dela: a geometria e nossa, em milimetro, e o ezdxf so escreve o
    arquivo. Quem quer so abrir o programa e montar uma linha nao instala nada.
    """
    import ezdxf
    return ezdxf

# camada -> (cor ACI, tipo de linha). A cor 1 e vermelho, 7 preto/branco,
# 8 cinza escuro, 9 cinza claro - as cores basicas do AutoCAD.
CAMADAS = {
    "CORPO": (7, "CONTINUOUS"),
    "FLANGE": (7, "CONTINUOUS"),
    "CHAPA_LISA": (7, "CONTINUOUS"),
    "EIXO": (1, "CENTER"),
    "MALHA": (8, "CONTINUOUS"),
    "FURO": (8, "CONTINUOUS"),
    "SOLDA": (8, "CONTINUOUS"),
    "PARAFUSO": (7, "CONTINUOUS"),
    "PORCA": (7, "CONTINUOUS"),
    "JUNTA": (1, "CONTINUOUS"),
    "FLUXO": (8, "CONTINUOUS"),
    "COTA": (9, "CONTINUOUS"),
}
CLASSE_CAMADA = {"corpo": "CORPO", "flange": "FLANGE", "chapa_lisa": "CHAPA_LISA",
                 "centro": "EIXO", "malha": "MALHA", "furo": "FURO",
                 "solda": "SOLDA", "parafuso": "PARAFUSO", "porca": "PORCA",
                 "junta": "JUNTA", "fluxo": "FLUXO"}
ALTURA_TEXTO = 24.0        # mm, para a cota escrita dentro da peca

def _fechar(d, linhas):
    return [(p + [p[0]] if "Z" in d or "z" in d else p) for p in linhas]


def _girar(pontos, graus, cx, cy):
    rad = math.radians(graus)
    cos, sen = math.cos(rad), math.sin(rad)
    return [(cx + (px - cx) * cos - (py - cy) * sen,
             cy + (px - cx) * sen + (py - cy) * cos) for px, py in pontos]


def _y_para_cima(pontos):
    """O simbolo desenha com y para baixo, como SVG. O CAD usa y para cima."""
    return [(px, -py) for px, py in pontos]


def _transformar(elemento, pontos):
    for graus, cx, cy in ([elemento["girar"]] if elemento.get("girar") else []) \
            + ([(elemento["girar_fora"], 0.0, 0.0)]
               if elemento.get("girar_fora") else []):
        pontos = _girar(pontos, graus, cx, cy)
    return _y_para_cima(pontos)


def _sem_acento(texto):
    normal = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in normal if not unicodedata.combining(c))


def nome_do_bloco(simbolo):
    """O nome do bloco: o codigo SAP quando a peca veio do catalogo.

    E como a lista da Netafim nomeia - o codigo identifica, a descricao
    explica. Peca montada a mao (um tubo de 500 mm que so existe no desenho)
    nao tem codigo, e cai no rotulo.
    """
    return _nome_de_bloco(simbolo.params.get("sap") or simbolo.rotulo)


def _nome_de_bloco(rotulo):
    """Nome de bloco valido: sem acento, sem espaco, maiusculo."""
    limpo = _sem_acento(rotulo).upper()
    limpo = re.sub(r'["°×]', lambda m: {'"': "P", "°": "G",
                                                  "×": "X"}[m.group()], limpo)
    return re.sub(r"[^A-Z0-9_-]+", "_", limpo).strip("_")[:60] or "PECA"


def _desenhar(alvo, elemento):
    camada = CLASSE_CAMADA.get(elemento.get("classe", "corpo"), "CORPO")
    atributos = {"layer": camada}
    if elemento["tipo"] == "path":
        for pontos in _fechar(elemento["d"], pontos_do_path(elemento["d"])):
            alvo.add_lwpolyline(_transformar(elemento, pontos),
                                dxfattribs=atributos)
    elif elemento["tipo"] == "rect":
        x, y, w, h = (elemento["x"], elemento["y"], elemento["w"], elemento["h"])
        canto = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        alvo.add_lwpolyline(_transformar(elemento, canto), dxfattribs=atributos)
    elif elemento["tipo"] == "circulo":
        (cx, cy), = _transformar(elemento, [(elemento["cx"], elemento["cy"])])
        alvo.add_circle((cx, cy), elemento["r"], dxfattribs=atributos)
    elif elemento["tipo"] == "nota":
        (cx, cy), = _transformar(elemento, [(elemento["x"], elemento["y"])])
        texto = alvo.add_text(_sem_acento(elemento["texto"]),
                              height=ALTURA_TEXTO,
                              dxfattribs={"layer": "COTA"})
        texto.set_placement(
            (cx, cy),
            align=_ezdxf().enums.TextEntityAlignment.CENTER)


def _documento():
    doc = _ezdxf().new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4        # milimetro
    for nome, (cor, tipo) in CAMADAS.items():
        if nome not in doc.layers:
            doc.layers.add(nome, color=cor, linetype=tipo)
    return doc


def _assinatura(simbolo):
    return repr(simbolo.elementos)


def _variante(simbolo):
    """O que distingue duas pecas de mesmo rotulo - o motor, quase sempre."""
    p = simbolo.params
    for chave in ("carcaca_motor", "cv", "acionamento", "serie", "tipo"):
        if p.get(chave):
            return _nome_de_bloco(str(p[chave]))
    return ""


def bloco(doc, simbolo, nome=None):
    """Cria (ou reaproveita) o BLOCK de um simbolo. Devolve o nome.

    Duas pecas podem ter o mesmo rotulo e geometria diferente - a mesma bomba
    com dois motores e o caso que aparece na folha. Entao o nome nao basta:
    o bloco so e reaproveitado quando a geometria e a mesma, e quando nao e,
    o nome ganha o que as distingue.
    """
    doc.__dict__.setdefault("_assinaturas", {})
    assinaturas = doc.__dict__["_assinaturas"]
    marca = _assinatura(simbolo)
    base = nome or nome_do_bloco(simbolo)
    nome = base
    for tentativa in [base] + ([f"{base}_{_variante(simbolo)}"]
                               if _variante(simbolo) else []) \
            + [f"{base}_{k}" for k in range(2, 40)]:
        nome = tentativa
        if assinaturas.get(nome) == marca:
            return nome
        if nome not in doc.blocks:
            break
    assinaturas[nome] = marca
    definicao = doc.blocks.new(name=nome)
    # a descricao e o campo Description do CAD, o mesmo texto da lista
    definicao.block.dxf.description = _sem_acento(
        simbolo.params.get("descricao") or simbolo.rotulo)[:255]
    for elemento in simbolo.elementos:
        if elemento["tipo"] != "texto_furos":
            _desenhar(definicao, elemento)
    return nome


def escrever_pecas(caminho, simbolos, passo=None):
    """Uma folha de blocos: cada peca inserida uma vez, lado a lado.

    E a biblioteca que a casa ja tem em DWG, so que gerada - e completa, com
    a cota do fabricante em vez de um bloco por bitola desenhado a mao.
    """
    doc = _documento()
    modelo = doc.modelspace()
    x = 0.0
    for simbolo in simbolos:
        nome = bloco(doc, simbolo)
        _, _, larg, _ = simbolo.caixa
        modelo.add_blockref(nome, (x, 0))
        x += (passo or larg * 1.25)
    doc.saveas(caminho)
    return doc


def linha_em_dxf(postos, rotulo=None):
    """O documento DXF da linha montada, sem gravar em disco.

    Existe separado de escrever_linha porque a exportacao do programa devolve
    o CONTEUDO e nao um caminho: no navegador ele vira um download e no
    Electron o processo pai escolhe onde salvar. Gravar aqui obrigaria a
    inventar uma pasta.
    """
    doc = _documento()
    modelo = doc.modelspace()
    for posto in postos:
        nome = bloco(doc, posto.simbolo)
        modelo.add_blockref(nome, (posto.dx, -posto.dy),
                            dxfattribs={"rotation": -posto.giro})
    if rotulo:
        texto = modelo.add_text(_sem_acento(rotulo), height=ALTURA_TEXTO * 2,
                                dxfattribs={"layer": "COTA"})
        texto.set_placement((0, 0))
    return doc


def escrever_linha(caminho, postos, rotulo=None):
    """A linha montada em disco: um INSERT por peca, com a rotacao da corrente.

    A geometria nao e repetida - o bloco entra uma vez na tabela e a linha so
    aponta para ele, do mesmo jeito que um DWG de projeto faz.
    """
    doc = linha_em_dxf(postos, rotulo)
    doc.saveas(caminho)
    return doc


def texto_do_dxf(doc):
    """O DXF como texto, para quem vai mandar e nao gravar.

    A escala e 1:1 em milimetro, porque a geometria dos simbolos ja e em
    milimetro real - o desenho da tela e que e escalado, o DXF nao.
    """
    import io
    fluxo = io.StringIO()
    doc.write(fluxo)
    return fluxo.getvalue()
