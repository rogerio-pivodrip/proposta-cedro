"""Indice consultavel do catalogo normalizado.

Carrega data/catalogo.json (saida de tools/normalizar.py) e responde consultas
do tipo "qual SAP de curva 90 de 8" flange NBR PN16" em tempo constante.
"""
import json
import os
import re
import unicodedata
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_PADRAO = os.path.join(RAIZ, "data", "catalogo.json")


class Catalogo:
    def __init__(self, caminho=CAMINHO_PADRAO):
        with open(caminho, encoding="utf-8") as fh:
            self.itens = json.load(fh)
        self.por_sap = {i["sap"]: i for i in self.itens}
        self._indice = defaultdict(list)
        for item in self.itens:
            if not item["familia"]:
                continue
            for dn in set(item["dn"]):
                self._indice[(item["familia"], dn)].append(item)

    # Ordem de preferencia de acionamento, do melhor para o pior. A casa usa
    # borboleta com alavanca; onde nao houver, caixa redutora ("gear"), e
    # volante por ultimo. Quem nao declara acionamento fica no meio.
    ACIONAMENTO_PREFERIDO = {
        "VALVULA_BORBOLETA": ["ALAVANCA", "CAIXA", "VOLANTE"],
    }

    # ------------------------------------------------------------ procurar
    def procurar(self, texto, limite=12):
        """Busca por texto livre: codigo, descricao, familia, bitola.

        E a busca de quem esta com a peca na cabeca e nao no indice - "curva
        90 8", "01523-134", "borboleta caixa 8". `buscar` exige familia e DN
        porque serve ao motor; esta serve a pessoa, que digita o que lembra.

        **Numero solto e BITOLA, e nao pedaco de texto.** Procurar "curva 8"
        por substring devolve 18" e 20", e o codigo 01523-000048 na frente das
        duas - porque o "8" esta dentro deles. Aqui o numero e conferido
        contra a lista de DN do item, e so cai no texto (como palavra inteira)
        se nao casar com nenhuma bitola.

        Toda palavra tem de aparecer em algum lugar. Isso e mais util que
        "qualquer palavra": digitar mais SEMPRE estreita, que e o que se
        espera de uma caixa de busca. Nao ha correcao de digitacao - errar
        devolve nada, e isso e melhor que devolver a peca errada com cara de
        certa.
        """
        termos = _sem_acento(texto).split()
        if not termos:
            return []
        numeros, palavras = [], []
        for t in termos:
            valor = _numero(t)
            (numeros if valor is not None else palavras).append(
                valor if valor is not None else t)
        achados = []
        for item in self.itens:
            campos = self._texto_de(item)
            if not all(p in campos for p in palavras):
                continue
            bitolas = {float(d) for d in (item["dn"] or [])
                       if isinstance(d, (int, float))}
            na_bitola = 0
            falhou = False
            for n in numeros:
                if n in bitolas:
                    na_bitola += 1
                elif not re.search(rf"(?<![\d,.]){n:g}(?![\d,.])", campos):
                    falhou = True
                    break
            if falhou:
                continue
            # a ordem: quem casou o numero na BITOLA na frente de quem casou
            # so no texto; depois codigo, depois quem casa cedo na descricao,
            # e por fim a descricao mais curta - a peca mais "limpa"
            por_codigo = any(p in _sem_acento(item["sap"] or "")
                             for p in palavras)
            achados.append((-na_bitola, not por_codigo,
                            campos.find(palavras[0]) if palavras else 0,
                            len(item["descricao"]), item["sap"], item))
        achados.sort(key=lambda t: t[:5])
        return [item for *_ordem, item in achados[:limite]]

    def _texto_de(self, item):
        """Tudo o que se pode digitar para achar a peca, num campo so."""
        return _sem_acento(" ".join(str(v) for v in (
            item["sap"], item["descricao"], item["familia"] or "",
            item.get("acionamento") or "", item.get("material") or "",
            " ".join(c.get("norma") or "" for c in (item["conexoes"] or [])))))

    def buscar(self, familia, dn, norma=None, angulo=None, material="ACO_ZINCADO",
               comprimento_mm=None, dn_saida=None, acionamento=None):
        """Candidatos ordenados do mais simples (menos ressalvas) ao mais exotico."""
        cand = []
        for item in self._indice.get((familia, dn), []):
            if material and item["material"] != material:
                continue
            if angulo is not None and item["angulo"] != angulo:
                continue
            if norma and not any(c["norma"] == norma for c in item["conexoes"]):
                continue
            if dn_saida is not None and dn_saida not in item["dn"]:
                continue
            if comprimento_mm is not None and item["comprimento_mm"] != comprimento_mm:
                continue
            if acionamento and item.get("acionamento") != acionamento:
                continue
            cand.append(item)
        # Preferencia, nesta ordem:
        #  1. peca homogenea - todas as pontas na norma pedida (evita puxar um
        #     tubo com ponta K10 quando a linha inteira e flangeada NBR PN16);
        #  2. menos acessorios soldados (luvas, escapes);
        #  3. descricao mais curta = peca mais "limpa".
        preferido = self.ACIONAMENTO_PREFERIDO.get(familia)

        def ranking(item):
            # acionamento: o pedido primeiro, depois o que nao declara, e por
            # ultimo o outro acionamento
            if not preferido:
                ordem_acionamento = 0
            elif item.get("acionamento") in preferido:
                ordem_acionamento = preferido.index(item["acionamento"])
            else:
                # nao declara acionamento: fica entre o preferido e o ultimo
                ordem_acionamento = len(preferido) - 1
            # engate K nao e usado nas montagens: peca com ponta K so entra se
            # nao houver outra
            tem_k = any(c["tipo"] == "ENGATE_K" for c in item["conexoes"])
            conexoes = [c for c in item["conexoes"] if c["norma"]]
            if norma and conexoes:
                fora = sum(1 for c in conexoes if c["norma"] != norma)
            else:
                fora = 0
            return (ordem_acionamento, tem_k, fora, len(item["derivacoes"]),
                    len(item["descricao"]))

        cand.sort(key=ranking)
        return cand

    def melhor(self, *args, **kwargs):
        cand = self.buscar(*args, **kwargs)
        return cand[0] if cand else None

    def barras_irmas(self, item):
        """As barras do MESMO tubo em outros comprimentos, por comprimento.

        Irma quer dizer: mesma familia, mesma bitola, mesmo material e as
        MESMAS PONTAS. A ponta importa mais do que parece - a lista tem o
        mesmo 8" em FL NBR PN16, em K10 e em ponta lisa, e trocar de
        comprimento pulando para outra ponta entregaria uma barra que nao
        encaixa em nada da linha. Entao a assinatura de conexao entra na
        chave, e nao so o DN.

        Devolve {comprimento_mm: item}, com o mais parecido quando ha mais de
        um no mesmo comprimento - a descricao mais curta, que e a peca mais
        limpa, como em `buscar`.
        """
        if item["familia"] != "TUBO" or not item["dn"]:
            return {}
        assinatura = _pontas(item)
        familia = {}
        for outro in self._indice.get(("TUBO", item["dn"][0]), []):
            if (outro["material"] != item["material"]
                    or not outro["comprimento_mm"]
                    or _pontas(outro) != assinatura):
                continue
            atual = familia.get(outro["comprimento_mm"])
            if atual is None or len(outro["descricao"]) < len(atual["descricao"]):
                familia[outro["comprimento_mm"]] = outro
        return dict(sorted(familia.items()))

    def comprimentos_tubo(self, dn, norma="NBR PN16", material="ACO_ZINCADO"):
        """Comprimentos de tubo disponiveis em estoque para esse DN (mm)."""
        comps = {
            i["comprimento_mm"]
            for i in self.buscar("TUBO", dn, norma=norma, material=material)
            if i["comprimento_mm"]
        }
        return sorted(comps)


def _pontas(item):
    """A assinatura das pontas: tipo e norma de cada conexao, em ordem.

    E o que separa o 8" FL NBR PN16 do 8" K10 e do 8" de ponta lisa. Sem ela,
    esticar um tubo flangeado podia devolver uma barra de ponta lisa - mesma
    bitola, mesmo comprimento, e nada onde parafusar.
    """
    return tuple(sorted((c.get("tipo") or "", c.get("norma") or "")
                        for c in (item.get("conexoes") or [])))


def _numero(termo):
    """O termo e um numero solto? Devolve o valor, ou None.

    Codigo SAP tem traco e nao entra aqui - `01523-134` continua sendo
    palavra, e e assim que procurar por pedaco de codigo funciona.
    """
    try:
        return float(termo.replace(",", "."))
    except ValueError:
        return None


def _sem_acento(texto):
    """Minusculo e sem acento, para comparar o que a pessoa digitou.

    A descricao da lista vem em maiuscula e sem acento; o que se digita vem em
    minuscula e as vezes com acento. Normalizar os dois lados e o que faz
    "sucção" achar "SUCCAO".
    """
    normal = unicodedata.normalize("NFD", str(texto).lower())
    return re.sub(r"\s+", " ",
                  "".join(c for c in normal if not unicodedata.combining(c)))
