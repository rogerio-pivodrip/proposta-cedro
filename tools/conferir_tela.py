#!/usr/bin/env python3
"""Confere a tela: ela liga o desenho a tabela, e nao guarda documento.

Sobe o servidor local, abre a pagina num navegador de verdade e cobra tres
coisas. Nenhuma delas e "a pagina carrega":

  **Clicar no desenho seleciona a mesma peca da tabela.** E a promessa do
  documento unico chegando na interface: o balao e a linha da tabela sao a
  mesma peca, com o mesmo id. Se a tela tivesse duas listas, e aqui que
  divergiriam.

  **Desfazer pelo botao devolve o desenho e a tabela.** O mesmo que
  conferir_comandos cobra do motor e conferir_api da camada, agora atravessado
  pela tela - que e onde um estado guardado a mais apareceria.

  **O console fica limpo.** Erro de JavaScript nao aparece no desenho: a tela
  simplesmente para de repintar, e quem usa acha que o programa travou.

Uso: python3 tools/conferir_tela.py [--porta 8799]
"""
import argparse
import asyncio
import subprocess
import sys
import time

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


async def rodar(porta):
    from playwright.async_api import async_playwright

    problemas, erros = [], []

    def conferir(caso, condicao, detalhe=""):
        if condicao:
            print(f"  ok {caso}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}" + (f": {detalhe}" if detalhe else ""))

    async with async_playwright() as pw:
        navegador = await pw.chromium.launch(executable_path=CHROME)
        pagina = await navegador.new_page(viewport={"width": 1400,
                                                    "height": 900})
        pagina.on("console",
                  lambda m: erros.append(m.text) if m.type == "error" else None)
        pagina.on("pageerror", lambda e: erros.append(str(e)))
        await pagina.goto(f"http://127.0.0.1:{porta}/")
        await pagina.wait_for_timeout(900)

        print("== a tela monta e desenha")
        await pagina.click("#succao")
        await pagina.wait_for_selector("g.peca[data-id]")
        pecas = await pagina.query_selector_all("g.peca[data-id]")
        linhas = await pagina.query_selector_all("#lista tbody tr")
        conferir("desenhou peça", len(pecas) > 0, f"{len(pecas)}")
        conferir("a lista tem mais linhas que o desenho tem peças",
                 len(linhas) > len(pecas),
                 f"{len(linhas)} linhas para {len(pecas)} peças")

        print("\n== o desenho e a tabela são a mesma peça")
        alvo = pecas[1]
        id_peca = await alvo.get_attribute("data-id")
        await alvo.click()
        await pagina.wait_for_timeout(400)
        escolhidas = await pagina.query_selector_all("g.peca.escolhida")
        conferir("clicar no desenho seleciona uma peça só",
                 len(escolhidas) == 1, f"{len(escolhidas)}")
        if escolhidas:
            conferir("é a peça clicada",
                     await escolhidas[0].get_attribute("data-id") == id_peca)
        conferir("a linha da tabela acendeu junto",
                 len(await pagina.query_selector_all("#lista tr.escolhida")) == 1)
        conferir("o painel mostra o código da peça",
                 "-" in (await pagina.inner_text("#painel_sap")))

        print("\n== desfazer devolve o desenho e a tabela")
        antes = await retrato(pagina)
        await pagina.click("#remover")
        await pagina.wait_for_timeout(500)
        depois = await retrato(pagina)
        conferir("remover mudou o desenho e a lista", antes != depois)
        await pagina.click("#desfazer")
        await pagina.wait_for_timeout(500)
        conferir("desfazer volta ao anterior", await retrato(pagina) == antes)
        await pagina.click("#refazer")
        await pagina.wait_for_timeout(500)
        conferir("refazer volta ao posterior", await retrato(pagina) == depois)

        print("\n== o console fica limpo")
        conferir("nenhum erro de JavaScript", not erros, " · ".join(erros[:3]))
        await navegador.close()

    print(f"\n{len(problemas)} problemas")
    return 1 if problemas else 0


async def retrato(pagina):
    """O que a pessoa ve: as peças do desenho e as linhas da tabela."""
    ids = await pagina.eval_on_selector_all(
        "g.peca[data-id]", "gs => gs.map(g => g.dataset.id)")
    lista = await pagina.eval_on_selector_all(
        "#lista tbody tr", "rs => rs.map(r => r.innerText)")
    return ids, lista


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--porta", type=int, default=8799)
    args = p.parse_args()
    servidor = subprocess.Popen([sys.executable, "-m", "api.http",
                                 "--porta", str(args.porta)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    try:
        time.sleep(2)
        return asyncio.run(rodar(args.porta))
    finally:
        servidor.terminate()
        servidor.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
