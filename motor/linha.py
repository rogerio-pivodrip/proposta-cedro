"""Documento unico: a linha. Desenho e lista sao duas projecoes dela.

Nenhuma sincronizacao entre desenho e planilha - as duas views leem o mesmo
objeto Linha e escrevem nele pelos mesmos comandos (inserir / remover /
substituir / alterar / mover). Toda edicao dispara recalculo das juncoes e da
ferragem derivada.
"""
from collections import OrderedDict

from . import corte, ferragem, regras


class Peca:
    """Uma peca instanciada na linha, com suas portas."""

    def __init__(self, item, comprimento_mm=None, rotulo=None):
        self.item = item                      # registro do catalogo
        self.sap = item["sap"]
        self.descricao = item["descricao"]
        self.familia = item["familia"]
        self.material = item["material"]
        self.unidade_dn = item["unidade_dn"] or "in"
        self.angulo = item["angulo"]
        self.comprimento_mm = (comprimento_mm or item.get("comprimento_mm")
                               or self._face_a_face() or 0)
        self.rotulo = rotulo
        self.portas = self._portas()

    def _face_a_face(self):
        """Valvula wafer tem espessura de corpo tabelada na ficha do fabricante -
        e ela que entra na geometria da vista lateral."""
        if not self.item["dn"] or self.item["familia"] not in \
                regras.BARRA_ROSCADA_POR_PECA:
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
        return [j for j in self.juncoes()
                if j["acao"] in ("reducao", "adaptador", "recusada")]

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

        # valvula wafer: 3 tirantes de barra roscada, com porca e arruela.
        # As barras sao cortadas, entao os tirantes viram metragem e so no fim
        # se sabe quantas barras de 1 m comprar.
        cortes = {}
        for peca in self.pecas:
            dn = peca.item["dn"][0] if peca.item["dn"] else None
            if dn is None:
                continue
            contexto = regras.contexto_da_junta(peca.material, peca.material)
            ficha = (regras.ficha_wafer(
                regras.dn_em_polegada(dn, peca.unidade_dn) or dn)
                if peca.familia in regras.BARRA_ROSCADA_POR_PECA else None)
            if ficha:
                dn_nom = regras.dn_nominal(dn, peca.unidade_dn)
                flange = regras.FUROS.get(("NBR PN16", dn_nom)) if dn_nom else None
                if flange and flange["furos"] != ficha["furos"]:
                    avisos.append(
                        f"{peca.familia} {dn:g}: a valvula e classe ASME 150 com "
                        f"{ficha['furos']} furos e o flange NBR PN16 tem "
                        f"{flange['furos']} - conferir o casamento de furacao"
                    )
            for papel, esp, qtd in regras.barra_roscada_da_peca(
                    peca.familia, dn, peca.unidade_dn, contexto):
                item = ferragem.resolver(self.catalogo, papel, esp)
                if not item:
                    avisos.append(f"sem SAP para {papel} {esp}")
                    continue
                if papel != "BARRA_ROSCADA":
                    somar(item["sap"], item["descricao"], qtd, "tirante")
                    continue
                if esp.get("comprimento_mm"):
                    cortes.setdefault(item["sap"], {"item": item, "cortes": []})
                    cortes[item["sap"]]["cortes"].extend(
                        [esp["comprimento_mm"]] * qtd)
                else:
                    somar(item["sap"], item["descricao"], qtd, "tirante")
                    avisos.append(
                        f"{peca.familia} {peca.item['dn'][0]:g}: {qtd} tirantes de "
                        f"{esp['bitola_pol']}\" - espessura do corpo da valvula nao "
                        "cadastrada, contado como barra inteira"
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

        for sap, reg in cortes.items():
            plano = corte.planejar(reg["cortes"], regras.BARRA_MM)
            somar(sap, reg["item"]["descricao"], plano["barras"], "tirante")
            avisos.append(
                f"{len(reg['cortes'])} tirantes ({sum(reg['cortes'])/1000:.2f} m) "
                f"-> {plano['barras']} barra(s) de {regras.BARRA_MM/1000:g} m, "
                f"aproveitamento {plano['aproveitamento']:.0%}"
            )

        return list(bom.values()), avisos
