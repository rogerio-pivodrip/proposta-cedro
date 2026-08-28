"""Documento unico: a linha. Desenho e lista sao duas projecoes dela.

Nenhuma sincronizacao entre desenho e planilha - as duas views leem o mesmo
objeto Linha e escrevem nele pelos mesmos comandos (inserir / remover /
substituir / alterar / mover). Toda edicao dispara recalculo das juncoes e da
ferragem derivada.

Os cinco comandos sao a UNICA porta de escrita, e cada um sabe se desfazer.
Isso nao e conforto de interface: e o que garante que desenho e lista nunca
divirjam. Quem edita nao mexe em `pecas` - mexer ali contorna o historico e
deixa o documento num estado que nao da para reverter.

**A peca e enderecada por id, nao por posicao.** Indice muda quando alguem
insere, remove ou move, e a tela que segurou um indice passa a apontar para
outra peca. O id nasce com a peca e morre com ela, e e o mesmo no balao do
desenho e na linha da tabela.
"""
import itertools
from collections import OrderedDict

from . import corte, cotas, ferragem, regras

_contador = itertools.count(1)


class Peca:
    """Uma peca instanciada na linha, com suas portas."""

    def __init__(self, item, comprimento_mm=None, rotulo=None, fonte=None,
                 sentido=1, pose=None):
        self.id = f"p{next(_contador)}"       # estavel: sobrevive a mover
        self.item = item                      # registro do catalogo
        self.sap = item["sap"]
        self.descricao = item["descricao"]
        self.familia = item["familia"]
        self.material = item["material"]
        self.unidade_dn = item["unidade_dn"] or "in"
        self.angulo = item["angulo"]
        self.fonte = fonte or cotas.PADRAO   # fabricante da peca comprada
        self.sentido = sentido               # +1 sobe, -1 desce: espelha a curva
        # como a peca esta MONTADA, quando ela tem mais de um jeito. O te em
        # linha e o te de pe sobre a derivacao sao o mesmo codigo SAP - a pose
        # e da instancia, como o sentido da curva
        self.pose = pose
        self.fonte_cota = None               # de quem veio a cota que entrou
        self._comprimento_pedido = comprimento_mm
        self.comprimento_mm = (comprimento_mm or item.get("comprimento_mm")
                               or self._da_tabela() or self._face_a_face() or 0)
        self.rotulo = rotulo
        # o que fecha a boca que sobra desta peca. O te tem tres bocas e a
        # corrente usa duas; a terceira nao e um ramo novo - e uma ponta, e o
        # que entra nela e uma peca terminal: flange cega, ventosa, dreno.
        # Guardar aqui, e nao numa lista paralela, e o que faz o acessorio
        # sair junto quando a peca sai
        self.acessorios = []
        self.portas = self._portas()

    def recalcular(self):
        """Refaz o que depende da fonte e da cota, sem trocar a peca.

        Existe por causa do comando `alterar`: trocar o fabricante nao troca a
        peca, troca a TABELA de onde a cota dela sai - e a cota tem de vir
        junto. Ver docs/MOTOR.md 4: a mesma peca mede diferente em cada folha.
        """
        self.comprimento_mm = (self._comprimento_pedido
                               or self.item.get("comprimento_mm")
                               or self._da_tabela() or self._face_a_face() or 0)
        self.portas = self._portas()
        return self

    def _chave_de_cota(self):
        """(familia, variante, significado) para procurar na tabela de cotas."""
        if self.familia == "CURVA" and self.angulo:
            return "CURVA", str(self.angulo), "perna_mm"
        if self.familia == "CRIVO":
            return "CRIVO", "", "comprimento_mm"
        if self.familia in ("MANIFOLD", "ARTICULADOR"):
            return self.familia, "", "comprimento_mm"
        if self.familia == "VALVULA_HIDRAULICA":
            # a cota do corpo sai da serie do fabricante, nao do codigo
            return self.familia, self.item.get("serie") or "", "face_a_face_mm"
        if self.familia == "VALVULA_BORBOLETA":
            # a ficha separa alavanca de caixa redutora: o corpo tambem muda
            return self.familia, self.item.get("acionamento") or "", "face_a_face_mm"
        return self.familia, "", "face_a_face_mm"

    def _da_tabela(self):
        """A cota do fabricante. E aqui que o padrao da casa entra no desenho."""
        if self.unidade_dn != "in":
            return None
        bitolas = [d for d in (self.item["dn"] or []) if isinstance(d, (int, float))]
        if not bitolas:
            return None
        familia, variante, significado = self._chave_de_cota()
        menor = min(bitolas) if len(bitolas) > 1 else None
        valor, fonte = cotas.cota_com_fonte(familia, max(bitolas), variante,
                                            significado, self.fonte, menor)
        self.fonte_cota = fonte
        return valor

    def avancos(self):
        """Quanto a peca avanca antes e depois de girar a direcao.

        So a curva tem duas pernas - entra por uma e sai pela outra, e o giro
        acontece no meio. O resto avanca tudo antes e nao gira nada.
        """
        comp = self.comprimento_mm or 0
        if self.familia == "CURVA" and self.angulo:
            return comp, comp
        return comp, 0.0

    def _face_a_face(self):
        """Valvula wafer tem espessura de corpo tabelada na ficha do fabricante -
        e ela que entra na geometria da vista lateral."""
        if not self.item["dn"] or self.item["familia"] not in \
                regras.BARRAS_ROSCADAS_POR_PECA:
            return None
        ficha = regras.ficha_wafer(self.item["dn"][0])
        return ficha["esp_corpo_mm"] if ficha else None

    def _portas(self):
        portas = []
        for con in self.item["conexoes"]:
            if con["dn"] is None:
                continue
            portas.append({"dn": con["dn"], "tipo": con["tipo"], "norma": con["norma"]})
        if not portas and self.item["dn"]:
            dn = self.item["dn"][0]
            portas = [{"dn": dn, "tipo": "FLANGE", "norma": None}] * 2
        return portas

    @property
    def entrada(self):
        return self.portas[0] if self.portas else None

    @property
    def saida(self):
        return self.portas[-1] if self.portas else None

    def __repr__(self):
        return f"<{self.familia} {self.sap}>"


class Comando:
    """Uma edicao e o bastante para desfaze-la e para refaze-la.

    Guardar o comando em vez do estado inteiro e o que torna desfazer barato
    numa linha de sessenta pecas: o que se guarda e a diferenca, nao a copia.
    """

    def __init__(self, nome, fazer, desfazer, alvo=None):
        self.nome = nome
        self.fazer = fazer
        self.desfazer = desfazer
        self.alvo = alvo          # id da peca que o comando atingiu

    def __repr__(self):
        return f"<{self.nome} {self.alvo or ''}>".replace(" >", ">")


class Linha:
    # o que `alterar` pode mudar sem trocar a peca. Fora desta lista o
    # comando recusa: mudar familia ou SAP nao e alterar, e substituir
    ALTERAVEIS = ("comprimento_mm", "sentido", "rotulo", "fonte", "pose")

    def __init__(self, catalogo, tipo="RECALQUE", area="P01"):
        self.catalogo = catalogo
        self.tipo = tipo          # SUCCAO | RECALQUE
        self.area = area
        self.pecas = []
        # a POSE da linha na folha: de quanto ela esta girada, e se esta
        # espelhada. Nao e geometria da peca - e como o conjunto se deita no
        # papel, e por isso vale para a tela E para o DXF exportado
        self.giro = 0.0           # graus, no sentido do SVG (y para baixo)
        self.espelho = 1          # +1 normal, -1 refletida no eixo da linha
        self.feitos = []          # pilha de comandos aplicados
        self.desfeitos = []       # o que saiu do desfazer, esperando refazer

    # ---------------- comandos (unica porta de escrita do modelo) -----------
    def _executar(self, comando):
        """Aplica o comando e o empilha.

        Editar apaga o refazer, e isso e proposital: depois de desfazer tres
        passos e editar, o que estava adiante deixou de existir. Manter a
        pilha daria a impressao de um futuro que nao volta mais.
        """
        comando.fazer()
        self.feitos.append(comando)
        self.desfeitos.clear()
        return comando

    def posicao(self, alvo):
        """Aceita indice ou id, e devolve o indice de agora.

        A tela segura o ID; o indice ela nao pode segurar, porque inserir,
        remover e mover mudam o indice de todo mundo depois deles.
        """
        if isinstance(alvo, Peca):
            alvo = alvo.id
        if isinstance(alvo, str):
            for i, peca in enumerate(self.pecas):
                if peca.id == alvo:
                    return i
            raise KeyError(f"peca {alvo} nao esta na linha")
        if alvo < 0:
            alvo += len(self.pecas)
        if not 0 <= alvo < len(self.pecas):
            raise IndexError(f"posicao {alvo} fora da linha de "
                             f"{len(self.pecas)} pecas")
        return alvo

    def inserir(self, peca, pos=None):
        pos = len(self.pecas) if pos is None else (
            pos if isinstance(pos, int) else self.posicao(pos))
        pos = max(0, min(pos, len(self.pecas)))
        self._executar(Comando(
            "inserir",
            lambda: self.pecas.insert(pos, peca),
            lambda: self.pecas.pop(pos),
            peca.id))
        return peca

    def remover(self, alvo):
        pos = self.posicao(alvo)
        peca = self.pecas[pos]
        self._executar(Comando(
            "remover",
            lambda: self.pecas.pop(pos),
            lambda: self.pecas.insert(pos, peca),
            peca.id))
        return peca

    def substituir(self, alvo, peca):
        pos = self.posicao(alvo)
        antiga = self.pecas[pos]
        self._executar(Comando(
            "substituir",
            lambda: self.pecas.__setitem__(pos, peca),
            lambda: self.pecas.__setitem__(pos, antiga),
            peca.id))
        return antiga

    def alterar(self, alvo, **campos):
        """Muda um parametro da peca SEM trocar a peca.

        E a diferenca entre `alterar` e `substituir`, e ela importa na lista:
        alterar o comprimento de um tubo nao muda o codigo SAP que se compra,
        trocar a peca muda. Por isso o id sobrevive ao alterar.

        Trocar a `fonte` e alterar de verdade: nao troca a peca, troca a folha
        de onde a cota dela sai - e a cota vem junto, por `recalcular()`.
        """
        pos = self.posicao(alvo)
        peca = self.pecas[pos]
        fora = [c for c in campos if c not in self.ALTERAVEIS]
        if fora:
            raise ValueError(
                f"{', '.join(fora)} nao e alteravel - so "
                f"{', '.join(self.ALTERAVEIS)}. Mudar familia ou codigo nao e "
                f"alterar, e substituir")
        antes = {c: getattr(peca, c) for c in campos}
        # o comprimento pedido a mao vira o novo pedido: sem isso o
        # recalcular() da fonte apagaria o que a pessoa digitou
        pedido_antes = peca._comprimento_pedido

        def fazer():
            for campo, valor in campos.items():
                setattr(peca, campo, valor)
            if "comprimento_mm" in campos:
                peca._comprimento_pedido = campos["comprimento_mm"]
            elif "fonte" in campos:
                peca.recalcular()

        def desfazer():
            for campo, valor in antes.items():
                setattr(peca, campo, valor)
            peca._comprimento_pedido = pedido_antes
            if "fonte" in campos and "comprimento_mm" not in campos:
                peca.recalcular()

        self._executar(Comando("alterar", fazer, desfazer, peca.id))
        return peca

    def pose(self, giro=None, espelho=None):
        """Gira ou espelha a LINHA INTEIRA na folha. Tambem e comando.

        A peca de uma linha nao tem posicao propria - ela cai onde a anterior
        deixou, ver geometria(). Entao "girar a peca" nao existe aqui: o que
        existe e girar o conjunto, e espelhar uma peca, que e o `sentido` dela.

        Passa pelo historico como qualquer edicao porque muda o que sai no
        DXF: quem girou a folha e desfez tem de voltar ao que exportou antes.
        """
        antes = (self.giro, self.espelho)
        depois = (self.giro if giro is None else float(giro) % 360,
                  self.espelho if espelho is None else (1 if espelho > 0 else -1))
        if depois == antes:
            return self

        def fazer():
            self.giro, self.espelho = depois

        def desfazer():
            self.giro, self.espelho = antes

        self._executar(Comando("pose", fazer, desfazer, None))
        return self

    def acoplar(self, alvo, peca):
        """Poe uma peca terminal na boca que sobra do alvo.

        E o unico jeito honesto de desenhar um te de verdade numa corrente
        linear. O te tem tres bocas: a corrente entra por uma e sai por outra,
        e a terceira fica. O que vai nela - flange cega, ventosa, dreno - nao
        continua a linha, TERMINA ali, e por isso nao precisa virar um ramo
        com regras proprias.

        O acessorio conta na lista de materiais como qualquer peca, e some
        junto quando a peca que o carrega sai - ele vive DENTRO dela.
        """
        pos = self.posicao(alvo)
        dono = self.pecas[pos]

        def fazer():
            dono.acessorios.append(peca)

        def desfazer():
            dono.acessorios.remove(peca)

        self._executar(Comando("acoplar", fazer, desfazer, peca.id))
        return peca

    def desacoplar(self, alvo):
        """Tira um acessorio da peca que o carrega."""
        for dono in self.pecas:
            for i, peca in enumerate(dono.acessorios):
                if peca.id == alvo or peca is alvo:
                    def fazer():
                        dono.acessorios.pop(i)

                    def desfazer():
                        dono.acessorios.insert(i, peca)

                    self._executar(Comando("desacoplar", fazer, desfazer,
                                           peca.id))
                    return peca
        raise KeyError(f"acessorio {alvo} nao esta na linha")

    def todas_as_pecas(self):
        """As pecas da corrente e os acessorios delas, em ordem de leitura.

        E o que a LISTA DE MATERIAIS conta: o acessorio se compra do mesmo
        jeito que a peca que o carrega.
        """
        for peca in self.pecas:
            yield peca
            for acessorio in peca.acessorios:
                yield acessorio

    def mover(self, alvo, para):
        """Tira a peca de onde ela esta e a poe em outra posicao da sequencia.

        A posicao de uma peca e consequencia de quem veio antes - ver
        geometria(). Entao mover uma peca move tudo o que vem depois dela, e e
        por isso que mover e um comando do documento e nao um arrasto na tela.
        """
        de = self.posicao(alvo)
        para = para if isinstance(para, int) else self.posicao(para)
        para = max(0, min(para, len(self.pecas) - 1))
        peca = self.pecas[de]

        def fazer():
            self.pecas.insert(para, self.pecas.pop(de))

        def desfazer():
            self.pecas.insert(de, self.pecas.pop(para))

        self._executar(Comando("mover", fazer, desfazer, peca.id))
        return peca

    # ---------------- desfazer e refazer ------------------------------------
    def desfazer(self):
        """Volta um comando. Devolve o comando desfeito, ou None."""
        if not self.feitos:
            return None
        comando = self.feitos.pop()
        comando.desfazer()
        self.desfeitos.append(comando)
        return comando

    def refazer(self):
        """Reaplica o ultimo comando desfeito. Devolve ele, ou None."""
        if not self.desfeitos:
            return None
        comando = self.desfeitos.pop()
        comando.fazer()
        self.feitos.append(comando)
        return comando

    @property
    def historico(self):
        """Os comandos aplicados, do primeiro ao ultimo."""
        return list(self.feitos)

    # ---------------- derivacoes (recalculadas, nunca digitadas) -----------
    def juncoes(self):
        """Lista de juncoes entre pecas consecutivas, ja resolvidas."""
        out = []
        for i in range(len(self.pecas) - 1):
            a, b = self.pecas[i].saida, self.pecas[i + 1].entrada
            if not a or not b:
                continue
            acao, dados = regras.resolver_juncao(a, b)
            out.append({"pos": i, "acao": acao, "dados": dados,
                        "de": self.pecas[i], "para": self.pecas[i + 1]})
        return out

    def divergencias(self):
        """Peca cuja MEDIDA DESENHADA nao e a medida do CODIGO comprado.

        E a conferencia mais barata do programa e a que evita o erro mais
        caro: um tubo desenhado com 2,35 m carregando o codigo da barra de
        6 m. O desenho vai para a obra dizendo 2,35 e a lista vai para a
        compra dizendo 6 - e as duas estao certas cada uma por si.

        Isso acontece de proposito as vezes: barra de 6 m cortada no campo. Nao
        e defeito, e decisao - mas tem de estar ESCRITA, e nao implicita no
        fato de os dois numeros nunca serem comparados. Quem le a folha ve
        "cortado de 6 m" e sabe o que pedir.

        So o tubo entra: e a unica peca que se corta. Numa valvula os dois
        numeros divergirem seria outra coisa - cota de fabricante contra cota
        da casa - e isso ja e dito pela `fonte`.
        """
        fora = []
        for peca in self.pecas:
            if peca.familia != "TUBO":
                continue
            do_codigo = peca.item.get("comprimento_mm")
            if not do_codigo:
                continue
            desenhado = peca.comprimento_mm or 0
            if abs(desenhado - do_codigo) > 1:
                fora.append({"peca": peca, "desenhado_mm": desenhado,
                             "do_codigo_mm": do_codigo})
        return fora

    def problemas(self):
        return [j for j in self.juncoes()
                if j["acao"] in ("reducao", "adaptador", "recusada")]

    def trechos_retos(self):
        """Confere o tubo reto exigido antes e depois de cada equipamento.

        Conta so tubo: qualquer peca que perturba o fluxo - curva, te, reducao,
        valvula - zera a contagem, porque e ela que estraga a medicao.
        """
        achados = []
        for i, peca in enumerate(self.pecas):
            dn = peca.item["dn"][0] if peca.item["dn"] else None
            if dn is None:
                continue
            exigido = regras.trecho_reto_exigido(peca.familia, dn,
                                                 peca.unidade_dn)
            if not exigido:
                continue
            antes = self._reto(range(i - 1, -1, -1))
            depois = self._reto(range(i + 1, len(self.pecas)))
            achados.append({
                "pos": i, "peca": peca,
                "antes_mm": antes, "depois_mm": depois,
                "exige_antes_mm": exigido[0], "exige_depois_mm": exigido[1],
                "ok": antes >= exigido[0] and depois >= exigido[1],
            })
        return achados

    def _reto(self, indices):
        total = 0
        for i in indices:
            peca = self.pecas[i]
            if peca.familia in regras.PERTURBAM_FLUXO:
                break
            if peca.familia == "TUBO":
                total += peca.comprimento_mm or 0
        return total

    def geometria(self):
        """Posicao acumulada de cada peca no eixo da linha (mm) e angulo corrente.

        Nao e CAD: e a soma vetorial das cotas, com a curva girando a direcao
        entre as suas duas pernas. Nenhuma peca tem posicao propria - a posicao
        e consequencia de quem veio antes, e e isso que faz arrastar uma peca
        no desenho virar "alongar o tubo vizinho" na lista.
        """
        import math

        x = y = 0.0
        direcao = self.giro          # a pose da folha vale aqui tambem: o
        pontos = []                  # esquema nao pode discordar do desenho

        for peca in self.pecas:
            antes, depois = peca.avancos()
            nx = x + antes * math.cos(math.radians(direcao))
            ny = y + antes * math.sin(math.radians(direcao))
            ponto = {"peca": peca, "de": (x, y), "para": (nx, ny),
                     "direcao": direcao, "direcao_saida": direcao,
                     "canto": None, "fonte_cota": peca.fonte_cota}
            x, y = nx, ny

            if peca.familia == "CURVA" and peca.angulo:
                direcao += peca.angulo * peca.sentido * self.espelho
                ponto["direcao_saida"] = direcao
                if depois:
                    ponto["canto"] = (x, y)
                    x += depois * math.cos(math.radians(direcao))
                    y += depois * math.sin(math.radians(direcao))
                    ponto["para"] = (x, y)

            pontos.append(ponto)
        return pontos

    # ---------------- saidas ------------------------------------------------
    def lista_materiais(self):
        """BOM final: pecas da linha + ferragem derivada, agregada por SAP.

        Formato de saida = as colunas da aba Orcamento (Area, Cod. SAP, Qtd).
        """
        bom = OrderedDict()
        avisos = []

        def somar(sap, descricao, qtd, origem):
            reg = bom.setdefault(sap, {"sap": sap, "descricao": descricao,
                                       "qtd": 0, "origem": origem})
            reg["qtd"] += qtd

        for peca in self.todas_as_pecas():
            somar(peca.sap, peca.descricao, 1, "linha")
            # flange de PVC puxa a contra-flange que a prende no tubo
            for papel, esp, qtd in regras.contra_flange_de(peca.item):
                item = ferragem.resolver(self.catalogo, papel, esp)
                if not item:
                    avisos.append(f"sem contra-flange para {peca.sap}")
                    continue
                somar(item["sap"], item["descricao"], qtd, "contra-flange")

        # valvula wafer: 3 barras roscadas inteiras por valvula. O corte
        # acontece na montagem e nao muda a quantidade comprada.
        for peca in self.pecas:
            dn = peca.item["dn"][0] if peca.item["dn"] else None
            if dn is None:
                continue
            contexto = regras.contexto_da_junta(peca.material, peca.material)
            ficha = (regras.ficha_wafer(
                regras.dn_em_polegada(dn, peca.unidade_dn) or dn)
                if peca.familia in regras.BARRAS_ROSCADAS_POR_PECA else None)
            if ficha:
                furos = regras.furos_da_valvula(dn, peca.unidade_dn, "NBR PN16",
                                                ficha)
                if furos != ficha["furos"]:
                    avisos.append(
                        f"{peca.familia} {dn:g}: pedir a valvula em NBR PN16 "
                        f"({furos} furos). A ficha do fabricante e da versao "
                        f"ASME 150, com {ficha['furos']}"
                    )
            for papel, esp, qtd in regras.barra_roscada_da_peca(
                    peca.familia, dn, peca.unidade_dn, contexto):
                item = ferragem.resolver(self.catalogo, papel, esp)
                if not item:
                    avisos.append(f"sem SAP para {papel} {esp}")
                    continue
                somar(item["sap"], item["descricao"], qtd, "tirante")
                if papel == "BARRA_ROSCADA" and ficha:
                    _, por_barra = regras.barras_da_valvula(
                        peca.familia, ficha, dn, peca.unidade_dn)
                    furos = regras.furos_da_valvula(dn, peca.unidade_dn,
                                                    "NBR PN16", ficha)
                    extra = (" (3 nao cobririam a furacao)"
                             if qtd > regras.BARRAS_ROSCADAS_POR_PECA[peca.familia]
                             else "")
                    avisos.append(
                        f"{peca.familia} {dn:g}: {qtd} barras de "
                        f"{esp['bitola_pol']}\" - tirante de "
                        f"{ficha['comp_prisioneiro_mm']:.0f} mm, "
                        f"{por_barra} por barra, {qtd * por_barra} tirantes "
                        f"para {furos} furos{extra}"
                    )

        for junc in self.juncoes():
            if junc["acao"] == "recusada":
                avisos.append(f"juncao {junc['pos']} "
                              f"({junc['de'].familia} -> {junc['para'].familia}): "
                              f"{junc['dados']['motivo']}")
                continue
            if junc["acao"] != "direta":
                avisos.append(
                    f"juncao {junc['pos']}: precisa de {junc['acao']} {junc['dados']}"
                )
                continue
            dados = junc["dados"]
            if dados["junta"] not in regras.TIPOS_FLANGE:
                continue  # rosca, solda, ponta lisa: sem ferragem
            contexto = regras.contexto_da_junta(junc["de"].material,
                                                junc["para"].material)
            if regras.contexto_sem_regra(contexto):
                avisos.append(
                    f"juncao {junc['pos']} ({junc['de'].material} x "
                    f"{junc['para'].material}): combinacao sem regra de "
                    "parafuso - conferir"
                )
            try:
                itens = regras.ferragem_da_junta(
                    dados["dn"], dados["norma"], junc["de"].unidade_dn, contexto)
            except regras.Incompatibilidade as erro:
                avisos.append(str(erro))
                continue
            for papel, esp, qtd in itens:
                item = ferragem.resolver(self.catalogo, papel, esp)
                if not item:
                    avisos.append(f"sem SAP para {papel} {esp}")
                    continue
                somar(item["sap"], item["descricao"], qtd, "ferragem")

        for t in self.trechos_retos():
            if t["ok"]:
                continue
            avisos.append(
                f"{t['peca'].familia} na posicao {t['pos']}: precisa de "
                f"{t['exige_antes_mm']/1000:.2f} m de tubo reto antes e "
                f"{t['exige_depois_mm']/1000:.2f} m depois; o desenho tem "
                f"{t['antes_mm']/1000:.2f} m e {t['depois_mm']/1000:.2f} m"
            )

        return list(bom.values()), avisos
