#!/usr/bin/env python3
"""O motor como processo filho: um JSON por linha na entrada, um na saida.

E assim que o Electron conversa com ele. Sem porta e sem servidor: o pai abre
o processo, escreve o comando na stdin e le a resposta na stdout. Nao ha
firewall para autorizar, nem porta que outra coisa na maquina possa achar.

Uma regra que o protocolo impoe ao codigo: **a stdout e do protocolo**. Todo
recado - erro, aviso, depuracao - vai para a stderr. Um `print` perdido aqui
corrompe a conversa inteira, e por isso a saida e escrita num lugar so, no fim
desta funcao.

O `eco` volta como veio: e o que deixa o pai casar resposta com pedido quando
ele manda varios sem esperar.

Uso:  python3 -m api.stdio
      {"nome": "template", "template": "SUCCAO", "dn": 8}
"""
import json
import sys

from .nucleo import Sessao, executar


def main(entrada=None, saida=None, erros=None):
    entrada = entrada or sys.stdin
    saida = saida or sys.stdout
    erros = erros or sys.stderr
    sessao = Sessao()
    print("# motor pronto", file=erros, flush=True)

    for numero, linha in enumerate(entrada, 1):
        linha = linha.strip()
        if not linha:
            continue
        try:
            comando = json.loads(linha)
        except json.JSONDecodeError as erro:
            resposta = {"ok": False, "erro": f"linha {numero} nao e JSON: {erro}"}
        else:
            resposta = executar(sessao, comando)
            if isinstance(comando, dict) and "eco" in comando:
                resposta["eco"] = comando["eco"]
        saida.write(json.dumps(resposta, ensure_ascii=False) + "\n")
        saida.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
