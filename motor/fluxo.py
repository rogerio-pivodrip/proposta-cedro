"""O sentido do fluxo: que peca so serve de um lado, e de que lado ela esta.

A analise de furacao pergunta se duas faces PARAFUSAM. A de classe pergunta se
o que sai dali AGUENTA. Falta a terceira, que e a que mais aparece na obra:
**a peca esta no lado certo da bomba?**

Nenhum destes erros da erro. O desenho fecha, a lista fecha, a furacao casa, e
a linha e montada. O crivo depois da bomba deixa passar tudo o que ele deveria
ter segurado - e o que ele deveria ter segurado ja passou pelo rotor. A
excentrica no recalque poe uma bolsa de ar onde ninguem procura. A ventosa
enfiada na corrente vira peca de passagem, e o ponto alto continua com ar
preso.

**A ordem da arvore E a ordem do fluxo.** O ramo nasce na boca de quem vem
antes dele, entao ler a arvore de fio a pavio e descer a linha com a agua. E o
mesmo caminho que `hidraulica.conferir_sequencia` usa, e por isso as duas
conferencias sao chamadas do mesmo lugar.

O que este modulo NAO faz e adivinhar a orientacao da bomba. Ela nao esta no
modelo - `bomba.orientacao_pelo_desenho` deduz a orientacao a partir da
reducao, que e o unico lugar onde ela ficou registrada. Conferir a reducao
contra uma orientacao lida da propria reducao seria conferir uma coisa contra
ela mesma.
"""

# A boca que fica na agua. O crivo e a valvula de pe sao o COMECO da succao:
# antes deles nao ha linha, ha poco
NA_AGUA = ("CRIVO", "VALVULA_PE")


def conferir(pecas, acessorios=()):
    """Os conflitos de sentido desta corrente. (lista de frases)

    `pecas` e a corrente na ordem do fluxo - so as pecas de passagem, sem os
    acessorios, porque a posicao do acessorio e a da peca que o carrega.
    `acessorios` sao as pecas que fecham boca, e entram so para a ventosa: ela
    pertence a esse grupo, e estar fora dele ja e o problema.
    """
    familias = [p.familia for p in pecas]
    problemas = []
    bomba = familias.index("BOMBA") if "BOMBA" in familias else None

    for i, peca in enumerate(pecas):
        if peca.familia in NA_AGUA:
            if i != 0:
                problemas.append(
                    f"{_nome(peca)} na posição {i + 1} - a boca que fica na "
                    f"água é o começo da linha, não um meio de caminho")
            if bomba is not None and i > bomba:
                problemas.append(
                    f"{_nome(peca)} depois da bomba - o crivo protege o "
                    f"rotor, e depois dele não há o que proteger")
        elif peca.familia == "REDUCAO_EXCENTRICA" and bomba is not None \
                and i > bomba:
            problemas.append(
                f"{_nome(peca)} depois da bomba - a excêntrica é peça de "
                f"sucção (o lado plano em cima evita bolsa de ar antes do "
                f"rotor); no recalque a casa usa concêntrica")
        elif peca.familia == "VALVULA_RETENCAO" and bomba is not None \
                and i < bomba and not _no_pe(familias, i):
            problemas.append(
                f"{_nome(peca)} na sucção, longe do pé - a retenção da casa "
                f"é a do pé (junto ao crivo) ou a do recalque (depois da "
                f"bomba); no meio da sucção ela segura a coluna onde a "
                f"escorva precisa dela solta")
        elif peca.familia == "VENTOSA":
            problemas.append(
                f"{_nome(peca)} na corrente - a ventosa sobe de uma "
                f"derivação no ponto alto, e não passa a linha por dentro "
                f"dela")

    for peca in acessorios:
        if peca.familia in NA_AGUA:
            problemas.append(
                f"{_nome(peca)} pendurada numa boca - o crivo é a entrada da "
                f"linha, e não o que fecha uma sobra")
    return problemas


def _no_pe(familias, i):
    """Se a retencao nesta posicao e a valvula de pe: colada no crivo."""
    vizinhas = familias[max(0, i - 1):i] + familias[i + 1:i + 2]
    return any(f in NA_AGUA for f in vizinhas)


def _nome(peca):
    return peca.familia.replace("_", " ").lower()
