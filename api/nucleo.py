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
from motor import exportar as exportacao, templates, vista
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

    # ------------------------------------------------------------------ ler
    def documento(self):
        """As duas projecoes, mais o que a tela precisa para se desenhar."""
        linha = self.linha
        lista, avisos = linha.lista_materiais()
        return {
            "tipo": linha.tipo,
            "area": linha.area,
            "pecas": [_peca(p) for p in linha.pecas],
            "geometria": [_ponto(g) for g in linha.geometria()],
            "juncoes": [_juncao(j) for j in linha.juncoes()],
            "trechos_retos": [_trecho(t) for t in linha.trechos_retos()],
            "lista": [dict(r) for r in lista],
            "avisos": list(avisos),
            "vista": vista.vista(linha, **self.janela),
            "pode_desfazer": bool(linha.feitos),
            "pode_refazer": bool(linha.desfeitos),
            "historico": [c.nome for c in linha.feitos],
        }


def _peca(p):
    return {
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


def _alterar(sessao, comando):
    campos = comando.get("campos") or {}
    if not campos:
        raise Erro("alterar sem campo nenhum")
    return {"peca": sessao.linha.alterar(comando["alvo"], **campos).id}


def _mover(sessao, comando):
    return {"peca": sessao.linha.mover(comando["alvo"], comando["para"]).id}


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
    if formato == "dxf":
        conteudo, recusadas = exportacao.para_dxf(sessao.linha, rotulo)
    elif formato == "svg":
        conteudo, recusadas = exportacao.para_svg(sessao.linha)
    elif formato == "csv":
        conteudo, _ = exportacao.para_csv(sessao.linha)
    else:
        conteudo, _ = exportacao.para_xlsx(sessao.linha)
    saida = {"formato": formato, "arquivo": nome, "mime": mime,
             "recusadas": recusadas}
    if tipo == "binario":
        saida["base64"] = base64.b64encode(conteudo).decode("ascii")
        saida["bytes"] = len(conteudo)
    else:
        saida["texto"] = conteudo
        saida["bytes"] = len(conteudo.encode("utf-8"))
    return saida


def _estilo(sessao, comando):
    """O CSS do desenho, do motor. A tela pede uma vez e nao copia nada.

    Se a tela tivesse a propria copia, o traco da tela e o da folha de
    simbolos divergiriam no primeiro ajuste - e o traco e do desenho, nao da
    interface.
    """
    return {"css": vista.ESTILO}


def _janela(sessao, comando):
    """Diz ao motor de quanto espaco a tela dispoe, em pixel."""
    for campo in ("largura", "altura_max"):
        if comando.get(campo):
            sessao.janela[campo] = max(200, int(comando[campo]))
    return dict(sessao.janela)


COMANDOS = {
    "inserir": _inserir, "remover": _remover, "substituir": _substituir,
    "alterar": _alterar, "mover": _mover,
    "desfazer": _desfazer, "refazer": _refazer,
    "template": _template, "catalogo": _catalogo, "janela": _janela,
    "estilo": _estilo, "simular": _simular, "exportar": _exportar,
    # ler nao muda nada, e por isso nao entra no historico
    "documento": lambda sessao, comando: {},
}


def executar(sessao, comando):
    """Aplica um comando e devolve o documento inteiro.

    A resposta traz sempre o documento, mesmo no erro: a tela que pediu algo
    invalido precisa continuar mostrando o que existe, e nao ficar em branco.
    """
    nome = (comando or {}).get("nome")
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
