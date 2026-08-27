"""De um item do catalogo para o simbolo dele.

E a ponte entre as duas metades do motor: o catalogo sabe o codigo SAP e a
descricao, os simbolos sabem desenhar. Aqui os dois se encontram, e e por
isso que o bloco exportado sai com o codigo no nome e a descricao no campo
Description - do jeito que a lista da Netafim nomeia.

    from motor import catalogo, desenho
    simbolo = desenho.de_item(item)
    simbolo.params["sap"]        -> '01523-051000'
    simbolo.params["descricao"]  -> 'CRIVO AZ 8" NBR PN16'
"""
import re

from . import simbolos as s
from .bomba import MM_PARA_POLEGADA

# METB 150-125-200 -> o tamanho 125-200 do folheto, com succao de 150.
# O nome da lista tem tres grupos e o do folheto dois: a succao fica implicita.
RX_TRES = re.compile(r"(\d{2,3})-(\d{2,3})-(\d{2,4})")
RX_DOIS = re.compile(r"(\d{2,3})-(\d{2,4})(?!\d)")
RX_CV = re.compile(r"(\d+(?:[,.]\d+)?)\s*CV")
RX_MEGABLOC = re.compile(r"\bMETB\b")
RX_MEGANORM = re.compile(r"\bMETN\b")

# Tubo que vem em rolo nao e peca de linha - e material por metro. O FXN e
# layflat: enrola, nao tem forma propria e nao entra em vista lateral.
RX_ROLO = re.compile(r"\bFXN\b|LAYFLAT|\bCEGO\s+\d+\s*M\b", re.I)
# A barra mais longa que a casa compra. Acima disso o cadastro esta errado:
# 01503-000008 diz "TUBO AZ 20\"X4,75MMX2000M", que sao 2 metros e nao 2 km.
BARRA_MAXIMA_MM = 12000


class SemSimbolo(Exception):
    """A peca nao tem simbolo, e o motivo esta na mensagem."""


def tamanho_de_bomba(descricao):
    m = RX_TRES.search(descricao)
    if m:
        return f"{int(m.group(2))}-{int(m.group(3))}"
    m = RX_DOIS.search(descricao)
    return f"{int(m.group(1))}-{int(m.group(2))}" if m else None


def _bomba(item):
    descricao = item["descricao"]
    megabloc = bool(RX_MEGABLOC.search(descricao))
    if not megabloc and not RX_MEGANORM.search(descricao):
        raise SemSimbolo("bomba fora das linhas Mega")
    tamanho = tamanho_de_bomba(descricao)
    if not tamanho:
        raise SemSimbolo("nome sem tamanho legivel")
    m = RX_CV.search(descricao)
    cv = float(m.group(1).replace(",", ".")) if m else None
    return (s.bomba_megabloc(tamanho, cv=cv) if megabloc
            else s.bomba_meganorm(tamanho, cv=cv))


def _tubo(item, dn_pol):
    """O tubo, se for barra. Rolo e cadastro fora de faixa nao desenham.

    Rolo nao e peca: entra na lista por metro e no desenho por trecho, nao por
    bloco. E comprimento acima da barra maxima quase sempre e virgula errada
    no cadastro, nao um tubo de dois quilometros.
    """
    if RX_ROLO.search(item["descricao"]):
        raise SemSimbolo("tubo de rolo - material por metro")
    comprimento = item.get("comprimento_mm") or 6000
    if comprimento > BARRA_MAXIMA_MM:
        raise SemSimbolo(f"comprimento de {comprimento/1000:.0f} m fora de "
                         f"barra - conferir cadastro")
    return s.tubo(dn_pol, comprimento)


def _pead(item, familia, maior):
    if item["material"] == "PEAD" or familia == "COLAR_PEAD":
        if familia == "COLAR_PEAD":
            return s.colar_pead(maior)
        if familia == "TUBO":
            if RX_ROLO.search(item["descricao"]):
                raise SemSimbolo("tubo de rolo - material por metro")
            return s.tubo_pead(maior, min(item.get("comprimento_mm") or 6000,
                                          BARRA_MAXIMA_MM))
    raise SemSimbolo(f"{familia} em mm sem simbolo")


def de_item(item):
    """O simbolo do item, ja com o codigo e a descricao nos params."""
    simbolo = _desenhar(item)
    return simbolo._replace(params={**simbolo.params,
                                    "sap": item["sap"],
                                    "descricao": item["descricao"]})


def _desenhar(item):
    familia = item["familia"]
    if familia == "BOMBA":
        return _bomba(item)

    bitolas = [d for d in (item["dn"] or []) if isinstance(d, (int, float))]
    if not bitolas:
        raise SemSimbolo("sem DN na descricao")
    maior = max(bitolas)
    menor = min(bitolas) if len(bitolas) > 1 else None
    if item.get("unidade_dn") == "mm":
        return _pead(item, familia, maior)

    if familia == "TUBO":
        return _tubo(item, maior)

    despacho = {
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
        raise SemSimbolo("familia sem simbolo")
    return despacho[familia]()
