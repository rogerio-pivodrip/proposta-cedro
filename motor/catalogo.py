"""Indice consultavel do catalogo normalizado.

Carrega data/catalogo.json (saida de tools/normalizar.py) e responde consultas
do tipo "qual SAP de curva 90 de 8" flange NBR PN16" em tempo constante.
"""
import json
import os
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

    # A casa usa borboleta com alavanca; volante entra so se nao houver.
    ACIONAMENTO_PREFERIDO = {"VALVULA_BORBOLETA": "ALAVANCA"}

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
            elif item.get("acionamento") == preferido:
                ordem_acionamento = 0
            elif not item.get("acionamento"):
                ordem_acionamento = 1
            else:
                ordem_acionamento = 2
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

    def comprimentos_tubo(self, dn, norma="NBR PN16", material="ACO_ZINCADO"):
        """Comprimentos de tubo disponiveis em estoque para esse DN (mm)."""
        comps = {
            i["comprimento_mm"]
            for i in self.buscar("TUBO", dn, norma=norma, material=material)
            if i["comprimento_mm"]
        }
        return sorted(comps)
