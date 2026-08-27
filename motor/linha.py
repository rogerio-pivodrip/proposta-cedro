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
