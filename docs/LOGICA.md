# Lógica do programa de sucção e recalque

Documento de projeto. Modelo de dados, regras de montagem e o mecanismo que
mantém desenho e lista sempre iguais.

Baseado em três coisas reais: a lista de materiais Netafim (`LM_CANAL_REV1`,
5.157 itens, base jul/2026) e três casas de máquinas já desenhadas
(Marcelo Amorim 1855NN, Lincoln Junqueira 2040/25NN, Thiago Derks).

## 1. O alvo

O produto final é o que os projetos já entregam hoje: uma prancha com o desenho
balonado e a **Lista de peças** (`Item | Número da peça | Qtd`) — só que
**vista lateral 2D**, não conjunto 3D, e com a lista saindo pronta em código SAP.

Dois formatos convivem hoje e o programa precisa dos dois:

| formato | quem usa | chave |
|---|---|---|
| Lista de peças do desenho | projetista, montagem em campo | nome livre (`Red Exc AZ 4"x 2"`) |
| Aba Orçamento da planilha | comercial | código SAP (`01523-281940`) |

## 2. O ponto central: não existe sincronização

A tentação é ter um desenho e uma planilha e sincronizar os dois. Isso sempre
diverge. Aqui:

> **Existe um único documento — a Linha. Desenho e lista são duas projeções
> dela.** Editar no desenho e editar na tabela são o mesmo comando atingindo o
> mesmo objeto.

**Uma casa de bomba não é uma linha.** Tem a sucção, o recalque, o barrilete,
o trecho que sai para o campo — e com duas bombas, em série ou em paralelo,
tem tudo isso duas vezes. Então o que a sessão guarda é um `Projeto`: N
montagens, cada uma sendo a `Linha` de sempre. Nenhum comando de edição mudou
de lugar — eles agem na montagem aberta. O projeto só sabe criar, escolher,
renomear e apagar montagem, e essas quatro também são comandos, porque apagar
por engano tem de poder voltar.

**O tipo da montagem é um rótulo, e não uma chave.** Foi `SUCCAO` e `RECALQUE`
porque foram as duas primeiras; adução, barrilete, bombeamento e o que a casa
inventar não precisam de permissão do programa para existir. As montagens
*prontas* vivem num registro (`templates.MONTAGENS`) — uma nova é uma função e
uma linha na tabela, e ela aparece sozinha na barra de comando e na tela, pelo
mesmo motivo que o vocabulário mora no motor.

**O ramo é uma montagem ancorada numa boca livre.** Não é acessório —
acessório é peça terminal, que *fecha* a boca (flange cega, ventosa); o ramo
*continua* a partir dela, com tubo, curva, válvula e o que precisar. Sendo uma
`Linha` como qualquer outra, ele se edita com os mesmos comandos, desfaz na
mesma pilha e numera os mesmos balões. É assim que se monta barrilete, adução
e duas bombas em paralelo.

No desenho isso não custou geometria nova: monta-se o ramo na origem, acha-se
a boca em que ele nasce e leva-se a corrente inteira para lá — a mesma
transformação rígida que já pendurava um acessório, aplicada a uma corrente em
vez de a uma peça. E é recursiva: um ramo pode ter ramos.

**Com ramo, a lista passa a ser da árvore.** O desenho mostra o tronco e as
saídas juntos, então a lista tem de mostrar as duas — lista só do tronco ao
lado de um desenho com os ramos seria exatamente a divergência que este
programa existe para não ter.

**Desfazer atravessa montagens.** Cada comando sabe *quando* aconteceu, e o
`ctrl+Z` desfaz o mais recente do projeto inteiro — não o último da aba em que
o olho está. Quem edita a sucção, troca para o recalque e desfaz quer de volta
o que acabou de fazer.

Comandos (única porta de escrita): `inserir`, `remover`, `substituir`,
`alterar`, `mover`. Cada comando → valida → recalcula junções e ferragem →
redesenha as duas views. Undo/redo é a pilha de comandos. O balão do desenho e a
linha da tabela são a mesma peça, com o mesmo id.

**O comando conta até n.** Escolher três tubos e mandar `comprimento 1500` é o
mesmo verbo, com três alvos — não existe uma segunda versão de cada comando
para "várias". As edições de uma leva viram **um** comando no histórico
(`Linha.lote`), e é isso que faz trocar a bitola de doze peças desfazer numa
vez só. Cada uma continua sabendo se desfazer sozinha; o lote só as desfaz na
ordem contrária.

**A posição é consequência, e por isso ninguém "atualiza" ninguém.** Mudar o
comprimento de um tubo move tudo o que vem depois dele, porque a posição de
cada peça é a soma das cotas de quem veio antes — ver 5. Não há o que
selecionar para propagar: o que se guarda é a escolha, e o desenho é
recalculado inteiro a cada comando. O que **não** se propaga sozinho é a
bitola: trocar uma peça de 6" por uma de 8" deixa a vizinha em 6" e a junção
passa a acusar redução. É por isso que existe `bitola`, que troca a linha
inteira (ou só o que estiver escolhido) por *a mesma peça noutro tamanho* — e
diz por escrito o que a lista não tinha naquele tamanho, em vez de escolher um
código parecido calado.

### A tela não guarda o documento

`web/` é o programa: desenho à esquerda, lista de materiais à direita, painel
da peça selecionada. E ela **não acumula estado** — cada comando devolve o
documento inteiro e a tela repinta. O único estado dela é qual peça está
selecionada, e mesmo esse é um id que veio do motor.

Duas decisões que caem daí:

**O SVG vem pronto do motor.** `motor/vista.py` desenha a linha e marca cada
grupo com `data-id`. A tela não sabe desenhar nada — ela sabe em quem o dedo
caiu, e só. Desenhar no navegador significaria uma segunda biblioteca de
símbolos em JavaScript, que é exatamente a duplicação que este projeto evita
em todo o resto.

**O CSS do desenho também vem do motor**, por um comando `estilo`. Duas folhas
de estilo divergiriam no primeiro ajuste, e o traço é do desenho, não da
interface.

Uma coisa que só apareceu ao clicar: **traço de 1 px não é alvo**. Quem quer
selecionar o tubo aponta para o meio dele, que é vazio. Cada peça leva um
retângulo transparente do tamanho da caixa dela — invisível no papel, alvo no
programa.

`tools/conferir_tela.py` sobe o servidor, abre um navegador de verdade e cobra
as três coisas: clicar no desenho acende a linha certa da tabela, desfazer pelo
botão devolve o desenho **e** a tabela, e o console fica limpo — erro de
JavaScript não aparece no desenho, a tela só para de repintar e quem usa acha
que o programa travou.

### Arrastar pergunta antes de soltar

Arrastar uma peça sobre outra a coloca na posição dela. E antes de soltar, a
tela **pergunta ao motor o que aconteceria** — comando `simular`, que executa o
comando de verdade e o desfaz.

Não há segundo caminho de código, e é isso que importa: um "validador" no
navegador seria a mesma regra escrita duas vezes, com duas chances de estar
diferente. Dá para fazer assim porque desfazer é exato — `conferir_comandos.py`
cobra que o documento volte idêntico nas duas projeções. Se não fosse, arrastar
uma peça sujaria o desenho.

O comando some das duas pilhas: sai dos feitos ao desfazer, e sai dos desfeitos
à mão — senão apareceria um "refazer" de algo que ninguém fez.

Duas coisas que só apareceram ao arrastar de verdade:

**O arrasto é estado da tela, como a seleção.** A tela repinta a cada comando,
inclusive o `simular` do próprio arrasto — então guardar o elemento em vez do
id perdia o arrasto no meio dele. Cada repintura reaplica o estado.

**A anotação não é alvo de nada.** A cota de cada peça cai bem no meio dela, e
a camada de anotação fica por cima do desenho: sem `pointer-events:none`, a
própria cota comia o clique da peça que ela cota.

### O que volta: a montagem salva

Das cinco saídas, só uma **volta a ser documento**. `motor/arquivo.py` grava o
código de cada peça, o que foi pedido a mão nela (o corte de campo), a pose, o
balão e a ordem dos itens — e não grava cota, nem ferragem, nem lista, que são
derivados e se recalculam ao abrir.

**O arquivo guarda a escolha, e não o resultado.** A consequência é a que
interessa: corrigir uma tabela de cotas melhora os desenhos já salvos, em vez
de deixar cada projeto antigo carregando para sempre o erro do dia em que foi
feito. A cota que valia na gravação vai junto só como conferência — ao abrir,
o que a folha de hoje diz diferente vira aviso escrito, e o desenho segue a
folha. Código que saiu da lista também vira aviso, não um buraco calado.

Abrir passa pelos mesmos `inserir` e `acoplar` de quem monta a mão, e limpa o
histórico no fim: abrir não é edição, e um `desfazer` logo depois não pode
começar a desmontar a linha peça por peça.

### O que sai: DXF em 1:1, planilha nas colunas do Orçamento

`motor/exportar.py` devolve **conteúdo**, não caminho: no navegador vira um
download, no Electron o processo pai escolhe onde salvar. Gravar no motor
obrigaria a inventar uma pasta, e a pasta é de quem usa.

O **DXF sai 1:1 em milímetro** — a geometria dos símbolos já é milímetro real,
e é a vista da tela que é escalada dentro de um `<g transform="scale()">`.
Exportar não converte nada. Cada peça vira um `BLOCK` com o **código SAP** no
nome e um `INSERT` com a rotação da corrente, nas camadas da convenção do
desenho: eixo vermelho traço-ponto numa camada só, corpo em preto, chapa e
ferragem separadas — dá para apagar todos os eixos de uma vez, ou plotar só o
corpo.

A **planilha** sai nas colunas da aba Orçamento (Área, Cód. SAP, Descrição,
Qtd, Origem), com os avisos numa aba própria — aviso é sobre o *pedido*
("pedir a válvula em NBR PN16, 12 furos"), não sobre a quantidade, e misturar
os dois faria o comercial somar o que é recado.

### A camada que expõe isso não decide nada

`api/nucleo.py` é a única função que a tela precisa conhecer:
`executar(sessao, comando) → {"ok", "documento"}`. Ela não tem regra nenhuma —
traduz JSON em comando e as projeções em JSON. Qualquer regra que aparecer ali
é regra no lugar errado, porque as duas telas teriam de repeti-la.

**Devolve o documento inteiro a cada comando, e não um remendo.** Numa linha de
sessenta peças são alguns kilobytes, e o que se ganha é que a tela nunca pode
divergir do modelo: ela não acumula estado, só pinta o que chegou. É a mesma
decisão da seção 2, levada até a interface.

**Erro é resposta, não exceção** — `{"ok": false, "erro": …, "documento": …}`,
com o documento intacto. A tela que pediu algo inválido continua mostrando o
que existe, e a pessoa lê o motivo em vez de um traceback.

Duas cascas sobre o mesmo núcleo, e as duas são descartáveis:

| casca | para quem | por quê |
|---|---|---|
| `api/stdio.py` | o Electron | sem porta, sem firewall, sem outra coisa na máquina falando com o motor |
| `api/http.py` | desenvolver a tela | dá para inspecionar no navegador; escuta só em 127.0.0.1 |

`tools/conferir_api.py` cobra as três coisas que importam: o documento
atravessa o JSON inteiro (sem tupla nem objeto perdido), desfazer pela API
devolve o documento idêntico, e **a mesma sequência pelo núcleo e pelo processo
filho dá exatamente os mesmos documentos** — que é a prova de que a casca não
ganhou regra.

Uma sutileza que o teste fixou: desfazer devolve as peças, a geometria e a
lista ao que eram, mas **não** devolve `pode_refazer` — ele passa a ser
verdadeiro justamente porque houve um desfazer. O desenho e a tabela voltam
iguais; a barra de ferramentas não, e nem deveria.

### Os cinco existem, e o teste é sobre as projeções

`motor/linha.py` implementa os cinco, com `desfazer()` e `refazer()`. Cada
comando guarda **como se desfazer**, não uma cópia do documento: numa linha de
sessenta peças o que se guarda é a diferença.

O teste (`tools/conferir_comandos.py`) não verifica que o comando roda —
verifica que **desfazer devolve o documento ao estado exato de antes**, medido
nas duas projeções, a lista de materiais e a geometria. Comparar `linha.pecas`
compararia os mesmos objetos consigo mesmos e passaria com o recálculo
quebrado; as projeções são derivadas, então só voltam iguais se tudo que
depende delas voltou.

Três regras que o teste fixa, e que são decisões de modelo:

**A peça é endereçada por `id`, não por posição.** Índice muda quando alguém
insere, remove ou move, e a tela que segurou um índice passa a apontar para
outra peça. O `id` nasce com a peça e morre com ela.

**`alterar` mantém o id; `substituir` troca.** É a diferença entre os dois, e
ela aparece na lista: alterar o comprimento de um tubo não muda o código SAP
que se compra, trocar a peça muda. Por isso `alterar` recusa `familia` e `sap`
— mudar isso não é alterar, é substituir.

**Trocar a `fonte` é alterar de verdade.** Não troca a peça, troca a folha de
onde a cota dela sai — e a cota vem junto. A curva de 8" mede 335 mm de perna
no Irrigafour e 297 na Netafim, e trocar a fonte move tudo que vem depois dela.

E editar depois de desfazer **apaga o refazer**: depois de voltar três passos e
editar, o que estava adiante deixou de existir; manter a pilha daria a
impressão de um futuro que não volta mais.

## 3. Modelo de dados

### Peça
Cada item do catálogo vira registro paramétrico (`tools/normalizar.py`, a partir
da descrição em texto livre):

| campo | exemplo |
|---|---|
| `sap` | `01523-134000` |
| `familia` | `CURVA`, `TUBO`, `TE`, `REDUCAO_CONCENTRICA`, `MANIFOLD`, `VALVULA_HIDRAULICA`, … |
| `material` | `ACO_ZINCADO`, `PVC_PLASSON`, `PEAD`, `FOFO` |
| `dn` / `unidade_dn` | `[8.0]` / `in` — ou `[160]` / `mm` |
| `angulo`, `espessura_mm`, `comprimento_mm` | `90`, `2.65`, `3000` |
| `conexoes` | `[{dn:8, tipo:FLANGE, norma:"NBR PN16"} × 2]` |
| `derivacoes` | `[{qtd:2, dn:2, tipo:LUVA}]` (os `2 LG 2"` e `C/ESC.2"`) |

### Porta
Cada peça expõe **portas** — as pontas — como `(dn, tipo, norma)`:
`FLANGE`, `ENGATE_K`, `ROSCA_MACHO`, `RANHURADA`, `SOLDA`, `PONTA_LISA`;
normas `NBR PN10/16/25/40`, `EN PN10/16/40`, `ANSI 150/300`, `K6…K12`,
`PVC SOLDÁVEL`.

### Linha
Sequência ordenada de peças. Entre duas peças consecutivas há uma **junção**,
que é calculada, não digitada.

## 4. Regras de montagem

### 4.1 Compatibilidade (`motor/regras.py::resolver_juncao`)

| situação | resultado |
|---|---|
| DN igual, tipo igual, norma igual | **junção direta** |
| DN diferente | **redução** (concêntrica por padrão; excêntrica na sucção junto à bomba, para não formar bolsa de ar) |
| DN igual, normas diferentes (`NBR PN16` × `ANSI 150`) | **adaptador** — o catálogo tem 67 |
| DN igual, tipos diferentes (`FLANGE` × `ENGATE_K`) | **adaptador FL × K** |

O motor nunca conserta em silêncio: insere a peça de transição e registra o
motivo, ou levanta o problema.

### 4.2 Ferragem derivada (`motor/regras.py`)

Nenhum parafuso é digitado — e hoje **nenhuma das três listas de peças tem
ferragem**, o que é justamente o buraco a fechar. Cada junção flangeada gera:

```
1 × junta plana DN
n × parafuso   (n = nº de furos da norma/DN)
n × porca
n × arruela    (uma só, do lado da porca)
```

A arruela é **uma por parafuso**, e não duas: quem precisa dela é o lado que
gira no aperto — a cabeça assenta direto na chapa. O número sai de
`regras.ARRUELAS_POR_PARAFUSO`, que o desenho e a lista leem do mesmo lugar.

**Bitola e comprimento** (`data/regras_ferragem.csv`). Não é mais regra da
casa: é **calculado**, e a conta está em `motor/regras.aperto_da_junta` e em
`tools/conferir_flanges.py`.

*A bitola* é o maior parafuso que entra no furo da flange com folga de 1,5 a
4,5 mm — furo 14 → 3/8", 18 → 5/8", 22 → 3/4", 26 → 7/8", 31 → 1 1/8".

*O comprimento* é `aperto + arruela + porca + 3 fios`, arredondado para cima na
medida **comercial que a lista tem**: a casa compra por código, e 7/8" × 4½"
não existe nela.

*O aperto* não é "duas chapas" em todo lugar — depende de quem se encontra:

| contexto | o que o parafuso atravessa | camadas |
|---|---|---|
| `AZ_AZ` | chapa + chapa | duas |
| `ACO_PLASSON` | chapa + colar + flange solta | três |
| `PLASSON_PLASSON` | flange solta + colar + colar + flange solta | quatro |

A ponta Plasson é feita de **duas peças**: o colar (desenho 5510), soldado no
tubo, com ressalto de espessura `B`; e a flange solta (5900), de espessura `H`,
que corre por trás do ressalto. É por isso que o parafuso Plasson é mais longo
que o de aço na mesma bitola — não por folga, por geometria. Em 6", o aço pede
3/4" × 2½" e o Plasson-Plasson pede 3/4" × 5" para o mesmo furo.

**As duas flanges soltas não se encostam.** Quem se encosta são os ressaltos
dos colares, e o ressalto é mais estreito que o círculo de furação (no d160,
213 contra 241). Entre uma flange e outra fica um vão de `2·B` com o parafuso à
mostra — 26 mm no d160, 36 no d225. O desenho mostra esse vão, e é ele que
explica os 4" e 5" da tabela.

A conta diz o **mínimo**; o que entra na tabela é o comprimento que a casa já
estoca e que também fecha. Parafuso mais longo sempre fecha, e um código a
menos no almoxarifado vale mais que 20 mm de rosca poupados — por isso o
Plasson sai inteiro em 4" e 5".

Dois contextos **não** são medidos, e isso é deliberado: `BOMBA`, porque o
flange da bomba é do fabricante dela e não há folha aqui; e `MISTO`, que é o que
não cai em nenhum caso (PEAD, por exemplo, que entra por colar de tomada e não
por flange). Medir esses com a chapa de aço dos dois lados daria um veredito
sobre um sanduíche que não existe. `BOMBA` mantém o acréscimo de 1" que a casa
usa sobre a junta de aço; `MISTO` usa uma faixa marcada como chute e o motor
avisa a junção.

**Furação** (`data/regras_furacao.csv`, gerada por `tools/gerar_furacao.py`):
124 linhas cobrindo NBR 7675, EN 1092-1 em PN10/16/25/40 e ANSI 150/300, de
DN40 a DN600, com furos, parafuso, bitola UNC equivalente, diâmetro do furo,
círculo de furação e espessura do flange.

As linhas **NBR 7675 são medidas, não estimadas** — vêm da ficha técnica T.153FB
(`data/fichas/FIG153_valvula_gaveta_flange_NBR7675.pdf`) e estão
`homologado=SIM`. EN e ANSI continuam escritas de norma, `homologado=NAO`.

A NBR 7675 tem um comportamento que a EN não tem: **até DN200 a furação coincide
com PN16; de DN250 para cima ela segue o padrão PN10.** Isso acompanha a queda de
classe da própria válvula na ficha (40–200 mm PN16, 250–300 PN10, 350–600 PN6).

**A regra da casa é a norma, em todos os DN:**

| DN | furos | furo | NBR 7675 | casa usa |
|---|---|---|---|---|
| 2" a 5" | 4 a 8 | 18 mm | M16 → 5/8" | 5/8" |
| 6" | 8 | 22 mm | M20 → 3/4" | 3/4" |
| 8" | 12 | 22 mm | M20 → 3/4" | 3/4" |
| 10" e 12" | 12 | 22 mm | M20 → 3/4" | 3/4" |
| 14" | 16 | 22 mm | M20 → 3/4" | 3/4" |

> **Correção.** A versão anterior deste documento apontava divergência de 10" a
> 14", dizendo que a norma pediria M24. Estava errado: aquilo era a tabela
> EN 1092-1 PN16, e a NBR 7675 segue PN10 nesses diâmetros — furo de 22 mm,
> M20, 3/4". A regra da casa bate com a norma em todos os DN de 2" a 14".

**Chave da tabela: DN nominal em mm.** É o denominador comum entre a série em
polegada do aço e a série em milímetro do PVC — 8" e 225 mm caem os dois em
DN200. `motor/regras.py::dn_nominal` faz a conversão.

**Onde a norma muda na linha.** A linha é sempre NBR PN16; quem traz outra norma
é o equipamento. O catálogo mostra onde a transição acontece:

| peça | contra ANSI 150 | ANSI 300 | EN PN16 | EN PN10 |
|---|---|---|---|---|
| redução concêntrica (91) | 28 | 17 | 18 | 6 |
| redução excêntrica (70) | 24 | 16 | 16 | 7 |
| adaptador (34) | 5 | 4 | — | — |

Ou seja: **a redução é a peça de transição para a bomba importada**, não só um
degrau de diâmetro. Quando o motor insere uma redução ele já tem que decidir a
norma da ponta de jusante — e é aí que a tabela ANSI entra.
`tools/relatorio_furacao.py` imprime esse cruzamento.

### 4.2.2 A norma da bomba não é a norma da linha

A flange que o fabricante entrega na boca da bomba é dele — EN 1092 (PN10,
PN16, PN40) nas europeias, ANSI nas americanas — e a linha corre em NBR 7675.
É por isso que a casa compra **redução concêntrica e excêntrica específica**,
com uma face em cada norma: o catálogo tem **167 delas** (97 concêntricas, 70
excêntricas): 86 contra ANSI, 58 contra EN e 23 entre classes NBR.

**O que decide se duas faces parafusam não é o nome da norma — é a furação.**
Medido na tabela da casa (`data/furacao.csv`), contra NBR PN16:

| | 4" | 6" | 8" | 10" | 12" |
|---|---|---|---|---|---|
| **EN PN16** | casa | casa | casa | ⌀26 contra ⌀22 | ⌀26 contra ⌀22 |
| **EN PN10** | casa | casa | 8 furos contra 12 | casa | casa |
| **ANSI 150** | ⌀19 contra ⌀18 | ⌀241,3 contra ⌀240 | 8 furos contra 12 | — | — |

Três leituras que valem para a obra:

- **ANSI nunca casa com NBR**, em bitola nenhuma. Em 6" as duas têm os mesmos
  8 furos de 22 mm e mesmo assim não fecham: o círculo de furação é 241,3
  contra 240. É 1,3 mm que só aparece na montagem, e é exatamente para isso
  que a peça específica existe.
- **EN casa com NBR na maior parte das bitolas**, e para de casar em pontos
  precisos: a PN10 em 8" (8 furos contra 12), a PN16 de 10" para cima.
- **NBR PN10, PN16 e PN25 têm a mesma furação nas 16 bitolas** — entre elas
  nunca é caso de peça específica.

O motor continua **recusando pelo nome**, que é o lado conservador: ninguém
monta por engano. O que mudou é que a mensagem agora diz qual dos dois casos
é, em números que se conferem com o paquímetro, e aponta o código da peça que
faz a ponte (`catalogo.ponte`). Antes ela dizia só "precisa de redução" — e
calava a metade que decide *qual* redução, porque a redução comum tem as duas
faces em NBR e não serve.

### 4.2.1 Barra roscada

Válvula wafer é presa por tirante. Porca e arruela saem da furação: **2 de cada
por furo do flange** — uma em cada ponta do tirante.

**E o tirante ocupa o furo, então a junta da wafer não leva parafuso nenhum.**
A válvula não tem flange: ela é abraçada pelas duas vizinhas, e a furação
inteira vai de tirante — não sobra furo. O desenho já sabia disso (as duas
junções da wafer viram uma só, com barra roscada de ponta a ponta) e a lista
não: ela cobrava os parafusos das duas faces *além* das barras. Num recalque
de 6" isso eram 16 parafusos comprados para uma válvula que não usa nenhum.
Hoje a exceção mora num lugar só (`linha.ferragem_de_juncao`), lido pelas duas
projeções. A regra de compra é
**3 barras roscadas inteiras por válvula** de retenção ou borboleta — o corte acontece na montagem e
não reduz a quantidade comprada. De 10" para cima 3 barras não rendem um tirante
por furo, e a quantidade sobe para cobrir a furação: **4 barras**.

A bitola e o comprimento do tirante vêm da ficha do fabricante
(`data/valvulas_wafer.csv`, fichas T.160 e T.162 da MP Válvulas):

| DN | corpo | furos | bitola | parafuso | prisioneiro |
|---|---|---|---|---|---|
| 3" | 73 mm | 4 | 5/8" | 149 mm | 162 mm |
| 4" | 73 mm | 8 | 5/8" | 149 mm | 162 mm |
| 6" | 98 mm | 8 | 3/4" | 170 mm | 181 mm |
| 8" | 127 mm | 8 | 3/4" | 216 mm | 230 mm |
| 10" | 146 mm | 12 | 7/8" | 241 mm | 260 mm |
| 12" | 181 mm | 12 | 7/8" | 283 mm | 296 mm |
| 14" | 184 mm | 12 | 1" | 292 mm | 311 mm |

**A furação da válvula depende da norma em que ela é pedida.** As colunas da
ficha são da versão ASME 150 porque foi assim que o fabricante publicou; pedida
em NBR PN16, a válvula sai com a furação da NBR e casa com o flange da linha. Por
isso o número de furos vem da tabela de furação, não da ficha — e o alerta de
"8 furos contra 12" virou um lembrete de especificação, não um conflito.

O comprimento do prisioneiro não muda a compra, mas serve de conferência —
quantos tirantes saem das 3 barras de 1 m, contra os furos da válvula em
NBR PN16:

| DN | tirante | por barra | 3 barras dão | furos | |
|---|---|---|---|---|---|
| 3" e 4" | 162 mm | 6 | 18 | 8 | 3 barras |
| 5" e 6" | 181 mm | 5 | 15 | 8 | 3 barras |
| 8" | 230 mm | 4 | 12 | 12 | 3 barras, no limite |
| 10" e 12" | 260 a 296 mm | 3 | 9 | 12 | **4 barras** |
| 14" | 311 mm | 3 | 9 | **16** | **6 barras** |

`barras_da_valvula()` calcula `max(3, teto(furos ÷ tirantes_por_barra))`: mantém
as 3 barras como piso e só sobe quando a furação exige.

A espessura do corpo também entra na geometria da vista lateral — é o face a
face da válvula.

O 14" pesa porque a NBR PN16 dá **16 furos** em DN350 e o tirante de 311 mm só
rende 3 por barra. O motor lembra, em cada válvula, de pedi-la na norma da linha.

### 4.3 Kits: peças que nunca vêm sozinhas

**A flange de PVC não prende no tubo sozinha** — precisa da contra-flange, que é
o adaptador soldável. Uma para cada flange lançada na linha.

Isso aparecia nos projetos antes de eu saber o porquê:

| projeto | `FL PVC` | `ADAPTADOR P/FL … SOLDA` |
|---|---|---|
| Marcelo Amorim | 90 mm × 9 | 90 mm × 9 |
| Marcelo Amorim | 110 mm × 4 | 110 mm × 4 |
| Lincoln Junqueira | 160 mm × 14 | 160 mm × 14 |

Um a um, em dois projetos diferentes. E explica o número ímpar: o par vale por
**ponta de tubo**, não por junta — quando o Plasson encontra um flange de aço ou
de válvula, só o lado do Plasson leva o par.

`data/kits_flange_pvc.csv` amarra os cinco pares que existem no catálogo
(75, 90, 110, 160 e 225 mm) e `regras.contra_flange_de()` puxa a contra-flange
sozinha, marcada como origem `contra-flange` na lista.

Vale o mesmo para conjuntos como `Retrolavagem 90mm`, que aparece na lista de
peças como um item mas é uma montagem.

### 4.4 Corte × barra (`motor/corte.py`)

O desenho lista pedaços; a compra é por barra inteira. No projeto Lincoln
Junqueira o tubo PVC PBA 160 aparece como 1,0 m / 1,5 m / 2,5 m / 5,6 m — mas o
catálogo só tem a **barra de 5,6 m** (`75260-004200`). Sem essa conversão a
lista pede um código que não existe.

Os 10 cortes daquele projeto somam 20,6 m. Com plano de corte
(first-fit decreasing): **4 barras**, 92% de aproveitamento.

```
barra 1: 5,6                    sobra 0,0
barra 2: 2,5 + 2,5 + 0,5        sobra 0,1
barra 3: 2,5 + 1,5 + 1,5        sobra 0,1
barra 4: 1,5 + 1,5 + 1,0        sobra 1,6
```

### 4.5 A bomba decide as reduções (`motor/bomba.py`)

Os bocais estão no próprio código da bomba:

| formato | leitura |
|---|---|
| `000-000` (dois grupos) | saída, rotor padrão |
| `000-000-000` (três grupos) | entrada, saída, rotor padrão |

**A bomba de dois grupos não declara a entrada** — e o catálogo permite deduzi-la.
Medindo as 128 bombas de três grupos (KSB METB, METN e MCPK), o par saída→entrada
é determinístico, sem uma única exceção:

| saída | entrada | degraus | bombas |
|---|---|---|---|
| 32 mm | 50 mm | 2 | 9 |
| 40 mm | 65 mm | 2 | 8 |
| 50 mm | 80 mm | 2 | 15 |
| 65 mm | 100 mm | 2 | 11 |
| 80 mm | 125 mm | 2 | 17 |
| **100 mm** | **125 mm** | **1** | 16 |
| **125 mm** | **150 mm** | **1** | 23 |
| **150 mm** | **200 mm** | **1** | 19 |
| **200 mm** | **250 mm** | **1** | 9 |

Ou seja: **uma bitola acima vale de 100 mm em diante; abaixo disso são duas.** A
quebra é exatamente em 100 mm. Ressalva: as famílias de dois grupos do catálogo
(IMBIL INI e INIB, KSB ETA e BLOC) nunca declaram a entrada, então a tabela
aplicada a elas é inferência a partir das bombas de processo da KSB.

Daí sai a regra: **a sucção termina na entrada e o recalque começa na saída**.
Como a linha quase sempre é maior que os bocais, há uma redução de cada lado — e
é por isso que 161 reduções do catálogo têm uma ponta em norma de equipamento
(ANSI, EN) e a outra em NBR PN16.

**Conferido nos dois projetos que nomeiam a bomba** (``):

| projeto | bomba | entrada | saída | redução no desenho |
|---|---|---|---|---|
| Marcelo Amorim | `METB 050-32-200` | 50 mm (2") | 32 mm (1¼") | `Red Exc AZ 4"x 2"` e `Red Con AZ 3" x 1.1/4"` |
| Lincoln Junqueira | `METB 125-80-315` | 125 mm (5") | 80 mm (3") | `Red Con AZ 8" x 5"` e `Red Con AZ 6" x 3"` |

**As quatro reduções batem com os bocais.** O motor, resolvendo sozinho a
sucção de 8" da `METB 125-080-315`, escolhe
`01523-282050 RED EXC AZ 8" FL NBRPN16X5" FL ANSI150` — a ponta ANSI 150 é
exatamente a que encaixa na KSB importada.

> **Correção.** Este documento tratava `Red Con AZ 3" x 1".1.4"` como erro de
> digitação do desenho. Não é: é **1.1/4"**, o bocal de saída de 32 mm da bomba.
> O interpretador passou a entender `1.1/4"` e `1".1.4"`.

**O tipo da redução depende da montagem, não do modelo** — os dois projetos usam
METB, um deitado e outro em pé:

| lado | bomba deitada | bomba em pé |
|---|---|---|
| sucção (entrada) | **excêntrica** — topo reto, não acumula ar antes do rotor | **concêntrica** — não há bolsa de ar a evitar |
| recalque (saída) | **concêntrica** | **concêntrica** |

Por isso a orientação é atributo da bomba no desenho, escolhido por quem monta,
e não algo que se derive do código do modelo.

O caminho inverso também vale: `orientacao_pelo_desenho()` lê um projeto pronto e
diz como a bomba foi montada. Rodando nos dois projetos, ele acerta os dois —
horizontal no Marcelo Amorim, vertical no Lincoln Junqueira, exatamente o que os
isométricos mostram.

### 4.6 Compatibilizar a bomba com a norma da redução

O motor sabe o **DN** dos bocais pela nomenclatura, mas a redução tem uma ponta
em cada norma: NBR PN16 do lado da linha e a norma do equipamento do outro. Falta
saber em que norma cada bomba vem.

`data/bombas_norma.csv` é a tabela dessa amarração — família da bomba (e, se
precisar, DN) → norma do flange de entrada e de saída. Está criada e vazia de
propósito: em branco, o motor pergunta em vez de escolher errado.

Enquanto ela não é preenchida, `tools/compatibilizar_bomba.py` mostra o cardápio
— quais reduções existem em cada bocal, em cada norma:

```
== METB 125-80-315 - 40cv ==
  entrada  125 mm (5")  ->  EN PN16 (6), ANSI 150 (6), ANSI 300 (4), EN PN40 (2)
  saida     80 mm (3")  ->  ANSI 150 (4), EN PN16 (4), ANSI 300 (3), BSP (2)
```

O relatório também acha os buracos: no bocal de **25 mm (1")** não existe
nenhuma redução fora da NBR PN16 — se aparecer uma bomba com essa saída, não há
peça de transição no catálogo.

Bocais que as bombas do catálogo realmente usam, e o que existe de redução em
cada um:

| bocal | bombas | normas de redução disponíveis |
|---|---|---|
| 25 mm · 1" | 1 | **nenhuma** fora da NBR PN16 |
| 32 mm · 1¼" | 13 | ANSI 150, ANSI 300, BSP |
| 40 mm · 1½" | 12 | ANSI 150, ANSI 300, EN PN16, BSP |
| 50 mm · 2" | 35 | ANSI 150, ANSI 300, EN PN16, BSP |
| 65 mm · 2½" | 31 | ANSI 150, ANSI 300, EN PN16, EN PN10, BSP |
| 80 mm · 3" | 48 | ANSI 150, ANSI 300, EN PN16, BSP |
| 100 mm · 4" | 50 | ANSI 150, ANSI 300, EN PN16, EN PN40, EN PN10 |
| 125 mm · 5" | 104 | EN PN16, ANSI 150, ANSI 300, EN PN40 |
| 150 mm · 6" | 86 | EN PN16, ANSI 150, ANSI 300, EN PN40, NBR PN25 |
| 200 mm · 8" | 53 | ANSI 150, ANSI 300, EN PN10, NBR PN40, NBR PN25 |
| 250 mm · 10" | 15 | ANSI 300, EN PN16, EN PN10, ANSI 150 |
| 300 mm · 12" | 1 | NBR PN25, EN PN16, NBR PN40, EN PN10, ANSI 150 |

### 4.7 Trecho reto: regra de layout, não de peça

O hidrômetro só mede direito com o fluxo desenvolvido: **10 vezes a bitola de
tubo reto antes e 5 depois**. É a primeira regra que não fala de peça, e sim de
espaço — vale no desenho antes de valer na lista.

| bitola | antes (10×) | depois (5×) | total |
|---|---|---|---|
| 3" | 0,80 m | 0,40 m | 1,20 m |
| 4" | 1,00 m | 0,50 m | 1,50 m |
| 6" | 1,50 m | 0,75 m | 2,25 m |
| 8" | 2,00 m | 1,00 m | 3,00 m |
| 10" | 2,50 m | 1,25 m | 3,75 m |
| 12" | 3,00 m | 1,50 m | 4,50 m |

A contagem é só de tubo. Qualquer peça que perturba o fluxo — curva, tê, redução,
válvula, filtro, bomba — zera o trecho, porque é ela que estraga a medição
(`regras.PERTURBAM_FLUXO`). `Linha.trechos_retos()` mede os dois lados e a lista
acusa quando falta.

O mecanismo é genérico: `regras.TRECHO_RETO` é um dicionário família → (antes,
depois) em múltiplos do DN. Outros equipamentos com exigência parecida entram
adicionando uma linha.

**A regra da casa é mais folgada que a do fabricante.** A ficha do ARAD WSTsb
pede `U5/D3` — cinco bitolas antes e três depois. A casa usa 10 e 5, quase o
dobro. Fica como está: a regra mais conservadora é a que vale, e agora se sabe
qual é o mínimo homologado se algum dia faltar espaço.

Duas outras exigências da mesma ficha, ainda **não implementadas** porque
mudam o layout e precisam de confirmação:

- **o medidor vem antes da válvula**, não depois — "in case of an existing
  valve in the pipe line, it is recommended to install the meter before the
  valve". A sequência da casa hoje é filtro → válvula → medidor (seção 7.4);
  o fabricante pede o inverso.
- **o medidor é horizontal, com o mostrador para cima.** Isso é restrição de
  orientação: num trecho vertical o medidor não pode entrar.

## 5. Do desenho à geometria — sem CAD

Vista lateral 2D. Cada peça tem comprimento face a face; curva tem ângulo. A
linha é a soma vetorial ao longo do eixo:

```
posição(n+1) = posição(n) + comprimento(n) · (cos θ, sen θ)
θ += ângulo da curva
```

Isso já dá o esquema em escala com cotas. Traçado em SVG: peça = símbolo +
balão numerado, que é o mesmo número da linha na tabela.

## 6. A camada de nomes (o de-para)

O CAD escreve `Red Exc AZ 4"x 2"`; a proposta precisa de `01523-281940`.
`tools/casar_lista.py` faz a ponte: interpreta o nome do desenho com o mesmo
interpretador do catálogo e procura o item de mesmos parâmetros.

Medido nos três projetos — **110 peças**:

| resultado | peças |
|---|---|
| resolvido direto (um único candidato) | 66 |
| empate a decidir (2+ candidatos igualmente válidos) | 34 |
| sem correspondência | 10 |

Dos 10 sem correspondência, 5 são sub-conjuntos do CAD que não são item de
compra (`Base`, `TopLevelAssembly`, `Casa de Máquinas Padrão`,
`Retrolavagem` ×2), 2 são flange de aço avulso — que o catálogo realmente não
tem — e 1 era o `Red Con AZ 3" x 1".1.4"`, que eu tinha lido como erro de digitação e
é 1.1/4" — o bocal de saída da bomba. As duas flanges de aço deixaram de faltar: o catálogo as chama de `FL 6" (152MM) NBR
PN16` e `FL 10" (261MM) NBR PN16` — entrou no de-para.

**Conclusão que isso força:** casar por nome não é o mecanismo definitivo — 60%
de acerto único não serve para gerar proposta. O nome do desenho é
*subespecificado*: não diz norma de flange nem espessura de parede, então dois
SAPs diferentes servem igualmente. Por isso:

> Cada peça da biblioteca de desenho carrega o **código SAP como atributo**.
> A lista sai exata por construção. O casamento por nome serve para uma coisa
> só: migrar o acervo de desenhos que já existe, uma vez, com conferência.

O que reduz empate sem ambiguidade é vocabulário de marca/linha
(`UNIFLAP`, `PLASSON`, `ARAD`, `DOROT`) — está em `data/depara_nomes.csv`,
tabela editável. Foi ela que levou o acerto de 34 para 66.

## 7. Desenhos padrão (templates)

### 7.1 Sucção

A sucção da casa segue sempre a mesma ordem:

```
crivo → válvula de retenção → tubo de 1 m → curva (se precisar) → redução → bomba
```

A curva é opcional e a redução sai da bomba: concêntrica ou excêntrica conforme a
orientação, sempre no DN do bocal de entrada.

`motor/templates.py::succao()` resolve isso contra o catálogo.
**Reproduz os dois projetos peça por peça** (`tools/demo_template.py`):

| | Marcelo Amorim, 4", bomba deitada | Lincoln Junqueira, 8", bomba em pé |
|---|---|---|
| 1 | `01523-052000` CRIVO AZ 4" | `01523-054000` CRIVO AZ 8" |
| 2 | `01566-000003` VALV RETENÇÃO 4" | `01566-021141` VALV RETENÇÃO 8" UNIFLAP |
| 3 | `01503-320220` TUBO AZ 4"×1M | `01503-540220` TUBO AZ 8"×1M |
| 4 | `01523-132000` CURVA 90 AZ 4" | — sem curva |
| 5 | `01523-281151` RED **EXC** 4"×2" | `01523-261946` RED **CON** 8"×5" |

Mesma ordem, mesmas famílias, mesmos DN — e o tipo da redução saindo certo dos
dois lados pela orientação da bomba.

### 7.8 Manifolds

Os **manifolds já são desenhos padrão** no catálogo: `MNFD AZ D02 … D20`,
14 tipos, 151 itens; só o `D09` tem 43 variações de DN e comprimento. O conceito
já existe na Netafim — o programa formaliza.

### 7.2 Trecho de PEAD, depois da primeira bomba

Depois da primeira bomba a linha vira PEAD, e o trecho é sempre o mesmo
conjunto: **N tubos de PEAD** (o usual é de 4 a 8) e, em cada ponta, um **colar
de flange PEAD** apertado por uma **flange solta de aço**.

Conferido nos três projetos:

| projeto | tubos PEAD | flanges AZ |
|---|---|---|
| Marcelo Amorim | 3" × 4 | — |
| Lincoln Junqueira | 6" × 4 | 6" × **2** |
| Thiago Derks | 10" × 9 | 10" × **2** |

Sempre 2 flanges, qualquer que seja o número de tubos. `templates.trecho_pead()`
resolve os três: em 6" dá `TUBO PEAD 160MM` × 4, `COLAR. P/FL PEAD DN160` × 2 e
`FL 6" (152MM) NBR PN16` × 2.

Em 3" falta a flange — e o catálogo realmente não tem flange solta de 3", o que
explica o projeto do Marcelo Amorim não listar nenhuma.

### 7.3 Talude

A sequência é **trecho de PEAD → articulador na crista → curvas para descer**.
O articulador de 30° fica no alto, onde a linha muda de inclinação, e é nele que
o movimento angular do trecho de PEAD é absorvido.

As curvas, duas maneiras conforme o material:

| material | peças | como |
|---|---|---|
| aço zincado | 2 × curva 45° | uma no pé, outra no topo |
| Plasson | 2 × curva 90° | giradas uma em relação à outra até dar o ângulo |

O segundo caso tem geometria fechada. Duas curvas de 90° com giro relativo φ
entre os planos defletem o eixo em θ:

```
cos(θ) = sen(φ)      →      φ = arcsen(cos θ)
```

| deflexão desejada | 15° | 22,5° | 30° | 45° | 60° | 90° |
|---|---|---|---|---|---|---|
| **girar** | 75° | 67,5° | 60° | 45° | 30° | 0° |

Sem giro dá 90°; com giro de 90° as duas se cancelam e a linha volta ao rumo
original, só deslocada.

A travessia completa em 6", com os 4 tubos de PEAD:

```
 4 x 01521-113111  TUBO PEAD PE100 PN06 160MMX6,2MMX6M
 2 x 01541-000016  COLAR. P/FL PEAD PE100 DN160 NBR PN16
 2 x 01542-083000  FL 6" (152MM) NBR PN16
 1 x 01523-850001  ARTICULADOR 30° 6" 150PSI FL NBR PN16     ← a crista
 2 x 01523-093000  CURVA 45 AZ 6" FL NBR PN16
```

**Em 3" a travessia não fecha:** faltam a flange solta e o articulador, que só
existem de 4" para cima. O motor aponta os dois.

> **Flutuador fica fora.** O manual descreve sucção com flutuante e o catálogo
> tem o flutuador bipartido de 3" a 16", mas a casa **ainda não usa**. A peça
> segue reconhecida no catálogo e fora dos templates
> (`templates.FLUTUADOR_EM_USO`).

### 7.3.1 Medidor e borboleta: lista fechada, não busca por família

Duas peças em que buscar pela família traz a coisa errada.

**PN10 e PN16 não aparafusam entre si de 10" para cima.** A tabela de flanges
do catálogo RAN publica as duas classes lado a lado, com **círculo de
furação** — que nem a ficha MP Válvulas nem o Irrigafour davam. E o círculo é
o que decide se duas flanges casam:

| DN | PN10 | PN16 |
|---|---|---|
| 250 (10") | círculo 350, furo 23 | círculo **355**, furo **28** |
| 300 (12") | círculo 400, furo 23 | círculo **410**, furo **28** |
| 350 (14") | círculo 460, furo 23 | círculo **470**, furo **28** |

De 2" a 6" as duas classes são idênticas. Em 8" mudam só os furos (8 contra
12) com o mesmo círculo. De 10" para cima **mudam o círculo e o furo**: uma
flange PN16 de verdade não entra numa PN10 da mesma bitola.

E a nossa tabela, rotulada `NBR PN16`, tem o círculo do **PN10** em 10", 12"
e 14". Não é erro: é a terceira confirmação de que a NBR 7675 segue as
dimensões PN10 acima de DN200 — e é o que sustenta a regra de parafuso da casa
(3/4" em tudo acima de 5"), porque um furo de 28 mm pediria 1".
`tools/conferir_furacao_ran.py` mostra a comparação linha a linha.

**Válvula hidráulica: a cota sai da série, não do código.** A tabela da seção A
do catálogo Dorot mede o corpo por série e bitola — L de face a face, H de
altura — e as séries 47, 77 e 87 partilham a mesma tabela. Por isso
`normalizar.py` passou a extrair `serie` da descrição (o `47` de
`DOROT VALV MET 47-8" BASICA`): 35 das 69 hidráulicas têm série legível. As
Bermad não têm — a nomenclatura delas põe o modelo depois da bitola
(`BERMAD VALV MET IR 3" 405`), e a série ali é `405`, que essa tabela não cobre.

A tabela também **fecha o caso do 47-14"**. O corpo não está na LM, mas
aparecia em dois acessórios (`71680-008300` e `71680-008995`) — e agora
aparece no catálogo do fabricante, com cota: **L = 580 mm, H = 495 mm**. A
válvula existe na linha; o que falta é o código.

**A furação do medidor tem de ser pedida.** A folha do tangencial WI
(`data/medidores_wi.csv`, ficha em `data/fichas/`) mostra por que a regra "ponta
sem norma adota a do vizinho" não basta:

- **em 8" a mesma peça sai com 8 furos em PN10 e 12 em PN16** — mesmo L, mesmo
  H, mesmo peso. Não é ANSI contra ISO: é PN contra PN, e a diferença está no
  pedido. A linha da casa é PN16, de 12 furos; o PN10 chega com 8 contra 12, e
  8 em 12 só coincidem em 4 posições;
- **de 10" para cima o medidor é EN PN16 e não NBR** — M24 / furo 26 em 355 e
  410, contra M20 / furo 22 em 350 e 400. É a mesma divergência da folha de
  flange Netafim, pelo mesmo motivo. De 2" a 8", que é onde a casa monta, as
  duas normas coincidem e a questão some.

A conexão é flangeada NBR 7675 — está escrito em texto na folha. **Não há
carretel de transição a comprar**: o medidor aparafusa direto na linha, desde
que o PN case. `tools/conferir_flanges.py` mostra as nove bitolas e marca as
duas.

**Medidor** (`data/medidores.csv`). Usar só a linha **ARAD IRT analógica de
pulso**, que já vem com cabo:

| DN | código |
|---|---|
| 3" | `70240-006010` ARAD IRT 3" ISO16 EV 100L |
| 4" | `70240-006125` |
| 6" | `70240-006157` |
| 8" | `70240-006277` |
| 10" | `70240-006390` |

**Não usar** os ARAD IRT **ER**: são digitais e dependem do cabo
`70220-030000`. São 5, um por bitola, e a descrição é quase idêntica à da versão
analógica — daí a lista ser por código e não por padrão de texto.

O 3" analógico está cadastrado como `ARAD IRT 3" ISO16 EV 100L`, **sem a palavra
MEDIDOR**. Buscar por família nunca o acharia.

Ainda **a conferir**, porque existem e ninguém decidiu:

| linha | bitolas |
|---|---|
| ARAD IRT (variantes 100L e 10M3) | 3", 8", 10" |
| **DOROT MEDIDOR IRT ISO16 PUL** | 2", 3", 4", 6", 8", 10" |
| ARAD WSTSB | 12" |

A linha DOROT é uma família completa e paralela à ARAD. E **acima de 10" não há
IRT**: em 12" só existe a WSTSB, e em 14" não há medidor nenhum.

**Borboleta.** Procurando por "gear" apareceram **35 borboletas que estavam
invisíveis**: cadastradas como `VALV.BORB.` — com o ponto da abreviação — e com
`CX.` no fim, que é a **caixa redutora**. De 12 itens a busca passou para **47**.

| linha | acionamento | bitolas |
|---|---|---|
| BRAY S30-169 150LB | caixa | 2" a 20" |
| BRAY S30H-375 250LB | caixa | 2" a 20" |
| BRAY S33-169 150LB | caixa | 24" |
| FN/CF8 150 EPDM | caixa | 3" a 20" |
| FN/CF8 PN16 (250) | caixa | 4" a 14" |
| GAER com volante | volante | 3" a 16" |
| **GAER com alavanca** | **alavanca** | **só 4"** |
| PVC ABNT16 | — | 3" a 6" |

A preferência de acionamento virou lista ordenada em
`Catalogo.ACIONAMENTO_PREFERIDO`: **alavanca → caixa redutora → volante**, com
quem não declara ficando no meio. Hoje isso escolhe alavanca em 4" e caixa
redutora no resto.

> **Falta decidir qual linha é a da casa.** Cinco linhas com caixa redutora
> cobrem 3" a 14" inteiro, mas são de três fabricantes diferentes. E a alavanca
> da GAER continua existindo só em 4" — os projetos pedem 3" e 8" com alavanca,
> e nenhum dos dois está cadastrado.

### 7.4 Ventosa: colar de tomada ou saída na peça

A ventosa entra de duas maneiras, conforme o material do trecho:

| material | como | peça |
|---|---|---|
| Plasson, PVC, PEAD | **colar de tomada** com saída de 2" | `COLAR TOMADA POLIPROPILENO 160X2" PN 10` |
| aço zincado | a **saída já vem na peça** | manifold com luva de 2", flange cega com LG 2", ou curva de 90 com escape de 2" |

A diferença importa para a lista: no plástico a ventosa **acrescenta** um item (o
colar); no aço ela **troca** a peça por uma versão com saída — a curva de 90
simples vira `CURVA 90 AZ 8" FL NBR PN16 C/ESC.2"`, mesmo código de família,
outro SAP.

Colar de tomada resolvido em todos os diâmetros de Plasson:

| tubo | colar |
|---|---|
| 90 mm | `78400-005580` |
| 110 mm | `78400-020000` |
| 160 mm | `78400-020050` |
| 225 mm | `78400-020100` |

E em aço, as peças que já trazem a saída de 2":

| DN | opções |
|---|---|
| 3" | flange cega c/ LG 2", curva 90 c/ escape |
| 4" | manifold D06, curva 90 c/ escape |
| 6" | só a curva 90 c/ escape |
| 8" | manifold D06, curva 90 c/ escape |
| 10" | flange cega c/ LG 2", curva 90 c/ escape |
| 12" | manifold D06, flange cega, curva 90 c/ escape |
| 14" | só o manifold D06 |

**Uma observação dos projetos:** Marcelo Amorim e Lincoln Junqueira têm ambos
**3 colares de tomada para 2 ventosas**. O terceiro colar é de outra coisa —
manômetro, provavelmente. Fica registrado como pergunta.

### 7.5 Válvula hidráulica: fica na saída do filtro

Ordem confirmada nos **três projetos**:

```
filtro → válvula hidráulica → medidor
```

| projeto | filtro | válvula | medidor |
|---|---|---|---|
| Marcelo Amorim | item 27 | item 29 (Dorot 47-3") | item 30 |
| Lincoln Junqueira | item 15 | item 16 (Dorot 47-6") | item 17 |
| Thiago Derks | item 19 | item 22 (Dorot 47-10") | item 23 |

`hidraulica.conferir_sequencia()` acusa filtro sem válvula na saída, e medidor
que venha antes dela.

**Achei todas?** Não, na primeira passada. Auditando o catálogo, o classificador
pegava **14** e errava dos dois lados:

- **falsos positivos** — `DOROT MOLA P/ VALV 47-8"`, `ASSENTO P/ MOLA`,
  `TAÇA DA JUNTA`, `BOIA` entravam como válvula, e são peça de reposição;
- **falsos negativos** — a linha **Bermad inteira** ficava de fora
  (`BERMAD VALV MET IR 6" 405 FL NBR PN10/16`, série 735, 350P), e as séries
  Dorot que não são a 47 (44, 57, 67, 75, 77, 96, Galil 09).

Corrigido, são **69 corpos de válvula de controle**, com reposição e piloto
separados em famílias próprias:

| família | itens |
|---|---|
| `VALVULA_HIDRAULICA` | 69 |
| `PECA_REPOSICAO` | 71 |
| `PILOTO` | 33 |
| `VENTOSA` | 18 |
| `VALVULA_ALIVIO` | 7 |

Por marca e série: Dorot 96 (10), 75 (9), 47 (7), 77, 67, 57, 44, Galil 09;
Bermad 405 (7), 735, 350P. A ordem das regras passou a importar — ventosa e
alívio ganham da hidráulica, senão `BERMAD VALV AR ANTIVACUO` seria lida como
válvula de controle.

Os projetos usam só a **série 47**. A faixa cadastrada não é contínua:

```
corpos cadastrados: 3"  4"  --  6"  8"  10"  12"
                            5"                    14"
```

- **5"** não tem corpo — coerente com 5" não ser bitola de linha.
- **14" não tem corpo, mas existe.** Dois acessórios provam:
  `DOROT MOLA P/ VALV 47-8" A 14"` (`71680-008300`) e
  `DOROT ASSENTO P/ MOLA VALV 47-8" A 14"` (`71680-008995`). A válvula está na
  linha do fabricante; **o código do corpo é que não está na LM**.
- **12" tem dois códigos**: `71600-005120` e `01542-000285`
  (`BR DOROT VALV MET 47-12" BASICA - ABNT`). Conferir se um substituiu o outro.

`tools/conferir_serie_valvula.py` faz essa varredura para qualquer série: cruza
o DN dos corpos com o DN que só aparece em acessório, e aponta códigos
duplicados. Na série 75 ele acha o mesmo padrão — 2" e 3" com dois códigos cada.

**A válvula nunca vem sozinha:** leva o esquema de piloto
(`data/fichas/DOROT_esquema_valvula_redutora_sustentadora_31-310.pdf`), e o
conjunto lista junto. `data/pilotos.csv` amarra:

| item | código |
|---|---|
| piloto | `71680-001200` DOROT PILOTO METÁLICO 3W 31-310/47 VD |
| kit | `71680-001590` DOROT KIT PARA PILOTO 31-310 |
| mola | `71680-010500` (VM), `71680-010550` (VD), `71680-010600` (AM) |

A mola escolhe a faixa de pressão e o próprio esquema manda ver o catálogo
Dorot — fica em aberto até a faixa ser definida.

**O rodapé do esquema diz o mesmo que este programa:** ele lista os itens do
piloto mas avisa que *"não estão listados nenhum material de ligação como: solda
plástica, solução limpadora, parafuso, porca, arruela"*. É exatamente o buraco
que a ferragem derivada fecha.

E avisa também que *"códigos e produtos poderão ser substituídos ou
desativados"* — por isso `tools/conferir_codigos.py` varre todas as tabelas e o
próprio documento, e confere cada SAP citado contra a lista atual. Hoje:
**32 códigos citados, 32 conferem.**

### 7.6 Tubo de aço: comprimento por bitola

Os comprimentos usuais da casa — 0,50 / 1,00 / 1,50 / 2,00 / 3,00 e 6,00 m — em
cada bitola. O catálogo escreve tanto `1M` quanto `1000MM`, e o interpretador
normaliza os dois (`tools/matriz_tubos.py`):

```
         0.50m   1.00m   1.50m   2.00m   3.00m   6.00m
   3"      # 2     # 1     # 1       -     # 1     # 1
   4"      # 2     # 1     # 1     # 1     # 1     # 1
   5"        -       -       -       -       -       -
   6"      # 1     # 1     # 1     # 1     # 1     # 1
   8"      # 2     # 1     # 2     # 2     # 1     # 1
  10"      # 3     # 2     # 3     # 2     # 2     # 2
  12"      # 1     # 2     # 1     # 2     # 2     # 2
  14"      # 4     # 3     # 2     # 1     # 1     # 2
```

De 3" a 14" está tudo coberto, com **um único buraco: 3" de 2,00 m**. E 5" de
novo vazio, o que já era esperado.

> **Uma correção importante.** Na primeira passada esta matriz acusava três
> casos que só existiriam com ponta de engate K — 6" de 1 m, 8" de 1 m e 12" de
> 1,5 m. Era bug do interpretador: esses tubos existem flangeados, escritos como
> `FL NBR7675 PN16` em vez de `FL NBR PN16`. **NBR 7675 é a norma do flange** —
> mesma coisa, outra grafia. O template de sucção vinha escolhendo um tubo com
> ponta K10 em 8" quando havia um limpo (`01503-340220`), e era daí que saía o
> aviso de engate K que aparecia desde o começo.

Duas outras grafias entraram junto: `FL ABNT PN16` e ponta que **não declara
norma**. Válvula, medidor e junta não trazem norma na descrição porque ela é
definida no pedido — então uma ponta sem norma encaixa na do vizinho, em vez de
o motor pedir adaptador. O mesmo vale para o material: o corpo da válvula não
declara material, e adota o do vizinho para escolher o parafuso.

Com isso a lista do recalque de 8" fecha em **cinco junções diretas**, sem
nenhum adaptador espúrio.

### 7.7 Cobertura de 3" a 14"

Antes de montar qualquer linha, `tools/matriz_bitolas.py` responde onde o
catálogo tem buraco. `#` serve na linha (é NBR PN16, ou a peça não declara norma
— válvula, junta e medidor têm a norma definida no pedido); `o` só existe em
outra norma; `-` não existe.

```
                         3"   4"   5"   6"   8"  10"  12"  14"
crivo                     #    #    -    #    #    #    #    #
valvula de retencao       #    #    -    #    #    #    #    #
valvula borboleta         #    #    -    #    #    #    #    #
valvula gaveta            #    #    -    #    #    #    #    -
tubo 1 / 3 / 6 m          #    #    -    #    #    #    #    #
curva 90 / 45             #    #    o    #    #    #    #    #
te                        #    #    -    #    #    #    #    #
flange / flange cega      #    #    o    #    #    #    #    #
junta plana               #    #    #    #    #    #    #    #
manifold                  #    #    -    #    #    #    #    #
medidor                   #    #    -    #    #    #    #    -
articulador               -    #    -    #    #    #    #    #
```

**5" não é bitola de linha, é bocal de bomba.** Não existe crivo, válvula, tubo,
tê nem manifold em 5" — só curva, flange e junta. E 125 mm aparece 104 vezes
como bocal de bomba. O programa deve tratar 5" como diâmetro de transição, nunca
como diâmetro de trecho.

Fora isso, os buracos são pontuais: **válvula gaveta** vai até 12" (a borboleta
chega a 16"), **articulador** não existe em 3", **medidor** não existe em 14".

> **Correção.** Esta matriz já disse que a gaveta ia só até 4". Era erro do
> interpretador: a gaveta flangeada da linha está cadastrada como
> `GAER REG. GAVETA … ISO16 C/ VOLANTE`, com **REG. abreviado**, e o padrão
> exigia "REGISTRO" por extenso. Mesma coisa em `VALV. GAVETA`, onde o ponto da
> abreviação derrubava o casamento. Corrigido, são 13 itens de 1" a 12".

**Reduções de degrau** — de uma bitola para a anterior, que é o caso da linha:

```
                         4"   5"   6"   8"  10"  12"  14"
concentrica               #    #    #    #    #    #    #
excentrica                #    -    #    #    #    #    #
```

Uma única falha: **não existe redução excêntrica de 5" para 4"**. Como a
excêntrica é a da sucção com bomba deitada, uma bomba de entrada 4" numa linha
de 5" não fecha — mas 5" também não é bitola de linha, então o caso é teórico.

**O template monta em todas as bitolas.** Testado com uma bomba real do catálogo
cujo bocal de entrada é a bitola anterior, nas duas orientações:

| linha → entrada | bomba | horizontal | vertical |
|---|---|---|---|
| 4" → 3" | `KSB METN 080-050-160` | ok, 5 peças | ok, 4 peças |
| 6" → 5" | `KSB METB 125-080-315` | ok, 5 peças | ok, 4 peças |
| 8" → 6" | `KSB METB 150-125-200` | ok, 5 peças | ok, 4 peças |
| 10" → 8" | `KSB METN 200-150-315` | ok, 5 peças | ok, 4 peças |
| 12" → 10" | `KSB METN 250-200-400` | ok, 5 peças | ok, 4 peças |

Em 14" o catálogo não tem bomba com entrada de 12", então o caso não se testa
por aí — as peças de 14" existem, o que falta é a bomba.

## 7.9 O caderno de desenhos e o manual

Duas fontes oficiais entraram na base
(`data/fichas/NETAFIM_desenhos_tubos_conexoes_aco_PN16_rev20.pdf` e
`NETAFIM_manual_projeto_2025_rev1.pdf`). O caderno de desenhos é a peça que
faltava para a vista lateral: cada página traz a tabela paramétrica de uma peça,
com **cota face a face, espessura, tipo das duas pontas e o código** — que a
descrição do item não tem.

`tools/extrair_desenhos.py` converte as 42 páginas em
`data/desenhos_netafim.csv`: **360 posições**.

### O que o manual confirmou

| assunto | manual |
|---|---|
| flange | *"seguem a norma NBR 7675"* — confirma a tabela de furação |
| espessura por DN | 2,00 mm até 8"; 2,65 mm em 10" e 12"; 3,00 e 4,75 mm de 14" para cima |
| velocidade na sucção | **menor que 1,5 m/s**, com NPSH disponível conferido contra o requerido |
| kit da flange PVC | `ADFL = ADAPTADOR P/FL + FL PVC ISO 2536 PN16 + JUNTA PLANA + PARAFUSO + ARRUELA + PORCA` |

O último confirma a contra-flange e **estende o kit**: além do adaptador, entram
junta plana e ferragem. O motor hoje puxa só a contra-flange.

### As duas fontes não concordam

| | |
|---|---|
| códigos citados no caderno | 173 |
| desses, na LM Canal | 141 |
| **fora da LM Canal** | **32** |
| posições marcadas `CADASTRAR` pela própria Netafim | **101** |
| dessas, dentro de 3" a 14" | **55** |

`tools/conferir_desenhos.py` roda os dois sentidos. É a mesma checagem que achou
o 47-14" faltando, agora em escala — e a marcação `CADASTRAR` é da própria
Netafim, não minha inferência.

### As que faltam cadastrar são necessárias?

Quase nenhuma. Das **55** posições `CADASTRAR` entre 3" e 14":

| | |
|---|---|
| **4** são padrão da casa — `FL NBR7675 PN16` nas duas pontas | **faltam mesmo** |
| 31 têm uma ponta em rosca BSP | derivação, não peça de linha |
| 7 são `EN 1092` e 7 são BSP puro | norma de equipamento importado |
| 3 têm ponta lisa e 3 são K10 | não é o padrão da casa de máquinas |

Ou seja: **51 das 55 são variantes** que a casa não usa ou só usa na transição
com equipamento. O trabalho de cadastro real é bem menor do que o número sugere.

### O problema não são as 4 — é a página inteira

As 4 estão todas na **página 32**, e ali o buraco é outro: **nenhum dos 9
códigos que a página cita existe na LM**. A peça é o manifold com derivação
flangeada, corpo de 1000 mm com a saída a 500 mm.

Na faixa `01528-08xxxx` a LM tem só dois itens, e os dois são **inox**, não aço
zincado. E o projeto **Thiago Derks usa a peça**: `Te AZ 10" -1000mm`, quantidade 2.

> Peça desenhada, usada em projeto real, sem código de aço zincado na lista.
> Não é variante exótica — é peça de linha.

Outras duas páginas estão na mesma situação: a **18** (curva 45 com uma ponta
K10, 3 códigos) e a **30** (manifold curto com derivação BSP, 3 códigos e mais
10 `CADASTRAR`).

Ainda faltam 77 posições cujo código o PDF corta na extração; as páginas estão
listadas no relatório para conferência à mão.

## 8. Decisões em aberto

1. **A página 32 do caderno não tem nenhum código na LM** — manifold com
   derivação flangeada, 1000 × 500 mm. O projeto Thiago Derks usa
   (`Te AZ 10" -1000mm` ×2). Como isso é comprado hoje?
2. **Engate K10: o manual diz que é usado** nas adutoras, e vocês disseram que
   não usam. A diferença é o trecho — K10 na adutora, flange na casa de
   máquinas? O motor hoje recusa K em qualquer lugar.
3. **O kit da flange PVC leva junta e ferragem**, segundo o manual. Hoje o motor
   puxa só a contra-flange.
4. **Norma do flange de cada família de bomba** (`data/bombas_norma.csv`).
5. **Por que 3 colares de tomada para 2 ventosas?**

## 9. Estado do código

```
tools/importar_catalogo.py    xlsx  -> data/catalogo_bruto.json   (5.157 itens)
tools/normalizar.py           texto -> data/catalogo.json          (peças paramétricas)
tools/extrair_lista_pdf.py    PDF do CAD -> lista de peças em CSV
tools/casar_lista.py          nome de desenho -> código SAP
tools/gerar_furacao.py        tabelas EN 1092-1 e ASME B16.5 -> regras_furacao.csv
tools/relatorio_furacao.py    regra da casa x norma, e onde a norma muda na linha
data/fichas/                  fichas técnicas do fabricante (fonte das tabelas)
tools/conferir_bomba.py       reduções do desenho x bocais da bomba
tools/compatibilizar_bomba.py norma da redução em cada bocal da bomba
tools/demo_succao.py          demonstração ponta a ponta (sucção, bomba, recalque)
tools/demo_template.py        template de sucção conferido contra os dois projetos
tools/matriz_bitolas.py       cobertura de peças e reduções de 3" a 14"
tools/matriz_tubos.py         comprimento de tubo AZ por bitola
tools/conferir_serie_valvula.py  faixa de cada série de válvula
tools/extrair_desenhos.py     caderno de desenhos -> tabela de cotas e códigos
tools/conferir_desenhos.py    caderno de desenhos x LM Canal
motor/templates.py            receitas padrão resolvidas contra o catálogo
motor/talude.py               travessia do talude e o giro das curvas de 90
motor/ventosa.py              colar de tomada ou peça de aço com saída de 2"
motor/hidraulica.py           sequência filtro/válvula/medidor e kit de piloto
tools/conferir_codigos.py     confere cada SAP citado contra a lista atual
motor/bomba.py                nomenclatura da bomba -> entrada, saída e rotor
motor/catalogo.py             índice por (família, DN, norma)
motor/regras.py               compatibilidade + ferragem
motor/ferragem.py             ferragem -> código SAP
motor/corte.py                cortes -> barras de estoque
motor/traducao.py             vocabulário do desenho -> vocabulário do catálogo
motor/linha.py                documento, comandos, junções, geometria, lista
```

Cobertura do interpretador no escopo de sucção/recalque (aço ≥ 3" e
Plasson ≥ 75 mm): **732 de 732 itens** com família identificada.
