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

        print("\n== arrastar pergunta ao motor antes de soltar")
        # remonta: o bloco anterior removeu e desfez, e o arrasto precisa de
        # tres pecas para ter para onde ir
        await pagina.click("#succao")
        await pagina.wait_for_timeout(700)
        pecas = await pagina.query_selector_all("g.peca[data-id]")
        conferir("a linha tem peça para arrastar", len(pecas) >= 3,
                 f"{len(pecas)}")
        ordem = [await g.get_attribute("data-id") for g in pecas]
        if len(pecas) >= 3:
            origem = await pecas[0].bounding_box()
            destino = await pecas[2].bounding_box()
            await pagina.mouse.move(origem["x"] + origem["width"] / 2,
                                    origem["y"] + origem["height"] / 2)
            await pagina.mouse.down()
            await pagina.mouse.move(destino["x"] + destino["width"] / 2,
                                    destino["y"] + destino["height"] / 2,
                                    steps=8)
            await pagina.wait_for_timeout(700)
            conferir("a previsão aparece antes de soltar",
                     await pagina.is_visible("#previsao"))
            conferir("a previsão veio do motor, não da tela",
                     "junç" in (await pagina.inner_text("#previsao")).lower(),
                     await pagina.inner_text("#previsao"))
            conferir("a peça que recebe fica marcada",
                     len(await pagina.query_selector_all(
                         "g.peca.recebe, g.peca.recusa")) == 1)
            await pagina.mouse.up()
            await pagina.wait_for_timeout(700)
            nova = await pagina.eval_on_selector_all(
                "g.peca[data-id]", "gs => gs.map(g => g.dataset.id)")
            esperada = ordem[1:3] + [ordem[0]] + ordem[3:]
            conferir("soltar move a peça para a posição de quem recebeu",
                     nova == esperada, f"{nova} contra {esperada}")
            conferir("a previsão some depois de soltar",
                     not await pagina.is_visible("#previsao"))

        print("\n== o balão é da peça, e arrastá-lo não move a peça")
        baloes = await pagina.query_selector_all("g.balao[data-id]")
        conferir("cada peça desenhada leva um balão",
                 len(baloes) >= len(await pagina.query_selector_all(
                     "g.peca[data-id]")), f"{len(baloes)}")
        numeros = await pagina.eval_on_selector_all(
            "#lista tbody tr td.item span", "s => s.map(e => e.textContent)")
        conferir("e a tabela repete o mesmo número",
                 set(await pagina.eval_on_selector_all(
                     "g.balao[data-id]", "g => g.map(e => e.dataset.item)"))
                 <= set(numeros), f"{numeros}")
        if baloes:
            balao = baloes[0]
            id_balao = await balao.get_attribute("data-id")
            ordem = await pagina.eval_on_selector_all(
                "g.peca[data-id]", "gs => gs.map(g => g.dataset.id)")
            bola = await balao.query_selector("circle.bola")
            caixa = await bola.bounding_box()
            await pagina.mouse.move(caixa["x"] + caixa["width"] / 2,
                                    caixa["y"] + caixa["height"] / 2)
            await pagina.mouse.down()
            await pagina.mouse.move(caixa["x"] + 90, caixa["y"] + 60, steps=8)
            await pagina.mouse.up()
            await pagina.wait_for_timeout(700)
            depois = await pagina.eval_on_selector_all(
                "g.peca[data-id]", "gs => gs.map(g => g.dataset.id)")
            conferir("arrastar o balão não mexe na linha", depois == ordem,
                     f"{depois} contra {ordem}")
            movido = await pagina.eval_on_selector(
                f'g.balao[data-id="{id_balao}"] circle.bola',
                "e => [Number(e.getAttribute('cx')), "
                "Number(e.getAttribute('cy'))]")
            conferir("e o desenho volta do motor com o balão no lugar novo",
                     movido[0] > 0 and movido[1] > 0, str(movido))
            # a prova de que o LUGAR foi para o documento, e nao ficou na
            # tela: desfazer o traz de volta, como qualquer edicao
            await pagina.click("#desfazer")
            await pagina.wait_for_timeout(600)
            voltou = await pagina.eval_on_selector(
                f'g.balao[data-id="{id_balao}"] circle.bola',
                "e => [Number(e.getAttribute('cx')), "
                "Number(e.getAttribute('cy'))]")
            conferir("e desfazer devolve o balão para onde ele estava",
                     voltou != movido, f"{voltou} contra {movido}")
            # o clique cai no NUMERO, que e o que fica por cima do circulo -
            # e o que o dedo acerta quando alguem mira no balao
            await pagina.click(f'g.balao[data-id="{id_balao}"] text.n')
            await pagina.wait_for_timeout(400)
            conferir("clicar no balão escolhe a peça dele",
                     len(await pagina.query_selector_all(
                         f'g.peca.escolhida[data-id="{id_balao}"]')) == 1)
            linhas = len(await pagina.query_selector_all("#lista tbody tr"))
            await pagina.click("#balao")
            await pagina.wait_for_timeout(600)
            conferir("desmarcar tira o balão do desenho",
                     not await pagina.query_selector_all(
                         f'g.balao[data-id="{id_balao}"]'))
            # a peca desmarcada NAO sai da lista: o balao e do desenho, o
            # item e da compra. Na tabela o circulo dela so muda de traco
            conferir("e a peça continua na lista, com o círculo apagado",
                     len(await pagina.query_selector_all(
                         "#lista tbody tr")) == linhas
                     and bool(await pagina.query_selector_all(
                         "#lista tbody tr td.item span.sem")))
            await pagina.click("#balao")
            await pagina.wait_for_timeout(600)
            conferir("e remarcar o traz de volta",
                     bool(await pagina.query_selector_all(
                         f'g.balao[data-id="{id_balao}"]')))

        print("\n== exportar dá arquivo, e o DXF sai em milímetro")
        for formato, esperado in (("dxf", ".dxf"), ("xlsx", ".xlsx")):
            async with pagina.expect_download() as espera:
                await pagina.click(f'[data-exportar="{formato}"]')
            baixado = await espera.value
            conferir(f"baixou o {formato}",
                     baixado.suggested_filename.endswith(esperado),
                     baixado.suggested_filename)
            if formato == "dxf":
                caminho = await baixado.path()
                with open(caminho, encoding="utf-8", errors="replace") as fh:
                    texto = fh.read()
                conferir("o DXF tem os blocos e os inserts da linha",
                         "INSERT" in texto and "BLOCK" in texto)

        print("\n== a ficha da peça escolhida")
        await pagina.select_option("#prontas", "SUCCAO")
        await pagina.click("#succao")
        await pagina.wait_for_timeout(800)
        await pagina.fill("#comando", "inserir ksb metb 150-125-250")
        await pagina.keyboard.press("Enter")
        await pagina.wait_for_timeout(900)
        bomba = await pagina.query_selector('g.peca[data-familia="BOMBA"]')
        conferir("a bomba entrou na linha", bomba is not None)
        if bomba:
            await bomba.click()
            await pagina.wait_for_timeout(900)
            conferir("a ficha aparece ao escolher a peça",
                     await pagina.is_visible("#ficha"))
            texto = await pagina.inner_text("#ficha")
            # o que uma ficha de bomba tem de dizer: as duas bocas com a
            # NORMA de cada uma, e de onde essa norma veio
            for esperado in ('6" flange · ANSI 150', '5" flange · ANSI 150',
                             "CL 125", "METB150-125-250"):
                conferir(f"a ficha diz {esperado!r}", esperado in texto,
                         texto[:90].replace("\n", " · "))
            conferir("e não inventa a chapa de uma norma que a casa não tem",
                     "não tem a folha desta norma" in texto)
        # a ficha ENVELHECE com a edicao: depois de cortar o tubo ela tem de
        # dizer o corte, e nao o comprimento do codigo
        tubo = await pagina.query_selector('g.peca[data-familia="TUBO"]')
        if tubo:
            await tubo.click()
            await pagina.wait_for_timeout(400)
            await pagina.fill("#comando", "comprimento 1500")
            await pagina.keyboard.press("Enter")
            await pagina.wait_for_timeout(900)
            texto = await pagina.inner_text("#ficha")
            conferir("a ficha segue a edição do comprimento",
                     "1500 mm" in texto, texto[:90].replace("\n", " · "))
            conferir("e diz que aquilo é corte, e de que barra",
                     "corte" in texto and "barra de" in texto,
                     texto[:110].replace("\n", " · "))

        # com duas escolhidas a ficha some: ela e de UMA peca
        pecas = await pagina.query_selector_all("g.peca[data-id]")
        await pecas[0].click()
        await pagina.wait_for_timeout(300)
        pecas = await pagina.query_selector_all("g.peca[data-id]")
        await pecas[1].click(modifiers=["Shift"])
        await pagina.wait_for_timeout(600)
        conferir("e some quando há mais de uma escolhida",
                 not await pagina.is_visible("#ficha"))
        await pagina.keyboard.press("Escape")
        await pagina.wait_for_timeout(300)

        print("\n== a tira de montagens: o projeto inteiro numa linha")
        # a sessao ja vem com o que as secoes anteriores montaram: o que se
        # confere e a DIFERENCA, e nao um numero absoluto
        tinha = len(await pagina.query_selector_all(".abas button:not(.nova)"))
        await pagina.select_option("#prontas", "RECALQUE")
        await pagina.click("#succao")
        await pagina.wait_for_timeout(900)
        abas = await pagina.query_selector_all(".abas button:not(.nova)")
        conferir("montar de novo abre outra aba, e não apaga a primeira",
                 len(abas) == tinha + 1, f"{len(abas)} abas, eram {tinha}")
        ativa = await pagina.query_selector_all(".abas button.ativa")
        conferir("a nova é a aberta", len(ativa) == 1)
        pecas_recalque = len(await pagina.query_selector_all("g.peca[data-id]"))
        await abas[0].click()
        await pagina.wait_for_timeout(700)
        conferir("clicar na aba troca o desenho",
                 len(await pagina.query_selector_all("g.peca[data-id]"))
                 != pecas_recalque)
        await pagina.click(".abas .nova")
        await pagina.wait_for_timeout(700)
        conferir("o + abre uma montagem em branco",
                 len(await pagina.query_selector_all(
                     ".abas button:not(.nova)")) == tinha + 2)
        # apagar a aba em branco e voltar ao recalque
        fechar = await pagina.query_selector_all(".abas button.ativa .fechar")
        if fechar:
            await fechar[0].click()
            await pagina.wait_for_timeout(700)
        conferir("o × apaga a montagem",
                 len(await pagina.query_selector_all(
                     ".abas button:not(.nova)")) == tinha + 1)

        print("\n== escolher várias, e mudar as três de uma vez")
        await pagina.click("#succao")
        await pagina.wait_for_timeout(900)
        # a tela repinta a cada comando: o elemento guardado some do DOM no
        # primeiro clique, e o segundo tem de ser procurado de novo
        pecas = await pagina.query_selector_all("g.peca[data-id]")
        await pecas[1].click()
        await pagina.wait_for_timeout(300)
        pecas = await pagina.query_selector_all("g.peca[data-id]")
        await pecas[2].click(modifiers=["Shift"])
        await pagina.wait_for_timeout(400)
        conferir("shift acrescenta à escolha",
                 len(await pagina.query_selector_all("g.peca.escolhida")) == 2,
                 str(len(await pagina.query_selector_all("g.peca.escolhida"))))
        conferir("a tabela acende as duas",
                 len(await pagina.query_selector_all("#lista tr.escolhida")) == 2)
        conferir("e o painel avisa que o que mudar aqui muda todas",
                 await pagina.is_visible("#painel_varias"))
        # o balao e o efeito mais direto de ver: desmarcar com duas
        # escolhidas tem de tirar DOIS baloes do desenho, e voltar os dois
        # num desfazer so
        tinha = len(await pagina.query_selector_all("g.balao[data-id]"))
        await pagina.click("#balao")
        await pagina.wait_for_timeout(600)
        conferir("desmarcar o balão valeu para as duas",
                 len(await pagina.query_selector_all("g.balao[data-id]"))
                 == tinha - 2,
                 f'{len(await pagina.query_selector_all("g.balao[data-id]"))} '
                 f"de {tinha}")
        await pagina.click("#desfazer")
        await pagina.wait_for_timeout(500)
        conferir("e UM desfazer devolveu os dois",
                 len(await pagina.query_selector_all("g.balao[data-id]"))
                 == tinha)
        # trocar a bitola das escolhidas: a peca troca de codigo, e a
        # selecao tem de seguir a peca nova
        antes = await retrato(pagina)
        await pagina.select_option("#trocar_bitola", "6")
        await pagina.wait_for_timeout(900)
        conferir("trocar a bitola mudou o desenho e a lista",
                 await retrato(pagina) != antes)
        conferir("e a escolha seguiu as peças novas",
                 len(await pagina.query_selector_all("g.peca.escolhida")) == 2,
                 str(len(await pagina.query_selector_all("g.peca.escolhida"))))
        await pagina.click("#desfazer")
        await pagina.wait_for_timeout(600)
        conferir("um desfazer devolve as duas",
                 await retrato(pagina) == antes)
        await pagina.keyboard.press("Escape")
        await pagina.wait_for_timeout(300)
        conferir("Escape solta a escolha",
                 not await pagina.query_selector_all("g.peca.escolhida"))

        print("\n== a bomba entra por nome e pelo painel, e diz quando não desenha")
        await pagina.select_option("#prontas", "SUCCAO")
        await pagina.click("#succao")
        await pagina.wait_for_timeout(800)
        antes = len(await pagina.query_selector_all("g.peca[data-id]"))
        await pagina.fill("#comando", "inserir ebara gsd 125-250")
        await pagina.keyboard.press("Enter")
        await pagina.wait_for_timeout(900)
        conferir("a bomba com folha dimensional entra e desenha",
                 len(await pagina.query_selector_all("g.peca[data-id]"))
                 == antes + 1)
        await pagina.select_option("#familia", "BOMBA")
        await pagina.wait_for_timeout(800)
        conferir("e o painel oferece bomba, que não tem bitola",
                 len(await pagina.query_selector_all("#candidatos button")) > 5,
                 str(len(await pagina.query_selector_all("#candidatos button"))))
        # a que a folha nao traz NAO pode entrar calada: ela some do desenho
        await pagina.fill("#comando", "inserir ebara gsd 100-200")
        await pagina.keyboard.press("Enter")
        await pagina.wait_for_timeout(900)
        recado = (await pagina.inner_text("#recado")).strip()
        conferir("a bomba sem folha dimensional diz por que não desenhou",
                 "folha dimensional" in recado, recado[:80])
        conferir("e o motivo vem sem nome de exceção",
                 "ValueError" not in recado and "Error" not in recado,
                 recado[:80])
        await pagina.click("#desfazer")
        await pagina.wait_for_timeout(600)

        print("\n== ramificar: o barrilete com duas saídas, numa folha só")
        await pagina.select_option("#prontas", "LIVRE")
        await pagina.click("#succao")
        await pagina.wait_for_timeout(800)
        for familia in ("tubo", "tê", "tubo"):
            await pagina.fill("#comando", f"inserir {familia} 8")
            await pagina.keyboard.press("Enter")
            await pagina.wait_for_timeout(600)
        te = await pagina.query_selector('g.peca[data-familia="TE"]')
        conferir("o tê entrou na montagem em branco", te is not None)
        if te:
            await te.click()
            await pagina.wait_for_timeout(400)
            desenhadas = len(await pagina.query_selector_all("g.peca[data-id]"))
            abas = len(await pagina.query_selector_all(
                ".abas button:not(.nova)"))
            await pagina.click("#ramificar")
            await pagina.wait_for_timeout(800)
            conferir("ramificar abre outra montagem",
                     len(await pagina.query_selector_all(
                         ".abas button:not(.nova)")) == abas + 1)
            conferir("e ela aparece na tira como ramo",
                     bool(await pagina.query_selector_all(".abas .ramo")))
            # a peca que entra no ramo tem de aparecer no MESMO desenho: o
            # tronco e o ramo sao a mesma folha
            await pagina.fill("#comando", "inserir tubo 8")
            await pagina.keyboard.press("Enter")
            await pagina.wait_for_timeout(800)
            conferir("a peça do ramo entra no desenho do tronco",
                     len(await pagina.query_selector_all("g.peca[data-id]"))
                     == desenhadas + 1,
                     f'{len(await pagina.query_selector_all("g.peca[data-id]"))}'
                     f" contra {desenhadas + 1}")
            linhas = await pagina.eval_on_selector_all(
                "#lista tbody tr", "rs => rs.length")
            conferir("e na lista da árvore", linhas > 0)

        print("\n== salvar e abrir devolvem a mesma montagem")
        antes = await retrato(pagina)
        async with pagina.expect_download() as espera:
            await pagina.click("#salvar")
        salvo = await espera.value
        caminho = await salvo.path()
        conferir("salvou a montagem",
                 salvo.suggested_filename.endswith(".linha.json"),
                 salvo.suggested_filename)
        # mexe na linha ANTES de reabrir, senao abrir nao teria o que provar
        # uma peca que ainda NAO esta escolhida: clicar na escolhida
        # desmarca, e o painel fecharia junto
        await (await pagina.query_selector(
            "g.peca[data-id]:not(.escolhida)")).click()
        await pagina.wait_for_timeout(400)
        await pagina.click("#remover")
        await pagina.wait_for_timeout(600)
        conferir("mexer na linha muda o desenho e a lista",
                 await retrato(pagina) != antes)
        await pagina.set_input_files("#arquivo", str(caminho))
        await pagina.wait_for_timeout(1200)
        depois = await retrato(pagina)
        # o id nasce com a peca da sessao, e reabrir cria pecas novas: o que
        # tem de voltar igual e a LISTA, que e o que se compra
        conferir("abrir devolve a mesma lista de materiais",
                 depois[1] == antes[1],
                 f"{len(depois[1])} linhas contra {len(antes[1])}")
        conferir("e o mesmo tanto de peças no desenho",
                 len(depois[0]) == len(antes[0]),
                 f"{len(depois[0])} contra {len(antes[0])}")

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
