"""Documento unico: a linha. Desenho e lista sao duas projecoes dela.

Nenhuma sincronizacao entre desenho e planilha - as duas views leem o mesmo
objeto Linha e escrevem nele pelos mesmos comandos (inserir / remover /
substituir / alterar / mover). Toda edicao dispara recalculo das juncoes e da
ferragem derivada.
"""
from collections import OrderedDict

from . import ferragem, regras


class Peca:
    """Uma peca instanciada na linha, com suas portas."""

    def __init__(self, item, comprimento_mm=None, rotulo=None):
        self.item = item                      # registro do catalogo
        self.sap = item["sap"]
        self.descricao = item["descricao"]
        self.familia = item["familia"]
        self.angulo = item["angulo"]
        self.comprimento_mm = comprimento_mm or item.get("comprimento_mm") or 0
        self.rotulo = rotulo
        self.portas = self._portas()

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


class Linha:
    def __init__(self, catalogo, tipo="RECALQUE", area="P01"):
        self.catalogo = catalogo
        self.tipo = tipo          # SUCCAO | RECALQUE
        self.area = area
        self.pecas = []
        self.historico = []       # pilha de comandos para undo

    # ---------------- comandos (unica porta de escrita do modelo) -----------
    def inserir(self, peca, pos=None):
        pos = len(self.pecas) if pos is None else pos
        self.pecas.insert(pos, peca)
        self.historico.append(("inserir", pos, peca))
        return peca

    def remover(self, pos):
        peca = self.pecas.pop(pos)
        self.historico.append(("remover", pos, peca))
        return peca

    def substituir(self, pos, peca):
        antiga = self.pecas[pos]
        self.pecas[pos] = peca
        self.historico.append(("substituir", pos, antiga))
        return antiga

    def desfazer(self):
        if not self.historico:
            return
        acao, pos, peca = self.historico.pop()
        if acao == "inserir":
            self.pecas.pop(pos)
        elif acao == "remover":
            self.pecas.insert(pos, peca)
        elif acao == "substituir":
            self.pecas[pos] = peca

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

    def problemas(self):
        return [j for j in self.juncoes() if j["acao"] in ("reducao", "adaptador")]

    def geometria(self):
        """Posicao acumulada de cada peca no eixo da linha (mm) e angulo corrente.

        E o que o desenho consome: nao e CAD, e a soma dos comprimentos
        face-a-face com as curvas girando a direcao.
        """
        x = y = 0.0
        direcao = 0.0
        pontos = []
        import math

        for peca in self.pecas:
            comp = peca.comprimento_mm or 300  # peca curta padrao p/ conexao
            nx = x + comp * math.cos(math.radians(direcao))
            ny = y + comp * math.sin(math.radians(direcao))
            pontos.append({"peca": peca, "de": (x, y), "para": (nx, ny),
                           "direcao": direcao})
            x, y = nx, ny
            if peca.familia == "CURVA" and peca.angulo:
                direcao += peca.angulo
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

        for peca in self.pecas:
            somar(peca.sap, peca.descricao, 1, "linha")

        for junc in self.juncoes():
            if junc["acao"] != "direta":
                avisos.append(
                    f"juncao {junc['pos']}: precisa de {junc['acao']} {junc['dados']}"
                )
                continue
            dados = junc["dados"]
            if dados["junta"] not in regras.TIPOS_FLANGE:
                continue  # engate K, rosca, solda: sem ferragem
            try:
                itens = regras.ferragem_da_junta(dados["dn"], dados["norma"])
            except regras.Incompatibilidade as erro:
                avisos.append(str(erro))
                continue
            for papel, esp, qtd in itens:
                item = ferragem.resolver(self.catalogo, papel, esp)
                if not item:
                    avisos.append(f"sem SAP para {papel} {esp}")
                    continue
                somar(item["sap"], item["descricao"], qtd, "ferragem")

        return list(bom.values()), avisos
