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
from motor import (arquivo, desenho, exportar as exportacao, ficha,
                   folha, regras, templates, vista)

from . import linguagem
from motor.catalogo import Catalogo
from motor.linha import Linha, Peca
from motor.projeto import Projeto


class Erro(Exception):
    """O comando nao pode ser cumprido, e o motivo e para a pessoa ler."""


class Sessao:
    """Um projeto aberto, com o catalogo que ele consulta.

    **A sessao guarda um PROJETO, e nao uma linha.** Uma casa de bomba tem a
    sucção, o recalque, o barrilete e o trecho que sai para o campo - e com
    duas bombas tem tudo isso duas vezes. `sessao.linha` continua existindo e
    continua querendo dizer a mesma coisa: a montagem em que os comandos
    caem. Por isso nenhum comando de edicao mudou - eles agem na ativa.
    """

    def __init__(self, catalogo=None, tipo="RECALQUE", area="P01"):
        self.catalogo = catalogo or Catalogo()
        self.projeto = Projeto(self.catalogo, area=area)
        self.projeto.criar(Linha(self.catalogo, tipo=tipo, area=area))
        # a montagem em branco com que a sessao abre NAO e uma edicao: um
        # ctrl+Z recem aberto o programa nao pode apagar a folha onde a pessoa
        # ainda nem comecou
        self.projeto.feitos.clear()
        # o tamanho da area de desenho da tela. Fica na sessao porque o SVG
        # sai pronto do motor, ja escalado - a tela nao redesenha nada, so
        # avisa de quanto espaco dispoe
        self.janela = {"largura": 940, "altura_max": 620}
        # como o desenho e lido: tracado de projeto, preto e branco, ou
        # metalizado. E folha de estilo, nao geometria - a linha e a mesma
        self.modo = "traco"

    @property
    def linha(self):
        """A montagem ativa. Escrever aqui TROCA a montagem ativa.

        O `setter` existe por causa dos templates: eles montam uma linha nova
        e a punham no lugar da anterior quando a sessao tinha uma so. Agora
        isso acrescenta uma montagem ao projeto, que e o que a casa faz - a
        sucção nao apaga o recalque.
        """
        return self.projeto.ativa

    @linha.setter
    def linha(self, montagem):
        self.projeto.criar(montagem)

    # ------------------------------------------------------------------ ler
    def documento(self):
        """As duas projecoes, mais o que a tela precisa para se desenhar."""
        linha = self.linha
        # a lista e a ARVORE, e nao so esta montagem: o desenho mostra o
        # tronco com os ramos, e lista e desenho sao duas projecoes da mesma
        # coisa. Lista so do tronco ao lado de desenho com os ramos seria a
        # divergencia que este programa existe para nao ter
        lista, avisos = self.projeto.lista_materiais(linha)
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
                for d in linha.divergencias()] + [
                f'{c["juntas"]} junta{"s" if c["juntas"] > 1 else ""} de '
                f'{c["dn_pol"]:g}": o parafuso {c["bitola_pol"]}" x '
                f'{c["comprimento_pol"]}" da tabela não fecha - '
                + (f'faltam {-c["sobra_mm"]:.0f} mm' if c["sobra_mm"] < 0
                   else f'sobram só {c["sobra_mm"]:.0f} mm de rosca '
                        f'depois da porca')
                for c in vista.parafusos_curtos_por_caso(linha)],
            "divergencias": [{"id": d["peca"].id, "sap": d["peca"].sap,
                              "desenhado_mm": d["desenhado_mm"],
                              "do_codigo_mm": d["do_codigo_mm"]}
                             for d in linha.divergencias()],
            "vista": vista.vista(linha, modo=self.modo,
                                 projeto=self.projeto, **self.janela),
            "pontas": vista.pontas_erradas(linha),
            "projeto": {"nome": self.projeto.nome, "area": self.projeto.area},
            "montagens": self.projeto.resumo(),
            "montagem": linha.id,
            "pode_desfazer": self.projeto.pode_desfazer,
            "pode_refazer": self.projeto.pode_refazer,
            "historico": [c.nome for c in self.projeto.historico()],
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
        "angulo": p.angulo, "sentido": p.sentido, "pose": p.pose,
        "acessorios": [{"id": a.id, "sap": a.sap, "descricao": a.descricao,
                        "familia": a.familia, "balao": a.balao}
                       for a in p.acessorios],
        "comprimento_mm": p.comprimento_mm,
        "fonte": p.fonte, "fonte_cota": p.fonte_cota,
        "rotulo": p.rotulo,
        "balao": p.balao, "balao_angulo": p.balao_angulo,
        "balao_distancia": p.balao_distancia,
        "flange_bomba": p.flange_bomba,
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


def _alvos(comando):
    """As pecas que o comando atinge - uma ou varias, sempre como lista.

    A tela escolhe uma peca ou um punhado delas, e o comando e o mesmo: quem
    seleciona tres tubos e digita `comprimento 1500` quer os tres em 1500. Por
    isso `alvo` e `alvos` chegam pelo mesmo caminho e saem daqui iguais - o
    comando nao tem duas versoes, tem uma que conta ate n.
    """
    varios = comando.get("alvos")
    if varios:
        return [a for a in varios if a]
    return [comando["alvo"]] if comando.get("alvo") else []


def _remover(sessao, comando):
    """Tira a peca da linha - ou o acessorio da peca que o carrega.

    Quem usa nao distingue os dois, e nao deve: os dois estao no desenho e na
    lista, e apagar e apagar. Quem sabe onde a peca esta e o documento.
    """
    alvos = _alvos(comando)
    if not alvos:
        raise Erro("remover age sobre uma peca - escolha uma antes")
    saiu = []
    with sessao.linha.lote("remover"):
        for cada in alvos:
            try:
                saiu.append(sessao.linha.remover(cada).id)
            except KeyError:
                saiu.append(sessao.linha.desacoplar(cada).id)
    return {"peca": saiu[0], "pecas": saiu}


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
    alvos = _alvos(comando)
    if not alvos:
        raise Erro("esticar age sobre uma peca - escolha um tubo antes")
    if len(alvos) > 1:
        # varias escolhidas: estica os tubos e diz o que ficou de fora. Com
        # uma so, recusar e o certo - quem escolheu a valvula e mandou
        # esticar errou de peca. Com doze, recusar tudo por causa de uma
        # seria pior: o gesto foi "estica os tubos daqui"
        feitas, recados = [], []
        with sessao.linha.lote("esticar"):
            for cada in alvos:
                try:
                    feitas.append(_esticar(sessao, {**comando, "alvo": cada,
                                                    "alvos": None}))
                except Erro as erro:
                    recados.append(str(erro))
        if not feitas:
            raise Erro(" · ".join(recados) or "nenhum tubo na escolha")
        return {"peca": feitas[0]["peca"],
                "pecas": [f["peca"] for f in feitas],
                "saiu": [f["saiu"] for f in feitas], "recado": recados}
    alvo = alvos[0]
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


def _acoplar(sessao, comando):
    """Poe uma peca terminal na boca que sobra do alvo - a do te, a do manifold."""
    peca = Peca(_item(sessao, comando))
    sessao.linha.acoplar(comando["alvo"], peca)
    return {"peca": peca.id, "dono": comando["alvo"]}


def _balao(sessao, comando):
    """Marca, desmarca ou move o balao de uma peca.

    Sem nada, ALTERNA - marcado vira desmarcado. E o gesto de quem clica na
    caixinha, e nao um comando diferente do de quem digita.

    Mover e `alterar` como qualquer outro campo, e por isso desfaz junto com o
    resto: o balao e da peca, do mesmo jeito que o sentido da curva. O que ele
    NAO muda e o numero - esse e da lista, e mudar de lugar na folha nao muda
    o item que se compra.
    """
    alvos = _alvos(comando)
    if not alvos:
        raise Erro("balao age sobre uma peca - escolha uma antes")
    if len(alvos) > 1:
        # com varias, o botao nao alterna uma a uma: se ALGUMA esta marcada,
        # apaga todas; se nenhuma esta, acende todas. Alternar cada uma pelo
        # seu estado deixaria a escolha metade acesa e metade apagada, e o
        # proximo clique inverteria as duas metades sem nunca chegar a lugar
        # nenhum
        pecas = [sessao.linha.achar(a) for a in alvos]
        mostrar = comando.get("mostrar")
        if mostrar is None and not any(comando.get(c) is not None
                                       for c in ("angulo", "distancia")):
            mostrar = not any(p.balao for p in pecas)
        feitas = []
        with sessao.linha.lote("balao"):
            for peca in pecas:
                feitas.append(_balao(sessao, {**comando, "alvo": peca.id,
                                              "alvos": None,
                                              "mostrar": mostrar}))
        return {"peca": feitas[0]["peca"],
                "pecas": [f["peca"] for f in feitas]}
    peca = sessao.linha.achar(alvos[0])
    campos = {}
    if comando.get("angulo") is not None:
        campos["balao_angulo"] = float(comando["angulo"]) % 360
    if comando.get("distancia") is not None:
        # distancia negativa nao existe: o balao ficaria do lado oposto ao
        # angulo pedido, e quem arrastou para tras quer o angulo de tras
        campos["balao_distancia"] = max(float(comando["distancia"]), 0.0)
    if comando.get("solto"):
        campos["balao_distancia"] = None      # volta a achar a distancia dele
    if comando.get("mostrar") is not None:
        campos["balao"] = bool(comando["mostrar"])
    elif not campos:
        campos["balao"] = not peca.balao
    elif not peca.balao:
        # mover um balao apagado e pedir para ve-lo: ninguem arrasta o que
        # nao esta na tela
        campos["balao"] = True
    sessao.linha.alterar(peca, **campos)
    return {"peca": peca.id, "balao": peca.balao,
            "angulo": peca.balao_angulo, "distancia": peca.balao_distancia}


def _numerar(sessao, comando):
    """Poe a peca escolhida noutro numero de item - e renumera o resto.

    A tela arrasta a linha da tabela ou o balao; aqui se digita o numero de
    destino. Nos dois casos e a MESMA `renumerar` do documento, que guarda a
    ordem por codigo - ver linha.renumerar.
    """
    ordem = [reg["sap"] for reg in sessao.linha.lista_materiais()[0]]
    if comando.get("ordem"):
        return {"numeracao": _limpo(sessao.linha.renumerar(comando["ordem"]))}
    if not comando.get("alvo"):
        raise Erro("numerar age sobre uma peca - escolha uma antes, ou mande "
                   "a ordem inteira")
    peca = sessao.linha.achar(comando["alvo"])
    if peca.sap not in ordem:
        raise Erro(f"{peca.descricao} nao esta na lista")
    destino = comando.get("item")
    if destino is None:
        raise Erro("numerar precisa do numero de destino")
    destino = max(1, min(int(destino), len(ordem)))
    ordem.remove(peca.sap)
    ordem.insert(destino - 1, peca.sap)
    numeracao = sessao.linha.renumerar(ordem)
    return {"peca": peca.id, "item": numeracao[peca.sap],
            "numeracao": _limpo(numeracao)}


def _alterar(sessao, comando):
    campos = comando.get("campos") or {}
    if not campos:
        raise Erro("alterar sem campo nenhum")
    alvos = _alvos(comando)
    if not alvos:
        raise Erro("alterar age sobre uma peca - escolha uma antes")
    mexidas = []
    with sessao.linha.lote("alterar"):
        for cada in alvos:
            mexidas.append(sessao.linha.alterar(cada, **campos).id)
    return {"peca": mexidas[0], "pecas": mexidas}


def _mover(sessao, comando):
    """Poe a peca - ou o bloco escolhido - noutro ponto da sequencia."""
    alvos = _alvos(comando)
    if not alvos:
        raise Erro("mover age sobre uma peca - escolha uma antes")
    if len(alvos) == 1:
        return {"peca": sessao.linha.mover(alvos[0], comando["para"]).id,
                "pecas": [sessao.linha.achar(alvos[0]).id]}
    sessao.linha.mover_bloco(alvos, comando["para"])
    return {"peca": sessao.linha.achar(alvos[0]).id,
            "pecas": [sessao.linha.achar(a).id for a in alvos]}


def _fora_a_bitola(descricao):
    """A descricao sem a bitola, para comparar duas pecas de tamanhos difer.

    So o numero colado na aspa sai - 6", 8", 2,5". O resto dos numeros FICA,
    e e o que importa: 150LB e 300LB sao duas valvulas, e apagar todo digito
    faria as duas parecerem a mesma peca noutro tamanho.
    """
    import re
    return " ".join(re.sub(r'\d+(?:[.,]\d+)?\s*"', " ", descricao).split()).upper()


def _bitola(sessao, comando):
    """A MESMA peca noutro tamanho, para uma peca ou para a linha inteira.

    E o comando que faltava para a pergunta que todo projeto faz: "e se esta
    linha fosse de 8?". Peca por peca isso e `substituir` doze vezes, e cada
    uma exige achar o codigo novo a mao - que e onde entra o erro que a lista
    nao pega, porque os dois codigos existem.

    **A troca e uma so no historico**, e desfazer devolve a linha inteira.

    **O que a peca CARREGA vai junto, mas so o que esta na bitola dela.** A
    flange cega de 6" no alto do te vira a de 8" com o te; a ventosa de 2"
    enroscada na luva dela continua de 2", porque a bitola dela nunca foi a
    da linha. Sem essa distincao, mudar a linha de 6 para 8 trocaria a ventosa
    por uma de 8" que nao existe - e, se existisse, seria a peca errada.

    **O que a lista nao tem, nao se inventa.** Peca sem equivalente fica como
    esta e vira aviso: a juncao passa a acusar reducao, que e a verdade do
    desenho, em vez de um codigo parecido escolhido pelo programa.
    """
    dn = comando.get("dn")
    if dn is None:
        raise Erro("bitola precisa do tamanho novo")
    dn = float(dn)
    alvos = _alvos(comando) or [p.id for p in sessao.linha.pecas]
    trocas, recados = [], []

    def trocar(peca):
        novo = sessao.catalogo.equivalente(peca.item, dn)
        if novo is None:
            recados.append(f'{peca.descricao}: a lista não tem esta peça em '
                           f'{dn:g}" - ficou como estava')
            return peca
        if novo["sap"] == peca.sap:
            return peca
        nova = Peca(novo, comprimento_mm=peca._comprimento_pedido,
                    rotulo=peca.rotulo, fonte=peca.fonte,
                    sentido=peca.sentido, pose=peca.pose)
        for campo in ("balao", "balao_angulo", "balao_distancia"):
            setattr(nova, campo, getattr(peca, campo))
        # o acessorio vive DENTRO da peca: ele nao pode ficar para tras
        # quando ela troca, senao a flange cega sumia do alto do te
        nova.acessorios = list(peca.acessorios)
        sessao.linha.substituir(peca.id, nova)
        trocas.append({"de": peca.descricao, "para": nova.descricao,
                       "sap_de": peca.sap, "sap_para": nova.sap,
                       "id": nova.id})
        if _fora_a_bitola(peca.descricao) != _fora_a_bitola(nova.descricao):
            # a peca que entrou nao e a mesma de antes noutro tamanho: a
            # lista nao tinha aquela nesta bitola e o que veio e a mais
            # parecida. Isso NAO pode passar calado - a 735-M virando 405, o
            # medidor IRT virando Woltman, a retencao 150LB virando 300LB
            recados.append(f'{peca.descricao} → {nova.descricao}: em '
                           f'{dn:g}" a lista não tem a mesma peça, entrou a '
                           f'mais parecida - confira a folha')
        return nova

    with sessao.linha.lote("bitola"):
        for cada in alvos:
            peca = sessao.linha.achar(cada)
            antiga = peca.item["dn"][0] if peca.item["dn"] else None
            nova = trocar(peca)
            # so acompanha o acessorio que estava NA BITOLA da peca: o que
            # tem bitola propria - a ventosa de 2" na luva - nao e da linha
            for junto in list(nova.acessorios):
                if junto.item["dn"] and junto.item["dn"][0] == antiga:
                    trocar(junto)
    return {"dn": dn, "trocas": trocas, "recado": recados,
            "pecas": [t["id"] for t in trocas]}


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
    viradas = []
    with sessao.linha.lote("espelhar"):
        for cada in _alvos(comando):
            peca = sessao.linha.achar(cada)
            viradas.append(
                sessao.linha.alterar(cada, sentido=-peca.sentido).id)
    return {"peca": viradas[0], "pecas": viradas}


def _desfazer(sessao, comando):
    """Desfaz o ULTIMO comando do projeto, esteja ele em que montagem estiver.

    Nao e o ultimo da montagem aberta: quem edita a sucção, troca para o
    recalque e aperta ctrl+Z quer de volta o que acabou de fazer. Ver
    projeto.Projeto.desfazer e Comando.ordem.
    """
    feito = sessao.projeto.desfazer()
    if feito is None:
        raise Erro("nao ha o que desfazer")
    return {"comando": feito.nome, "peca": feito.alvo}


def _refazer(sessao, comando):
    feito = sessao.projeto.refazer()
    if feito is None:
        raise Erro("nao ha o que refazer")
    return {"comando": feito.nome, "peca": feito.alvo}


def _template(sessao, comando):
    """Acrescenta ao projeto uma montagem pronta.

    **Nao ha mais um `if` por montagem aqui.** Sucção e recalque foram as duas
    primeiras e por um tempo pareceram ser as unicas; a casa monta adução,
    barrilete, bomba em série, bomba em paralelo. Quem sabe quais existem e
    motor/templates.MONTAGENS - uma montagem nova e uma funcao e uma linha na
    tabela, e ela aparece sozinha aqui, na barra e na tela.

    O `faltando` vem junto na resposta e nao vira excecao: a lista nao ter a
    peca e informacao de projeto. O template monta o que da e diz o que nao deu.
    """
    nome = (comando.get("template") or "SUCCAO").upper()
    try:
        linha, faltando = templates.montar(
            sessao.catalogo, nome, comando.get("dn"),
            bomba=comando.get("bomba"), curva=comando.get("curva"),
            area=sessao.projeto.area, nome=comando.get("rotulo"))
    except KeyError:
        raise Erro(f"nao ha montagem {nome} - so "
                   f'{", ".join(templates.MONTAGENS)}') from None
    except ValueError as erro:
        raise Erro(str(erro)) from None
    # a folha em branco com que a sessao abriu nao vira aba orfa: se ninguem
    # mexeu nela, a montagem nova ocupa o lugar dela
    antiga = sessao.projeto.ativa
    limpa = not antiga.pecas and not antiga.feitos
    sessao.projeto.criar(linha)
    if limpa and antiga in sessao.projeto.montagens:
        sessao.projeto.remover(antiga)
    return {"template": nome, "montagem": linha.id, "rotulo": linha.nome,
            "pecas": len(linha.pecas),
            "faltando": [{"familia": f, "dn": d, "filtros": _limpo(e)}
                         for f, d, e in faltando]}


def _ramificar(sessao, comando):
    """Abre uma montagem nova saindo da boca livre da peca escolhida.

    O ramo NAO e um acessorio. Acessorio e peca terminal - flange cega,
    ventosa - que fecha a boca; o ramo continua a partir dela, com tubo,
    curva, valvula e o que mais precisar. E como se monta o barrilete, a
    adução e as duas bombas em paralelo, e por isso ele e uma `Linha` como
    qualquer outra: os mesmos comandos, o mesmo desfazer, os mesmos baloes.
    """
    alvo = comando.get("alvo")
    if not alvo:
        raise Erro("ramificar sai de uma peça - escolha a que tem a boca livre")
    # a peca pode estar em QUALQUER montagem do projeto - quem ramifica um
    # tronco costuma estar com um ramo aberto quando lembra da segunda saida
    dona = sessao.projeto.dona_da_peca(alvo if isinstance(alvo, str) else None)
    peca = (dona or sessao.linha).achar(alvo)
    simbolo = None
    try:
        simbolo = desenho.de_item(peca.item, peca.pose, peca.comprimento_mm)
    except Exception:                                       # noqa: BLE001
        pass
    if simbolo is not None:
        gastas = 1 if peca.acessorios else 0
        bocas = vista.bocas_livres(simbolo, gastas)
        # ja usadas por outros ramos desta mesma peca
        tomadas = {m.origem.get("boca", 0) for m in sessao.projeto.montagens
                   if m.origem and m.origem.get("peca") == peca.id}
        livres = [i for i in range(len(bocas)) if i not in tomadas]
        if not livres:
            raise Erro(f"{peca.descricao} não tem boca livre - o que sobrava "
                       f"já está ocupado")
        boca = comando.get("boca")
        boca = livres[0] if boca is None else int(boca)
    else:
        boca = int(comando.get("boca") or 0)
    ramo = sessao.projeto.ramificar(
        peca.id, boca=boca, nome=comando.get("rotulo"),
        tipo=comando.get("tipo") or "RAMO")
    return {"montagem": ramo.id, "rotulo": ramo.nome, "boca": boca,
            "peca": peca.id}


def _ficha(sessao, comando):
    """O que o programa sabe da peca escolhida, com a fonte de cada linha.

    Nao entra no `documento` de proposito: numa linha de sessenta pecas seriam
    sessenta fichas viajando a cada comando, e quem le uma ficha esta olhando
    UMA peca. A tela pede quando a escolha muda.
    """
    alvo = comando.get("alvo")
    if not alvo:
        raise Erro("ficha de qual peça?")
    dona = sessao.projeto.dona_da_peca(alvo if isinstance(alvo, str) else None)
    peca = (dona or sessao.linha).achar(alvo)
    return {"peca": peca.id, "descricao": peca.descricao,
            "linhas": ficha.da_peca(peca, sessao.catalogo)}


def _montagem(sessao, comando):
    """Cria, escolhe, renomeia ou apaga uma montagem do projeto.

    Editar peca e da montagem; isto e do PROJETO - a pasta que as guarda. Sao
    comandos como os outros (menos escolher, que nao edita nada) porque apagar
    uma montagem por engano tem de poder voltar.
    """
    # `nome` e do COMANDO neste protocolo - o nome da MONTAGEM viaja como
    # `rotulo`, senao o comando se chamaria pelo nome da coisa que ele cria
    acao = (comando.get("acao") or "criar").lower()
    projeto = sessao.projeto
    if acao == "criar":
        linha = Linha(sessao.catalogo,
                      tipo=(comando.get("tipo") or "LIVRE").upper(),
                      area=projeto.area, nome=comando.get("rotulo"))
        projeto.criar(linha)
        return {"montagem": linha.id, "rotulo": linha.nome}
    if not comando.get("alvo") and acao != "renomear":
        raise Erro(f"{acao} precisa dizer qual montagem")
    try:
        if acao == "escolher":
            montagem = projeto.escolher(comando["alvo"])
        elif acao == "renomear":
            montagem = projeto.renomear(comando.get("alvo") or projeto.ativa.id,
                                        comando.get("rotulo"),
                                        comando.get("tipo"))
        elif acao == "remover":
            if len(projeto.montagens) < 2:
                raise Erro("o projeto ficaria sem montagem nenhuma")
            montagem = projeto.remover(comando["alvo"])
        else:
            raise Erro(f"nao sei {acao!r} - só criar, escolher, renomear "
                       f"ou remover")
    except KeyError as erro:
        raise Erro(str(erro).strip("'")) from None
    return {"montagem": montagem.id, "rotulo": montagem.nome,
            "tipo": montagem.tipo}


def _vocabulario(sessao, comando):
    """Os verbos da barra de comando. A tela pede uma vez e completa sozinha.

    Se a tela tivesse a propria lista, um verbo novo no motor nao apareceria
    na barra e um verbo removido continuaria sendo oferecido - a mesma
    divergencia que ela evita nao guardando documento.
    """
    return {"verbos": linguagem.vocabulario(),
            "montagens": templates.catalogo_de_montagens(),
            # a mesma maquina sai furada de tres jeitos conforme o pedido -
            # quem sabe quais e o motor, e a tela so oferece
            "furacoes_bomba": [{"chave": chave, "nome": nome}
                               for chave, nome
                               in regras.FURACOES_DE_BOMBA.items()]}


def _procurar(sessao, comando):
    """Busca por texto livre no catalogo - codigo, nome, familia, bitola."""
    texto = comando.get("texto") or ""
    achados = sessao.catalogo.procurar(texto, comando.get("limite", 12))
    return {"texto": texto,
            "itens": [{"sap": i["sap"], "descricao": i["descricao"],
                       "familia": i["familia"], "material": i["material"],
                       "dn": list(i["dn"] or [])} for i in achados]}


# Familias que NAO se escolhem por bitola. A bomba nao tem DN: ela tem
# tamanho (65-200), rotor e potencia, e as bocas dela e que tem bitola - uma
# de sucção e outra de recalque, quase sempre diferentes. Pedir "bomba de 8"
# nao quer dizer nada, e enquanto o painel so sabia perguntar familia+bitola
# a bomba nao aparecia nele: so dava para chamar pelo nome, na barra.
SEM_BITOLA = ("BOMBA", "QUADRO", "FILTRO")


def _catalogo(sessao, comando):
    """O que a lista tem para essa familia e bitola - para a tela oferecer."""
    familia, dn = comando.get("familia"), comando.get("dn")
    if not familia:
        raise Erro("informe a familia")
    if (familia or "").upper() in SEM_BITOLA:
        texto = (comando.get("texto") or "").strip()
        achados = [i for i in sessao.catalogo.itens
                   if i["familia"] == familia.upper()]
        if texto:
            procurados = {i["sap"] for i in
                          sessao.catalogo.procurar(texto, 200)}
            achados = [i for i in achados if i["sap"] in procurados]
        achados.sort(key=lambda i: i["descricao"])
        return {"itens": [{"sap": i["sap"], "descricao": i["descricao"],
                           "dn": list(i["dn"] or []),
                           "material": i["material"], "angulo": i["angulo"]}
                          for i in achados[:comando.get("limite", 40)]],
                "sem_bitola": True}
    if dn is None:
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
        if formato == "linha":
            conteudo = arquivo.guardar(sessao.projeto)
        elif formato == "dxf":
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


def _abrir(sessao, comando):
    """Poe no lugar do documento aberto a montagem que veio do arquivo.

    Nao entra no historico, e por um motivo so: o historico e do DOCUMENTO, e
    este e outro documento. Um `desfazer` que voltasse ao projeto anterior
    misturaria duas linhas na mesma pilha, e a peca que o comando de tras
    aponta ja nao existiria.
    """
    texto = comando.get("texto")
    if not texto:
        raise Erro("abrir precisa do arquivo da montagem")
    try:
        projeto, avisos = arquivo.abrir(sessao.catalogo, texto)
    except arquivo.Recusado as erro:
        raise Erro(str(erro)) from erro
    sessao.projeto = projeto
    return {"montagens": len(projeto.montagens),
            "pecas": len(projeto.ativa.pecas), "nome": projeto.nome,
            "area": projeto.area, "recado": avisos}


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
    "acoplar": _acoplar,
    "girar": _girar, "espelhar": _espelhar,
    "balao": _balao, "numerar": _numerar, "bitola": _bitola,
    "ficha": _ficha,
    "desfazer": _desfazer, "refazer": _refazer,
    "template": _template, "catalogo": _catalogo, "janela": _janela,
    "montagem": _montagem, "ramificar": _ramificar,
    "modo": _modo,
    "estilo": _estilo, "simular": _simular, "exportar": _exportar,
    "abrir": _abrir,
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
            # a SELECAO INTEIRA acompanha o que se digitou. O vocabulario nao
            # precisa saber contar: quem escolheu tres tubos e digitou
            # `comprimento 1500` quer os tres, e o verbo continua sendo um so
            if comando.get("alvos") and "alvo" in interno:
                interno["alvos"] = comando["alvos"]
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
