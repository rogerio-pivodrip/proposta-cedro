#!/usr/bin/env python3
"""Quantos codigos do catalogo o desenho ja cobre, e o que falta para o resto.

Tenta desenhar cada item do catalogo com o simbolo da sua familia. Nao conta
familia coberta: conta CODIGO que sai desenhado, que e a pergunta que importa
quando alguem escolhe uma peca na lista e espera ver o desenho.

Uso: python3 tools/conferir_cobertura.py
"""
import collections
import json
import re
import sys

sys.path.insert(0, ".")
from motor import simbolos as s  # noqa: E402
from motor.traducao import POLEGADA_MM  # noqa: E402

CATALOGO = "data/catalogo.json"
PEAD_DN = {v for v in POLEGADA_MM.values()}


# METB 150-125-200 -> o tamanho 125-200 do folheto, com succao de 150.
# O nome da lista tem tres grupos e o do catalogo dois: a succao fica implicita.
RX_METB = re.compile(r"(\d{2,3})-(\d{2,3})-(\d{2,4})")
RX_METB_CURTO = re.compile(r"(\d{2,3})-(\d{2,4})(?!\d)")


def tamanho_metb(descricao):
    m = RX_METB.search(descricao)
    if m:
        return f"{int(m.group(2))}-{int(m.group(3))}"
    m = RX_METB_CURTO.search(descricao)
    return f"{int(m.group(1))}-{int(m.group(2))}" if m else None


RX_CV = re.compile(r"(\d+(?:[,.]\d+)?)\s*CV")


def desenhar(item):
    familia = item["familia"]
    if familia == "BOMBA":
        linha = "METB" if re.search(r"\bMETB\b", item["descricao"]) else (
            "METN" if re.search(r"\bMETN\b", item["descricao"]) else None)
        if not linha:
            raise ValueError("bomba fora das linhas Mega")
        tamanho = tamanho_metb(item["descricao"])
        if not tamanho:
            raise ValueError("nome sem tamanho legivel")
        m = RX_CV.search(item["descricao"])
        cv = float(m.group(1).replace(",", ".")) if m else None
        if linha == "METB":
            return s.bomba_megabloc(tamanho, cv=cv)
        return s.bomba_meganorm(tamanho, cv=cv)
    bitolas = [d for d in (item["dn"] or []) if isinstance(d, (int, float))]
    if not bitolas:
        raise ValueError("sem DN na descricao")
    maior, menor = max(bitolas), (min(bitolas) if len(bitolas) > 1 else None)

    if item.get("unidade_dn") == "mm":
        # PEAD: o DN E o externo, entao ele mesmo e a bitola do desenho
        if item["material"] == "PEAD" or familia == "COLAR_PEAD":
            if familia == "COLAR_PEAD":
                return s.colar_pead(maior)
            if familia == "TUBO":
                return s.tubo_pead(maior, item.get("comprimento_mm") or 6000)
        raise ValueError(f"{familia} em mm sem simbolo")

    despacho = {
        "TUBO": lambda: s.tubo(maior, item.get("comprimento_mm") or 6000),
        "CURVA": lambda: s.curva(maior, angulo=int(item["angulo"] or 90)),
        "CURVA_SAIDA": lambda: s.curva_saida(maior, int(item["angulo"] or 90)),
        "REDUCAO_CONCENTRICA": lambda: s.reducao(maior, menor or maior / 2,
                                                 "CONCENTRICA"),
        "REDUCAO_EXCENTRICA": lambda: s.reducao(maior, menor or maior / 2,
                                                "EXCENTRICA"),
        "TE": lambda: s.te(maior, dn_derivacao=menor),
        "CRIVO": lambda: s.crivo(maior),
        "FLANGE_CEGA": lambda: s.flange_cega(maior, menor),
        "FLANGE": lambda: s.flange_avulsa(maior),
        "MANIFOLD": lambda: s.manifold(maior, menor),
        "ADAPTADOR": lambda: s.adaptador(maior),
        "VALVULA_BORBOLETA": lambda: s.valvula_borboleta(
            maior, item.get("acionamento") or "ALAVANCA"),
        "VALVULA_GAVETA": lambda: s.valvula_gaveta(maior),
        "VALVULA_HIDRAULICA": lambda: s.valvula_hidraulica(
            maior, item.get("serie") or "47"),
        "MEDIDOR": lambda: s.medidor(maior),
        "VALVULA_RETENCAO": lambda: s.valvula_retencao(maior),
        "VALVULA_PE": lambda: s.valvula_pe(maior),
    }
    if familia not in despacho:
        raise ValueError("familia sem simbolo")
    return despacho[familia]()


def main():
    itens = json.load(open(CATALOGO, encoding="utf-8"))
    ok, motivos = collections.Counter(), collections.Counter()
    for item in itens:
        try:
            desenhar(item)
            ok[item["familia"]] += 1
        except Exception as erro:
            motivos[f'{item["familia"]}: {erro}'] += 1

    total = sum(ok.values())
    print(f"{total} de {len(itens)} codigos do catalogo saem desenhados hoje\n")
    for familia, n in sorted(ok.items(), key=lambda kv: -kv[1]):
        print(f"{n:5d}  {familia}")
    print("\n-- o que ainda nao sai, por motivo --")
    for motivo, n in motivos.most_common(14):
        print(f"{n:5d}  {motivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
