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
from motor import templates
from motor.catalogo import Catalogo
from motor.linha import Linha, Peca


class Erro(Exception):
    """O comando nao pode ser cumprido, e o motivo e para a pessoa ler."""


class Sessao:
    """Um documento aberto, com o catalogo que ele consulta."""

    def __init__(self, catalogo=None, tipo="RECALQUE", area="P01"):
        self.catalogo = catalogo or Catalogo()
        self.linha = Linha(self.catalogo, tipo=tipo, area=area)

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


COMANDOS = {
    "inserir": _inserir, "remover": _remover, "substituir": _substituir,
    "alterar": _alterar, "mover": _mover,
    "desfazer": _desfazer, "refazer": _refazer,
    "template": _template, "catalogo": _catalogo,
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
