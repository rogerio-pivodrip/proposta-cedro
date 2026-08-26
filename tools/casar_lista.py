#!/usr/bin/env python3
"""Casa uma lista de pecas de desenho (nomes livres do CAD) com a base SAP.

O CAD gera "Red Exc AZ 4\"x 2\"". A proposta precisa de "01523-281940". Este
modulo faz a ponte: interpreta o nome do desenho com o mesmo interpretador do
catalogo e procura o item da lista Netafim que tem os mesmos parametros.

Uso: python3 tools/casar_lista.py [lista.csv]
"""
import csv
import re
import sys

sys.path.insert(0, ".")
from motor.catalogo import Catalogo
from motor.traducao import polegada_para_mm, sem_acento, traduzir
from tools.normalizar import normalizar_item

PADRAO_LISTA = "data/exemplo_casa_maquinas.csv"

# Material do desenho -> materiais aceitos no catalogo. None = qualquer um.
EQUIVALENTES = {
    "PVC_PLASSON": ("PVC_PLASSON", "PVC"),
    "PVC": ("PVC", "PVC_PLASSON"),
    "ACO_ZINCADO": ("ACO_ZINCADO",),
    "FOFO": ("FOFO", "FERRO_GALV"),
    "PEAD": ("PEAD",),
}


# palavras que nao distinguem uma peca de outra
VAZIAS = {"DE", "DA", "DO", "P/", "C/", "X", "E", "PARA", "COM", "MM", "UN", "-"}


def palavras(texto):
    return {t for t in re.split(r"[^A-Z0-9/º\".,]+", sem_acento(texto).upper())
            if len(t) > 1 and t not in VAZIAS}


def pontuar(alvo, cand, chaves=frozenset()):
    """Quanto o item do catalogo responde ao que o desenho pediu. Maior e melhor."""
    if cand["familia"] != alvo["familia"]:
        return -1
    if alvo["unidade_dn"] and cand["unidade_dn"] and \
            alvo["unidade_dn"] != cand["unidade_dn"]:
        return -1                        # 90 mm nao e 90 polegadas
    dn_alvo, dn_cand = set(alvo["dn"]), set(cand["dn"])
    if dn_alvo and not dn_alvo <= dn_cand:
        return -1
    if alvo["angulo"] is not None and cand["angulo"] != alvo["angulo"]:
        return -1
    if alvo["material"]:
        aceitos = EQUIVALENTES.get(alvo["material"], (alvo["material"],))
        if cand["material"] not in aceitos:
            return -1

    pontos = 10
    if dn_alvo and dn_alvo == dn_cand:
        pontos += 6                      # mesmos diametros, sem sobra
    if alvo["material"] and cand["material"] == alvo["material"]:
        pontos += 3
    if alvo["comprimento_mm"]:
        if cand["comprimento_mm"] == alvo["comprimento_mm"]:
            pontos += 6
        elif cand["comprimento_mm"]:
            pontos -= 4                  # comprimento existe e e outro
    if alvo["angulo"] is not None and cand["angulo"] == alvo["angulo"]:
        pontos += 2
    # desempate por vocabulario: marca e linha do produto (UNIFLAP, PLASSON,
    # ARAD, DOROT) aparecem no nome do desenho e na descricao do catalogo
    if chaves:
        pontos += 2 * len(chaves & palavras(cand["descricao"]))
    # na duvida a linha e flangeada NBR PN16, que e o padrao da casa
    if any(c["norma"] == "NBR PN16" for c in cand["conexoes"]):
        pontos += 2
    pontos -= len(cand["derivacoes"])    # peca com escape/luva extra e mais especifica
    return pontos


def casar(catalogo, nome):
    traduzido = traduzir(nome)
    alvo = normalizar_item(traduzido)
    if not alvo["familia"]:
        return alvo, []
    # PVC e PEAD sao catalogados em milimetro, mas o desenho chama de 6"
    if alvo["unidade_dn"] == "in" and alvo["material"] in ("PEAD", "PVC",
                                                           "PVC_PLASSON"):
        mm = [polegada_para_mm(d) for d in alvo["dn"]]
        if all(mm):
            alvo["dn"], alvo["unidade_dn"] = mm, "mm"
    chaves = palavras(traduzido)
    marcados = []
    for cand in catalogo.itens:
        p = pontuar(alvo, cand, chaves)
        if p >= 0:
            marcados.append((p, cand))
    marcados.sort(key=lambda t: (-t[0], len(t[1]["descricao"])))
    return alvo, marcados


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else PADRAO_LISTA
    cat = Catalogo()
    with open(caminho, encoding="utf-8") as fh:
        linhas = [ln for ln in fh if not ln.startswith("#")]

    achou = duvida = perdeu = 0
    print(f"{'#':>3}  {'nome no desenho':44s} {'SAP':14s} descricao no catalogo")
    print("-" * 118)
    for reg in csv.DictReader(linhas):
        nome = reg["nome_peca"]
        alvo, marcados = casar(cat, nome)
        if not marcados:
            perdeu += 1
            motivo = "familia nao reconhecida" if not alvo["familia"] else \
                     f"sem item {alvo['familia']} DN {alvo['dn']}"
            print(f"{reg['item']:>3}  {nome[:44]:44s} {'--':14s} ! {motivo}")
            continue
        melhor = marcados[0][1]
        empate = sum(1 for p, _ in marcados if p == marcados[0][0])
        marca = " " if empate == 1 else "?"
        if empate == 1:
            achou += 1
        else:
            duvida += 1
        print(f"{reg['item']:>3}  {nome[:44]:44s} {melhor['sap']:14s} {marca}"
              f"{melhor['descricao'][:52]}"
              + (f"  (+{empate - 1} iguais)" if empate > 1 else ""))

    total = achou + duvida + perdeu
    print("-" * 118)
    print(f"{total} itens: {achou} resolvidos direto, {duvida} com empate a decidir, "
          f"{perdeu} sem correspondencia")


if __name__ == "__main__":
    main()
