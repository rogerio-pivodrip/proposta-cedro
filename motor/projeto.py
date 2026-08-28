"""O projeto: varias montagens no mesmo documento.

Uma casa de bomba nao e uma linha. E a sucção, o recalque, o barrilete, o
trecho de PEAD que sai para o campo - e, quando ha duas bombas, e tudo isso
duas vezes, em serie ou em paralelo. Enquanto a sessao guardava UMA `Linha`, o
programa sabia desenhar cada pedaco e nao sabia guardar a casa.

**A montagem continua sendo o documento; o projeto e a pasta.** Nenhum comando
de edicao mudou de lugar: `inserir`, `remover`, `alterar`, `mover` e
`substituir` continuam sendo da `Linha`, e agem na montagem ATIVA. O que o
projeto faz e outra coisa - criar, escolher, renomear e apagar montagem - e
essas quatro tambem sao comandos, pelo mesmo motivo que as outras cinco sao:
quem apagou uma montagem por engano tem de poder voltar.

**Desfazer atravessa montagens.** Cada `Comando` sabe QUANDO aconteceu
(`Comando.ordem`), e o desfazer do projeto escolhe o mais recente de todas as
pilhas. Sem isso, quem edita a sucção, troca para o recalque e aperta ctrl+Z
desfaria a ultima edicao do RECALQUE - um comando que ele fez faz dez minutos
- em vez do que acabou de fazer. A pilha e por montagem; a ordem e do
programa inteiro.
"""
from .linha import Comando, Linha


class Projeto:
    def __init__(self, catalogo, nome="Casa de bomba", area="P01"):
        self.catalogo = catalogo
        self.nome = nome
        self.area = area
        self.montagens = []
        self._ativa = None
        self.feitos = []          # so os comandos DO PROJETO
        self.desfeitos = []

    # ---------------------------------------------------------------- ler
    @property
    def ativa(self):
        """A montagem em que os comandos caem. Nunca None num projeto com uma.

        Quem pede a montagem ativa de um projeto vazio recebe uma vazia recem
        criada, e nao None: a tela nao tem de saber desenhar "nenhuma".
        """
        for montagem in self.montagens:
            if montagem.id == self._ativa:
                return montagem
        if self.montagens:
            self._ativa = self.montagens[0].id
            return self.montagens[0]
        return self.criar(Linha(self.catalogo, tipo="LIVRE",
                                area=self.area, nome="Montagem"))

    def achar(self, alvo):
        """A montagem pelo id, pelo nome ou pela posicao (contando de 1)."""
        if isinstance(alvo, Linha):
            return alvo
        if isinstance(alvo, int):
            if 1 <= alvo <= len(self.montagens):
                return self.montagens[alvo - 1]
            raise KeyError(f"nao ha montagem {alvo}")
        chave = str(alvo).strip()
        for montagem in self.montagens:
            if montagem.id == chave:
                return montagem
        baixo = chave.lower()
        for montagem in self.montagens:
            if montagem.nome.lower() == baixo:
                return montagem
        for montagem in self.montagens:
            if baixo and baixo in montagem.nome.lower():
                return montagem
        raise KeyError(f"nao ha montagem {alvo!r} neste projeto")

    # ----------------------------------------------------------- a arvore
    #
    # Um ramo e uma montagem ANCORADA numa boca livre de uma peca de outra.
    # Nao e um acessorio: acessorio e peca terminal, que fecha a boca; o ramo
    # continua, com tubo, curva, valvula e o que mais precisar. E e assim que
    # se monta o barrilete, a adução e as duas bombas em paralelo - cada
    # derivação e uma corrente, e corrente o programa ja sabe montar.
    def dona_da_peca(self, peca_id):
        """A montagem em que esta peca esta. None se ela nao esta em nenhuma."""
        for montagem in self.montagens:
            for peca in montagem.todas_as_pecas():
                if peca.id == peca_id:
                    return montagem
        return None

    def filhos(self, montagem):
        """As montagens que saem de alguma peca desta."""
        montagem = self.achar(montagem)
        meus = {p.id for p in montagem.todas_as_pecas()}
        return [m for m in self.montagens
                if m.origem and m.origem.get("peca") in meus]

    def pai(self, montagem):
        montagem = self.achar(montagem)
        if not montagem.origem:
            return None
        return self.dona_da_peca(montagem.origem.get("peca"))

    def raiz(self, montagem):
        """A montagem de onde a arvore desta pende. Ela mesma, se for raiz."""
        montagem = self.achar(montagem)
        vistos = {montagem.id}
        while True:
            acima = self.pai(montagem)
            if acima is None or acima.id in vistos:
                return montagem
            montagem, _ = acima, vistos.add(acima.id)

    def arvore(self, montagem):
        """A raiz e tudo o que pende dela, em ordem de leitura."""
        raiz = self.raiz(montagem)
        saida, fila = [], [raiz]
        while fila:
            atual = fila.pop(0)
            if atual in saida:
                continue
            saida.append(atual)
            fila += self.filhos(atual)
        return saida

    def ramificar(self, peca_id, boca=0, nome=None, tipo="RAMO"):
        """Abre uma montagem nova saindo da boca livre de uma peca.

        A boca e o INDICE entre as bocas que sobram na peca - o te tem uma, o
        manifold tem uma por bocal. Quem escolhe qual e quem ramifica; o
        desenho so obedece.
        """
        dona = self.dona_da_peca(peca_id)
        if dona is None:
            raise KeyError(f"peca {peca_id} nao esta em montagem nenhuma")
        ramo = Linha(self.catalogo, tipo=(tipo or "RAMO").upper(),
                     area=dona.area, nome=nome)
        ramo.origem = {"peca": peca_id, "boca": int(boca)}
        return self.criar(ramo)

    # ----------------------------------------------------- comandos do projeto
    def _executar(self, comando):
        comando.fazer()
        self.feitos.append(comando)
        self.desfeitos.clear()
        return comando

    def criar(self, montagem, escolher=True):
        """Poe uma montagem no projeto. Devolve ela."""
        antes = self._ativa

        def fazer():
            self.montagens.append(montagem)
            if escolher:
                self._ativa = montagem.id

        def desfazer():
            self.montagens.remove(montagem)
            self._ativa = antes

        self._executar(Comando("montagem", fazer, desfazer, montagem.id))
        return montagem

    def remover(self, alvo):
        montagem = self.achar(alvo)
        pos = self.montagens.index(montagem)
        antes = self._ativa

        def fazer():
            self.montagens.pop(pos)
            if self._ativa == montagem.id:
                seguinte = self.montagens[min(pos, len(self.montagens) - 1)] \
                    if self.montagens else None
                self._ativa = seguinte.id if seguinte else None

        def desfazer():
            self.montagens.insert(pos, montagem)
            self._ativa = antes

        self._executar(Comando("montagem", fazer, desfazer, montagem.id))
        return montagem

    def escolher(self, alvo):
        """Troca a montagem ativa.

        Nao entra no historico: escolher nao edita nada. Um ctrl+Z depois de
        trocar de aba tem de desfazer a ULTIMA EDICAO, e nao a troca de aba.
        """
        self._ativa = self.achar(alvo).id
        return self.ativa

    def renomear(self, alvo, nome, tipo=None):
        montagem = self.achar(alvo)
        antes = (montagem.nome, montagem.tipo)
        depois = (str(nome or montagem.nome).strip() or montagem.nome,
                  (tipo or montagem.tipo).strip().upper() or montagem.tipo)
        if antes == depois:
            return montagem

        def fazer():
            montagem.nome, montagem.tipo = depois

        def desfazer():
            montagem.nome, montagem.tipo = antes

        self._executar(Comando("montagem", fazer, desfazer, montagem.id))
        return montagem

    # --------------------------------------------- desfazer, projeto inteiro
    def _pilhas(self, quais="feitos"):
        return [getattr(self, quais)] + [getattr(m, quais)
                                         for m in self.montagens]

    def desfazer(self):
        """Desfaz O MAIS RECENTE de todas as pilhas. Devolve o comando, ou None.

        Trocar de montagem nao muda o que ctrl+Z faz, e e essa a razao de o
        comando carregar a ordem em que aconteceu.
        """
        pilhas = [p for p in self._pilhas("feitos") if p]
        if not pilhas:
            return None
        pilha = max(pilhas, key=lambda p: p[-1].ordem)
        comando = pilha.pop()
        comando.desfazer()
        self._guardar_desfeito(pilha, comando)
        return comando

    def refazer(self):
        pilhas = [p for p in self._pilhas("desfeitos") if p]
        if not pilhas:
            return None
        pilha = max(pilhas, key=lambda p: p[-1].ordem)
        comando = pilha.pop()
        comando.fazer()
        self._guardar_feito(pilha, comando)
        return comando

    def _dona(self, pilha, quais):
        """De quem e a pilha - do projeto ou de uma montagem."""
        if pilha is getattr(self, quais):
            return self
        for montagem in self.montagens:
            if pilha is getattr(montagem, quais):
                return montagem
        return self

    def _guardar_desfeito(self, pilha, comando):
        self._dona(pilha, "feitos").desfeitos.append(comando)

    def _guardar_feito(self, pilha, comando):
        self._dona(pilha, "desfeitos").feitos.append(comando)

    @property
    def pode_desfazer(self):
        return any(self._pilhas("feitos"))

    @property
    def pode_refazer(self):
        return any(self._pilhas("desfeitos"))

    def historico(self):
        """Os comandos do projeto inteiro, do primeiro ao ultimo."""
        todos = [c for pilha in self._pilhas("feitos") for c in pilha]
        return sorted(todos, key=lambda c: c.ordem)

    # ------------------------------------------------- as duas projecoes
    #
    # Com ramo, a lista deixa de ser da montagem e passa a ser da ARVORE: o
    # desenho mostra o tronco e as saidas juntos, e lista e desenho sao as
    # duas projecoes DA MESMA COISA. Uma lista so do tronco, ao lado de um
    # desenho que mostra as saidas, seria a divergencia que este programa
    # existe para nao ter.
    def lista_materiais(self, montagem=None):
        """A lista da arvore inteira. (itens, avisos)"""
        from collections import OrderedDict

        from . import regras
        from .linha import ferragem_de_juncao

        bom, avisos = OrderedDict(), []

        def somar(sap, descricao, qtd, origem):
            reg = bom.setdefault(sap, {"sap": sap, "descricao": descricao,
                                       "qtd": 0, "origem": origem})
            reg["qtd"] += qtd

        arvore = self.arvore(montagem or self.ativa)
        for cada in arvore:
            itens, recados = cada.lista_materiais()
            for reg in itens:
                somar(reg["sap"], reg["descricao"], reg["qtd"], reg["origem"])
            avisos += [f"{cada.nome}: {a}" if len(self.montagens) > 1 else a
                       for a in recados]
        # A BOCA EM QUE O RAMO NASCE E UMA JUNTA, e ela nao pertence a
        # montagem nenhuma - nasce entre duas, e por isso escapava das duas
        # listas. O desenho ja punha a ferragem dela; a lista nao comprava
        # nenhuma, e o barrilete saia com tres derivações sem parafuso.
        for ramo in arvore:
            if not ramo.origem or not ramo.pecas:
                continue
            dona = self.dona_da_peca(ramo.origem.get("peca"))
            if dona is None or dona not in arvore:
                continue
            dono = dona.achar(ramo.origem["peca"])
            # a boca da derivação nao esta separada nas conexoes do cadastro:
            # no te igual ela tem a mesma bitola e a mesma norma das outras,
            # e e por isso que a saida serve de porta. Num te REDUZIDO isso
            # aproxima - a derivação e a menor - e o aviso de bitola aparece
            saida, entrada = dono.saida, ramo.pecas[0].entrada
            if not saida or not entrada:
                continue
            acao, dados = regras.resolver_juncao(saida, entrada)
            ferragem_de_juncao(
                self.catalogo,
                {"pos": 0, "acao": acao, "dados": dados,
                 "de": dono, "para": ramo.pecas[0]},
                somar, avisos, rotulo=f"{ramo.nome} nasce em {dona.nome}: ")
        for numero, reg in enumerate(bom.values(), 1):
            reg["item"] = numero
        return list(bom.values()), avisos

    def numeracao(self, montagem=None):
        """{codigo SAP: numero do item} da arvore desenhada."""
        from collections import OrderedDict

        itens, _avisos = self.lista_materiais(montagem)
        return OrderedDict((r["sap"], r["item"]) for r in itens)

    def baloes(self, montagem=None):
        """Os baloes de todas as montagens da arvore, com o numero da lista."""
        numeros = self.numeracao(montagem)
        saida = []
        for cada in self.arvore(montagem or self.ativa):
            for peca in cada.todas_as_pecas():
                if not peca.balao or peca.sap not in numeros:
                    continue
                saida.append({"id": peca.id, "n": numeros[peca.sap],
                              "angulo": peca.balao_angulo,
                              "distancia": peca.balao_distancia,
                              "montagem": cada.id})
        return saida

    def resumo(self):
        """O que a tela mostra na tira de montagens."""
        ativa = self.ativa
        return [{"id": m.id, "nome": m.nome, "tipo": m.tipo, "area": m.area,
                 "pecas": len(m.pecas), "ativa": m.id == ativa.id,
                 "ramo": bool(m.origem),
                 "origem": dict(m.origem) if m.origem else None}
                for m in self.montagens]
