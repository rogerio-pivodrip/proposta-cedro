# Desenho do motor: peça, bitola e conexão

Documento de projeto. Não descreve o que está implementado — descreve para onde
o modelo precisa ir, e por quê.

## O diagnóstico

Medindo os 847 itens do escopo contra o modelo atual:

| sintoma | itens | o que isso quebra |
|---|---|---|
| dois DN diferentes na mesma peça, guardados como `dn=[12, 8]` | **340** | a lista não diz qual ponta é a de entrada |
| peça com uma única conexão lida na descrição | ~400 | tubo, curva e manifold ficam com uma boca só |
| tê lido com 3 bocas | **2** de 19 | o resto do modelo acha que tê tem 2 |
| manifold com derivação lida | 55, no máximo 1 cada | `2LG2"` vira uma luva, não duas |

O padrão é sempre o mesmo: **o modelo está tentando extrair a topologia da
descrição**. E a descrição não tem topologia — ela tem parâmetros.

`TE AZ 8" FL NBR PN16` não diz que o tê tem três bocas. Diz que as bocas de um
tê são de 8" flangeadas NBR PN16. A forma vem de ser um tê.

## 1. A forma vem da família, o parâmetro vem da descrição

Cada família tem um **gabarito**: quantas portas, com que papel, e como se
posicionam. A descrição só preenche.

```python
GABARITO = {
    "TUBO":     [("entrada", EIXO), ("saida", EIXO)],
    "CURVA":    [("entrada", EIXO), ("saida", GIRA)],       # o ângulo separa
    "TE":       [("entrada", EIXO), ("saida", EIXO), ("derivacao", ORTOGONAL)],
    "REDUCAO":  [("maior", EIXO), ("menor", EIXO)],
    "MANIFOLD": [("entrada", EIXO), ("saida", EIXO), *derivacoes],
    "CRIVO":    [("saida", EIXO)],                          # terminal: começa a linha
    "FLANGE_CEGA": [("entrada", EIXO), *derivacoes],        # terminal: fecha a linha
}
```

Isso resolve os quatro sintomas de uma vez. O tê passa a ter três bocas mesmo
quando a descrição menciona um DN só; a redução passa a ter `maior` e `menor`
nomeados em vez de uma lista ordenada por acaso; o crivo passa a ser terminal, e
o motor sabe que nada vem antes dele.

**Consequência prática:** o interpretador de descrição deixa de decidir a forma
e passa a fazer só o que sabe fazer — ler DN, norma, ângulo, comprimento — e a
preencher um gabarito que já existe.

## 2. Bitola é identidade, não número

Três bugs desta semana vieram de tratar bitola como número:

- `3/4"` lido como **4"**, porque o denominador da fração casou com o padrão de
  polegada;
- `90` de PVC comparado com `90` de curva — milímetro contra grau;
- `225 mm` e `8"` tratados como coisas diferentes, quando são **a mesma flange
  de 12 furos**.

Bitola precisa ser um objeto com **DN nominal em milímetro como identidade**, e
as representações como apresentação:

```python
class Bitola:
    dn_nominal_mm        # 200 - a identidade
    def em_polegada()    # 8"    - como o aço se chama
    def em_mm_externo()  # 225   - como o PVC se chama
    def __eq__(outro)    # compara dn_nominal, nunca o número exibido
```

A conversão é **tabelada e depende do material**, não é aritmética. E as séries
não são a mesma coisa:

| série | valores | onde vale |
|---|---|---|
| linha em aço | 3" 4" 6" 8" 10" 12" 14" | trecho de tubulação |
| bocal de bomba | inclui **5"** | entrada e saída da bomba |
| PVC/Plasson | 75 90 110 160 225 mm | trecho de PVC |
| PEAD | 90 160 225 280 mm | depois da bomba |

**5" é o caso que prova a regra:** existe como bocal, não existe como linha. Não
há crivo, válvula, tubo, tê nem manifold em 5". Uma `Bitola` sem série não tem
como saber disso; com série, o motor recusa 5" como diâmetro de trecho e aceita
como diâmetro de transição.

## 3. Conectar é negociar, e há quatro saídas — não duas

O modelo atual pergunta "encaixa?" e responde sim ou não, inserindo adaptador
quando não. Faltava uma saída:

| resultado | quando | exemplo |
|---|---|---|
| **encaixa** | DN, tipo e norma batem — ou uma ponta não declara norma | curva NBR PN16 → tubo NBR PN16 |
| **insere transição** | DN diferente, ou norma diferente | 8" → 5" na entrada da bomba: redução |
| **troca a peça** | a peça certa existe, com outra ponta | curva 90 simples → `CURVA 90 AZ 8" C/ESC.2"` para a ventosa |
| **recusa** | não há caminho | engate K na casa de máquinas |

A terceira apareceu duas vezes e não cabia em "inserir adaptador":

- **ventosa em aço** não acrescenta peça, **substitui**: a curva simples vira
  curva com escape de 2", mesma família, outro código;
- **tubo com ponta K** onde existe o mesmo tubo flangeado — trocar é o certo,
  adaptar seria errado.

Cada resultado carrega o **motivo**, que é o que alimenta o aviso na lista. Isso
já está certo no modelo atual e deve continuar: o motor nunca conserta calado.

## 3.1 A solução de conectar

Conectar não é comparar duas portas. É uma operação com **contexto**, que produz
uma junção e **três validações no mesmo ato**.

```python
def conectar(porta_a, porta_b, contexto) -> Juncao
```

O `contexto` importa porque **o mesmo par de portas resolve diferente conforme
onde está**. Já provado: uma redução de 8" para 5" é excêntrica se a bomba está
deitada e concêntrica se está em pé. Sem contexto, o conector teria de escolher
uma e errar metade das vezes.

```python
Contexto:
    norma_da_linha       # NBR PN16 — o padrão da casa
    material_vizinho     # para o parafuso: AZ×AZ, aço×Plasson, contra a bomba
    orientacao_bomba     # decide excêntrica ou concêntrica na sucção
    trecho               # casa de máquinas ou adutora — decide se K entra
    posicao              # antes ou depois da bomba, entrada ou saída
```

### A junção que sai

```python
Juncao:
    resultado     # ENCAIXA | TRANSICAO | TROCA | RECUSA
    pecas         # o que entra no meio, se entrar
    substituicao  # a peça trocada, se for troca
    derivados     # ferragem, contra-flange, tirante
    avisos        # cada um com severidade e motivo
```

### As três validações, nesta ordem

Elas dependem umas das outras — não dá para inverter.

**1. Conexão.** Tipo e norma das duas portas.

| situação | resultado |
|---|---|
| tipo e norma iguais | encaixa |
| uma ponta não declara norma | encaixa, na norma do vizinho — válvula, medidor e junta têm a norma definida no pedido |
| normas diferentes | transição: adaptador |
| tipos diferentes (flange × engate K) | transição, ou recusa se o trecho for casa de máquinas |
| existe a mesma peça com a ponta certa | **troca**, não adapta |

**2. Medida.** Três coisas diferentes, e só a primeira é o DN.

| o que se valida | como |
|---|---|
| **DN** | pela identidade da bitola, não pelo número exibido: 225 mm e 8" são o mesmo DN200 |
| **comprimento** | soma face a face das peças contra o vão disponível; o caderno de desenhos dá o face a face que a descrição não tem |
| **trecho reto** | o hidrômetro exige 10 bitolas antes e 5 depois, e a contagem zera em qualquer peça que perturbe o fluxo |

O segundo é o que transforma a lista em desenho: sem face a face não há vista
lateral em escala, só sequência.

**3. Acessórios.** Só faz sentido depois que a junção está resolvida — o
parafuso depende de qual junta ficou, e a junta depende da negociação.

| a junção virou | puxa |
|---|---|
| flangeada | junta plana + n parafusos + n porcas + 2n arruelas, com bitola e comprimento pelo contexto |
| flange de PVC de um lado | contra-flange, e o kit do manual leva junta e ferragem |
| válvula wafer no meio | 3 barras roscadas, ou mais se a furação exigir |
| solda, rosca ou engate | nada |

### Severidade, não sim ou não

A validação **não bloqueia a lista**. O projetista precisa do rascunho mesmo com
pendência, e é isso que hoje já funciona: o motor emite a lista e anota o que
está aberto.

| severidade | significa | exemplo |
|---|---|---|
| **erro** | a lista sai errada se ninguém olhar | não existe redução excêntrica de 5" para 4" |
| **aviso** | resolve sozinho, mas alguém precisa saber | tirante contado como barra inteira |
| **nota** | escolha registrada, sem pendência | redução excêntrica porque a bomba está deitada |

Cada aviso carrega o **motivo**, nunca só o código. `"juncao 1: engate K não é
usado nas montagens"` diz o que fazer; `"incompatível"` não diz nada.

### Por que a validação mora na junção, e não na peça

Uma peça sozinha nunca está errada. A `CURVA 90 AZ 8" FL NBR PN16 X K10` é uma
peça legítima — ela só fica errada quando encontra uma flange NBR PN16 numa casa
de máquinas. O erro nasce do encontro, então é no encontro que ele é detectado.

Isso também é o que permite o **recálculo incremental**: mexeu numa peça,
revalida só as duas junções vizinhas, não a linha inteira.

## 4. Desenhar: dez símbolos, não 836

A pergunta é se cada peça vira um desenho ou se um desenho serve para várias.
A medição responde: **nem 836 desenhos, nem um símbolo genérico. Cerca de dez
símbolos paramétricos, um por família.**

O escopo de 3" a 14" tem **836 itens em 19 famílias** — 44 itens por família,
em média. E dentro de cada família a variação é **paramétrica, não formal**:

| família | itens no escopo | formas distintas |
|---|---|---|
| TUBO | 201 | **1** — muda o DN e o comprimento |
| REDUCAO_CONCENTRICA | 103 | **1** — muda só o par de DN |
| REDUCAO_EXCENTRICA | 67 | **1** |
| CURVA | 60 | **3** — 90°, 45°, 30° |
| ADAPTADOR | 51 | **1** — muda o DN e a ponta |
| TE | 15 | **1** |

103 reduções não são 103 desenhos. São um cone, desenhado 103 vezes com
parâmetros diferentes. Somando as famílias geométricas, dez símbolos cobrem
tudo que o motor precisa traçar; as demais famílias — filtro, válvula, medidor
— são caixas, e a caixa sai da ficha do fabricante.

### A prova: a cota não é do código, é da família

O caderno de desenhos da Netafim (páginas 36–39) mostra a redução medida por
uma cota só, e essa cota **depende apenas do DN maior** — não do DN menor, não
da norma da outra ponta:

| DN maior | 3" | 4" | 5" | 6" | 8" | 10" | 12" | 14" |
|---|---|---|---|---|---|---|---|---|
| face a face | 250 | 250 | 250 | 300 | 300 | 350 | 450 | 600 |

Quatro amostras por bitola, uma por norma de flange. **Zero divergências.**

Generalizando para as demais famílias, com a variante certa como segunda
chave — o ângulo na curva, o modelo de derivação no manifold —, a tabela fecha:

> **150 combinações de (família, variante, DN). 0 divergências.**

Isso está em `data/cotas_por_familia.csv`, gerado por `tools/extrair_cotas.py`.
A segunda chave era o que faltava: sem ela, curva e manifold divergiam em toda
bitola, porque a página 15 (45°) e a página 22 (90°) medem coisas diferentes —
a curva de 45° de 8" mede 337 mm, a de 90° mede 297 mm — e um manifold D06 de
8" tem 500 mm contra 3250 mm de um D12.

### De onde sai a cota de cada peça, na ordem

| fonte | itens no escopo |
|---|---|
| tabela `(família, variante, DN)` | **359** |
| comprimento na própria descrição (tubo de 1 m, 6 m) | **200** |
| ficha do fabricante (`valvulas_wafer.csv`, `valvulas_gaveta.csv`) | wafer e gaveta |
| **sem cota** | **277** |

Os 277 sem cota não são um buraco aleatório: são filtro (53), válvula
borboleta (38), válvula hidráulica (31), medidor (15) — exatamente as famílias
de **lista fechada** da seção 5. A cota delas vem da ficha do fornecedor, não
do caderno, e é assim que deve ser. O que sobra de verdade é pequeno:
manifold (44, variantes de derivação ainda não mapeadas), flange cega (23) e
curva (11 — as sete de 30°, que o caderno não desenha, mais quatro sem ângulo
na descrição).

### A quarta chave: o fabricante

O catálogo Irrigafour (43 páginas de tabela de cota, em `data/fichas/`) responde
uma pergunta que o caderno Netafim sozinho não respondia: **a cota é da família
ou do fabricante?**

É das duas. A estrutura se confirma — a cota continua saindo de uma tabela por
bitola, e não de código —, mas o valor muda de fábrica para fábrica:

| peça | Netafim | Irrigafour |
|---|---|---|
| redução concêntrica 3"–8" | 250 a 300 mm | **150 mm em todas** |
| curva 90° 8" | 297 mm | **335 mm** |
| curva 90° 14" | 370 mm | **408 mm** |
| crivo 8" | 250 mm | **300 mm** |

O crivo explica o resto: o da Netafim é **cônico** e cresce com a bitola; o da
Irrigafour é um **cesto cilíndrico** de 300 mm fixo de 2" a 20". Não é
divergência de medida — são duas peças diferentes com o mesmo nome. O símbolo
do crivo precisa de variante `cone | cesto`.

Então a chave da cota é `(fabricante, família, variante, DN)`. Sem o fabricante,
uma linha desenhada com peça Netafim e orçada com peça Irrigafour fecha 
com quase 100 mm de erro por redução.

**O que o gomo não é.** O catálogo separa curva de 2, 3 e 4 gomos — e as três
dão **a mesma cota C em todas as 17 bitolas**. Gomo é processo de fabricação,
não geometria: entra na descrição e no preço, nunca no desenho.

### O que o Irrigafour homologou

A furação que geramos da NBR 7675 nunca tinha sido conferida contra uma segunda
fonte. Agora foi, contra o DIN 2533 PN16 do Irrigafour:

> **10 bitolas de 2" a 14", 10 confirmadas, 0 divergentes.**

E apareceu uma armadilha que nenhuma das duas tabelas anteriores mostrava: **em
3" e em 8" a furação muda com a classe de pressão** — 3" PN10 tem 4 furos e
PN16 tem 8; 8" PN10 tem 8 furos e PN16 tem 12. Nas outras bitolas da casa, PN10
e PN16 furam igual. Como o parafuso e a porca saem da furação, especificar PN10
onde a casa usa PN16 erra a ferragem de 8" em um terço.

### A quarta fonte: a própria folha de flange da Netafim

O caderno Netafim tem duas folhas de flange que ninguém tinha lido —
a página 6 (*Flange para soldar, EN 1092-1 PN16*) e a página 4 (*Flange cega
com luva fêmea 2" BSP*). Extraídas para `data/flanges_netafim.csv`, elas
respondem à pergunta que estava em aberto desde o Irrigafour:

> **Até 8" as duas tabelas dizem a mesma coisa. De 10" para cima o caderno
> desenha 355 / 410 / 470 / 525 / 585 / 650 / 770 de círculo — que é EN PN16,
> não os 350 / 400 / 460 / 515 / 565 / 620 / 725 da NBR 7675 PN16.**

`tools/conferir_flanges_netafim.py`: 11 linhas batem, 14 não, e **todas as 14
casam exatamente com a EN**. É a terceira fonte independente a dizer o mesmo —
Irrigafour (DIN 2533), MP/RAN, e agora o desenho de fabricação da própria
Netafim. Quem compra flange pela NBR e monta contra peça Netafim de 10" ou
mais **não fecha o parafuso**: o círculo erra 5 mm e o furo erra 6.

As folhas trouxeram também duas cotas que a tabela de furação não tinha e o
desenho usa: o **ressalto** (onde a junta assenta) e a **espessura real da
chapa**. Entram por `simbolos.flange_netafim()`.

### Decidido: o padrão da casa é Irrigafour

A cota que entra no desenho passa a sair do Irrigafour. A Netafim fica como
alternativa declarada, para quando a peça comprada for dela — a tabela
`data/cotas.csv` guarda as duas com a coluna `fonte`, e o motor pergunta por
uma porta só:

```python
cotas.cota("REDUCAO_CONCENTRICA", 8)                    # 150 mm, Irrigafour
cotas.cota("REDUCAO_CONCENTRICA", 8, fonte="NETAFIM")   # 300 mm
cotas.cota("CURVA", 8, "90", "perna_mm")                # 335 mm
```

A peça carrega o fabricante (`Peca(item, fonte=...)`) e guarda de quem a cota
veio (`fonte_cota`), porque o padrão cai para o outro fornecedor quando o
primeiro não tem a peça — e o desenho precisa poder avisar quando isso
aconteceu. São **707 cotas**: 545 do Irrigafour, 162 do caderno Netafim.

**A redução excêntrica precisa do par, não da bitola maior.** Descoberto ao
ligar a tabela no motor: a excêntrica de 8" mede 200 mm contra 6" e **300 mm
contra 3"** — o cone mais fechado precisa de corpo mais longo. A concêntrica
não tem isso (150 mm em quase tudo). Então a chave da cota é
`(fabricante, família, variante, DN maior, DN menor)`, com o par caindo para o
valor mais comum da bitola quando não estiver listado.

**A curva passou a ter duas pernas.** A `geometria()` avançava o comprimento e
depois girava — o que desenha uma perna só. Agora a curva avança a perna, gira,
e avança a segunda perna: uma curva de 90° de 8" ocupa 335 mm em cada direção.
É a `sentido = +1 | -1` que espelha a curva para cima ou para baixo, sem
mexer no código da peça.

### As três camadas do desenho

O que separa "símbolo paramétrico" de "clipart" é que a geometria é real:

1. **Geometria em escala real** — cada peça ocupa no papel a sua cota em
   milímetro. Os projetos reais desenham em 1:15 a 1:35; nessa escala um erro
   de 50 mm na redução aparece. A linha é a soma vetorial das cotas, e é ela
   que fecha a cota geral do conjunto.
2. **Símbolo paramétrico** — a forma da família, redesenhada com os parâmetros
   da peça: o cone da redução recebe (DN maior, DN menor, face a face); a curva
   recebe (raio, ângulo); o tê recebe (DN corrido, DN derivação). Um símbolo
   por família, ~10 no total.
3. **Anotação em tamanho fixo** — balão, código SAP, cota escrita. Esta camada
   **não escala**: texto de 3 mm é texto de 3 mm em 1:15 e em 1:35. Por isso
   ela vive fora da geometria, num plano próprio.

A consequência prática é a que interessa: **cadastrar uma peça nova não é
desenhar nada**. Se ela é de uma família conhecida, já tem símbolo; só precisa
de uma linha na tabela de cotas — e, na maior parte das bitolas, nem isso,
porque a linha já existe.

### A folha: duas regras que a fazem ler como caderno

A geometria estava certa antes de a folha ficar boa. Duas decisões mudaram
isso, e nenhuma é sobre a peça:

**O eixo de todas as peças cai na mesma altura da célula.** Como cada peça tem
a sua própria escala, isso não alinha as medidas — alinha os *eixos*. O
resultado é que os traço-e-ponto vermelhos correm de ponta a ponta da linha e
a folha vira um conjunto em vez de uma coleção de figuras soltas. A altura é
por seção, não por peça: dentro de uma seção todas as células têm a mesma
caixa, e é isso que segura o alinhamento.

**O que é fato sai do desenho e vai para uma tarja embaixo dele.** Bitola,
furação, norma, carcaça, peso, fonte — nada disso é cota, então nada disso
tem por que disputar espaço com o traço. Dentro do desenho fica só o que é
medida. Foi o que finalmente tirou o `⌀340` de cima da peça e o `12×⌀22` do
canto.

Uma terceira, menor: **peça comprida ocupa duas colunas**. Um manifold de
1,5 m ou uma barra de PEAD de 6 m numa célula de bitola vira fio de cabelo.
A bomba ganha duas colunas por regra, porque é a âncora do desenho.

## 4.1 As famílias que faltavam: PEAD, flange e manifold

Três buracos fechados, todos com folha de fabricante atrás.

### PEAD é tubo de 6 m com colar soldado e flange solta

No PEAD **o DN é o diâmetro externo** — o tubo DN225 mede 225 mm por fora.
Não há tabela de DE a consultar como no aço: o número do código já é o do
desenho. A parede sai da razão DN/SDR fixada pela pressão, e a tabela
`SDR_POR_PN` foi conferida contra a parede que a própria descrição carrega:

> `tools/conferir_pead.py` — **40 tubos conferem, 2 não.** Um erra 0,4 mm
> (arredondamento da norma) e o outro é um `PN80` que não é pressão, é a
> resina PE80.

A ponta do trecho é uma peça só, e é assim que se desenha:

    a flange entra no tubo → o colar é soldado depois → o ressalto a prende

Desenhar o colar sem a flange seria desenhar um estado que não existe montado.
Por isso `colar_pead()` devolve os dois, e a lista já pedia os dois aos pares
(`templates.trecho_pead`: N tubos, 2 colares, 2 flanges AZ). O ressalto tem o
diâmetro do ressalto da flange de aço da mesma bitola — é onde a junta assenta.

**O único número sem folha** é o comprimento do pescoço do colar. Está
estimado (`max(esp_flange + 40, DN×0,40)`, que cai perto do stub end
DIN 16963-4) e marcado com `params["pescoco_estimado"]`. É a próxima tabela a
buscar.

### Flange: a mesma chapa, dois papéis

`flange_avulsa(dn, tipo)` cobre as duas: `SOLDAR` solda na ponta do tubo de
aço; `SOLTA` é a mesma chapa correndo pelo tubo de PEAD até travar no
ressalto — muda o furo central, não o desenho. E `flange_cega(dn, saída)`
cobre as três versões que o catálogo tem: sem luva, com luva 2" BSP (a
ventosa, o manômetro) e com flange pequena.

A luva de 2" BSP não precisa de tabela: mede **30 mm de comprimento por 40 de
externo** nas duas folhas em que o caderno a desenha.

### Manifold: o barrilete que carrega as ventosas

Página 25 do caderno, extraída para `data/manifold_netafim.csv`. As duas luvas
de 2" BSP não são acessório — são a razão de o manifold ter ventosa. A folha as
cota pelo topo, e a regra fecha em todas as bitolas de 4" a 20":

> **altura do topo da luva = D/2 + 40 — 20 linhas, 20 confirmadas.**

Nem toda coluna da folha entrou no desenho, e isso está registrado em vez de
inventado: `R` e `F2` são alturas ligadas por `F2 = (R + D/2)/2` (também 20 de
20) mas sem a folha em imagem não dá para dizer o que cada uma mede; `X1..X4`
são o gabarito da boca de lobo a 0°, 15°, 30° e 45°, que serve ao caldeireiro
e não à vista lateral. Ficam gravadas na tabela, fora do traço.

### O crivo, com a folha na mão

Página 14. O que faz um crivo não ser um tubo furado está tudo lá: furo de
6 mm a cada 3, margem lisa de 10 mm antes do primeiro furo, parede de 2 a
6,35 conforme a bitola, e **fundo de chapa lisa** — a água entra só pela
parede. Um crivo de 14" tem mais de dois mil furos; o desenho mostra o trecho
junto ao fundo e anota o resto, que é a convenção de elemento repetido.

## 4.2 A bomba: a âncora do desenho

A bomba é o único item da casa que **não é tubulação e ainda assim manda na
geometria**: tudo se posiciona em relação a ela, e a altura do eixo decide
onde a sucção entra. Três cotas colocam os dois bocais, e é só isso que a
tubulação precisa:

| o que mede | Megabloc | Meganorm (EN 733) |
|---|---|---|
| do eixo à **face** do flange de descarga | a | **h₂** |
| do eixo à base — a altura do eixo | b | **h₁** |
| da face da sucção ao **eixo** da descarga | c | **a** |

São as mesmas três medidas com nome diferente em cada folha, e o desenho
escreve a letra da folha de onde a cota veio. Isso não foi deduzido — está
conferido em **três folhas independentes**:

> `tools/conferir_bomba_ksb.py` — **25 de 28 tamanhos com as três folhas
> iguais**, e nos três que divergem a folha vencida é sempre a mais antiga.

As três divergências valem contar, porque duas eram erro do folheto antigo e
uma é revisão de verdade:

| tamanho | manual A2744 | folheto antigo | Meganorm A2742 |
|---|---|---|---|
| 50-250 | 225 | **228** | 225 |
| 125-250 | 355 | **335** | 355 |
| 150-200 | **180** (a) | 160 | 160 |

Nos dois primeiros o folheto antigo está sozinho contra dois. No terceiro é o
manual novo da Megabloc que está sozinho — e é ele que vale **para a
Megabloc**, porque é a folha corrente daquela linha. A regra é essa: cada
desenho usa a folha da sua linha, e nunca mistura.

### O erro que vale contar

Desenhei a voluta como um círculo e o desenho **engoliu a flange de sucção**.
Vista de lado a voluta não é um círculo: o caracol está no plano perpendicular
ao eixo, então de lado aparece de canto — estreito em x, alto em y. O círculo
grande é a vista que olha pelo eixo. Pelo mesmo motivo o rotor de lado é uma
linha, não um círculo: é um disco de canto.

E errei duas vezes o significado de `a` antes de a Meganorm chegar. O que
resolveu não foi raciocínio, foi a Fig. 04 do manual A2742, onde `h₂` e `h₁`
saem do eixo para cima e para baixo. Os valores estavam certos desde o começo;
a descrição é que estava errada.

### O detalhe que a folha permitiu desenhar

Depois que as tabelas entraram, o desenho da bomba passou a ter o que mostrar
sem inventar nada:

- **a ponta do eixo** com o diâmetro, o comprimento e o rasgo de chaveta reais
  (`d1`, `l`, `u`, `t` da tabela 06) — é a única parte da bomba que o montador
  mede com paquímetro;
- **o pé do mancal** no lugar certo: a folha cota `w` do eixo da descarga até
  ele e `m1` entre os furos, e **w + v = f em 43 dos 43 tamanhos**, o que
  mostra que os dois partem o `f` a partir do eixo da descarga. Sem essa
  identidade eu não teria como posicionar o pé sem chutar;
- **a carcaça do motor** escrita no bloco, vinda da seção 15;
- **o sentido do fluxo**, que entra pelo eixo e sai por cima — é a informação
  que decide de que lado a redução excêntrica leva o lado plano.

### O motor é dimensionado, e a tabela já dizia isso

O desenho tinha um motor de tamanho proporcional ao resto — o que é errado
duas vezes: um motor de 60 CV é muito maior que um de 3 CV, e a diferença não
é proporcional a nada da bomba.

A resposta estava na própria tabela do A2744, e apareceu ao separar as colunas
**por quem as faz variar**. Elas se partem em duas metades limpas, e nenhuma
coluna fica no meio:

| dependem do **tamanho da bomba** | dependem da **carcaça do motor** |
|---|---|
| h1 h2 a b m1 m2 n1 n2 n3 s1 | h **l** m3 m4 n4 n5 r1 s2 t1 w |

Ou seja: **o `l` do manual não é o comprimento do conjunto — é o comprimento
do motor.** Um `l` só por carcaça, em **22 de 22 carcaças**, nas duas
rotações. Eu vinha lendo `l` como o total e desenhando o motor no que sobrava
depois da voluta, o que fazia o motor encolher quando a bomba crescia — o
oposto do certo.

Três letras bastam, e as três se confirmam entre si:

| letra | o que é | prova |
|---|---|---|
| **h** | altura do eixo do motor | é o próprio número da carcaça IEC |
| **l** | comprimento do motor | 374 na 90S, 880 na 225S/M — magnitude de motor |
| **r1** | diâmetro do corpo | `h − r1/2` dá o pé do motor: sobe de 20 mm na 90 para 47 na 225, que é como motor IEC é mesmo |

`data/motores_iec.csv` guarda as doze carcaças. A Meganorm não repete essas
medidas: a seção 15 dela só diz **qual** carcaça monta em cada bomba — e como
a carcaça IEC é a mesma peça nas duas linhas, a tabela serve às duas.

No papel a diferença aparece: a mesma 125-200 com 20 CV e com 30 CV são dois
desenhos visivelmente diferentes, e o que muda entre eles é só o motor.

E a quina do motor ficou arredondada, porque carcaça de motor é fundida e não
dobrada — o único canto vivo dela é o da caixa de ligação.

### Vertical e horizontal são a mesma peça

A bomba montada na vertical é a **mesma fundição de pé** — motor em cima,
sucção entrando por baixo. Não há duas peças e não há dois conjuntos de cota:
há uma peça e duas poses, exatamente como a curva, que a folha desenha em pé e
a montagem usa deitada.

E na linha a montagem **sai sozinha**, sem parâmetro nenhum: a direção chega
acumulada pela corrente. Na sucção vertical a linha sobe reta e a bomba recebe
por baixo; na horizontal há uma curva de 90° antes, e ela recebe deitada. O
`montagem="VERTICAL"` só existe para a folha de símbolos mostrar as duas poses
lado a lado.

## 4.3 Monobloco e mancalizada: muda o que vem depois da voluta

METB é Megabloc, monobloco; METN é Meganorm, mancalizada. **A ponta molhada é
a mesma** — mesmo caracol, mesmo rotor, mesmos bocais no mesmo lugar. O que
muda é o que vem depois: na monobloco o motor encosta na voluta; na
mancalizada entram o mancal, a luva elástica e o motor, os três aparafusados
numa base única. Por isso a lista tem código **"C/BASE S/MOTOR"** e código
**"MANCAL"** separados — são peças separadas de verdade.

Para a tubulação isso **não muda nada**: os dois bocais estão na mesma bitola
e no mesmo lugar. `desenhar_linha.succao_mancalizada()` é a mesma receita da
horizontal com a outra bomba no fim.

A Meganorm cota uma quarta medida que a Megabloc não tem: **f**, do eixo da
descarga ao fim do mancal — o comprimento real da bomba sem o motor. E a
seção 15 do manual dá, para cada tamanho, **quais carcaças de motor a KSB
monta e qual base perfilada cada combinação usa**. É o que tirou o motor
inventado do desenho: a carcaça sai da folha, não de uma regra de CV.

### O que as folhas homologaram

- **o nome da bomba É o DN de recalque**: EN 733 nomeia por (DN de descarga) ×
  (rotor). Na Megabloc o primeiro número reproduz a coluna DN2 em **27 de 27**
  tamanhos da faixa da casa; na Meganorm o nome reproduz DN2 **e** o rotor em
  **43 de 43**. A sucção sobe uma ou duas bitolas e não tem regra — fica a
  tabela.
- **a regra do bocal**, que tinha saído de medir a lista da Netafim, confirma
  em 6 de 6 saídas.
- **a tabela 06 contra a seção 15** do mesmo manual da Meganorm: **964 cotas,
  0 divergentes**. São a mesma folha lida de dois lugares, e divergir ali
  seria erro de leitura.
- flange **ANSI B16.1 125# FF**, exceto os tamanhos marcados (1), que são
  250# FF — e o marcador vem do próprio PDF, não de uma lista minha. Ele
  corrigiu três tamanhos que eu tinha classificado errado. É a razão de a
  redução da sucção ter uma norma em cada ponta: NBR do lado da linha, ANSI
  do lado da bomba.
- **até o tamanho 65-200 o bocal pode vir rosqueado BSP** em vez de flangeado.
  Gravado, porque é o resolvedor de junção que precisa saber.
- **25-150 e 25-200 não são previstos na ISO 2858**, pela nota da própria
  folha. Gravado na coluna `iso_2858`.

### O que ainda não desenha

Onze códigos METN citam **150-500, 200-400 e 200-500**, tamanhos que a folha
de medidas não traz; treze códigos METB citam tamanhos fora do manual A2744.
Ficam de fora em vez de estimados — houve uma versão deste motor que estimava
a/b/c por ajuste sobre a tabela da Megabloc, e ela foi apagada no dia em que o
manual da Meganorm chegou. Estimativa não sobrevive à folha.

### Onde isso chegou### Onde isso chegou

`tools/conferir_cobertura.py` tenta desenhar cada código do catálogo:

> **1.237 de 5.157 códigos saem desenhados** — eram 919 antes destas famílias.

O que ainda não sai não é falha de símbolo: 1.764 códigos não têm DN na
descrição, 611 não têm família, e o resto é PVC, filtro e quadro elétrico —
fora do escopo de sucção e recalque.

## 4.4 DXF: o motor produz a biblioteca de bloco, não concorre com ela

A casa já tem biblioteca de bloco em DWG — bomba, válvula, curva, tudo
desenhado à mão, um bloco por peça por bitola. Isso parecia estar em tensão
com o motor paramétrico. Não está, e a saída é simples: **o motor gera o
mesmo tipo de coisa**.

`motor/dxf.py` escreve cada símbolo como um `BLOCK` com o nome da peça, e a
linha montada como um `INSERT` por peça, com a rotação acumulada da corrente.
A geometria não é repetida — o bloco entra uma vez na tabela e a linha aponta
para ele, do mesmo jeito que um DWG de projeto faz. A cota sai em milímetro
real e o arquivo declara `$INSUNITS = 4`, então abre no CAD já na escala
certa.

As camadas seguem a convenção do desenho: `EIXO` vermelho traço-ponto,
`CORPO` preto, `FLANGE`, `MALHA`, `PARAFUSO`, `PORCA`, `JUNTA`, `COTA`
separadas. Dá para apagar todos os eixos de uma vez, ou plotar só o corpo.

A diferença que fica é de cobertura: a biblioteca à mão tem as bitolas que
alguém já precisou; a gerada tem **1.262 peças**, todas com a cota do
fabricante.

### O bug que a exportação encontrou

`tools/conferir_dxf.py` exporta e lê de volta, e compara a caixa de cada bloco
com a caixa do símbolo que o gerou. Na primeira rodada: **7 de 28**.

A culpa não era do exportador. O `limites()` do símbolo montava a caixa
zipando os números do path em pares x,y — o que erra em toda peça que usa `H`
ou `V`, e quase toda peça usa. O crivo dizia 290 mm e media 350. Como o
`limites()` é quem dá a escala da célula na folha, as peças vinham sendo
enquadradas com a caixa errada esse tempo todo.

O conserto foi unificar: um parser de path só, em `simbolos.pontos_do_path()`,
usado pela caixa **e** pelo exportador. Agora são **28 de 28**, e a folha
enquadra melhor.

Um segundo achado do mesmo conferidor: duas peças de mesmo rótulo e geometria
diferente — a mesma bomba com dois motores — colidiam num bloco só. O bloco
agora só é reaproveitado quando a geometria é a mesma; quando não é, o nome
ganha o que as distingue (`..._180M`).

### O bloco sai nomeado como a lista nomeia

O CAD mostra dois campos na janela de bloco: o **nome** e a **Description**.
A lista da Netafim usa exatamente essa divisão — o código identifica, a
descrição explica. Então o bloco sai assim:

    nome          01523-054000
    Description   CRIVO AZ 8" FL NBR PN16 P/ VALV PE

Isso obrigou a fechar uma ponte que estava só na ferramenta de conferência:
`motor/desenho.py` leva um item do catálogo até o símbolo dele, e injeta o
código e a descrição nos `params`. É a mesma ponte que o contador de cobertura
usa, agora numa casa só.

`--catalogo` exporta a biblioteca inteira: **1.237 blocos, um por código**.
`--dn 8` exporta os 175 códigos de 8". Peça que só existe no desenho — um tubo
de 500 mm cortado na obra — não tem código, e cai no rótulo.

### Ler o DXF da casa

`tools/ler_dxf.py` faz o caminho inverso: inventaria um arquivo — quais
blocos, em que camada, e **quanto cada um mede**. É por isso que o DXF da
casa interessa: de um bloco de projeto o que importa não é o desenho, é a
medida. Se o bloco da gaveta de 3" mede 190 mm de face a face, isso é uma
quarta fonte independente para conferir contra a tabela de cotas, ao lado do
Irrigafour, da Netafim e do fabricante da válvula.

## 4.5 Os blocos da casa como referência de traço

A casa mandou os blocos que já usa. Duas coisas saíram dali.

A primeira é uma confirmação: **as curvas dela e as do motor são o mesmo
desenho** — gomos mitrados, eixo vermelho traço-ponto, a peça em pé entrando
por baixo, a bitola escrita dentro. Cheguei nisso por outro caminho e caiu
igual, o que quer dizer que a convenção está certa.

A segunda é uma lista de correções de traço, todas nos equipamentos:

| peça | o que o bloco da casa mostra e o motor não mostrava |
|---|---|
| gaveta | volante **de canto** — chato, aro nas pontas, porca da haste em cima; sobreposta em dois degraus com a caixa de gaxeta; corpo de **fundo abaulado** |
| borboleta | volante **de frente**, com os raios contáveis, ao lado da caixa redutora; as duas orelhas do wafer |
| hidráulica | tampa **chata e larga** com a cabeça do parafuso nas pontas — não é calota; corpo abaulado só por baixo |
| medidor | corpo em **ampulheta** (largo na flange, apertado no eixo do rotor); registrador com a **tampa levantada**, que também diz de que lado se lê |
| retenção | o **bujão da mola** em cima — de lado, é a única coisa que separa a retenção de um anel espaçador |

Nenhuma dessas é cota: são convenções de como a casa desenha. Por isso
entraram como forma, sem tocar em nenhuma tabela.

O que **não** dá para copiar são as bombas: os blocos delas são traçados do
modelo 3D do fabricante — olhal de içamento, nervura, alívio de fundição. Isso
não sai de parâmetro, e fingir que sai seria pior que a diferença.

## 4.6 O DXF da casa como quarta fonte

A casa mandou três arquivos: as bombas, a biblioteca de PVC/Plasson e a de
PEAD soldável. As camadas confirmaram a convenção — `PEÇAS`, `eixo` em
vermelho, `TEXTO`, `INTERNO` — e o resto virou medição.

Os arquivos **não vêm em bloco**: as peças estão soltas no modelo, lado a
lado, com o nome escrito perto de cada uma. Então medir é primeiro separar.
`tools/medir_dxf.py` faz isso em três passos — caixa por entidade, união por
vizinhança numa grade (o que se toca é a mesma peça), e o rótulo mais próximo
na mesma coluna. Saem **135 peças medidas** de 45 metros de desenho, sem
ninguém clicar em nada.

Duas armadilhas apareceram e valem registro. A primeira: o rótulo fica
**acima** da peça num arquivo e **abaixo** noutro, às vezes no mesmo — então a
regra é a mais próxima na coluna, para qualquer lado. A segunda: ir *da peça
para o texto* não funciona, porque peça larga rouba o rótulo da vizinha. Do
texto para a peça funciona, porque cada texto tem uma peça só ao lado dele.

E o **eixo entra no aglomerado mas não na medida** — é ele que costura a peça,
mas sobra dos dois lados e sobra diferente em cada desenho. Sem tirá-lo, uma
bomba de 950 mm parece 35% maior só por causa do traço-e-ponto.

### O que a comparação encontrou

`tools/conferir_cad.py` compara o corpo — sem eixo — peça a peça:

| peça | motor | casa | Δ largura | Δ altura |
|---|---|---|---|---|
| METB 200-150-250 50cv | 989 × 655 | 949,7 × **655,0** | +4,1% | **0,0%** |
| METN 200-150-315 100CV | 1877 × 715 | 1799,5 × 832,8 | +4,3% | −14,1% |

A altura da METB fecha **exata**: 655 = h1 + h2 = 280 + 375, direto do
folheto. Isso é o que dá confiança para levar a sério a diferença de largura,
e a diferença apontou um erro real:

> **O comprimento total da monobloco é `a + l`.** Na 150-250 de 50 CV isso dá
> 160 + 791 = **951**, contra 949,7 medidos — 1,3 mm.

Eu vinha desenhando uma **lanterna** entre a voluta e o motor. Monobloco não
tem lanterna: o flange do motor aparafusa na tampa de trás da voluta e o eixo
do motor **é** o eixo da bomba — é isso que a faz monobloco. A lanterna é peça
da mancalizada, e com ela a bomba saía 240 mm mais longa do que é. Junto veio
outro conserto: a largura axial do caracol estava saindo de
`max(rotor × 0,42, externo_da_sucção × 1,1)`, e o segundo termo engordava a
peça sem motivo — a boca de sucção entra pela frente, não ocupa comprimento de
caracol.

A altura da METN é a que sobra em aberto: −14%. A carcaça que a seção 15 lista
para a 150-315 para em 225, e um motor de 100 CV é maior que isso — o conjunto
da casa usa uma carcaça que aquela tabela não cobre. Fica anotado em vez de
forçado.

O DXF da casa é desenho de projeto, não folha de fabricante, e a casa avisou
que alguma peça pode ter entrado fora de escala. Por isso **nada dele é
importado**: o que sai é comparação. Onde diverge, a folha manda; o que a
comparação faz é dizer onde olhar. Nesta rodada apontou certo.

### A medida virou tabela — com um guarda na porta

A casa confirmou que confia nas medidas do arquivo, **com uma exceção
declarada: os registros de gaveta podem ter entrado fora de escala.** Isso
transformou a medição em fonte de cota — a única que cobre PVC, Plasson e PEAD
soldável, famílias que nenhuma folha de fabricante do motor alcança.

`tools/cotas_da_casa.py` lê o nome medido e o transforma em chave:
`CURVA 90. SOLDA 225MM PLASSON/FIP` vira `(CURVA, variante 90/SOLDA, DN225)`.
`motor/cotas.cota_da_casa()` é a porta, separada da tabela em polegada porque
a chave é outra: no PVC e no PEAD o DN **é** o diâmetro externo.

Três guardas, e cada um veio de um erro que o conferidor pegou:

**A junta faz parte da identidade.** A curva de 90° DN110 soldável mede 203 e a
de bolsa mede 186 — são duas peças. Sem separar por junta, as duas caíam na
mesma chave e a tabela recusava as duas. Separando, as cotas boas subiram de
113 para **138**.

**Cota medida duas vezes com duas respostas não é cota.** Acontece quando um
rótulo grudou na peça errada. Escolher uma das duas leituras seria propagar o
erro; a chave inteira sai. São 18 casos, listados.

**Suspeita fica na tabela, mas não sai pela porta.** Os 12 valores de gaveta
estão gravados com `confiavel=0` e só saem com `aceitar_suspeita=True`, o que
obriga quem usa a saber o que está usando. Apagá-los seria pior: some a
informação de que foram medidos.

O teste que fecha a conta é a monotonia: `tools/conferir_cotas_casa.py`
verifica se a cota **cresce com a bitola** em cada série. Cota que diminui
quando a bitola aumenta é leitura errada, não peça estranha. Depois de separar
por junta:

> **todas as séries com três pontos ou mais crescem.**

Antes disso havia três séries quebradas, e cada quebra era exatamente uma
leitura ruim.

O que a tabela abre: 138 cotas em 10 famílias — CURVA, TE, TE_REDUZIDO, LUVA,
LUVA_CORRER, LUVA_REDUCAO, ADAPTADOR, ADAPTADOR_FLANGE, BUCHA_REDUCAO e
FLANGE, em bolsa, solda, rosca e correr. São as famílias dos **207 códigos em
milímetro** que hoje não desenham. Os símbolos ainda não existem; a cota deles,
agora, sim.

### Tubo de rolo não é peça

A casa apontou os tubos de 100 m — FXN layflat — que o desenho tratava como
peça e desenhava com 100 metros de comprimento. Não são peça: entram na lista
por metro. A varredura pelo mesmo critério pegou de brinde um erro de
cadastro: `01503-000008 TUBO AZ 20"X4,75MMX2000M` são 2 metros, não 2 km.

A regra agora está em `motor/desenho.py`: tubo de rolo não desenha, e
comprimento acima da barra máxima que a casa compra (12 m) não desenha e diz
para conferir o cadastro. Custou 25 códigos na cobertura — **1.237** — e os 25
não eram peça.

## 5. O que a peça puxa: um mecanismo só

Hoje as derivações estão em quatro lugares diferentes. São todas o mesmo padrão
— *peça ou junção na linha implica outros itens*:

| gatilho | puxa |
|---|---|
| junta flangeada | junta plana + n parafusos + n porcas + 2n arruelas |
| flange de PVC | contra-flange (+ junta e ferragem, pelo manual) |
| válvula wafer | 3 barras roscadas + porcas + arruelas |
| válvula hidráulica | piloto + kit + mola |
| tubo cortado | conversão de metragem em barras |

Um `derivar(gatilho) -> [(papel, especificação, quantidade)]` só, com as regras
em tabela, e a resolução em SAP separada da regra.

## 6. O catálogo tem dois modos, e isso precisa ser explícito

Aprendido a duras penas:

| modo | quando | famílias |
|---|---|---|
| **busca paramétrica** | a descrição é fiel: família + DN + norma bastam | tubo, curva, redução, tê, adaptador, manifold |
| **lista fechada** | a escolha é comercial, não geométrica | medidor, piloto, bomba, borboleta |

O medidor prova: buscar por família traz 20 itens, dos quais 5 são digitais
(dependem de cabo) e o analógico de 3" **nem tem a palavra MEDIDOR na
descrição**. Nenhum padrão de texto resolve — só lista por código.

A borboleta prova de outro jeito: 47 itens de sete linhas comerciais, três
fabricantes, com alavanca, caixa redutora ou volante. O DN e a norma não
escolhem; a política da casa escolhe.

## 7. Ordem de implementação

1. **`Bitola`** — é a base de tudo e a fonte de mais bugs.
2. **Gabarito por família** — dá topologia a 340 itens que hoje têm uma lista.
3. **Negociação com quatro saídas** — inclui a troca de peça.
4. **`derivar()` unificado** — junta o que está espalhado.
5. **Modo do catálogo explícito** — encerra a busca que traz a coisa errada.
6. **Símbolo por família + tabela de cotas** — o desenho vem depois do modelo,
   não antes.

Nada disso muda as regras de montagem já levantadas. Muda onde elas moram.

## 8. Desktop ou web?

**Recomendação: servidor local em Python, interface no navegador.** Um
executável que a pessoa abre e que sobe o programa em `localhost` — sem
instalação de dependência, sem internet, sem servidor da empresa.

Por quê, e não as outras:

| opção | a favor | contra |
|---|---|---|
| **Web local (só navegador)** | zero instalação | o motor teria de ser reescrito em TypeScript — as regras de montagem, furação, bomba, corte e derivação já estão em Python e testadas contra três projetos reais |
| **Desktop Qt/Electron** | roda offline | a tela é desenho SVG e tabela; HTML faz isso melhor e mais barato que Qt, e Electron carrega um navegador inteiro para nada |
| **Servidor local + navegador** ✔ | mantém o motor, UI em SVG, offline, distribuição por um executável | precisa empacotar (PyInstaller) |
| **Web hospedada** | catálogo sempre atualizado, projetos compartilhados | depende de internet e de alguém cuidar da infraestrutura |

A escolha não é definitiva: **é o mesmo código nas duas pontas**. O motor não
sabe onde roda. Começar local e virar hospedado depois é trocar onde o processo
está, não reescrever.

### O que isso implica na prática

```
motor/            regras — não sabe se está na web ou no desktop
catalogo/         a lista de materiais, indexada
api/              camada fina HTTP: recebe comando, devolve modelo + lista
web/              a tela: vista lateral em SVG, tabela ao lado
```

A camada `api` é fina de propósito. Ela recebe os mesmos comandos que o modelo
já tem (`inserir`, `remover`, `substituir`, `alterar`, `mover`) e devolve o
documento inteiro recalculado. Não há lógica ali.

Exportação fica no Python, onde já está resolvido:

- **aba Orçamento** em XLSX — `openpyxl`, que já é usado na importação;
- **prancha em PDF** — a vista lateral já é SVG, e SVG para PDF é conversão
  direta.

### Quando ir para hospedado

Três sinais, e nenhum deles é hoje:

1. mais de um projetista precisando ver o mesmo projeto;
2. o catálogo mudando com frequência (a LM é revisada por safra, não por semana);
3. biblioteca de templates compartilhada entre as unidades.
