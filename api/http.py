#!/usr/bin/env python3
"""O mesmo motor atras de um HTTP local, para desenvolver a tela no navegador.

E a casca descartavel: o Electron nao precisa dela, quem precisa sou eu
enquanto a tela nao esta pronta, porque no navegador da para inspecionar. O
nucleo e o mesmo de api/stdio.py - se as duas divergirem, o defeito esta na
casca.

Escuta so em 127.0.0.1 de proposito. Este servidor executa comandos sobre o
documento sem autenticacao nenhuma; ele existe para a maquina de quem
desenvolve e nao para uma rede.

Uso: python3 -m api.http [--porta 8765] [--web web]
"""
import argparse
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .nucleo import Sessao, executar

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Punho(BaseHTTPRequestHandler):
    sessao = None
    pasta_web = os.path.join(RAIZ, "web")

    def log_message(self, formato, *args):        # noqa: A003
        # a stdout fica limpa; o log do servidor vai para a stderr
        sys.stderr.write("# %s %s\n" % (self.address_string(), formato % args))

    def _responder(self, codigo, corpo, tipo="application/json; charset=utf-8"):
        dados = corpo if isinstance(corpo, bytes) else corpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):                            # noqa: N802
        if self.path.rstrip("/") != "/comando":
            return self._responder(404, json.dumps({"ok": False,
                                                    "erro": "so /comando"}))
        tamanho = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(tamanho).decode("utf-8") if tamanho else "{}"
        try:
            comando = json.loads(bruto)
        except json.JSONDecodeError as erro:
            return self._responder(400, json.dumps(
                {"ok": False, "erro": f"corpo nao e JSON: {erro}"},
                ensure_ascii=False))
        resposta = executar(type(self).sessao, comando)
        self._responder(200, json.dumps(resposta, ensure_ascii=False))

    def do_GET(self):                             # noqa: N802
        caminho = self.path.split("?")[0]
        if caminho in ("/", ""):
            caminho = "/index.html"
        alvo = os.path.normpath(os.path.join(self.pasta_web,
                                             caminho.lstrip("/")))
        # nao servir nada fora da pasta web, nem por caminho com .. A barra no
        # fim importa: sem ela uma pasta "web2" ao lado de "web" passaria no
        # startswith e sairia servida
        dentro = os.path.join(self.pasta_web, "")
        if not alvo.startswith(dentro) or not os.path.isfile(alvo):
            return self._responder(404, json.dumps(
                {"ok": False, "erro": f"nao ha {caminho}"}))
        tipo = mimetypes.guess_type(alvo)[0] or "application/octet-stream"
        with open(alvo, "rb") as fh:
            self._responder(200, fh.read(), tipo)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--porta", type=int, default=8765)
    p.add_argument("--web", default=os.path.join(RAIZ, "web"))
    p.add_argument("--abrir", action="store_true",
                   help="abre o navegador no endereco do programa")
    args = p.parse_args(argv)
    Punho.sessao = Sessao()
    Punho.pasta_web = os.path.abspath(args.web)
    servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), Punho)
    endereco = f"http://127.0.0.1:{args.porta}"
    print(f"# o programa esta em {endereco}  (ctrl+c para parar)",
          file=sys.stderr, flush=True)
    if args.abrir:
        import threading
        import webbrowser
        threading.Timer(0.6, webbrowser.open, [endereco]).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
