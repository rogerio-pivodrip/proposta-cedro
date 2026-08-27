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


# Como a peca de milimetro se encaixa: bolsa, solda por encaixe, rosca ou
# luva de correr. O nome da lista diz, e a cota medida no DXF da casa esta
# guardada por junta - a curva de 90 de DN110 soldavel mede 203 e a de bolsa
# 186, entao errar a junta erra a cota.
RX_SOLDA = re.compile(r"SOLD|\bSOLDA\b", re.I)
RX_CORRER = re.compile(r"\bCORRER\b", re.I)
RX_ROSCA = re.compile(r"\bR(?:M|F)\b|ROSCA|\bBSP\b", re.I)
# a ponta da barra de PVC: PP e ponta e ponta (os dois lados lisos), JEI e
# junta elastica integrada e PB e ponta e bolsa - as duas com bolsa num lado
RX_PONTA_LISA = re.compile(r"\bPP\b|\bSOLD\w*\b|\bJS\b", re.I)


def junta_de(descricao):
    if RX_CORRER.search(descricao):
        return "CORRER"
    if RX_SOLDA.search(descricao):
        return "SOLDA"
    if RX_ROSCA.search(descricao):
        return "ROSCA"
    return "BOLSA"


def _pead(item, familia, maior):
    """As familias em milimetro: PVC, Plasson e PEAD.

    A cota dessas nao esta em folha de fabricante nenhuma - esta medida no DXF
    da casa, e entra por cotas.cota_da_casa. Ver docs/MOTOR.md 4.6.
    """
    descricao = item["descricao"]
    bitolas = sorted((d for d in (item["dn"] or [])
                      if isinstance(d, (int, float))), reverse=True)
    menor = bitolas[1] if len(bitolas) > 1 else None
    junta = junta_de(descricao)

    if familia == "COLAR_PEAD":
        return s.colar_pead(maior)
    if familia == "TUBO":
        if RX_ROLO.search(descricao):
            raise SemSimbolo("tubo de rolo - material por metro")
        if item["material"] == "PEAD":
            return s.tubo_pead(maior, min(item.get("comprimento_mm") or 6000,
                                          BARRA_MAXIMA_MM))
        ponta = "LISA" if RX_PONTA_LISA.search(descricao) else "BOLSA"
        return s.tubo_pvc(maior, min(item.get("comprimento_mm") or 6000,
                                     BARRA_MAXIMA_MM), ponta)
    if familia == "CURVA":
        angulo = int(item["angulo"] or 90)
        return s.curva_pvc(maior, angulo, junta)
    if familia in ("LUVA", "LUVA_CORRER"):
        if menor and menor != maior:
            return s.luva_reducao(maior, menor, junta)
        return s.luva_pvc(maior, "CORRER" if familia == "LUVA_CORRER" else junta)
    if familia in ("TE", "TE_REDUZIDO"):
        return s.te_pvc(maior, menor, junta)
    if familia == "BUCHA_REDUCAO":
        if not menor:
            raise SemSimbolo("bucha sem a bitola menor na descricao")
        return s.bucha_reducao(maior, menor)
    if familia == "CAP":
        return s.cap_pvc(maior, junta)
    if familia == "COLAR_TOMADA":
        return _colar_tomada(item, maior)
    if familia == "FLANGE":
        return _flange_em_mm(item, maior)
    if familia == "VALVULA_HIDRAULICA":
        # a Dorot de plastico e a mesma valvula da linha de aco em outra
        # carcaca: DN90 e a de 3". Sem equivalencia nao ha furacao, e sem
        # furacao a flange dela sairia inventada
        pol = s.PEAD_POL.get(maior)
        if not pol:
            raise SemSimbolo(f"DN{maior:g} sem equivalência de polegada")
        return s.valvula_hidraulica(pol, item.get("serie") or "47")
    if familia == "ADAPTADOR":
        if "FL" in descricao.upper() and "P/" in descricao.upper():
            return s.adaptador_flange(maior)
        if menor and menor != maior:
            return s.luva_reducao(maior, menor, junta)
        return s.luva_pvc(maior, junta)
    raise SemSimbolo(f"{familia} em mm sem simbolo")


def _colar_tomada(item, dn_mm):
    """O colar de tomada, que a lista descreve por inteiro.

    A descricao ja traz as tres coisas que a peca precisa: o diametro externo
    do tubo em milimetro, a bitola da saida em polegada, e o tipo da saida -
    flange com norma ou rosca femea. Nada aqui e chute.
    """
    saida = item.get("saida_pol")
    if not saida:
        raise SemSimbolo("colar sem a bitola da saída na descrição")
    flangeada = next((c for c in (item.get("conexoes") or [])
                      if c.get("tipo") == "FLANGE"), None)
    return s.colar_tomada(dn_mm, saida,
                          "FLANGE" if flangeada else "ROSCA",
                          (flangeada or {}).get("norma") or "NBR PN16")


def _flange_em_mm(item, dn_mm):
    """A flange que a lista cadastra em milimetro.

    Sao duas peças com o mesmo nome de familia. A de colar de PEAD e a mesma
    chapa de aco da linha, solta, furada na norma que a descricao diz - entao
    ela sai pela tabela de furacao, na bitola equivalente. A de PVC ISO 2536
    tem outra furacao, que nao esta em tabela nenhuma aqui, e essa nao sai.
    """
    if "2536" in item["descricao"]:
        raise SemSimbolo("flange de PVC ISO 2536 - furação fora de tabela")
    pol = s.PEAD_POL.get(dn_mm)
    if not pol:
        raise SemSimbolo(f"DN{dn_mm:g} sem equivalência de polegada")
    norma = next((c.get("norma") for c in (item.get("conexoes") or [])
                  if c.get("norma")), None)
    return s.flange_avulsa(pol, "SOLTA")


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
