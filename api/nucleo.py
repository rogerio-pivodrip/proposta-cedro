"""Recebe um comando, devolve o documento inteiro recalculado.

Esta e a unica funcao que a tela precisa conhecer. Ela nao decide nada: chama
o comando na `Linha` e serializa as duas projecoes dela. Toda regra mora no
motor, e e por isso que a mesma resposta serve ao navegador e ao Electron.

**Devolve o documento INTEIRO a cada comando, e nao um remendo.** Numa linha de
sessenta pecas isso e alguns kilobytes, e o que se ganha e que a tela nunca
pode divergir do modelo: ela nao acumula estado, so pinta o que chegou. Foi
essa a decisao que evitou a sincronizacao - ver docs/LOGICA.md 2.

O erro tambem e resposta, e nao excecao: `{"ok": false, "erro": ...}`. A tela
precisa mostrar o motivo, e nao um traceback.
"""
from motor import exportar as exportacao, folha, regras, templates, vista

from . import linguagem
from motor.catalogo import Catalogo
from motor.linha import Linha, Peca


class Erro(Exception):
    """O comando nao pode ser cumprido, e o motivo e para a pessoa ler."""


class Sessao:
    """Um documento aberto, com o catalogo que ele consulta."""

    def __init__(self, catalogo=None, tipo="RECALQUE", area="P01"):
        self.catalogo = catalogo or Catalogo()
        self.linha = Linha(self.catalogo, tipo=tipo, area=area)
        # o tamanho da area de desenho da tela. Fica na sessao porque o SVG
        # sai pronto do motor, ja escalado - a tela nao redesenha nada, so
        # avisa de quanto espaco dispoe
        self.janela = {"largura": 940, "altura_max": 620}
        # como o desenho e lido: tracado de projeto, preto e branco, ou
        # metalizado. E folha de estilo, nao geometria - a linha e a mesma
        self.modo = "traco"

    # ------------------------------------------------------------------ ler
    def documento(self):
        """As duas projecoes, mais o que a tela precisa para se desenhar."""
        linha = self.linha
        lista, avisos = linha.lista_materiais()
        return {
            "tipo": linha.tipo,
            "area": linha.area,
            "giro": linha.giro,
            "espelho": linha.espelho,
            "pecas": [_peca(p, self.catalogo) for p in linha.pecas],
            "geometria": [_ponto(g) for g in linha.geometria()],
            "juncoes": [_juncao(j) for j in linha.juncoes()],
            "trechos_retos": [_trecho(t) for t in linha.trechos_retos()],
            "lista": [dict(r) for r in lista],
            "avisos": list(avisos) + [
                f'{d["peca"].descricao}: desenhado com '
                f'{d["desenhado_mm"]/1000:g} m, cortado da barra de '
                f'{d["do_codigo_mm"]/1000:g} m que o código traz'
                for d in linha.divergencias()],
            "divergencias": [{"id": d["peca"].id, "sap": d["peca"].sap,
                              "desenhado_mm": d["desenhado_mm"],
                              "do_codigo_mm": d["do_codigo_mm"]}
                             for d in linha.divergencias()],
            "vista": vista.vista(linha, modo=self.modo, **self.janela),
            "pontas": vista.pontas_erradas(linha),
            "pode_desfazer": bool(linha.feitos),
            "pode_refazer": bool(linha.desfeitos),
            "historico": [c.nome for c in linha.feitos],
        }


def _peca(p, catalogo=None):
    # `barras` sao os comprimentos que a LISTA tem deste mesmo tubo. Vao no
    # documento porque a tela precisa deles para oferecer a escolha - e vem do
    # catalogo, e nao de uma tabela na tela, para que a medida oferecida seja
    # sempre uma medida que tem codigo
    barras = []
    if catalogo is not None and p.familia == "TUBO":
        barras = regras.escada_de_barras(catalogo.barras_irmas(p.item),
                                         p.item.get("comprimento_mm"))
    return {
        "barras": barras,
        "id": p.id, "sap": p.sap, "descricao": p.descricao,
        "familia": p.familia, "material": p.material,
        "dn": list(p.item.get("dn") or []), "unidade_dn": p.unidade_dn,
        "angulo": p.angulo, "sentido": p.sentido,
        "comprimento_mm": p.comprimento_mm,
        "fonte": p.fonte, "fonte_cota": p.fonte_cota,
        "rotulo": p.rotulo,
    }


def _ponto(g):
    return {
        "id": g["peca"].id,
        "de": list(g["de"]), "para": list(g["para"]),
        "canto": list(g["canto"]) if g["canto"] else None,
        "direcao": g["direcao"], "direcao_saida": g["direcao_saida"],
        "fonte_cota": g["fonte_cota"],
    }


def _juncao(j):
    return {"pos": j["pos"], "acao": j["acao"], "dados": _limpo(j["dados"]),
            "de": j["de"].id, "para": j["para"].id}


def _trecho(t):
    return {"id": t["peca"].id, "pos": t["pos"], "ok": t["ok"],
            "antes_mm": t["antes_mm"], "depois_mm": t["depois_mm"],
            "exige_antes_mm": t["exige_antes_mm"],
            "exige_depois_mm": t["exige_depois_mm"]}


def _limpo(valor):
    """Tupla vira lista: JSON nao tem tupla, e a tela nao precisa saber disso."""
    if isinstance(valor, dict):
        return {k: _limpo(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_limpo(v) for v in valor]
    return valor


# --------------------------------------------------------------- escrever
def _item(sessao, comando):
    """O item do catalogo que o comando pede - por SAP ou por familia e DN.

    Por SAP e o caminho normal: a tela ja escolheu na lista. Por familia e DN
    existe para o template e para quem esta montando na mao.
    """
    sap = comando.get("sap")
    if sap:
        item = sessao.catalogo.por_sap.get(sap)
        if not item:
            raise Erro(f"nao ha item {sap} no catalogo")
        return item
    familia, dn = comando.get("familia"), comando.get("dn")
    if not familia or dn is None:
        raise Erro("informe o sap, ou a familia e o dn")
    filtros = {k: comando[k] for k in ("angulo", "norma", "dn_saida",
                                       "acionamento", "comprimento_mm")
               if comando.get(k) is not None}
    item = sessao.catalogo.melhor(familia, dn, material=comando.get("material"),
                                  **filtros)
    if not item:
        raise Erro(f"a lista nao tem {familia} de {dn}")
    return item


def _inserir(sessao, comando):
    peca = Peca(_item(sessao, comando),
                comprimento_mm=comando.get("comprimento_mm"))
    sessao.linha.inserir(peca, comando.get("pos"))
    return {"peca": peca.id}


def _remover(sessao, comando):
    return {"peca": sessao.linha.remover(comando["alvo"]).id}


def _substituir(sessao, comando):
    peca = Peca(_item(sessao, comando),
                comprimento_mm=comando.get("comprimento_mm"))
    antiga = sessao.linha.substituir(comando["alvo"], peca)
    return {"peca": peca.id, "saiu": antiga.id}


def _esticar(sessao, comando):
    """Sobe ou desce o tubo escolhido para a proxima BARRA da lista.

    Esticar um tubo nao e alterar, e SUBSTITUIR - e a diferenca importa na
    hora de comprar. Um tubo de 8" de 1 m e um de 2 m sao dois codigos SAP
    diferentes na lista da Netafim; o comprimento nao e um parametro da mesma
    peca, e a peca. Por isso o id muda, como mudaria trocando a peca a mao.

    E os passos nao vem de uma tabela inventada aqui: vem do QUE A LISTA TEM
    para aquele tubo, naquela bitola, com aquelas pontas. Em 8" flangeado sao
    0,5 · 1 · 1,2 · 1,5 · 2 · 2,5 · 3 · 6 m; em K10 a lista nao tem o 0,5 nem
    o 1,2, e ai o passo pula. Uma tabela fixa ofereceria barra que ninguem
    vende.

    Para um comprimento que a lista NAO tem - a barra de 6 m cortada em 2,35 -
    o caminho e outro: `alterar` o comprimento, que mantem o codigo. Sao duas
    coisas de verdade diferentes, e o programa nao as mistura.
    """
    alvo = comando.get("alvo")
    if not alvo:
        raise Erro("esticar age sobre uma peca - escolha um tubo antes")
    peca = sessao.linha.pecas[sessao.linha.posicao(alvo)]
    if peca.familia != "TUBO":
        raise Erro(f"{peca.descricao} nao e tubo - so o tubo se estica, "
                   f"porque so ele se corta")
    irmas = sessao.catalogo.barras_irmas(peca.item)
    atual = peca.item.get("comprimento_mm") or peca.comprimento_mm or 0
    # a escada e o padrao da casa CRUZADO com o que a lista tem - ver
    # regras.escada_de_barras. Andar pela lista inteira faria `esticar` parar
    # em 1,2 e 2,5 m, que sao encomenda e nao degrau de projeto
    tamanhos = regras.escada_de_barras(irmas, atual)
    lista = " · ".join(f"{c/1000:g}" for c in tamanhos) + " m"
    if len(tamanhos) < 2:
        raise Erro(f"a lista so tem uma barra deste tubo: {lista}")
    if comando.get("para_mm") is not None:
        # comprimento pedido de uma vez: so vale se a lista tiver o codigo.
        # E o ponto todo - a medida do desenho tem de ser a medida que se
        # compra, e um numero sem codigo atras nao e uma barra, e um corte
        pedido = float(comando["para_mm"])
        # aqui vale a lista INTEIRA, e nao so a escada: quem digitou 2,5 m
        # sabe o que quer, e o codigo existe. A escada e para andar de degrau
        exato = next((c for c in irmas if abs(c - pedido) < 1), None)
        if exato is not None and exato not in tamanhos:
            tamanhos = sorted(tamanhos + [exato])
        if exato is None:
            raise Erro(f"a lista nao tem barra de {pedido/1000:g} m deste "
                       f"tubo - ela tem {lista}. Para cortar uma barra maior, "
                       f"use `comprimento`, que mantem o codigo e escreve o "
                       f"corte na folha")
        destino = tamanhos.index(exato)
        passos = 0
    else:
        passos = int(comando.get("passos") or 1)
        perto = min(range(len(tamanhos)),
                    key=lambda k: abs(tamanhos[k] - atual))
        destino = perto + passos
    if not 0 <= destino < len(tamanhos):
        ponta = "maior" if passos > 0 else "menor"
        raise Erro(f"a lista nao tem barra {ponta} que {atual/1000:g} m - "
                   f"ela tem {lista}")
    nova = Peca(irmas[tamanhos[destino]])
    antiga = sessao.linha.substituir(alvo, nova)
    return {"peca": nova.id, "saiu": antiga.id, "de_mm": atual,
            "para_mm": tamanhos[destino], "tamanhos": tamanhos}


def _alterar(sessao, comando):
    campos = comando.get("campos") or {}
    if not campos:
        raise Erro("alterar sem campo nenhum")
    return {"peca": sessao.linha.alterar(comando["alvo"], **campos).id}


def _mover(sessao, comando):
    return {"peca": sessao.linha.mover(comando["alvo"], comando["para"]).id}


def _girar(sessao, comando):
    """Gira a linha inteira na folha. `graus` e relativo, `para` e absoluto.

    Nao existe girar UMA peca: a peca de uma linha nao tem posicao propria,
    ela cai onde a anterior deixou. Girar uma no meio da corrente abriria a
    linha no ar. O que a peca tem e espelho - ver _espelhar.
    """
    if comando.get("alvo"):
        raise Erro("girar e da linha inteira - para virar uma peca, espelhar")
    if comando.get("para") is not None:
        sessao.linha.pose(giro=float(comando["para"]))
    else:
        sessao.linha.pose(giro=sessao.linha.giro + float(comando.get("graus", 90)))
    return {"giro": sessao.linha.giro}


def _espelhar(sessao, comando):
    """Vira a peca de cabeca para baixo - ou a linha inteira, sem alvo.

    Na peca isto e `alterar(sentido)`, e nao um comando novo: espelhar nao
    troca o codigo que se compra, e por isso a peca mantem o id e a lista de
    materiais nao muda. E a mesma curva, montada para o outro lado.
    """
    alvo = comando.get("alvo")
    if not alvo:
        sessao.linha.pose(espelho=-sessao.linha.espelho)
        return {"espelho": sessao.linha.espelho}
    pos = sessao.linha.posicao(alvo)
    peca = sessao.linha.pecas[pos]
    return {"peca": sessao.linha.alterar(alvo, sentido=-peca.sentido).id}


def _desfazer(sessao, comando):
    feito = sessao.linha.desfazer()
    if feito is None:
        raise Erro("nao ha o que desfazer")
    return {"comando": feito.nome, "peca": feito.alvo}


def _refazer(sessao, comando):
    feito = sessao.linha.refazer()
    if feito is None:
        raise Erro("nao ha o que refazer")
    return {"comando": feito.nome, "peca": feito.alvo}


def _template(sessao, comando):
    """Monta uma linha pronta - e o comeco de todo projeto real.

    O `faltando` do template vem junto na resposta e nao vira excecao: a lista
    nao ter a peca e informacao de projeto, do mesmo jeito que na folha de
    simbolos. O template monta o que da e diz o que nao deu.
    """
    nome = comando.get("template", "SUCCAO")
    dn = comando.get("dn")
    if dn is None:
        raise Erro("o template precisa da bitola da linha")
    if nome == "SUCCAO":
        linha, _reducao, faltando = templates.succao(
            sessao.catalogo, dn, modelo_bomba=comando.get("bomba"),
            curva=comando.get("curva"))
        sessao.linha = linha
    elif nome == "PEAD":
        itens, faltando = templates.trecho_pead(sessao.catalogo, dn)
        for item, quantas in itens:
            for _ in range(quantas):
                sessao.linha.inserir(Peca(item))
    else:
        raise Erro(f"nao ha template {nome}")
    return {"template": nome, "pecas": len(sessao.linha.pecas),
            "faltando": [{"familia": f, "dn": d, "filtros": _limpo(e)}
                         for f, d, e in faltando]}


def _vocabulario(sessao, comando):
    """Os verbos da barra de comando. A tela pede uma vez e completa sozinha.

    Se a tela tivesse a propria lista, um verbo novo no motor nao apareceria
    na barra e um verbo removido continuaria sendo oferecido - a mesma
    divergencia que ela evita nao guardando documento.
    """
    return {"verbos": linguagem.vocabulario()}


def _procurar(sessao, comando):
    """Busca por texto livre no catalogo - codigo, nome, familia, bitola."""
    texto = comando.get("texto") or ""
    achados = sessao.catalogo.procurar(texto, comando.get("limite", 12))
    return {"texto": texto,
            "itens": [{"sap": i["sap"], "descricao": i["descricao"],
                       "familia": i["familia"], "material": i["material"],
                       "dn": list(i["dn"] or [])} for i in achados]}


def _catalogo(sessao, comando):
    """O que a lista tem para essa familia e bitola - para a tela oferecer."""
    familia, dn = comando.get("familia"), comando.get("dn")
    if not familia or dn is None:
        raise Erro("informe a familia e o dn")
    achados = sessao.catalogo.buscar(familia, dn,
                                     material=comando.get("material"))
    return {"itens": [{"sap": i["sap"], "descricao": i["descricao"],
                       "dn": list(i["dn"] or []), "material": i["material"],
                       "angulo": i["angulo"]}
                      for i in achados[:comando.get("limite", 40)]]}


def _simular(sessao, comando):
    """Responde o que ACONTECERIA, sem deixar nada aplicado.

    A simulacao e o comando de verdade, executado e desfeito. Nao ha segundo
    caminho de codigo, e por isso nao ha como a previsao discordar do
    resultado - que e o defeito classico de quem escreve um "validador" ao lado
    do comando.

    Da para fazer isso porque desfazer e exato: conferir_comandos.py cobra que
    o documento volte identico nas duas projecoes. Se nao fosse, arrastar uma
    peca sujaria o desenho.

    O historico fica limpo nas duas pontas - o comando sai dos feitos ao
    desfazer, e sai dos desfeitos aqui, para nao aparecer um "refazer" de algo
    que a pessoa nunca fez.
    """
    dentro = dict(comando.get("comando") or {})
    if not dentro.get("nome"):
        raise Erro("simular precisa do comando a simular")
    if dentro["nome"] in ("simular", "desfazer", "refazer", "template"):
        raise Erro(f'nao da para simular {dentro["nome"]}')
    antes = len(sessao.linha.feitos)
    resposta = executar(sessao, dentro)
    aplicou = len(sessao.linha.feitos) > antes
    depois = None
    if resposta.get("ok"):
        depois = {"juncoes": resposta["documento"]["juncoes"],
                  "trechos_retos": resposta["documento"]["trechos_retos"],
                  "avisos": resposta["documento"]["avisos"],
                  "pecas": [p["id"] for p in resposta["documento"]["pecas"]]}
    if aplicou:
        sessao.linha.desfazer()
        sessao.linha.desfeitos.pop()          # nem no refazer isto aparece
    return {"seria": depois, "recusa": None if resposta.get("ok")
            else resposta.get("erro")}


def _exportar(sessao, comando):
    """O documento em DXF, SVG, XLSX ou CSV. Devolve o CONTEUDO.

    Nao grava em disco: no navegador isto vira um download e no Electron o
    processo pai escolhe onde salvar. O binario vai em base64 porque o
    protocolo e JSON de uma linha.
    """
    import base64

    formato = (comando.get("formato") or "dxf").lower()
    ficha = exportacao.FORMATOS.get(formato)
    if not ficha:
        raise Erro(f"nao exporto {formato} - so "
                   f'{", ".join(sorted(exportacao.FORMATOS))}')
    if not sessao.linha.pecas:
        raise Erro("a linha esta vazia")
    tipo, extensao, mime = ficha
    nome = comando.get("arquivo") or f"{sessao.linha.tipo.lower()}.{extensao}"
    rotulo = comando.get("rotulo") or f"{sessao.linha.tipo} {sessao.linha.area}"
    recusadas = []
    # desenhar nao precisa de biblioteca nenhuma; exportar precisa, e so na
    # hora. Quem so quer montar e ver a linha nao instala nada - e quando
    # precisar, a recusa diz o que instalar em vez de estourar um traceback
    try:
        if formato == "dxf":
            conteudo, recusadas = exportacao.para_dxf(sessao.linha, rotulo)
        elif formato == "svg":
            conteudo, recusadas = exportacao.para_svg(sessao.linha,
                                                      modo=sessao.modo)
        elif formato == "csv":
            conteudo, _ = exportacao.para_csv(sessao.linha)
        else:
            conteudo, _ = exportacao.para_xlsx(sessao.linha)
    except ImportError as erro:
        pacote = {"dxf": "ezdxf", "xlsx": "openpyxl"}.get(formato, "?")
        raise Erro(f"para exportar {formato} falta a biblioteca {pacote} - "
                   f"instale com: pip install {pacote}") from erro
    saida = {"formato": formato, "arquivo": nome, "mime": mime,
             "recusadas": recusadas}
    if tipo == "binario":
        saida["base64"] = base64.b64encode(conteudo).decode("ascii")
        saida["bytes"] = len(conteudo)
    else:
        saida["texto"] = conteudo
        saida["bytes"] = len(conteudo.encode("utf-8"))
    return saida


def _folha(sessao, comando):
    """A prancha de impressao: desenho em escala, lista e carimbo.

    E o terceiro formato de saida, e o unico para quem vai ASSINAR - DXF e
    planilha sao para quem vai continuar trabalhando no arquivo. Devolve HTML
    porque o navegador imprime, e assim o programa continua rodando sem
    instalar biblioteca de PDF.
    """
    if not sessao.linha.pecas:
        raise Erro("a linha esta vazia")
    formato = (comando.get("formato") or "A3").upper()
    if formato not in folha.FORMATOS:
        raise Erro(f"nao conheco o formato {formato} - so "
                   f'{", ".join(folha.FORMATOS)}')
    html, ficha = folha.montar(
        sessao.linha, formato=formato,
        orientacao=comando.get("orientacao") or "paisagem",
        titulo=comando.get("titulo"), modo=sessao.modo)
    return {"html": html, "arquivo": f"{sessao.linha.tipo.lower()}-"
                                    f"{sessao.linha.area.lower()}.html", **ficha}


def _estilo(sessao, comando):
    """O CSS do desenho, do motor. A tela pede uma vez e nao copia nada.

    Se a tela tivesse a propria copia, o traco da tela e o da folha de
    simbolos divergiriam no primeiro ajuste - e o traco e do desenho, nao da
    interface.
    """
    return {"css": vista.ESTILO}


def _modo(sessao, comando):
    """Troca a leitura do desenho. Nao mexe em peca nenhuma.

    Por isso nao entra no historico: desfazer e para edicao, e trocar de modo
    nao edita o documento - e o mesmo desenho visto de outro jeito.
    """
    pedido = (comando.get("modo") or "").lower()
    if pedido not in vista.MODOS:
        raise Erro(f"nao conheco o modo {pedido!r} - so "
                   f'{", ".join(vista.MODOS)}')
    sessao.modo = pedido
    return {"modo": sessao.modo}


def _janela(sessao, comando):
    """Diz ao motor de quanto espaco a tela dispoe, em pixel."""
    for campo in ("largura", "altura_max"):
        if comando.get(campo):
            sessao.janela[campo] = max(200, int(comando[campo]))
    return dict(sessao.janela)


COMANDOS = {
    "inserir": _inserir, "remover": _remover, "substituir": _substituir,
    "alterar": _alterar, "mover": _mover, "esticar": _esticar,
    "girar": _girar, "espelhar": _espelhar,
    "desfazer": _desfazer, "refazer": _refazer,
    "template": _template, "catalogo": _catalogo, "janela": _janela,
    "modo": _modo,
    "estilo": _estilo, "simular": _simular, "exportar": _exportar,
    "vocabulario": _vocabulario, "procurar": _procurar, "folha": _folha,
    # ler nao muda nada, e por isso nao entra no historico
    "documento": lambda sessao, comando: {},
}


def executar(sessao, comando):
    """Aplica um comando e devolve o documento inteiro.

    A resposta traz sempre o documento, mesmo no erro: a tela que pediu algo
    invalido precisa continuar mostrando o que existe, e nao ficar em branco.
    """
    nome = (comando or {}).get("nome")
    if nome == "dizer":
        # a barra de comando: uma linha digitada vira um comando de verdade e
        # segue o MESMO caminho de todos os outros. Nao ha atalho aqui - o que
        # a barra faz, o botao tambem faz, e os dois desfazem igual
        try:
            interno, entendido = linguagem.interpretar(
                comando.get("texto"), comando.get("alvo"), sessao)
        except linguagem.Erro as erro:
            return {"ok": False, "erro": str(erro), "entendido": None,
                    "documento": sessao.documento()}
        resposta = executar(sessao, interno)
        resposta["entendido"] = entendido
        return resposta
    funcao = COMANDOS.get(nome)
    if funcao is None:
        return {"ok": False, "erro": f"comando desconhecido: {nome!r}",
                "conhecidos": sorted(COMANDOS),
                "documento": sessao.documento()}
    try:
        extra = funcao(sessao, comando) or {}
    except Erro as erro:
        return {"ok": False, "erro": str(erro), "documento": sessao.documento()}
    except (KeyError, IndexError, ValueError) as erro:
        # o motor recusou: e resposta, nao defeito
        return {"ok": False, "erro": f"{type(erro).__name__}: {erro}",
                "documento": sessao.documento()}
    return {"ok": True, "comando": nome, **extra,
            "documento": sessao.documento()}
