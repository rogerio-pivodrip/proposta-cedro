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

    def resumo(self):
        """O que a tela mostra na tira de montagens."""
        ativa = self.ativa
        return [{"id": m.id, "nome": m.nome, "tipo": m.tipo, "area": m.area,
                 "pecas": len(m.pecas), "ativa": m.id == ativa.id}
                for m in self.montagens]
