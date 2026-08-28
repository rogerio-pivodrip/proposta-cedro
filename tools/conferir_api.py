#!/usr/bin/env python3
"""Confere a camada fina: ela traduz, e nao decide.

Tres coisas precisam ser verdade, e nenhuma delas e "a API responde":

  **O documento atravessa o JSON inteiro.** Se sobrar tupla, objeto ou float
  que nao serializa, a tela recebe um erro em vez do desenho - e o defeito
  aparece longe daqui. Entao o teste serializa e desserializa de verdade.

  **Desfazer pela API devolve o documento identico.** E a mesma garantia que
  conferir_comandos.py cobra do motor, agora atravessada pela camada: se a
  camada guardasse estado proprio, e aqui que apareceria.

  **A casca e descartavel.** A mesma sequencia de comandos pelo nucleo e pelo
  processo filho (api/stdio.py) tem de dar exatamente os mesmos documentos. Se
  divergirem, a casca ganhou regra - e regra na casca e regra repetida, porque
  o Electron e o navegador usam cascas diferentes.

E uma quarta, que e de postura: **erro e resposta, nao excecao.** A tela que
pediu algo invalido continua mostrando o que existe.

Uso: python3 tools/conferir_api.py
"""
import json
import subprocess
import sys

sys.path.insert(0, ".")
from api import Sessao, executar          # noqa: E402

ROTEIRO = [
    {"nome": "template", "template": "SUCCAO", "dn": 8, "curva": 90},
    {"nome": "inserir", "familia": "TUBO", "dn": 8, "comprimento_mm": 6000},
    {"nome": "inserir", "familia": "VALVULA_BORBOLETA", "dn": 8},
    {"nome": "mover", "alvo": -1, "para": 0},
    {"nome": "alterar", "alvo": 0, "campos": {"rotulo": "TR-01"}},
    {"nome": "desfazer"},
    {"nome": "refazer"},
    {"nome": "remover", "alvo": -1},
    {"nome": "documento"},
]


def pelo_nucleo(roteiro):
    sessao = Sessao()
    return [executar(sessao, dict(c)) for c in roteiro]


def pelo_processo(roteiro):
    entrada = "\n".join(json.dumps(c) for c in roteiro) + "\n"
    saida = subprocess.run([sys.executable, "-m", "api.stdio"],
                           input=entrada, capture_output=True, text=True,
                           cwd=".")
    if saida.returncode != 0:
        print(saida.stderr, file=sys.stderr)
        raise SystemExit("o processo filho morreu")
    return [json.loads(ln) for ln in saida.stdout.splitlines() if ln.strip()]


def main():
    problemas = []

    def conferir(caso, condicao, detalhe=""):
        if condicao:
            print(f"  ok {caso}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}" + (f": {detalhe}" if detalhe else ""))

    print("== o documento atravessa o JSON")
    respostas = pelo_nucleo(ROTEIRO)
    for comando, resposta in zip(ROTEIRO, respostas):
        try:
            volta = json.loads(json.dumps(resposta, ensure_ascii=False))
        except (TypeError, ValueError) as erro:
            conferir(f"{comando['nome']} serializa", False, str(erro))
            continue
        conferir(f"{comando['nome']} serializa e volta igual",
                 volta == resposta)

    print("\n== a casca é descartável")
    do_processo = pelo_processo(ROTEIRO)
    conferir("o processo respondeu a todos",
             len(do_processo) == len(ROTEIRO),
             f"{len(do_processo)} de {len(ROTEIRO)}")
    for i, (a, b) in enumerate(zip(respostas, do_processo)):
        # o id da peca e sequencial por processo, entao o que se compara e o
        # documento com os ids normalizados pela ordem em que aparecem
        conferir(f"comando {i + 1} ({ROTEIRO[i]['nome']}) dá o mesmo documento",
                 _sem_id(a) == _sem_id(b))

    print("\n== desfazer pela API devolve o documento idêntico")
    sessao = Sessao()
    executar(sessao, {"nome": "template", "template": "SUCCAO", "dn": 8})
    antes = _conteudo(sessao)
    executar(sessao, {"nome": "inserir", "familia": "TUBO", "dn": 8,
                      "comprimento_mm": 2500})
    depois = _conteudo(sessao)
    conferir("inserir mudou alguma coisa", antes != depois)
    executar(sessao, {"nome": "desfazer"})
    conferir("desfazer volta ao anterior", _conteudo(sessao) == antes)
    executar(sessao, {"nome": "refazer"})
    conferir("refazer volta ao posterior", _conteudo(sessao) == depois)

    print("\n== trocar a bitola da linha inteira, num comando só")
    sessao = Sessao()
    executar(sessao, {"nome": "template", "template": "RECALQUE", "dn": 6})
    antes = _conteudo(sessao)
    resposta = executar(sessao, {"nome": "bitola", "dn": 8})
    conferir("a linha inteira trocou", resposta["ok"]
             and len(resposta["trocas"]) > 5,
             str(len(resposta.get("trocas") or [])))
    pecas = resposta["documento"]["pecas"]
    conferir("nenhuma peça sobrou na bitola antiga",
             not [p for p in pecas if 6.0 in (p["dn"] or [])
                  and p["familia"] in ("CURVA", "TUBO", "TE")],
             str([p["descricao"] for p in pecas if 6.0 in (p["dn"] or [])]))
    # a VENTOSA de 2" nao e da linha: ela enrosca na luva da flange cega, e a
    # bitola dela nunca foi a da linha. Trocar 6 por 8 nao pode leva-la junto
    ventosa = [a for p in pecas for a in p["acessorios"]
               if a["familia"] == "VENTOSA"]
    conferir("a ventosa de 2\" continua de 2\"",
             bool(ventosa) and '2"' in ventosa[0]["descricao"],
             str([a["descricao"] for a in ventosa]))
    conferir("e o que a lista não tem naquela bitola vira aviso escrito",
             any("não tem" in a for a in (resposta.get("recado") or [])),
             str(resposta.get("recado")))
    executar(sessao, {"nome": "desfazer"})
    conferir("e um desfazer devolve a linha inteira",
             _conteudo(sessao) == antes)

    print("\n== erro é resposta, não exceção")
    # cada caso comeca de uma sessao NOVA: um comando que muda o documento
    # contaminaria o proximo, e foi assim que este teste ja se enganou
    for caso, comando in (
            ("comando que não existe", {"nome": "voar"}),
            ("peça que não está na linha", {"nome": "remover", "alvo": "p9999"}),
            ("campo que não é alterável",
             {"nome": "alterar", "alvo": 0, "campos": {"familia": "TUBO"}}),
            ("item que não está no catálogo",
             {"nome": "inserir", "sap": "00000-000000"}),
            ("família que a lista não tem nessa bitola",
             {"nome": "inserir", "familia": "CURVA", "dn": 8, "angulo": 60}),
            ("desfazer sem histórico", {"nome": "desfazer"}),
            ("comando vazio", {})):
        sessao = Sessao()
        # o caso do desfazer precisa da sessao vazia; os outros precisam de
        # uma linha montada, para o documento ter o que preservar
        if comando.get("nome") != "desfazer":
            executar(sessao, {"nome": "template", "template": "SUCCAO",
                              "dn": 8})
        inteiro = executar(sessao, {"nome": "documento"})["documento"]
        try:
            resposta = executar(sessao, comando)
        except Exception as erro:                      # noqa: BLE001
            conferir(caso, False, f"levantou {type(erro).__name__}: {erro}")
            continue
        ok = (resposta["ok"] is False and resposta.get("erro")
              and resposta["documento"] == inteiro)
        conferir(f"{caso} → recusa com motivo e documento intacto", ok,
                 resposta.get("erro", ""))

    print(f"\n{len(problemas)} problemas")
    return 1 if problemas else 0


def _conteudo(sessao):
    """O documento sem o estado do historico.

    Desfazer devolve as pecas, a geometria e a lista ao que eram - mas nao
    devolve `pode_refazer`, que passa a ser verdadeiro justamente porque houve
    um desfazer. O desenho e a tabela sao iguais; a barra de ferramentas nao e,
    e nem deveria ser.
    """
    doc = dict(executar(sessao, {"nome": "documento"})["documento"])
    for campo in ("pode_desfazer", "pode_refazer", "historico"):
        doc.pop(campo, None)
    return doc


def _sem_id(resposta):
    """A resposta com os ids trocados por ordem de aparicao.

    O id e sequencial por processo: o mesmo documento montado em dois
    processos tem ids diferentes e conteudo igual. Comparar sem eles e o que
    isola a casca do contador.
    """
    texto = json.dumps(resposta, ensure_ascii=False, sort_keys=True)
    ordem, contador = {}, [0]

    def trocar(achado):
        if achado not in ordem:
            contador[0] += 1
            ordem[achado] = f"#{contador[0]}"
        return ordem[achado]

    import re
    return re.sub(r'"p\d+"', lambda m: f'"{trocar(m.group())}"', texto)


if __name__ == "__main__":
    sys.exit(main())
