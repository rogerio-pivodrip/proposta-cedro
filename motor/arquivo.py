"""A montagem salva em arquivo: o documento vira texto e volta a documento.

**O arquivo guarda a ESCOLHA, e nao o resultado.** O que se salva e o codigo
de cada peca, o que foi pedido a mao nela e como ela esta montada - nao a
cota desenhada, nao a ferragem, nao a lista de materiais. Tudo isso e
derivado, e derivado se recalcula ao abrir.

A consequencia e a que interessa a esta casa: **corrigir uma tabela de cotas
melhora os desenhos ja salvos**. Se o arquivo guardasse a geometria, cada
projeto antigo carregaria para sempre o erro que havia no dia em que foi
feito, e ninguem saberia quais reabrir. Guardando a escolha, o desenho de
ontem sai hoje com a folha de hoje - e o que mudou aparece por escrito, na
conferencia de baixo, em vez de mudar calado.

**Abrir passa pelos mesmos comandos que montar a mao** - `inserir` e
`acoplar`, nao um atalho que escreve em `pecas`. Um caminho de escrita
paralelo seria a segunda chance de o documento nascer num estado que os
comandos nunca produziriam. O que abrir faz de diferente e LIMPAR o historico
no fim: abrir nao e edicao, e desfazer logo depois de abrir nao pode comecar
a desmontar a linha peca por peca.
"""
import json

from .linha import Linha, Peca

FORMATO = "linha-pivodrip"
VERSAO = 2      # 1 guardava UMA montagem; 2 guarda o projeto inteiro

# o que a peca guarda de proprio. `comprimento_mm` NAO entra: o que entra e o
# que foi pedido a mao (`_comprimento_pedido`), porque so isso e escolha - o
# resto vem da tabela de cotas, e a tabela pode ter melhorado desde entao
DA_PECA = ("sentido", "pose", "fonte", "rotulo",
           "balao", "balao_angulo", "balao_distancia")


def _da_peca(peca):
    ficha = {"sap": peca.sap}
    ficha.update({campo: getattr(peca, campo) for campo in DA_PECA})
    if peca._comprimento_pedido is not None:
        # corte de campo: e decisao, e por isso e escolha e nao derivado
        ficha["cortado_mm"] = peca._comprimento_pedido
    # a cota que valia no dia em que se salvou. Nao manda em nada ao abrir -
    # serve para o programa dizer o que mudou desde entao
    ficha["medido_mm"] = round(peca.comprimento_mm or 0, 1)
    if peca.acessorios:
        ficha["acessorios"] = [_da_peca(a) for a in peca.acessorios]
    return ficha


def _da_montagem(linha):
    return {
        "id": linha.id, "nome": linha.nome,
        "tipo": linha.tipo, "area": linha.area,
        "giro": linha.giro, "espelho": linha.espelho,
        "ordem_baloes": list(linha.ordem_baloes),
        "pecas": [_da_peca(p) for p in linha.pecas],
    }


def guardar(projeto):
    """O projeto inteiro em JSON, pronto para gravar.

    Aceita tambem uma `Linha` solta - e o que a versao 1 gravava, e o que os
    testes de motor montam. Uma montagem sozinha vira um projeto de uma.
    """
    montagens = getattr(projeto, "montagens", None)
    if montagens is None:
        montagens, ativa = [projeto], projeto.id
        nome, area = projeto.nome, projeto.area
    else:
        ativa = projeto.ativa.id if montagens else None
        nome, area = projeto.nome, projeto.area
    return json.dumps({
        "formato": FORMATO, "versao": VERSAO,
        "nome": nome, "area": area, "ativa": ativa,
        "montagens": [_da_montagem(m) for m in montagens],
    }, ensure_ascii=False, indent=1)


class Recusado(Exception):
    """O arquivo nao e uma montagem desta casa, e o motivo e para ler."""


def _montar_peca(catalogo, ficha, avisos):
    sap = ficha.get("sap")
    item = catalogo.por_sap.get(sap)
    if item is None:
        # o codigo saiu da lista: o desenho perde a peca, e quem abre precisa
        # saber DISSO, e nao de um traceback nem de um buraco silencioso
        avisos.append(f"{sap}: o código não está mais na lista - a peça não "
                      f"entrou no desenho")
        return None
    peca = Peca(item, comprimento_mm=ficha.get("cortado_mm"),
                rotulo=ficha.get("rotulo"), fonte=ficha.get("fonte"),
                sentido=int(ficha.get("sentido") or 1),
                pose=ficha.get("pose"))
    for campo in ("balao", "balao_angulo", "balao_distancia"):
        if campo in ficha:
            setattr(peca, campo, ficha[campo])
    medido = ficha.get("medido_mm")
    atual = round(peca.comprimento_mm or 0, 1)
    if medido is not None and abs(medido - atual) > 1:
        avisos.append(
            f"{peca.descricao}: salva com {medido:.0f} mm, e a folha de hoje "
            f"dá {atual:.0f} mm - o desenho seguiu a folha ({peca.fonte})")
    return peca


def _montar_linha(catalogo, dados, avisos):
    linha = Linha(catalogo, tipo=dados.get("tipo") or "RECALQUE",
                  area=dados.get("area") or "P01",
                  nome=dados.get("nome"))
    for ficha in dados.get("pecas") or []:
        peca = _montar_peca(catalogo, ficha, avisos)
        if peca is None:
            continue
        linha.inserir(peca)
        for outra in ficha.get("acessorios") or []:
            acessorio = _montar_peca(catalogo, outra, avisos)
            if acessorio is not None:
                linha.acoplar(peca.id, acessorio)
    linha.pose(giro=dados.get("giro") or 0.0,
               espelho=dados.get("espelho") or 1)
    linha.ordem_baloes = [s for s in (dados.get("ordem_baloes") or [])
                          if isinstance(s, str)]
    # abrir nao e edicao: o desfazer comeca vazio, e nao desmontando a linha
    linha.feitos.clear()
    linha.desfeitos.clear()
    return linha


def abrir(catalogo, texto):
    """O texto de volta a documento. (projeto, avisos)

    Le tanto o formato do projeto (versao 2) quanto o da montagem sozinha
    (versao 1), que virou um projeto de uma montagem. Arquivo salvo ontem tem
    de abrir hoje: a versao existe para isso, e nao para dar erro.
    """
    from .projeto import Projeto

    try:
        dados = json.loads(texto)
    except (ValueError, TypeError) as erro:
        raise Recusado(f"não consegui ler o arquivo: {erro}") from erro
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO:
        raise Recusado("este arquivo não é uma montagem deste programa")
    if int(dados.get("versao") or 0) > VERSAO:
        raise Recusado(
            f'a montagem foi salva na versão {dados["versao"]} e este '
            f"programa lê até a {VERSAO} - atualize o programa")
    avisos = []
    projeto = Projeto(catalogo, nome=dados.get("nome") or "Casa de bomba",
                      area=dados.get("area") or "P01")
    # versao 1: o arquivo E uma montagem, sem tira de montagens em volta
    fichas = dados.get("montagens") or [dados]
    for ficha in fichas:
        projeto.criar(_montar_linha(catalogo, ficha, avisos), escolher=False)
    guardado = dados.get("ativa")
    for montagem, ficha in zip(projeto.montagens, fichas):
        if ficha.get("id") and ficha["id"] == guardado:
            projeto.escolher(montagem)
    if not projeto._ativa and projeto.montagens:
        projeto.escolher(projeto.montagens[0])
    projeto.feitos.clear()
    projeto.desfeitos.clear()
    return projeto, avisos
