"""Documento unico: a linha. Desenho e lista sao duas projecoes dela.

Nenhuma sincronizacao entre desenho e planilha - as duas views leem o mesmo
objeto Linha e escrevem nele pelos mesmos comandos (inserir / remover /
substituir / alterar / mover). Toda edicao dispara recalculo das juncoes e da
ferragem derivada.

Os cinco comandos sao a UNICA porta de escrita, e cada um sabe se desfazer.
Isso nao e conforto de interface: e o que garante que desenho e lista nunca
divirjam. Quem edita nao mexe em `pecas` - mexer ali contorna o historico e
deixa o documento num estado que nao da para reverter.

**A peca e enderecada por id, nao por posicao.** Indice muda quando alguem
insere, remove ou move, e a tela que segurou um indice passa a apontar para
outra peca. O id nasce com a peca e morre com ela, e e o mesmo no balao do
desenho e na linha da tabela.
"""
import contextlib
import itertools
from collections import OrderedDict

from . import corte, cotas, ferragem, fluxo, hidraulica, pressao, regras

_contador = itertools.count(1)
_montagens = itertools.count(1)
_ordem = itertools.count(1)      # a ORDEM em que os comandos aconteceram

# O BALAO E DO DESENHO, O NUMERO E DA LISTA - e e o mesmo numero. Numa vista
# explodida o balao nao conta pecas, ele aponta para a LINHA da lista: duas
# curvas do mesmo codigo levam o mesmo numero, e quem quer saber quantas sao
# le a quantidade na lista, que e onde ela mora.
BALAO_ANGULO = 45.0     # graus, anti-horario, 0 para a direita - o do croqui


class Peca:
    """Uma peca instanciada na linha, com suas portas."""

    def __init__(self, item, comprimento_mm=None, rotulo=None, fonte=None,
                 sentido=1, pose=None):
        self.id = f"p{next(_contador)}"       # estavel: sobrevive a mover
        self.item = item                      # registro do catalogo
        self.sap = item["sap"]
        self.descricao = item["descricao"]
        self.familia = item["familia"]
        self.material = item["material"]
        self.unidade_dn = item["unidade_dn"] or "in"
        self.angulo = item["angulo"]
        self.fonte = fonte or cotas.PADRAO   # fabricante da peca comprada
        self.sentido = sentido               # +1 sobe, -1 desce: espelha a curva
        # como a peca esta MONTADA, quando ela tem mais de um jeito. O te em
        # linha e o te de pe sobre a derivacao sao o mesmo codigo SAP - a pose
        # e da instancia, como o sentido da curva
        self.pose = pose
        self.fonte_cota = None               # de quem veio a cota que entrou
        # o espelho da LINHA entra no giro desta peca: `Linha` o poe aqui ao
        # montar a geometria. Nasce em 1 para a peca solta continuar sabendo
        # se virar sozinha, que e o que os testes de simbolo pedem
        self._espelho_da_linha = 1
        self._comprimento_pedido = comprimento_mm
        self.comprimento_mm = (comprimento_mm or item.get("comprimento_mm")
                               or self._da_tabela() or self._face_a_face() or 0)
        self.rotulo = rotulo
        # o que fecha a boca que sobra desta peca. O te tem tres bocas e a
        # corrente usa duas; a terceira nao e um ramo novo - e uma ponta, e o
        # que entra nela e uma peca terminal: flange cega, ventosa, dreno.
        # Guardar aqui, e nao numa lista paralela, e o que faz o acessorio
        # sair junto quando a peca sai
        self.acessorios = []
        # o balao desta peca: o pontinho, o traco e o numero. `balao` diz se
        # ESTA peca mostra o dela - o numero continua na lista de qualquer
        # jeito, e e isso que permite listar o acessorio sem balao nenhum.
        # Angulo e distancia sao a POSE do balao, como `pose` e a da peca: 45
        # graus e a convencao do croqui, e distancia None deixa o desenho
        # achar a dele - que muda quando a peca muda de tamanho
        self.balao = True
        self.balao_angulo = BALAO_ANGULO
        self.balao_distancia = None
        # COM QUE FURACAO A BOMBA VEIO. A mesma maquina sai furada em ASME
        # B16.1 Classe 125, Classe 250 ou EN 1092-2 PN16 conforme o pedido -
        # ver regras.FURACOES_DE_BOMBA - e so quem tem a folha da maquina em
        # maos sabe qual. None deixa valer a folha, quando ha, e a Classe 125
        # quando nao ha
        self.flange_bomba = None
        self.portas = self._portas()

    def classe_pressao(self):
        """Quanto esta peca aguenta - ou None quando a lista nao diz.

        Vem do cadastro (`tools/normalizar.py` le a descricao pelo
        `motor/pressao.py`), com uma excecao: na BOMBA quem manda na junta e a
        furacao com que a maquina foi pedida, e nao o corpo dela. Ver
        `regras.FURACOES_DE_BOMBA` - a mesma bomba sai em Classe 125, 250 ou
        EN PN 16 conforme o pedido, e e essa flange que encosta na linha.
        """
        if self.familia == "BOMBA" and self.flange_bomba:
            da_flange = pressao.da_norma(self.flange_bomba)
            if da_flange:
                return da_flange
        return self.item.get("classe_pressao")

    def recalcular(self):
        """Refaz o que depende da fonte e da cota, sem trocar a peca.

        Existe por causa do comando `alterar`: trocar o fabricante nao troca a
        peca, troca a TABELA de onde a cota dela sai - e a cota tem de vir
        junto. Ver docs/MOTOR.md 4: a mesma peca mede diferente em cada folha.
        """
        self.comprimento_mm = (self._comprimento_pedido
                               or self.item.get("comprimento_mm")
                               or self._da_tabela() or self._face_a_face() or 0)
        self.portas = self._portas()
        return self

    def _chave_de_cota(self):
        """(familia, variante, significado) para procurar na tabela de cotas."""
        if self.familia == "CURVA" and self.angulo:
            return "CURVA", str(self.angulo), "perna_mm"
        if self.familia == "CRIVO":
            return "CRIVO", "", "comprimento_mm"
        if self.familia in ("MANIFOLD", "ARTICULADOR"):
            return self.familia, "", "comprimento_mm"
        if self.familia == "VALVULA_HIDRAULICA":
            # A COTA DO CORPO SAI DA SERIE, e nao do codigo - e quando o
            # codigo nao declara serie ela vem emprestada da Dorot basica, que
            # e a unica folha que a casa tem. Esta linha era
            # `item.get("serie") or ""`, e o "" nao acha linha nenhuma: toda
            # Bermad media ZERO no documento enquanto o desenho a mostrava com
            # 390 mm. Ver cotas.serie_da_valvula, que os dois lados chamam
            bitolas = [d for d in (self.item["dn"] or [])
                       if isinstance(d, (int, float))]
            serie, _emprestada = cotas.serie_da_valvula(
                self.item, max(bitolas) if bitolas else None)
            return self.familia, serie, "face_a_face_mm"
        if self.familia == "VALVULA_BORBOLETA":
            # a ficha separa alavanca de caixa redutora: o corpo tambem muda
            return self.familia, self.item.get("acionamento") or "", "face_a_face_mm"
        return self.familia, "", "face_a_face_mm"

    def _da_tabela(self):
        """A cota do fabricante. E aqui que o padrao da casa entra no desenho.

        **Milimetro tem cota tambem.** Esta funcao devolvia None para toda
        peca cadastrada em mm - PVC, CPVC, Plasson, PEAD - e elas acabavam
        medindo ZERO no documento enquanto o desenho as desenhava com a cota
        do DXF da casa. Meia linha de Plasson nao ocupava espaco nenhum no
        esquema. A tabela e a mesma que o simbolo le (cotas.cota_da_casa); o
        que este lado nao sabe e a decisao de junta que o desenho faz - bolsa
        contra soldavel - e onde as duas caem em linhas diferentes, quem
        acusa e tools/conferir_cota.py.
        """
        if self.unidade_dn != "in":
            bitolas = [d for d in (self.item["dn"] or [])
                       if isinstance(d, (int, float))]
            if not bitolas:
                return None
            familia, variante, significado = self._chave_de_cota()
            menor = min(bitolas) if len(bitolas) > 1 else None
            valor = cotas.cota_da_casa(familia, max(bitolas), variante,
                                       significado, menor)
            if valor is None and significado == "face_a_face_mm":
                # em milimetro a casa mediu "comprimento", e nao face a face:
                # o DXF nao separa os dois em peca de bolsa
                valor = cotas.cota_da_casa(familia, max(bitolas), variante,
                                           "comprimento_mm", menor)
            self.fonte_cota = "CASA" if valor is not None else None
            return valor
        # FOLHA DE FABRICANTE VEM ANTES DA TABELA, sempre - e no crivo as duas
        # discordam: a folha Netafim cota 250 mm em 8", e a tabela traz 300
        # para toda bitola, que e numero chapado e nao medida. O desenho ja
        # lia a folha; o documento nao lia, e os dois mediam o mesmo cesto
        # diferente
        if self.familia == "CRIVO" and self.item["dn"]:
            ficha = cotas.ficha_crivo(self.item["dn"][0])
            if ficha and ficha.get("comprimento_mm"):
                self.fonte_cota = "NETAFIM"
                return float(ficha["comprimento_mm"])
        bitolas = [d for d in (self.item["dn"] or []) if isinstance(d, (int, float))]
        if not bitolas:
            return None
        familia, variante, significado = self._chave_de_cota()
        menor = min(bitolas) if len(bitolas) > 1 else None
        valor, fonte = cotas.cota_com_fonte(familia, max(bitolas), variante,
                                            significado, self.fonte, menor)
        self.fonte_cota = fonte
        return valor

    def de_pe(self):
        """O te montado sobre a derivacao: a linha entra pela boca do meio.

        E uma POSE, nao outra peca - o mesmo codigo SAP - e e assim que ele
        sobe no pe do recalque: a ponta de cima recebe a flange cega com a
        luva da ventosa, a de baixo desce para a curva.
        """
        return self.familia in ("TE", "TE_REDUZIDO") and self.pose == "derivacao"

    # As familias cuja geometria SO existe na folha do fabricante, lida pelo
    # simbolo. Nao ha segunda fonte para conferir com a primeira - e inventar
    # uma seria pior que nao ter: a bomba entra pela sucção na horizontal e
    # sai pelo recalque para cima, e enquanto isso nao estava escrito aqui o
    # esquema seguia reto por dentro dela, com comprimento zero.
    PELO_SIMBOLO = ("BOMBA",)

    def _pernas_do_simbolo(self):
        """(antes, depois, giro) medidos nas portas do proprio simbolo.

        A peca entra olhando para +x e sai onde a porta de saida disser. Se
        ela vira, o caminho e o mesmo da curva: uma perna, o giro, outra perna
        - e as duas se acham resolvendo o deslocamento da entrada ate a saida.
        """
        import math

        from . import desenho

        try:
            simbolo = desenho.de_item(self.item, self.pose,
                                      self._comprimento_pedido)
        except Exception:                                   # noqa: BLE001
            return None
        portas = simbolo.portas
        entrada = next((p for p in portas if p.papel in ("entrada", "maior")),
                       None)
        saida = next((p for p in portas if p.papel in ("saida", "menor")), None)
        if saida is None:
            return None
        ex, ey = (entrada.x, entrada.y) if entrada else (0.0, 0.0)
        dx, dy = saida.x - ex, saida.y - ey
        gira = float(saida.direcao or 0.0)
        seno = math.sin(math.radians(gira))
        if abs(seno) < 1e-6:
            return (dx, 0.0, 0.0)
        depois = dy / seno
        return (dx - depois * math.cos(math.radians(gira)), depois, gira)

    def _bocas_do_simbolo(self):
        """As bocas da bomba, da folha do fabricante, na norma da casa."""
        from . import desenho

        try:
            simbolo = desenho.de_item(self.item, self.pose)
        except Exception:                                   # noqa: BLE001
            return []
        ficha = regras.flange_da_bomba(self.descricao)
        furacao = self.flange_bomba or ficha["furacao"]
        saida = []
        for porta in simbolo.portas:
            if porta.dn_pol is None:
                continue
            saida.append({"dn": porta.dn_pol, "tipo": "FLANGE",
                          "norma": furacao})
        return saida

    def giro_interno(self):
        """De quanto ESTA peca vira a direcao da linha, em graus de folha.

        **O sinal e o do desenho.** `sentido` +1 SOBE, e subir no papel e y
        negativo - entao a curva vira para -90, e nao para +90. Enquanto esta
        conta estava escrita direto em `geometria()`, com o sinal trocado, o
        esquema saia ESPELHADO do desenho em toda linha com curva, e nada
        comparava os dois. Ver tools/conferir_cota.py.

        O te de pe vira para o outro lado, e nao e engano: ele e o simbolo
        girado -90, e a boca por onde a linha sai e a de BAIXO. Por isso o
        giro e da peca e nao uma formula so - cada uma sabe do seu.
        """
        mao = self.sentido * (self._espelho_da_linha or 1)
        if self.familia == "CURVA" and self.angulo:
            return -self.angulo * mao
        if self.de_pe():
            return 90.0 * mao
        if self.familia in self.PELO_SIMBOLO:
            pernas = self._pernas_do_simbolo()
            return (pernas[2] if pernas else 0.0) * mao
        return 0.0

    def avancos(self):
        """Quanto a peca avanca antes e depois de girar a direcao.

        A curva tem duas pernas - entra por uma e sai pela outra, e o giro
        acontece no meio. **O te de pe tambem**: a linha chega pela derivacao,
        anda ate o eixo do corpo, vira 90 e desce meio corpo ate a ponta de
        baixo. Ele nao e curva, mas anda como uma, e enquanto isso nao estava
        escrito aqui o esquema seguia RETO por dentro dele - 1000 mm de tubo
        que o desenho nao tinha.

        O resto avanca tudo antes e nao gira nada.
        """
        comp = self.comprimento_mm or 0
        if self.familia in self.PELO_SIMBOLO:
            pernas = self._pernas_do_simbolo()
            if pernas:
                return pernas[0], pernas[1]
        if self.familia == "CURVA" and self.angulo:
            return comp, comp
        if self.de_pe():
            # a perna da derivacao vem da mesma folha que o simbolo le - a
            # cota `derivacao_mm` do te - e o corpo se parte no meio
            alt, _fonte = cotas.cota_com_fonte(
                "TE", max(self.item["dn"] or [0]), "", "derivacao_mm",
                self.fonte)
            return (alt or comp / 5), comp / 2
        return comp, 0.0

    def _face_a_face(self):
        """Valvula wafer tem espessura de corpo tabelada na ficha do fabricante -
        e ela que entra na geometria da vista lateral."""
        if not self.item["dn"] or self.item["familia"] not in \
                regras.BARRAS_ROSCADAS_POR_PECA:
            return None
        ficha = regras.ficha_wafer(self.item["dn"][0])
        if not ficha:
            return None
        # a ficha da MP e folha de fabricante como qualquer outra: sem dizer
        # de onde veio, o carimbo contava esta cota como estimativa
        self.fonte_cota = "MP"
        return ficha["esp_corpo_mm"]

    def _portas(self):
        # A BOMBA NAO TEM CONEXAO NO CADASTRO - ela entra na lista sem bitola
        # nenhuma - e por isso ela ficava SEM PORTA no documento. Sem porta
        # nao ha juncao, e `juncoes()` pulava a bomba inteira: a ligacao mais
        # critica da casa, a que sempre pede reducao especifica, era a unica
        # que o programa nao conferia. As bocas dela vem da folha dimensional,
        # que quem le e o simbolo, e a norma vem da regra da casa
        if self.familia in self.PELO_SIMBOLO:
            do_simbolo = self._bocas_do_simbolo()
            if do_simbolo:
                return do_simbolo
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


class Comando:
    """Uma edicao e o bastante para desfaze-la e para refaze-la.

    Guardar o comando em vez do estado inteiro e o que torna desfazer barato
    numa linha de sessenta pecas: o que se guarda e a diferenca, nao a copia.
    """

    def __init__(self, nome, fazer, desfazer, alvo=None):
        self.nome = nome
        self.fazer = fazer
        self.desfazer = desfazer
        self.alvo = alvo          # id da peca que o comando atingiu
        # QUANDO ele aconteceu, na conta do programa inteiro. Sem isto o
        # desfazer de um projeto com varias montagens teria de escolher em
        # qual pilha mexer, e escolheria errado: quem aperta ctrl+Z quer
        # desfazer O QUE ACABOU DE FAZER, e nao o ultimo comando da aba em
        # que o olho esta
        self.ordem = next(_ordem)

    def __repr__(self):
        return f"<{self.nome} {self.alvo or ''}>".replace(" >", ">")


def _explicar(catalogo, junc):
    """O que falta nesta juncao, em palavras de obra.

    Duas coisas entram aqui que a mensagem antiga calava:

    **A norma, quando ela muda junto com a bitola.** Na boca da bomba as duas
    mudam ao mesmo tempo - o fabricante entrega a flange em EN ou ANSI e a
    linha corre em NBR - e "precisa de reducao" nao diz qual: a reducao comum
    tem as DUAS faces em NBR e nao serve.

    **A furacao, em numeros.** O nome da norma nao decide se duas faces
    parafusam; a furacao decide. NBR PN16 e EN PN16 tem a mesma ate 8" e
    divergem de 10" para cima; ANSI nunca casa com NBR. Dizer "8 furos contra
    12" e uma frase que se confere com o paquimetro.
    """
    dados = junc["dados"]
    acao = junc["acao"]
    if acao == "adaptador":
        return _duas_faces(catalogo, dados)
    if acao != "reducao":
        return f"precisa de {acao} {dados}"
    de, para = dados["de"], dados["para"]
    frase = f'reducao de {de:g}" para {para:g}"'
    if not dados.get("normas_diferentes"):
        return frase
    a, b = dados["norma_de"], dados["norma_para"]
    furos = []
    for norma, dn in ((a, de), (b, para)):
        ficha = regras.furacao(norma, dn)
        furos.append(f'{norma} {dn:g}" '
                     + (f"({ficha[0]} furos ⌀{ficha[1]:g} em ⌀{ficha[2]:g})"
                        if ficha else "(sem furação tabelada)"))
    frase += f" E de norma: {furos[0]} contra {furos[1]}"
    pontes = catalogo.ponte(de, a, para, b) if catalogo else []
    if pontes:
        frase += (" - a lista tem "
                  + "; ".join(f'{i["descricao"]} ({i["sap"]})'
                              for i in pontes[:2]))
    else:
        frase += " - a lista nao tem peca com essas duas faces"
    return frase


def _duas_faces(catalogo, dados):
    """Duas pontas da MESMA bitola que nao se declararam iguais.

    Quando as duas sao flange e so a NORMA difere, a pergunta nao e o nome: e
    a furacao. NBR PN16 e EN PN16 tem a mesma ate 8" - ali as duas parafusam,
    e o que muda e a classe de pressao, nao o furo. De 10" para cima elas
    divergem, e ai nao ha aperto que resolva.

    A regra do motor continua conservadora - ela recusa pelo nome, e ninguem
    monta por engano. O que mudou e que a MENSAGEM diz qual dos dois casos e,
    em numeros que se conferem com o paquimetro.
    """
    tipo_a, norma_a = dados["de"]
    tipo_b, norma_b = dados["para"]
    dn = dados["dn"]
    if tipo_a != tipo_b:
        return (f'{tipo_a.lower()} contra {tipo_b.lower()} em {dn:g}" - '
                f"precisa de adaptador")
    iguais = regras.mesma_furacao(norma_a, norma_b, dn)
    fa, fb = regras.furacao(norma_a, dn), regras.furacao(norma_b, dn)
    # O CIRCULO ENTRA NA FRASE. Em 6" a ANSI 150 e a NBR PN16 tem os mesmos
    # 8 furos de 22, e mesmo assim nao fecham: o circulo e outro. Sem ele a
    # mensagem dizia "8 furos ⌀22 contra 8 furos ⌀22 - nao fecham", que parece
    # erro do programa e e a verdade da peca
    conta = (f"{fa[0]} furos ⌀{fa[1]:g} em ⌀{fa[2]:g}" if fa
             else "sem furação tabelada")
    contra = (f"{fb[0]} furos ⌀{fb[1]:g} em ⌀{fb[2]:g}" if fb
              else "sem furação tabelada")
    if iguais:
        return (f'{norma_a} contra {norma_b} em {dn:g}": a furação é a mesma '
                f"({conta}) e as duas parafusam - o que muda é a classe de "
                f"pressão, não o furo. Conferir a vedação e o que a folha do "
                f"fabricante manda")
    cabeca = (f'{norma_a} contra {norma_b} em {dn:g}": {conta} contra '
              f"{contra} - não fecham")
    pontes = catalogo.ponte(dn, norma_a, dn, norma_b) if catalogo else []
    if pontes:
        return cabeca + " - a lista tem " + "; ".join(
            f'{i["descricao"]} ({i["sap"]})' for i in pontes[:2])
    return cabeca + " - a lista não tem peça com essas duas faces"


def _avisar_classe(junc, avisos, onde):
    """A classe de pressao das duas pecas que se encontram.

    A furacao ja dizia se elas PARAFUSAM; isto diz se o que sai dali AGUENTA.
    Sao perguntas diferentes e as duas passam despercebidas do mesmo jeito:
    uma flange PN 10 casa perfeitamente com uma PN 16 de 6" - mesma furacao,
    mesmo parafuso, aperta redondo - e a linha inteira fica valendo 10 bar
    naquele ponto. So se descobre na pressao de teste, ja montado.

    Cala quando uma das duas nao declara classe. Ver `motor/pressao.py`: um
    numero inventado aqui pareceria resposta.
    """
    de, para = junc["de"], junc["para"]
    veredito, frase = pressao.na_juncao(de.classe_pressao(),
                                        para.classe_pressao())
    if veredito not in ("menor", "outra familia"):
        return
    # O FLANGE E O COLAR NAO CONDUZEM: eles APERTAM. Um colar PN 16 num tubo
    # de PEAD PN 6 e o par normal - o colar e a ferragem daquele tubo, e nao
    # um elo a mais na linha - e dizer ali "a junta so vale PN 6" seria repetir
    # a classe do tubo em cada ponta dele, em toda linha de PEAD que a casa
    # monta. O aviso perde o sentido quando ele aparece sempre
    if veredito == "menor":
        forte = max((de, para), key=lambda p: p.classe_pressao()["valor"])
        if forte.familia in pressao.SO_APERTAM:
            return
    avisos.append(f"{onde}: classe de pressão - {frase}")


def ferragem_de_juncao(catalogo, junc, somar, avisos, rotulo=""):
    """Os itens derivados de UMA juncao flangeada, somados na lista.

    Sai da `Linha` porque o PROJETO tambem precisa: a boca em que um ramo
    nasce e uma juncao flangeada como qualquer outra, e ela nao pertence a
    montagem nenhuma - nasce entre duas. Enquanto esta conta so existia dentro
    da Linha, o desenho punha parafuso ali e a lista nao comprava nenhum.

    **A WAFER E A EXCECAO.** Ela nao tem flange: e abraçada pelas duas
    vizinhas, e o que aperta sao as barras roscadas de ponta a ponta - toda a
    furacao vai de tirante, e nao sobra furo para parafuso. O desenho ja sabia
    disso (`desenhar_linha` funde as duas juncoes da wafer numa so); a lista
    cobrava os parafusos assim mesmo, e a valvula saia com tirante E parafuso.
    Fica so a junta, uma de cada lado.
    """
    onde = f"{rotulo}juncao {junc['pos']}"
    if junc["acao"] == "recusada":
        avisos.append(f"{onde} ({junc['de'].familia} -> "
                      f"{junc['para'].familia}): {junc['dados']['motivo']}")
        return
    _avisar_classe(junc, avisos, onde)
    if junc["acao"] != "direta":
        avisos.append(f"{onde}: {_explicar(catalogo, junc)}")
        return
    dados = junc["dados"]
    if dados["junta"] not in regras.TIPOS_FLANGE:
        return                # rosca, solda, ponta lisa: sem ferragem
    contexto = regras.contexto_da_junta(junc["de"].material,
                                        junc["para"].material)
    if regras.contexto_sem_regra(contexto):
        avisos.append(f"{onde} ({junc['de'].material} x "
                      f"{junc['para'].material}): combinacao sem regra de "
                      "parafuso - conferir")
    try:
        itens = regras.ferragem_da_junta(
            dados["dn"], dados["norma"], junc["de"].unidade_dn, contexto)
    except regras.Incompatibilidade as erro:
        avisos.append(str(erro))
        return
    aperta_barra = any(p.familia in regras.BARRAS_ROSCADAS_POR_PECA
                       for p in (junc["de"], junc["para"]))
    for papel, esp, qtd in itens:
        if aperta_barra and papel != "JUNTA_PLANA":
            continue          # a barra roscada da peca ja traz o que aperta
        item = ferragem.resolver(catalogo, papel, esp)
        if not item:
            avisos.append(f"sem SAP para {papel} {esp}")
            continue
        somar(item["sap"], item["descricao"], qtd, "ferragem")


class Linha:
    # o que `alterar` pode mudar sem trocar a peca. Fora desta lista o
    # comando recusa: mudar familia ou SAP nao e alterar, e substituir
    ALTERAVEIS = ("comprimento_mm", "sentido", "rotulo", "fonte", "pose",
                  "balao", "balao_angulo", "balao_distancia",
                  "flange_bomba")

    def __init__(self, catalogo, tipo="RECALQUE", area="P01", nome=None):
        self.catalogo = catalogo
        self.id = f"m{next(_montagens)}"   # estavel, como o da peca
        # O TIPO E UM ROTULO, e nao uma chave. Foi sucção e recalque porque
        # foram as duas primeiras; a casa monta adução, barrilete, bomba em
        # série, bomba em paralelo - e nenhuma delas precisa de permissão do
        # programa para existir. Quem quiser um tipo novo escreve o nome dele
        self.tipo = tipo
        self.area = area
        self.nome = nome or tipo.replace("_", " ").capitalize()
        # DE ONDE ESTA MONTAGEM SAI, quando ela e um ramo: {"peca", "boca"}.
        # O ramo nao e um acessorio - acessorio e peca terminal, que FECHA a
        # boca. O ramo continua: e uma corrente inteira que nasce numa boca
        # livre de outra, e e assim que se monta barrilete, adução e duas
        # bombas em paralelo. Sendo uma `Linha` como qualquer outra, ele se
        # edita com os mesmos comandos e desfaz na mesma pilha
        self.origem = None
        self.pecas = []
        # a POSE da linha na folha: de quanto ela esta girada, e se esta
        # espelhada. Nao e geometria da peca - e como o conjunto se deita no
        # papel, e por isso vale para a tela E para o DXF exportado
        self.giro = 0.0           # graus, no sentido do SVG (y para baixo)
        self.espelho = 1          # +1 normal, -1 refletida no eixo da linha
        # a ordem dos ITENS da lista - e com ela a numeracao dos baloes. Vazia
        # e a ordem de leitura da linha; `renumerar` fixa outra. Guarda codigo
        # SAP, e nao id de peca, porque o numero e da linha da lista: trocar a
        # peca de lugar na corrente nao renumera nada
        self.ordem_baloes = []
        self.feitos = []          # pilha de comandos aplicados
        self.desfeitos = []       # o que saiu do desfazer, esperando refazer

    # ---------------- comandos (unica porta de escrita do modelo) -----------
    def _executar(self, comando):
        """Aplica o comando e o empilha.

        Editar apaga o refazer, e isso e proposital: depois de desfazer tres
        passos e editar, o que estava adiante deixou de existir. Manter a
        pilha daria a impressao de um futuro que nao volta mais.
        """
        comando.fazer()
        self.feitos.append(comando)
        self.desfeitos.clear()
        return comando

    @contextlib.contextmanager
    def lote(self, nome):
        """As edicoes feitas aqui dentro viram UM comando no historico.

        Trocar a bitola de doze pecas sao doze `substituir`, e quem trocou
        espera desfazer isso uma vez, e nao doze. O lote nao e um sexto
        comando: e a costura dos que ja existem - cada um continua sabendo se
        desfazer, e o lote so os desfaz na ordem contraria, que e a unica
        ordem em que a pilha volta ao lugar.

        Um comando so, ou nenhum, passa direto: embrulhar um comando sozinho
        so trocaria o nome dele no historico.
        """
        marca = len(self.feitos)
        yield self
        juntos = self.feitos[marca:]
        if len(juntos) < 2:
            return
        del self.feitos[marca:]
        self.feitos.append(Comando(
            nome,
            lambda: [c.fazer() for c in juntos],
            lambda: [c.desfazer() for c in reversed(juntos)],
            juntos[0].alvo))

    def posicao(self, alvo):
        """Aceita indice ou id, e devolve o indice de agora.

        A tela segura o ID; o indice ela nao pode segurar, porque inserir,
        remover e mover mudam o indice de todo mundo depois deles.
        """
        if isinstance(alvo, Peca):
            alvo = alvo.id
        if isinstance(alvo, str):
            for i, peca in enumerate(self.pecas):
                if peca.id == alvo:
                    return i
            raise KeyError(f"peca {alvo} nao esta na linha")
        if alvo < 0:
            alvo += len(self.pecas)
        if not 0 <= alvo < len(self.pecas):
            raise IndexError(f"posicao {alvo} fora da linha de "
                             f"{len(self.pecas)} pecas")
        return alvo

    def achar(self, alvo):
        """A peca do id, esteja ela na corrente ou acoplada a alguem.

        `posicao` so enxerga a corrente, porque indice de acessorio nao
        existe - ele vive DENTRO da peca que o carrega. Quem precisa da peca,
        e nao do lugar dela, pergunta aqui: e o que deixa `alterar` chegar no
        acessorio para apagar o balao dele sem inventar um segundo comando.
        """
        if isinstance(alvo, Peca):
            return alvo
        if isinstance(alvo, int):
            return self.pecas[self.posicao(alvo)]
        for peca in self.todas_as_pecas():
            if peca.id == alvo:
                return peca
        raise KeyError(f"peca {alvo} nao esta na linha")

    # A BOMBA DESCARREGA PARA O LADO EM QUE A LINHA CONTINUA. Numa sucção a
    # linha sobe do poço e a bomba fica no alto; o recalque sai dali para o
    # campo, e no papel a linha corre da esquerda para a direita. Entao numa
    # linha DE PE a bomba nasce espelhada - com a boca de recalque para a
    # direita - em vez de descarregar para tras do desenho.
    #
    # E so o nascimento: `espelhar` continua virando a peca para o outro lado,
    # e quem virou manda.
    NASCEM_ESPELHADAS_NA_VERTICAL = ("BOMBA",)

    def _sentido_de_nascimento(self, peca):
        de_pe = abs(abs(self.giro % 360) - 90) < 1 or \
            abs(abs(self.giro % 360) - 270) < 1
        if (de_pe and peca.sentido == 1
                and peca.familia in self.NASCEM_ESPELHADAS_NA_VERTICAL):
            return -1
        return peca.sentido

    def inserir(self, peca, pos=None):
        peca.sentido = self._sentido_de_nascimento(peca)
        pos = len(self.pecas) if pos is None else (
            pos if isinstance(pos, int) else self.posicao(pos))
        pos = max(0, min(pos, len(self.pecas)))
        self._executar(Comando(
            "inserir",
            lambda: self.pecas.insert(pos, peca),
            lambda: self.pecas.pop(pos),
            peca.id))
        return peca

    def remover(self, alvo):
        pos = self.posicao(alvo)
        peca = self.pecas[pos]
        self._executar(Comando(
            "remover",
            lambda: self.pecas.pop(pos),
            lambda: self.pecas.insert(pos, peca),
            peca.id))
        return peca

    def _dono(self, alvo):
        """(peca que carrega, indice) do acessorio - ou None se nao for um."""
        chave = alvo.id if isinstance(alvo, Peca) else alvo
        for dono in self.pecas:
            for i, peca in enumerate(dono.acessorios):
                if peca.id == chave or peca is alvo:
                    return dono, i
        return None

    def substituir(self, alvo, peca):
        """Troca a peca por outra - na corrente ou dentro de quem a carrega.

        O acessorio se troca pelo mesmo comando, e nao por um proprio: para
        quem edita e a mesma coisa - a flange cega de 6" vira a de 8" - e o
        que muda e so onde ela esta guardada. O que ele NAO herda e o que
        estava acoplado nele, porque isso e da peca que sai; quem troca em
        lote leva os acessorios junto de proposito (ver api/nucleo._bitola).
        """
        onde = self._dono(alvo)
        if onde is not None:
            dono, i = onde
            antiga = dono.acessorios[i]
            self._executar(Comando(
                "substituir",
                lambda: dono.acessorios.__setitem__(i, peca),
                lambda: dono.acessorios.__setitem__(i, antiga),
                peca.id))
            return antiga
        pos = self.posicao(alvo)
        antiga = self.pecas[pos]
        self._executar(Comando(
            "substituir",
            lambda: self.pecas.__setitem__(pos, peca),
            lambda: self.pecas.__setitem__(pos, antiga),
            peca.id))
        return antiga

    def alterar(self, alvo, **campos):
        """Muda um parametro da peca SEM trocar a peca.

        E a diferenca entre `alterar` e `substituir`, e ela importa na lista:
        alterar o comprimento de um tubo nao muda o codigo SAP que se compra,
        trocar a peca muda. Por isso o id sobrevive ao alterar.

        Trocar a `fonte` e alterar de verdade: nao troca a peca, troca a folha
        de onde a cota dela sai - e a cota vem junto, por `recalcular()`.
        """
        peca = self.achar(alvo)
        fora = [c for c in campos if c not in self.ALTERAVEIS]
        if fora:
            raise ValueError(
                f"{', '.join(fora)} nao e alteravel - so "
                f"{', '.join(self.ALTERAVEIS)}. Mudar familia ou codigo nao e "
                f"alterar, e substituir")
        antes = {c: getattr(peca, c) for c in campos}
        # o comprimento pedido a mao vira o novo pedido: sem isso o
        # recalcular() da fonte apagaria o que a pessoa digitou
        pedido_antes = peca._comprimento_pedido

        # ALTERAR SEMPRE RECALCULA. Antes so a `fonte` disparava o recalculo,
        # e por isso mudar a furacao da flange da bomba nao mexia nas portas
        # dela - elas tinham sido montadas no nascimento da peca e ficavam com
        # a norma antiga. `recalcular` e barato e idempotente: refaz a cota a
        # partir do que foi pedido e remonta as portas
        def fazer():
            for campo, valor in campos.items():
                setattr(peca, campo, valor)
            if "comprimento_mm" in campos:
                peca._comprimento_pedido = campos["comprimento_mm"]
            peca.recalcular()

        def desfazer():
            for campo, valor in antes.items():
                setattr(peca, campo, valor)
            peca._comprimento_pedido = pedido_antes
            peca.recalcular()

        self._executar(Comando("alterar", fazer, desfazer, peca.id))
        return peca

    def pose(self, giro=None, espelho=None):
        """Gira ou espelha a LINHA INTEIRA na folha. Tambem e comando.

        A peca de uma linha nao tem posicao propria - ela cai onde a anterior
        deixou, ver geometria(). Entao "girar a peca" nao existe aqui: o que
        existe e girar o conjunto, e espelhar uma peca, que e o `sentido` dela.

        Passa pelo historico como qualquer edicao porque muda o que sai no
        DXF: quem girou a folha e desfez tem de voltar ao que exportou antes.
        """
        antes = (self.giro, self.espelho)
        depois = (self.giro if giro is None else float(giro) % 360,
                  self.espelho if espelho is None else (1 if espelho > 0 else -1))
        if depois == antes:
            return self

        def fazer():
            self.giro, self.espelho = depois

        def desfazer():
            self.giro, self.espelho = antes

        self._executar(Comando("pose", fazer, desfazer, None))
        return self

    def renumerar(self, ordem):
        """Poe os itens da lista na ordem pedida - e com eles os baloes.

        Recebe codigo SAP ou id de peca (o id vira o codigo dela), porque quem
        arrasta arrasta o balao, que e uma PECA, e quem arrasta na tabela
        arrasta uma LINHA, que e um codigo. O que nao vier fica atras, na
        ordem de leitura da linha: renumerar tres itens de trinta nao obriga
        ninguem a listar os outros vinte e sete.

        E comando como qualquer outro - a numeracao vai para o DXF e para a
        folha assinada, e quem renumerou e desfez tem de voltar ao que
        imprimiu antes.
        """
        pedida, vistos = [], set()
        for alvo in ordem or []:
            sap = alvo.sap if isinstance(alvo, Peca) else str(alvo)
            if sap not in self.catalogo.por_sap:
                achada = next((p for p in self.todas_as_pecas()
                               if p.id == sap), None)
                if achada is None:
                    raise KeyError(f"{sap} nao e codigo nem peca desta linha")
                sap = achada.sap
            if sap not in vistos:
                vistos.add(sap)
                pedida.append(sap)
        antes = list(self.ordem_baloes)

        def fazer():
            self.ordem_baloes = pedida

        def desfazer():
            self.ordem_baloes = antes

        self._executar(Comando("renumerar", fazer, desfazer, None))
        return self.numeracao()

    def acoplar(self, alvo, peca):
        """Poe uma peca terminal na boca que sobra do alvo.

        E o unico jeito honesto de desenhar um te de verdade numa corrente
        linear. O te tem tres bocas: a corrente entra por uma e sai por outra,
        e a terceira fica. O que vai nela - flange cega, ventosa, dreno - nao
        continua a linha, TERMINA ali, e por isso nao precisa virar um ramo
        com regras proprias.

        O acessorio conta na lista de materiais como qualquer peca, e some
        junto quando a peca que o carrega sai - ele vive DENTRO dela.
        """
        pos = self.posicao(alvo)
        dono = self.pecas[pos]

        def fazer():
            dono.acessorios.append(peca)

        def desfazer():
            dono.acessorios.remove(peca)

        self._executar(Comando("acoplar", fazer, desfazer, peca.id))
        return peca

    def desacoplar(self, alvo):
        """Tira um acessorio da peca que o carrega."""
        for dono in self.pecas:
            for i, peca in enumerate(dono.acessorios):
                if peca.id == alvo or peca is alvo:
                    def fazer():
                        dono.acessorios.pop(i)

                    def desfazer():
                        dono.acessorios.insert(i, peca)

                    self._executar(Comando("desacoplar", fazer, desfazer,
                                           peca.id))
                    return peca
        raise KeyError(f"acessorio {alvo} nao esta na linha")

    def todas_as_pecas(self):
        """As pecas da corrente e os acessorios delas, em ordem de leitura.

        E o que a LISTA DE MATERIAIS conta: o acessorio se compra do mesmo
        jeito que a peca que o carrega.
        """
        for peca in self.pecas:
            yield peca
            for acessorio in peca.acessorios:
                yield acessorio

    def mover(self, alvo, para):
        """Tira a peca de onde ela esta e a poe em outra posicao da sequencia.

        A posicao de uma peca e consequencia de quem veio antes - ver
        geometria(). Entao mover uma peca move tudo o que vem depois dela, e e
        por isso que mover e um comando do documento e nao um arrasto na tela.
        """
        de = self.posicao(alvo)
        para = para if isinstance(para, int) else self.posicao(para)
        para = max(0, min(para, len(self.pecas) - 1))
        peca = self.pecas[de]

        def fazer():
            self.pecas.insert(para, self.pecas.pop(de))

        def desfazer():
            self.pecas.insert(de, self.pecas.pop(para))

        self._executar(Comando("mover", fazer, desfazer, peca.id))
        return peca

    def mover_bloco(self, alvos, para):
        """Tira varias pecas da sequencia e as reinsere juntas noutro ponto.

        Nao e `mover` repetido: mover uma de cada vez muda o indice das
        outras no meio do caminho, e o bloco chegaria embaralhado. Aqui a
        sequencia nova se calcula inteira e entra de uma vez - um comando, um
        desfazer.

        As pecas entram na ordem em que ESTAVAM, e nao na ordem em que foram
        clicadas: quem seleciona tubo, curva e tubo e arrasta espera que eles
        continuem tubo, curva e tubo do outro lado.
        """
        escolhidas = {self.posicao(a) for a in alvos}
        if not escolhidas:
            return self
        bloco = [self.pecas[i] for i in sorted(escolhidas)]
        resto = [p for i, p in enumerate(self.pecas) if i not in escolhidas]
        # o destino e contado na linha SEM o bloco: e o unico jeito de "poe
        # antes da valvula" continuar querendo dizer a mesma coisa depois de
        # tirar as pecas do caminho
        para = para if isinstance(para, int) else self.posicao(para)
        para -= sum(1 for i in sorted(escolhidas) if i < para)
        para = max(0, min(para, len(resto)))
        antes = list(self.pecas)
        depois = resto[:para] + bloco + resto[para:]
        if depois == antes:
            return self

        def fazer():
            self.pecas[:] = depois

        def desfazer():
            self.pecas[:] = antes

        self._executar(Comando("mover", fazer, desfazer, bloco[0].id))
        return self

    # ---------------- desfazer e refazer ------------------------------------
    def desfazer(self):
        """Volta um comando. Devolve o comando desfeito, ou None."""
        if not self.feitos:
            return None
        comando = self.feitos.pop()
        comando.desfazer()
        self.desfeitos.append(comando)
        return comando

    def refazer(self):
        """Reaplica o ultimo comando desfeito. Devolve ele, ou None."""
        if not self.desfeitos:
            return None
        comando = self.desfeitos.pop()
        comando.fazer()
        self.feitos.append(comando)
        return comando

    @property
    def historico(self):
        """Os comandos aplicados, do primeiro ao ultimo."""
        return list(self.feitos)

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

    def divergencias(self):
        """Peca cuja MEDIDA DESENHADA nao e a medida do CODIGO comprado.

        E a conferencia mais barata do programa e a que evita o erro mais
        caro: um tubo desenhado com 2,35 m carregando o codigo da barra de
        6 m. O desenho vai para a obra dizendo 2,35 e a lista vai para a
        compra dizendo 6 - e as duas estao certas cada uma por si.

        Isso acontece de proposito as vezes: barra de 6 m cortada no campo. Nao
        e defeito, e decisao - mas tem de estar ESCRITA, e nao implicita no
        fato de os dois numeros nunca serem comparados. Quem le a folha ve
        "cortado de 6 m" e sabe o que pedir.

        So o tubo entra: e a unica peca que se corta. Numa valvula os dois
        numeros divergirem seria outra coisa - cota de fabricante contra cota
        da casa - e isso ja e dito pela `fonte`.
        """
        fora = []
        for peca in self.pecas:
            if peca.familia != "TUBO":
                continue
            do_codigo = peca.item.get("comprimento_mm")
            if not do_codigo:
                continue
            desenhado = peca.comprimento_mm or 0
            if abs(desenhado - do_codigo) > 1:
                fora.append({"peca": peca, "desenhado_mm": desenhado,
                             "do_codigo_mm": do_codigo})
        return fora

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

        Nao e CAD: e a soma vetorial das cotas, com a curva girando a direcao
        entre as suas duas pernas. Nenhuma peca tem posicao propria - a posicao
        e consequencia de quem veio antes, e e isso que faz arrastar uma peca
        no desenho virar "alongar o tubo vizinho" na lista.
        """
        import math

        x = y = 0.0
        direcao = self.giro          # a pose da folha vale aqui tambem: o
        pontos = []                  # esquema nao pode discordar do desenho

        for peca in self.pecas:
            peca._espelho_da_linha = self.espelho
            antes, depois = peca.avancos()
            nx = x + antes * math.cos(math.radians(direcao))
            ny = y + antes * math.sin(math.radians(direcao))
            ponto = {"peca": peca, "de": (x, y), "para": (nx, ny),
                     "direcao": direcao, "direcao_saida": direcao,
                     "canto": None, "fonte_cota": peca.fonte_cota}
            x, y = nx, ny

            # QUEM SABE DE QUANTO VIRA E A PECA, e nao esta funcao. Aqui
            # estava escrito "se for curva, some o angulo" - e o te de pe, que
            # vira a linha 90 sem ser curva, passava reto
            gira = peca.giro_interno()
            if gira:
                direcao += gira
                ponto["direcao_saida"] = direcao
                if depois:
                    ponto["canto"] = (x, y)
                    x += depois * math.cos(math.radians(direcao))
                    y += depois * math.sin(math.radians(direcao))
                    ponto["para"] = (x, y)

            pontos.append(ponto)
        return pontos

    # ---------------- saidas ------------------------------------------------
    def lista_materiais(self, sequencia=True):
        """BOM final: pecas da linha + ferragem derivada, agregada por SAP.

        Formato de saida = as colunas da aba Orcamento (Area, Cod. SAP, Qtd).

        `sequencia=False` cala a conferencia de ordem hidraulica. Quem passa
        isso e o `Projeto`, que faz a MESMA conferencia sobre a arvore
        inteira: o filtro pode estar no tronco e a valvula num ramo, e ai a
        montagem sozinha acusaria "filtro sem valvula" que existe.
        """
        bom = OrderedDict()
        avisos = []

        def somar(sap, descricao, qtd, origem):
            reg = bom.setdefault(sap, {"sap": sap, "descricao": descricao,
                                       "qtd": 0, "origem": origem})
            reg["qtd"] += qtd

        for peca in self.todas_as_pecas():
            somar(peca.sap, peca.descricao, 1, "linha")
            # A FOLHA EMPRESTADA SE DECLARA. A casa so tem dimensional da
            # Dorot; a Bermad da lista nao traz serie e a Dorot de plastico
            # traz o DN no lugar dela. As duas acabam desenhadas com o corpo
            # da Dorot basica - o que nao pode e isso passar calado numa folha
            # que alguem assina
            if peca.familia in Peca.PELO_SIMBOLO:
                ficha = regras.flange_da_bomba(peca.descricao)
                bocas = [p["dn"] for p in peca.portas]
                succao = bocas[0] if bocas else None
                if regras.pode_vir_roscada(succao, peca.descricao):
                    avisos.append(
                        f"{peca.descricao}: até o tamanho 65-200 a boca pode "
                        f"vir ROSQUEADA (BSP) em vez de flangeada - e rosca "
                        f"não leva junta nem parafuso. Confira o pedido")
                if peca.flange_bomba:
                    pass                    # alguem leu a folha e disse qual
                elif ficha["assumida"]:
                    avisos.append(
                        f"{peca.descricao}: a casa não tem a folha desta "
                        f"bomba. A mesma máquina sai furada em "
                        f"{', '.join(regras.FURACOES_DE_BOMBA)} conforme o "
                        f"pedido, e o desenho assumiu "
                        f"{ficha['furacao']} (ASME B16.1 Classe 125). Diga "
                        f"qual veio na folha antes de pedir a peça de ponte")
                else:
                    da_folha = [ficha["succao_pol"], ficha["recalque_pol"]]
                    if bocas and da_folha != bocas:
                        avisos.append(
                            f"{peca.descricao}: a folha diz "
                            f'{da_folha[0]:g}"×{da_folha[1]:g}" e o desenho '
                            f'saiu {bocas[0]:g}"×{bocas[1]:g}" - conferir')
            if peca.familia == "VALVULA_HIDRAULICA" and peca.item["dn"]:
                _serie, emprestada = cotas.serie_da_valvula(
                    peca.item, max(peca.item["dn"]))
                if emprestada:
                    avisos.append(
                        f"{peca.descricao}: a casa não tem folha desta "
                        f"válvula - o corpo saiu da Dorot básica "
                        f"({peca.comprimento_mm:.0f} mm de face a face). "
                        f"Confira antes de fechar a cota geral")
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
            ferragem_de_juncao(self.catalogo, junc, somar, avisos)

        for t in self.trechos_retos():
            if t["ok"]:
                continue
            avisos.append(
                f"{t['peca'].familia} na posicao {t['pos']}: precisa de "
                f"{t['exige_antes_mm']/1000:.2f} m de tubo reto antes e "
                f"{t['exige_depois_mm']/1000:.2f} m depois; o desenho tem "
                f"{t['antes_mm']/1000:.2f} m e {t['depois_mm']/1000:.2f} m"
            )

        # A ORDEM HIDRAULICA: filtro -> valvula -> medidor. A conferencia
        # existia em `motor/hidraulica.py` desde que a ordem foi confirmada
        # nos tres projetos, e nao era chamada por ninguem - sabia a resposta
        # e nunca era perguntada
        if sequencia:
            avisos += hidraulica.conferir_sequencia(
                [p.familia for p in self.todas_as_pecas()])
            avisos += fluxo.conferir(
                self.pecas,
                [a for p in self.pecas for a in p.acessorios])

        # o NUMERO DO ITEM sai daqui, e nao do desenho: e a posicao da linha
        # na lista, e o balao so a repete. Fosse ao contrario, uma peca sem
        # balao ficaria sem numero na lista, e a lista e quem se compra
        itens = [bom[sap] for sap in self._ordem_dos_itens(list(bom))]
        for numero, reg in enumerate(itens, 1):
            reg["item"] = numero
        return itens, avisos

    def _ordem_dos_itens(self, saps):
        """Os codigos na ordem que vale: a fixada primeiro, o resto atras.

        Ordem fixada que perdeu a peca simplesmente sai - e o que faz a
        numeracao se refazer sozinha quando alguem remove uma peca, em vez de
        deixar um buraco no meio dos numeros.
        """
        fixa = [s for s in self.ordem_baloes if s in saps]
        return fixa + [s for s in saps if s not in fixa]

    def numeracao(self):
        """{codigo SAP: numero do item}, na ordem em que a lista mostra."""
        itens, _avisos = self.lista_materiais()
        return OrderedDict((reg["sap"], reg["item"]) for reg in itens)

    def baloes(self):
        """O balao de cada peca que mostra o dela: id, numero e pose.

        Duas pecas do mesmo codigo levam o MESMO numero - ver BALAO_ANGULO.
        O acessorio entra como qualquer peca, e sai da lista de baloes (mas
        nao da lista de materiais) quando alguem desmarca o balao dele.
        """
        numeros = self.numeracao()
        saida = []
        for peca in self.todas_as_pecas():
            if not peca.balao or peca.sap not in numeros:
                continue
            saida.append({"id": peca.id, "n": numeros[peca.sap],
                          "angulo": peca.balao_angulo,
                          "distancia": peca.balao_distancia})
        return saida
