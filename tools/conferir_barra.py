#!/usr/bin/env python3
"""Confere a barra de comando: a linha digitada e o botao dao no mesmo.

A barra e uma segunda porta para os mesmos comandos, e uma segunda porta e
onde nascem duas verdades. Entao o que se cobra aqui nao e "o comando roda":

  **A barra e o botao seguem o MESMO caminho.** `girar 90` digitado e o botao
  de girar tem de deixar o documento identico - inclusive o historico, para
  que um desfazer volte igual dos dois lados. Se a barra tivesse atalho
  proprio, seria uma edicao que o desfazer nao conhece.

  **O exemplo de cada verbo funciona.** O vocabulario que a tela mostra traz
  um exemplo por verbo; ele e o que a pessoa vai copiar. Um exemplo que nao
  roda e pior que exemplo nenhum, e este teste cobra todos.

  **O prefixo resolve, e a ambiguidade recusa dizendo as opcoes.** `des`
  desfaz; `m` nao adivinha entre montar, mover e modo.

  **Numero solto e bitola.** Procurar "curva 8" por substring devolve 18" e
  20" - e o defeito que a busca tem de nao ter.

Uso: python3 tools/conferir_barra.py
"""
import re
import sys

sys.path.insert(0, ".")
from api import linguagem                            # noqa: E402
from api.nucleo import Sessao, executar              # noqa: E402


def _conteudo(documento):
    """O documento comparavel: sem historico e com os ids renumerados.

    O id da peca nasce de um contador global e nunca se repete - duas
    execucoes do mesmo comando dao ids diferentes para a mesma peca. Renumerar
    por POSICAO e o que deixa comparar duas execucoes sem afrouxar a
    comparacao: tudo o mais tem de bater exatamente, ids inclusive, so que na
    forma "a primeira peca", "a segunda".
    """
    limpo = {k: v for k, v in documento.items()
             if k not in ("pode_desfazer", "pode_refazer", "historico")}
    mapa = {p["id"]: f"#{i}" for i, p in enumerate(documento["pecas"])}

    def trocar(valor):
        if isinstance(valor, dict):
            return {k: trocar(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [trocar(v) for v in valor]
        if not isinstance(valor, str):
            return valor
        if valor in mapa:
            return mapa[valor]
        # o id tambem aparece DENTRO do SVG, em data-id - e e por ele que o
        # desenho e a tabela sao a mesma peca. Sem trocar ali, duas execucoes
        # do mesmo comando divergiriam so no numero do contador
        return re.sub(r"\bp\d+\b", lambda m: mapa.get(m.group(), m.group()),
                      valor) if "p" in valor else valor

    return trocar(limpo)


def main():
    problemas = []

    def conferir(caso, condicao, detalhe=""):
        if condicao:
            print(f"  ok {caso}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}" + (f": {detalhe}" if detalhe else ""))

    print("== o exemplo de cada verbo funciona")
    for verbo in linguagem.VERBOS:
        # uma sessao com historico dos DOIS lados: sem isso `refazer` recusa
        # por falta de futuro, e o exemplo dele apareceria como defeito
        sessao = Sessao()
        executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
        executar(sessao, {"nome": "inserir", "sap": "01523-134000"})
        executar(sessao, {"nome": "desfazer"})
        # o alvo e o TUBO, e nao a primeira peca: `esticar` so vale em tubo,
        # e o exemplo tem de rodar sobre uma peca em que ele faz sentido
        pecas = sessao.documento()["pecas"]
        alvo = next((p["id"] for p in pecas if p["familia"] == "TUBO"),
                    pecas[0]["id"])
        resposta = executar(sessao, {"nome": "dizer", "texto": verbo.exemplo,
                                     "alvo": alvo})
        conferir(f'{verbo.nome}: "{verbo.exemplo}"', resposta["ok"],
                 resposta.get("erro", ""))

    print("\n== a barra e o botão dão no mesmo")
    # a MESMA sessao nos dois lados, e nao duas: peca nova ganha id novo, e
    # duas sessoes nunca teriam os mesmos ids para comparar
    for texto, comando in (("girar 90", {"nome": "girar", "graus": 90}),
                           ("modo metal", {"nome": "modo", "modo": "metal"}),
                           ("inserir 01523-134000",
                            {"nome": "inserir", "sap": "01523-134000"})):
        sessao = Sessao()
        executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
        marco = len(sessao.linha.feitos)
        executar(sessao, {"nome": "dizer", "texto": texto})
        pela_barra = _conteudo(sessao.documento())
        historico_barra = [c.nome for c in sessao.linha.feitos[marco:]]
        while len(sessao.linha.feitos) > marco:
            executar(sessao, {"nome": "desfazer"})
        executar(sessao, comando)
        conferir(f'"{texto}" == {comando["nome"]}',
                 _conteudo(sessao.documento()) == pela_barra)
        conferir(f'"{texto}" entra no histórico como o botão',
                 historico_barra == [c.nome for c in sessao.linha.feitos[marco:]],
                 f'{historico_barra} vs '
                 f'{[c.nome for c in sessao.linha.feitos[marco:]]}')

    print("\n== desfazer volta o que a barra fez")
    sessao = Sessao()
    executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
    antes = _conteudo(sessao.documento())
    executar(sessao, {"nome": "dizer", "texto": "inserir curva 90 8"})
    mudou = _conteudo(sessao.documento()) != antes
    executar(sessao, {"nome": "dizer", "texto": "desfazer"})
    conferir("inserir pela barra mudou alguma coisa", mudou)
    conferir("desfazer devolve ao estado exato",
             _conteudo(sessao.documento()) == antes)

    print("\n== o argumento vai pelo tipo, e não pela posição")
    sessao = Sessao()
    a, _ = linguagem.interpretar("montar succao 8", None, sessao)
    b, _ = linguagem.interpretar("montar 8 succao", None, sessao)
    conferir("montar succao 8 == montar 8 succao", a == b, f"{a} · {b}")
    c, _ = linguagem.interpretar("montar 8", None, sessao)
    conferir("montar 8 assume sucção", c["template"] == "SUCCAO", str(c))

    print("\n== prefixo resolve, ambiguidade recusa")
    sessao = Sessao()
    for texto, espera in (("des", "desfazer"), ("gir", "girar"),
                          ("expor", "exportar")):
        try:
            achado = linguagem.achar(texto).nome
        except linguagem.Erro as erro:
            achado = str(erro)
        conferir(f'"{texto}" → {espera}', achado == espera, achado)
    for texto, dentro in (("m", "montar"), ("xis", "não conheço")):
        try:
            linguagem.achar(texto)
            conferir(f'"{texto}" é recusado', False, "passou")
        except linguagem.Erro as erro:
            conferir(f'"{texto}" é recusado dizendo por quê', dentro in str(erro),
                     str(erro))

    print("\n== verbo que age sobre peça recusa sem peça escolhida")
    sessao = Sessao()
    executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
    for verbo in (v for v in linguagem.VERBOS if v.precisa_alvo):
        resposta = executar(sessao, {"nome": "dizer", "texto": verbo.exemplo})
        conferir(f"{verbo.nome} sem alvo recusa com motivo",
                 not resposta["ok"] and "escolha uma" in (resposta["erro"] or ""),
                 resposta.get("erro", "passou"))

    print("\n== esticar só vale em tubo, e só nas barras que a lista tem")
    sessao = Sessao()
    executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
    pecas = sessao.documento()["pecas"]
    tubo = next(p for p in pecas if p["familia"] == "TUBO")
    outra = next(p for p in pecas if p["familia"] != "TUBO")
    recusa = executar(sessao, {"nome": "esticar", "alvo": outra["id"]})
    conferir("no que não é tubo, recusa dizendo por quê",
             not recusa["ok"] and "nao e tubo" in (recusa["erro"] or ""),
             recusa.get("erro", "passou"))
    barras = tubo["barras"]
    from motor import regras                          # noqa: E402
    conferir("o seletor traz as barras padrão da casa",
             tuple(barras) == regras.BARRAS_PADRAO_MM, str(barras))
    todas = sessao.catalogo.barras_irmas(
        sessao.catalogo.por_sap[tubo["sap"]])
    conferir("e só as que a lista tem código para este tubo",
             set(barras) <= set(todas),
             f"{sorted(set(barras) - set(todas))} sem código")
    conferir("a encomenda fica de fora do degrau",
             set(todas) - set(barras),
             "a lista não tem nada além do padrão neste tubo")
    subiu = executar(sessao, {"nome": "esticar", "alvo": tubo["id"]})
    conferir("esticar sobe um DEGRAU, e não para na encomenda",
             subiu["ok"] and subiu["para_mm"] == barras[barras.index(
                 tubo["comprimento_mm"]) + 1],
             f'{subiu.get("para_mm")} depois de {tubo["comprimento_mm"]}')
    conferir("e TROCA a peça - outro comprimento é outro código",
             subiu.get("peca") != tubo["id"])
    novo_tubo = next(p for p in subiu["documento"]["pecas"]
                     if p["id"] == subiu["peca"])
    conferir("a medida desenhada é a medida do código",
             novo_tubo["comprimento_mm"] == subiu["para_mm"],
             f'{novo_tubo["comprimento_mm"]} contra {subiu["para_mm"]}')
    sem_codigo = executar(sessao, {"nome": "esticar", "alvo": subiu["peca"],
                                   "para_mm": 2350})
    conferir("medida sem código é recusada, dizendo as que existem",
             not sem_codigo["ok"] and "2.35" in (sem_codigo["erro"] or ""),
             sem_codigo.get("erro", "passou"))

    print("\n== cortar é legítimo, mas nunca calado")
    executar(sessao, {"nome": "alterar", "alvo": subiu["peca"],
                      "campos": {"comprimento_mm": 2350}})
    documento = sessao.documento()
    conferir("o documento passa a trazer a divergência",
             len(documento["divergencias"]) == 1
             and documento["divergencias"][0]["desenhado_mm"] == 2350,
             str(documento["divergencias"]))
    conferir("e ela vira aviso, que é o que vai para a folha",
             any("cortado da barra" in a for a in documento["avisos"]),
             str(documento["avisos"][-1:]))

    print("\n== número solto é bitola, e não pedaço de texto")
    sessao = Sessao()
    for texto, espera in (("curva 90 8", 8.0), ("crivo 8", 8.0),
                          ("borboleta 10", 10.0)):
        itens = executar(sessao, {"nome": "procurar", "texto": texto,
                                  "limite": 3})["itens"]
        conferir(f'"{texto}" só devolve {espera:g}"',
                 itens and all(espera in i["dn"] for i in itens),
                 ", ".join(f'{i["sap"]} {i["dn"]}' for i in itens) or "nada")

    print("\n== o vocabulário que a tela recebe está completo")
    verbos = executar(Sessao(), {"nome": "vocabulario"})["verbos"]
    conferir("um verbo por verbo", len(verbos) == len(linguagem.VERBOS))
    conferir("todo verbo traz resumo e exemplo",
             all(v["resumo"] and v["exemplo"] for v in verbos))

    print(f"\n{len(problemas)} problemas")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
