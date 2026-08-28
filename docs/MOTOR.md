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

Bitola é um objeto com **DN nominal em milímetro como identidade**, e as
representações como apresentação — `motor/bitola.py`:

```python
class Bitola:
    dn_mm                # 200 - a identidade
    def em_polegada()    # 8"    - como o aço se chama
    def em_mm_externo()  # 225   - como o PVC se chama
    def em_serie(serie)  # o número dela naquela série, ou None
    def __eq__(outro)    # compara dn_nominal, nunca o número exibido
```

**Por que o DN nominal e não a polegada:** é ele a chave da tabela de furação,
e furação é a prova *física* de que duas bitolas são a mesma. 225 mm de Plasson
e 8" de aço tomam a mesma flange, com os mesmos 12 furos ⌀22 no mesmo círculo
de 295. `tools/conferir_bitola.py` confere isso indo buscar na tabela de
furação — não perguntando à `Bitola` se ela concorda consigo mesma.

**Comparar com número dá `False`**, não um acerto por acidente: é o bug do 90
de PVC contra 90 de grau, fechado no `__eq__`.

### A tabela era quatro, e virou uma

A conversão estava copiada em quatro lugares — `traducao.POLEGADA_MM`,
`regras.POLEGADA_PARA_DN`, `regras.PVC_PARA_DN` e `simbolos.PEAD_POL` — e
`bomba.MM_PARA_POLEGADA` era a inversa de uma delas. Os quatro nomes continuam
de pé, porque quem chama não precisa saber que mudaram de casa; o que mudou é
que agora **são projeções de uma tabela só**, e o teste cobra que as quatro
digam o mesmo que a `Bitola`.

### O catálogo tem três séries de milímetro, não uma

Passar as 3.555 medidas do catálogo pela `Bitola` mostrou que "milímetro" na
lista é três coisas diferentes:

| série | norma | como aparece | exemplo |
|---|---|---|---|
| métrica | ISO 161-1 | PEAD e Plasson | DN225 = 8" |
| DEFOFO | NBR 7665 | PVC de ponta e bolsa grande | 170, 222, 274, 326, 378 |
| externo de aço | — | dentro do nome da flange | `FL 8" (203MM)` |

O mesmo DN150 é **160 mm** na métrica e **170 mm** no DEFOFO. Comprar por uma
tabela e receber da outra não encaixa, e antes disso o programa não tinha como
saber de qual das três o número vinha.

### E encontrou leitura errada da descrição

Três medidas não são bitola nenhuma, são texto lido como diâmetro:

```
01542-000319   304 mm    VALV. RET. VERT. 1/2 BSP PN16 INOX 304
30500-001000   2000.75"  REG. PRESSAO 2000 3/4"X 1 - 06MCA
```

O `304` é do aço inox, o `2000` é o modelo do regulador. Ficam nomeados no
relatório em vez de virarem uma bitola de 2 metros. As 117 medidas que sobram
sem série são gotejamento e microtubo — 16, 17, 22 mm — que não são tubulação
de casa de bomba.



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

### O balão: o número é da lista, e não do desenho

O balão é o de vista explodida de manual: um pontinho pousado na peça, um fio
saindo dele a 45° e o número dentro de um círculo. Vive na camada de anotação,
em pixel fixo — ele não engorda quando a linha muda de escala.

**O número é o da linha da lista de materiais, e não um contador do desenho.**
Duas curvas do mesmo código levam o mesmo número, e quem quer saber quantas
são lê a quantidade na lista, que é onde ela mora. É a mesma decisão que o
resto do programa: existe um documento, e quem numera é ele. Se o desenho
contasse peças, girar a folha ou esconder um balão mudaria o número — e o
desenho passaria a discordar da lista, que é exatamente o que este programa
existe para não deixar acontecer.

Daí saem três consequências que ninguém precisa programar duas vezes:

- **acrescentar ou tirar peça renumera sozinho**, sem deixar buraco: a
  numeração é derivada da lista, e a lista se refaz a cada comando;
- **reordenar é reordenar a lista** (`renumerar`), e o balão acompanha;
- **desmarcar o balão não tira o item da lista.** O acessório continua sendo
  comprado; o que sai é o traço apontando para ele. Foi por isso que
  `alterar` passou a achar a peça por id em vez de por índice — acessório
  não tem índice, ele vive dentro da peça que o carrega.

**Onde o balão cai é do documento também** (ângulo e distância), e não do
navegador: quem arrastou um balão e exportou o DXF espera achá-lo onde
deixou, e quem desfez espera vê-lo voltar. Sem distância, o fio anda até
*sair do desenho* — da caixa da própria peça e de tudo que estiver encostado
nela, ferragem da junta inclusive — e só então começa o círculo. É por isso
que o balão continua fora do traço quando a linha muda de bitola: a distância
não é um número guardado, é uma consequência do que há embaixo.

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

### Onde isso chegou

`tools/conferir_cobertura.py` tenta desenhar cada código do catálogo:

> **1.712 de 5.157 códigos saem desenhados** — eram 919 antes destas
> famílias, 1.237 antes das de milímetro (4.7) e 1.487 antes da norma (4.9).

O que ainda não sai quase nunca é falha de símbolo: **2.265** códigos não têm
DN na descrição e **1.040** não têm família — e o resto é filtro e quadro
elétrico, fora do escopo de sucção e recalque.

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

`--catalogo` exporta a biblioteca inteira: **1.701 blocos, um por código**.
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
milímetro** que hoje não desenham. A cota deles saiu aqui; os símbolos, na
4.7.

### Tubo de rolo não é peça

A casa apontou os tubos de 100 m — FXN layflat — que o desenho tratava como
peça e desenhava com 100 metros de comprimento. Não são peça: entram na lista
por metro. A varredura pelo mesmo critério pegou de brinde um erro de
cadastro: `01503-000008 TUBO AZ 20"X4,75MMX2000M` são 2 metros, não 2 km.

A regra agora está em `motor/desenho.py`: tubo de rolo não desenha, e
comprimento acima da barra máxima que a casa compra (12 m) não desenha e diz
para conferir o cadastro. Custou 25 códigos na cobertura — **1.237** — e os 25
não eram peça.

## 4.7 Os símbolos em milímetro, montados contra a medida

Com a tabela medida na mão, as nove peças de PVC/Plasson foram desenhadas:
tubo, luva, luva de redução, curva, tê, tê reduzido, adaptador para flange e
bucha de redução. Três convenções de traço saíram dos blocos da casa e não da
minha cabeça:

**Curva de PVC é arco liso, não gomo.** O gomo é chapa de aço soldada — a
peça é cortada em fatias e as fatias são soldadas, e por isso o gomo aparece.
A peça injetada sai de molde: o traço é um arco tangente às duas pernas, com
o canto interno arredondado. Desenhar gomo numa curva de PVC é desenhar um
processo de fabricação que não existe.

**Bolsa é uma cinta curta na ponta da peça.** É a assinatura da peça de
encaixe, como a flange é a da peça de aço. Quem olha de lado reconhece a peça
pela cinta antes de ler o nome.

**Cada ponta carrega o seu DN escrito por dentro.** A casa escreve os dois
mesmo quando são iguais — é o que diz que a peça *não* é redução.

### A inversão: aqui a medida manda

Na linha de aço a folha do fabricante manda e a medição do DXF é informativa
— é o que a 4.6 diz e continua valendo. Em milímetro é o contrário: **não
existe folha**, a medida da casa *é* a cota, e então o desenho tem obrigação
de voltar nela. Isso é uma afirmação conferível, e `tools/conferir_pvc.py`
confere: monta cada peça na bitola medida e compara a caixa do corpo com a
medida.

    52 peças medidas · 102 cotas comparadas
    |Δ| médio  0.00%  ·  pior  0.07%  ·  102 dentro de 1%

### A curva: duas medidas, duas pernas

A casa mede dois envelopes da curva, não a perna. Antes eu resolvia uma perna
só contra o envelope maior e aceitava o erro no outro lado — dava 0% na de 90°
e −53% na de 45°, porque a de 45° da casa tem a perna de entrada bem maior que
a de saída. Duas medidas e duas incógnitas fecham exato: as pernas saem de um
Newton com jacobiano por diferença finita, e o arco fica com raio fixo em
1,8 raio de tubo.

O limite do raio veio da própria medida: a curva **soldável de DN225** mede
362 mm de envelope, e com raio acima de 2,1 r a peça não caberia dentro da
própria medida. Uma medida amarrando uma constante de forma é melhor que um
chute.

E uma percepção de pose: **a curva não tem pose canônica.** A de 45° da casa
está de pé, a minha entra pela horizontal, e o mesmo envelope cai num eixo
diferente em cada uma. Então o que se compara é o *par* de envelopes, não o
eixo em que cada um caiu — e as duas trocas de eixo são tentadas, ficando a
que fecha melhor.

### O que a conferência encontrou

Cinco erros, e nenhum deles apareceria olhando o desenho:

| onde | o erro |
|---|---|
| `conferir_pvc.py` | li `limites()` como par de cantos, e ela devolve `x, y, w, h`. Toda altura saía 50–80% maior — e por sorte toda largura batia, porque as peças começam em x=0 |
| a cinta | o `d_externo` medido é o da **bolsa**, não do corpo: a bolsa é o ponto mais gordo da peça e é nela que a trena encosta. O corpo agora sai 5% mais fino, e a altura fecha exata |
| `cotas.cota_da_casa` | a corrente de chaves não tinha `(família, "", dn, dn_menor)`. A bucha foi medida **com o par mas sem junta no nome** e caía na estimativa — 62 mm virava 66 |
| a nota | a anotação sai em pixel fixo, fora do `transform`, e ninguém girava a posição dela. Numa peça posada de pé o DN ia para outro canto da célula — foi assim que o DN da curva de 45° apareceu fora da peça |
| a peça soldável | sem cinta por fora, a luva de DN225 saía um quadrado limpo. A bolsa dela tem de aparecer **por dentro**: o furo do tubo e a crista onde as duas pontas param |

### Empate também é leitura errada

A conferência da tabela medida já recusava série que *diminui* com a bitola.
Faltava a que **empata**: duas bitolas seguidas com a mesma cota é o mesmo
rótulo lido duas vezes, não peça estranha. Com a série agrupada por bitola —
senão toda redução parece empatada, porque a mesma bitola aparece uma vez por
par — sobra uma de verdade para a casa olhar:

| família | cotas |
|---|---|
| TE SOLDA | 75:169 · 90:199 · 110:239 · **125:339 · 160:339** · 225:465 |

Um tê de DN160 não mede o mesmo que um de DN125. Fica registrado, não
corrigido: quem mede é a casa.

### Onde isso chegou

As nove peças entraram na folha de símbolos como seção própria, e a barra de
PVC entrou junto: `JEI` e `PB` têm bolsa num lado, `PP` é lisa dos dois — está
na descrição, não precisa de tabela. São 37 símbolos por bitola, todos com
bloco de DXF conferido, e a cobertura foi de **1.237 para 1.487** códigos.

## 4.8 A parte que sobe: onde o desenho escapava sem ninguém ver

A casa olhou a folha em 3" e disse: *a parte que sobe, nos tamanhos menores,
está muito grande.* Estava — e não só nos menores.

A peça de tubulação é fácil de conferir: começa numa flange, acaba na outra, e
a caixa dela **é** a cota. O equipamento não. Ele tem uma parte que sobe —
volante, caixa redutora, tampa, registrador — que não entra em face a face,
entra em altura total. E é ali que o desenho escapa, porque **o olho compara a
torre com o corpo, não com a cota**: numa bitola grande a torre parece
proporcional, e na pequena ela come a peça.

`tools/conferir_equipamento.py` mede o que a folha mede, e o primeiro
resultado foi este:

| peça | desenhado | folha | Δ |
|---|---|---|---|
| medidor 3" | 452 | 259 | **+74,7%** |
| medidor 8" | 630 | 377 | +67,1% |
| gaveta 14" | 1117 | 867 | +28,8% |
| hidráulica 3" | — | 203 | −18,5% |

### A raiz: `altura_total_mm` é total

Três símbolos tratavam a altura da folha como se fosse **do eixo para cima**, e
depois somavam o corpo por baixo. A folha da ARAD prova qual é a leitura certa
sem precisar de opinião: ela cota `altura_total_mm` **e** `altura_abaixo_mm`
para o mesmo medidor. Se a total fosse do eixo para cima, a de abaixo seria
informação sobrando.

E a de abaixo abriu outra coisa: no medidor de 12" a câmara desce 330 dos 505
mm, sobram 175 acima do eixo — o Woltmann **não é simétrico no eixo**. Meia
largura para os dois lados perdia isso e deixava a peça 10% baixa em 10" e 12"
ao mesmo tempo que a torre a deixava alta.

### O bug embaixo do bug: a curva nunca era medida

Corrigida a altura, a hidráulica ficou 26% **baixa**. A barriga dela é uma
quadrática, e o `pontos_do_path` reduzia Bézier ao ponto final — como diz o
próprio docstring de então, *"em vista lateral ninguém vê a diferença"*. Ninguém
vê no traço; **o medidor de caixa vê**, e para ele a barriga não existia.

Agora a Bézier é amostrada. E com ela veio a regra que faltava: o fundo é o
**ápice** da curva, não o ponto de controle. Para uma quadrática que sai e chega
em `corpo` com controle em `c`, o ápice fica em `corpo/2 + c/2` — usar o
controle como fundo dava barriga de sobra, usar a ponta dava barriga nenhuma.

É o mesmo tipo de erro do `H`/`V` da 4.4: uma peça do parser que ninguém
conferia, errando em toda caixa de uma vez.

### O que a folha não cota, a conferência não cobra

Duas coisas ficaram de fora da comparação de altura, e as duas por serem
verdade:

**A flange.** Uma hidráulica de 3" tem 203 mm de altura total e 200 mm de disco
de flange — o disco quase preenche a peça, e passa da altura cotada em bitola
pequena. É real. Cobrar isso da folha seria pedir uma medida que ela não deu.

**O volante da gaveta.** São 500 mm de volante numa válvula de 290 de face a
face. Ele passa dos dois lados de propósito, então na gaveta o comprimento sai
da comparação e fica só a altura.

### O que não tem folha, tem regra dita

A MP cota `altura_acima_mm` da borboleta de **alavanca**. Da caixa redutora,
nada — e a caixa é mais alta, tem o redutor e o volante em cima. Antes o
volante flutuava e a caixa crescia sem regra: +25% sobre a alavanca em 6" e
+2% em 3". Agora está dito de uma vez — **1,15 da alavanca** — e a conferência
confere contra isso, não contra a MP.

### Onde isso chegou

    50 cotas comparadas · 0 peças fora de 3%
    |Δ| médio  0.14%  ·  pior  1.90%

E a gaveta da casa merece nota. O bloco dela mede, nas seis bitolas de 4" a
14", uma razão altura/face de **2,53 exatos** — sem variar um décimo. Isso é um
desenho só, escalado seis vezes, e confirma o que a casa já tinha avisado. A
folha da RAN (Fig. 37) e a da MP concordam entre si nas nove bitolas, e é delas
que a cota sai. Do bloco da casa aproveita-se a forma; a medida, não.

## 4.9 A norma como quinta fonte, e a regra que a lista já dizia

Faltava a conexão de bitola pequena — nipe, luva, bucha, união, cap, tê
reduzido — cerca de 140 códigos. Ela não tem folha de fabricante nem desenho da
casa: tem **norma**, a equivalência entre a polegada e o milímetro. Isso entra
como quinta fonte de cota, em `data/series_nominais.csv`, e a tarja da peça
mostra qual norma foi usada — porque a mesma polegada cai em milímetro
diferente em cada série:

| série | norma | 2" | 3" | 4" |
|---|---|---|---|---|
| soldável | NBR 5648 | 60 | 85 | 110 |
| PBA / irrigação | NBR 5647 | 50 | 75 | 100 |
| rosca | ISO 65 | 60,3 | 88,9 | 114,3 |

Comprar pela tabela errada não encaixa, e é por isso que a série tem de ser
lida e não presumida. As três linhas da PBA vêm confirmadas pelo DXF da casa:
os adaptadores medidos lá são `ADAP. BS x RM 50 x 2"`, `75 x 3"` e `100 x 4"`.

### A regra estava no jeito de a lista nomear

Eu comecei tentando detectar a rosca por marcadores na descrição, e caía em
metade dos códigos. A regra é mais simples, e sai do próprio catálogo: **a peça
soldável e a PBA são designadas em MILÍMETRO** — `LUVA PVC IRRI LF BS 75 MM`,
`CURVA 90. SOLDA 225MM`. Então **conexão pequena designada em polegada é
rosqueada** — `LUVA PVC R 1/2"`, `NIPEL DUPLO FG 1"`. A rosca é o padrão, e o
que quebra a regra diz na descrição.

### A peça é montada em milímetro e comprada em polegada

A geometria sai do milímetro que a norma deu — é o único jeito de desenhar. Mas
o rótulo, a porta e a tarja voltam para a língua da lista: `nipe 2"`, não
`nipe DN60,3`. E a tarja passa a dizer `ISO 65` em vez de `casa`, que não mediu
esta peça. A nota dentro do desenho também: deixar *60,3* escrito dentro de um
nipe de 2" é dizer que a peça é outra.

Isso mora numa função só, `desenho.em_polegada`, usada tanto pelo catálogo
quanto pela folha de símbolos — senão a folha mostraria uma peça e a lista
outra.

### Duas peças novas, e um traço que não aparecia

**Nipe** e **união** não tinham símbolo. O nipe é o toco com rosca macho nas
duas pontas e o sextavado no meio; a união são duas meias luvas e a porca que
aperta uma na outra — e a porca *é* a peça, porque é por ela que a linha
rosqueada se desmonta sem girar tudo desde a ponta.

O filete da rosca deu trabalho, e o erro vale registro: eu desenhei o filete
como tracinhos sobre a linha do corpo, e **não aparecia nada** — os tracinhos
caíam exatamente onde o corpo já estava. O traço certo é o do desenho técnico:
a *crista* é a própria linha do corpo, e o *fundo* do filete é uma linha fina
por dentro dela.

### Onde isso chegou

Com as famílias de milímetro, o equipamento corrigido e a norma, a cobertura foi
de **1.487 para 1.701** códigos, e a folha passou de 37 para **42 símbolos por
bitola** — todos com bloco de DXF conferido nas oito bitolas.

## 4.10 Seis correções de traço, todas apontadas olhando a folha

A casa foi lendo a folha e apontando. Nenhuma destas seis apareceria numa
conferência de cota — todas passam pelo teste e todas estavam erradas no
desenho. Vale registrar porque mostra o limite do que a conferência pega.

**A cota centrada no eixo, com trim.** Pedido como duas coisas, é uma: a cota
encostada no eixo sem trim fica ilegível, e fugindo dele para o lado deixa de
dizer a que peça pertence. Agora o eixo abre para ela passar — a convenção de
CAD. O trim é um retângulo da cor do papel desenhado antes do texto: não há
como cortar um `path` em SVG, e máscara custa mais do que vale numa folha com
trezentas peças.

**Na curva, a cota no meio do EIXO.** O meio entre as duas portas cai na
*corda* da curva, fora do tubo — a cota ia parar no ar ao lado da peça.
`meio_do_eixo()` anda o eixo pelo comprimento dele e devolve o meio de verdade.
Na peça reta nada muda; na curva muda tudo.

**O medidor reto de flange a flange.** O ombro entrando na flange era o que
restava da "ampulheta" do bloco da casa, e em qualquer bitola lia como defeito
de traço. E o mostrador tinha de descer para tocar a peça: com o corpo reto
quem manda é `-r`, não a cintura antiga — usar a cintura deixava a torre
apoiada no ar.

**A hidráulica tem sede, não barriga.** A peça de diafragma não tem barriga
para baixo: tem duas curvas subindo do fundo até uma face no meio, e é por cima
dela que a água passa. As curvas se encontram numa *face* e não numa ponta —
uma ponta não veda nada.

**O volante da gaveta caía dentro da sobreposta.** A altura dela era 44% da
cota total, e em bitola grande passava do volante. Agora sai do vão disponível
— do topo do corpo ao topo do volante — e sobra haste livre entre os dois, como
no bloco da casa. Achei junto um erro de sinal meu: `-(alt - r) - r` é `-alt`,
não `alt - 2r`.

**A furação do crivo em dobro.** Furo de 6 mm num cesto de 368 é um ponto. O
furo e o passo dobram *juntos*, para a proporção entre chapa e vazio não mudar,
e a malha vai até perto da flange. A cota de verdade passou a sair sempre na
nota — antes ela só aparecia quando o desenho cortava a contagem, e agora é o
único lugar onde o 6 mm existe.

### E um bug de parser, de novo

A chapa do fundo da válvula de pé sobrava embaixo da peça: `V` do SVG é
**absoluto**, e sair de `-r*0.95` para `r*1.9` desce o dobro. É o terceiro erro
desta família — `H`/`V` lidos como par (4.4), Bézier reduzida à ponta (4.8), e
agora `V` absoluto usado como relativo. Todos no mesmo lugar: a fronteira entre
o que se escreve no path e o que se acredita que ele desenha.

## 4.11 O corpo da bomba, e a mesma chapa em dois desenhos

Mais três apontamentos, e o do caracol abriu uma incoerência que estava no
código desde o começo.

**O caracol é arredondado.** É peça fundida, e onde o rotor gira o corpo
acompanha o círculo dele. De canto isso é uma cápsula — meio círculo em cima,
meio embaixo — e não uma caixa de quinas vivas.

**O pescoço da descarga afunila.** A boca de 6" tem 152 mm de furo e o caracol
tem 84 de largura axial: vista de lado a boca **é mais larga** que o caracol, e
o pescoço fecha nele. Duas paredes verticais diziam que os dois tinham a mesma
largura, o que não é verdade em bitola nenhuma.

### A incoerência que isso revelou

Desenhado o pescoço afunilando, ele saiu torto: uma parede quase vertical e a
outra atravessando o motor. A causa estava no `recuar` da monobloco.

A monobloco recua o caracol para a face de trás dele cair em `c` — é o que faz
o comprimento total fechar em `a + l`, e foi assim que a 4.3 bateu com o DXF da
casa. Mas eu deixei a **boca** em `c` também. As duas coisas não podem estar
no mesmo lugar: `c` é onde o flange do motor aparafusa, e a boca fica *sobre* o
caracol, no meio dele. Com a boca em `c` o pescoço ficava pendurado na quina de
trás. *(A 4.13 corrige o que este parágrafo diz sobre o `a`: ele mede até a
face do flange do motor, e o eixo da descarga fica antes dela.)*

Agora a boca, o rotor, o dreno, a seta de fluxo, o eixo da descarga e a porta
de saída saem todos de `xd = (x0 + x1) / 2`. Com duas paredes verticais isso
nunca apareceu — a geometria errada estava escondida atrás de um traço que não
a exercitava.

### E a medida resolveu, não o argumento

Centrar a boca no caracol piorou a largura contra o bloco da casa — de +4,1%
para +5,9% — porque a flange da descarga passou a avançar atrás da face de
sucção. Isso levantou a pergunta certa: **onde a boca fica de verdade?** Duas
medidas responderam, e as duas apontam para o mesmo lugar:

`c + l` bate com o bloco da casa em **0,1%** (951 contra 949,7 medidos), o que
fixa a face de trás do caracol em `c` — é ali que o flange do motor aparafusa. E
com a boca *em* `c`, a flange dela cai em 20..300 mm e não avança da face de
sucção, que é exatamente o que um `c` de 160 mm implica.

Então o caracol é **assimétrico de propósito**: a face de trás é chata, porque é
o flange do motor, e a boca sobe da parte da frente. Foi o pedido de traço da
casa — "aumentar a voluta para não ficar desproporcional" — que forçou a
pergunta, e as duas cotas do folheto a responderam sem precisar de opinião.

A largura do caracol passou a ter piso e teto, os dois com motivo: não pode ser
mais estreita que a boca que ela sustenta (era um caracol de 105 mm carregando
uma boca de 152 de furo), nem mais larga que o vão até a face de sucção, senão
engole o bocal de entrada. Contra o bloco da casa: **+2,2%**, melhor que os
+4,1% de onde isso começou.

E de brinde, uma coisa que a seta escondia: a **seta de fluxo** da sucção
acabava atrás da face de sucção, e o comparador a contava como corpo — a bomba
parecia 32 mm mais larga do que é. Seta e eixo dizem algo *sobre* a peça, como
a cota diz; nenhum dos dois tem chapa, e agora nenhum dos dois entra na medida.

**Os furos da válvula de pé iguais aos do crivo.** É a mesma chapa perfurada na
obra, e na folha o furo de uma estava no dobro do da outra. Agora as duas saem
de `chapa_perfurada()`, com a **mesma ficha** — a do crivo daquela bitola. Sair
de uma função só é o que garante que não volte a divergir.

E a cota `furo 6 c/ 3` saiu do desenho a pedido da casa. Ela continua onde
sempre esteve — em `data/crivos_netafim.csv`, que é a folha — e quem precisa
dela pede pela ficha em vez de ler do desenho.

## 4.12 "Falta corpo": o desenho do fabricante ao lado do meu

A casa mandou dois desenhos de fábrica — uma METB e uma METN — e uma frase:
*falta corpo nessas bombas*. Faltava. Lado a lado, o que o meu desenho dizia
errado não era cota nenhuma: era **massa**.

| o que o fabricante mostra | o que eu desenhava |
|---|---|
| caracol grande, quase da altura do motor, descendo até perto da base | uma cápsula de 1,15 raio de rotor, um caroço no meio do conjunto |
| pé do caracol **aberto**, alargando para apoiar | um retângulo estreito |
| sucção abrindo em **sino** para dentro do caracol | tubo reto entrando |
| mancal de fundição cheia, alto junto do caracol e descendo em rampa | tubo escalonado |
| acoplamento **gordo** entre as duas pontas de eixo | um tubinho, e o vão entre bomba e motor vazio |
| junta aparafusada entre caracol e flange do motor | nada |

Todas essas são forma, não cota — e é por isso que a conferência não as pegava.
`conferir_cad` compara a **caixa** da peça, e caixa não vê onde a massa está
dentro dela. Uma bomba com o caracol pequeno e o mancal fino tem exatamente a
mesma caixa de uma bomba com os dois no tamanho certo.

O caracol ganhou piso e teto, e os dois vêm de medida: não pode ser mais
estreito que a boca que sustenta, nem passar do vão que `c` deixa até a face de
sucção — e o teto depende de como ele se apoia, porque a monobloco é recuada e
cresce só para trás da face, enquanto a mancalizada é centrada em `c` e cresce
para os dois lados.

### O que continua não saindo de parâmetro

Do desenho do fabricante ficaram de fora, e de propósito: o olhal de içamento,
as nervuras da lanterna, a tampa cônica do ventilador, o logotipo na fundição.
Isso é traçado do modelo 3D, como diz a 4.5 — não sai de cota, e fingir que sai
seria pior que a diferença.

## 4.13 Retratação: o que o `a` do folheto mede

A 4.11 diz que `c + l` bater com o bloco da casa em 0,1% "fixa a face de trás
do caracol em `c`, onde o flange do motor aparafusa". A conta estava certa e a
explicação estava errada, e a casa desfez o nó com três frases:

> tem que deslocar a voluta para centralizar com a flange de saída
> o funil é concêntrico
> **o motor não vai até o eixo das blocs**

A terceira é a que decide. Se o motor não chega no eixo da descarga, então o
`a` do folheto — 160 mm na 150-250 — **não** é a face de sucção até o eixo da
descarga. É a face de sucção até a face do **flange do motor**. E aí tudo fecha
de uma vez:

| fato | vem de |
|---|---|
| o motor começa em `a` e o total é `a + l` | 951 contra 949,7 medidos na casa |
| o eixo da descarga fica **antes** de `a` | a casa, e o desenho de fábrica |
| o caracol é centrado na boca, com a face de trás em `a` | as duas acima juntas |
| o funil sai concêntrico | consequência, não escolha |

Na 150-250 isso põe o caracol de 22 a 160, o eixo da descarga em **91**, e o
motor começando em 160 — depois do eixo, como a casa disse.

### A tabela toda, e o que ela deixa em aberto

A casa mandou um segundo desenho de fábrica — METB 125-80-315 30CV — e pediu
para comparar. A comparação fechou a **forma** e abriu o **comprimento**.

A forma primeiro. Medindo o desenho dela pela escala da flange de sucção:

| | desenho de fábrica | o motor desenha | Δ |
|---|---|---|---|
| largura do caracol | ~206 mm | 205 | −0,6% |
| diâmetro do caracol | ~435 mm | 430 | −1,1% |

São 0,65 e 1,38 do rotor. Eu vinha de 0,95 e 1,85 — chute, e o caracol saía
gordo e alto demais. Agora as duas proporções são **medidas**, não estimadas.

O comprimento é outra história. A tabela da 150-250, contra os 949,7 mm que o
bloco da casa mede:

| CV | carcaça | `a + l` | `w + l` |
|---|---|---|---|
| 30 | 180M | 848 (−10,7%) | **942 (−0,8%)** |
| 40 | 200M | 913 (−3,9%) | 1019 (+7,3%) |
| **50** | **200L** | **951 (+0,1%)** | 1057 (+11,3%) |
| 60 | 225S/M | 1040 (+9,5%) | 1162 (+22,4%) |

O bloco está rotulado **50cv**, e nessa linha quem casa é `a + l`, em 0,1%. Mas
`a` = 125 na 80-315 não cabe um caracol de 205 mm de largura antes do motor — e
a casa disse que o motor não chega no eixo da descarga. As duas coisas só
convivem se `l` **não for o comprimento do motor sozinho**: se `l` for medido do
eixo da descarga até o fim do motor, incluindo a metade de trás do caracol e a
lanterna, então `a + l` é o total e o motor começa depois do eixo — tudo fecha.

Isso é consistente com `l` depender só da carcaça (22 de 22 tamanhos), porque na
monobloco o adaptador é padronizado por carcaça IEC. E o `w` não serve de
alternativa: ele **varia com a carcaça** (254, 266, 266, 282 na mesma bomba),
então é cota do motor e não do caracol.

Fica registrado como está: o desenho segue o que a casa afirmou — caracol
centrado na boca, motor depois dela — e por isso o comprimento passa de `a + l`
pela metade da largura do caracol. `conferir_cad` mostra **+10,8%** na METB. Só
a KSB ou um conjunto medido resolve se `l` inclui a lanterna.

### O que eu tinha desfeito por achar impossível

Dois turnos atrás eu centrei a boca no caracol, vi a flange de descarga avançar
atrás da face de sucção, achei que nenhuma bomba faz isso, e desfiz. **Faz.** No
desenho de fábrica que a casa mandou, a borda esquerda da flange de descarga
está visivelmente à esquerda da face de sucção. Eu tinha a medida certa e a
descartei por um argumento de plausibilidade — o oposto da regra que este
projeto segue em toda parte.

O `recuar` saiu junto: as duas linhas centram o caracol na boca, e não havia
dois casos, havia um só mal entendido.

Fica registrado no relatório: `conferir_cad` mostra a caixa da METB em **+7,6%**
contra o bloco da casa, e a diferença é justamente esse avanço da flange — o
corpo, da face de sucção ao fim do motor, fecha em 951 contra 949,7.

## 4.14 A terceira linha de bomba: EBARA GSD

A casa mandou a folha dimensional da GSD (desenho 406.1 da EBARA) e a tabela da
base viga da GS, e pediu para acrescentar. As 14 GSD do catálogo estavam sem
família — não desenhavam porque a lista não diz "bomba" no nome delas, diz
`EBARA GSD 125-200 30CV`.

A ponta molhada é a mesma peça das duas KSB, e por isso a GSD reusa
`_corpo_bomba` inteiro. O que muda são as letras da folha:

| letra da GSD | o que mede | equivale a |
|---|---|---|
| `h1` | eixo → base | o `b` das KSB |
| `h2` | eixo → face do flange de descarga | o `a` das KSB |
| `f1` | face da sucção → face do flange de trás | — |
| `f2` | face da sucção → eixo da descarga | — |

### A elevação cotada corrige uma leitura minha

Eu tinha lido `f1` e `f2` como cotas medidas **do flange do motor**, e por isso
inferi que a face de sucção até o eixo da descarga fosse `f1 − f2`. A elevação
cotada que a casa mandou — com as linhas de `f1`, `f2`, `L1`, `L2`, `C`, `B`,
`BB`, `m1`, `m2` e `ØDN1` — mostra as duas nascendo na **face de sucção**: a
linha do `f2` morre no eixo da descarga, a do `f1` na face do flange de trás.
Então a cota que eu queria é **o `f2` sozinho**, e eu tinha derivado o que
estava cotado.

Uma correção sobre a correção, para o registro: eu escrevi aqui que essas
linhas de cota estavam na *folha 1 do desenho 406.1*. Não estão. O PDF 406.1
tem duas páginas e nenhuma delas é a elevação da bomba: a folha 1 é o desenho
do **motor** em quatro vistas e a folha 2 é só tabela. A elevação que resolveu
o `f2` é a imagem que a casa mandou. O que a folha 1 confirma é outra coisa, e
ela confirma bem: `AC` e `AD` são cotas **radiais**, medidas do eixo para cima
na vista de topo do motor — é por isso que `AC` fica sempre perto de `H`.

Isso amarra o caracol inteiro sem chute nenhum: ele é centrado no eixo da
descarga (`f2`) e a face de trás dele cai em `f1`, logo

    largura do caracol = 2 × (f1 − f2)

E a folha se confere sozinha nisso. Com essa leitura, a **frente** do caracol
cai a 27, 27 e 32 mm da face de sucção nos três grupos de suporte — que é a
espessura do flange de sucção mais uma folga, o mesmo número nos três. Três
grupos independentes chegando no mesmo valor não é coincidência; é a prova de
que a origem das duas cotas é a face de sucção.

| grupo | `f2` | `f1` | largura = 2(f1−f2) | frente |
|---|---|---|---|---|
| GSD/230 | 100 | 173 | 146 | 27 |
| GSD/240 | 125 | 223 | 196 | 27 |
| GSD/250 | 140 | 248 | 216 | 32 |

`_corpo_bomba` ganhou por isso um parâmetro `largura_folha`: quando existe folha
que cote o caracol, a largura é **medida**; onde não existe (as duas KSB), ela
continua saindo da proporção tirada do desenho de fábrica — 0,65 do rotor, com
a boca de descarga como piso.

### O motor da GSD chega por um pescoço

A casa apontou: *"esse motor é diferente na GSD, tem um pescoço mais fino"*. E
a folha cota exatamente isso, em duas medidas do mesmo motor: `L2` é o corpo
dele e `L1` é o total com a peça que liga no caracol. A diferença é o pescoço:

| carcaça | `L1 − L2` |
|---|---|
| 71 | 110 |
| 90 | 134 |
| 132 | 155 |
| grupo /230 | 185 |
| grupo /250 | 230 |

Nas duas KSB o flange do motor aparafusa direto na tampa de trás do caracol —
monobloco encostado. Na GSD não encosta: entre o caracol e o corpo do motor vai
um tubo mais fino, com a nervura onde ele agarra. É essa a diferença de forma
entre as três linhas, e ela está cotada, não estimada.

Duas ressalvas ditas em vez de escondidas. A folha dá `L1` em duas colunas, dos
suportes 230 e 250; o grupo **240 não tem coluna própria** e usa a do 230, com
`pescoco_da_folha=False` no `params` da peça para quem for conferir. E a carcaça
que a folha nomeia é **160M**, **200L**, **225S/M** — nomes que
`carcaca_do_motor()` não produz, porque ela devolve `"160"` e `"200"`. Daí
`carcaca_gsd()`, que lê a carcaça na tabela de CV **da própria folha**; onde a
linha da folha veio incompleta (160L, L160L, 200M), o pescoço sai da carcaça
vizinha de mesmo tamanho, porque ele anda com o tamanho e com o grupo do
suporte, não com a letra.

### Dá para extrair as formas?

Dá para **medir**, e foi o que fizemos. A folha 406.1 é vetorial — 2841 linhas
e 3600 curvas, nenhuma imagem — e o carimbo dela diz a escala: `ESCALA:1:9`,
`UNID.: Milímetro (mm)`, `Montagem referente a motor WEG`. Não é interpretação
de figura, é medição com a régua que a própria folha declara.

O limite é o traço automático do perfil, e ele é do arquivo, não do método: o
PDF não expõe camada por entidade. Linha de cota, hachura, quadro do desenho e
contorno da peça chegam como o mesmo tipo de objeto. Quem tenta traçar o
contorno sozinho leva as cotas dentro dele — foi o que aconteceu quando tentei.
Então o caminho que serve é o que está no código: **as cotas saem medidas da
folha, e a forma sai do símbolo paramétrico** que já desenha as duas KSB. É a
mesma divisão de trabalho de sempre aqui — o teste guarda a cota, o desenho
guarda a forma.

### Célula mesclada é o feitio mais fácil de ler errado

A folha compartilha o diâmetro nominal, o `f2`, o `b`, o `m1`, o `m2` e o `s1`
entre as bombas do mesmo grupo: o valor aparece uma vez e vale para o bloco.
Ler linha a linha perde a maioria dos números, e descer o valor do vizinho de
cima erra quando o rótulo do grupo está numa altura diferente da primeira bomba
dele.

`tools/extrair_gsd.py` lê **por posição x de coluna** e aplica quatro guardas:

**Faixa da folha.** Sem ela o `1 2 3 4 5 6` do quadro do desenho cai dentro da
tabela, e o `3` vira uma bomba com 3 mm de pé.

**Faixa plausível por cota.** O PDF entrega `21215` onde estão 212 e 15
grudados, e `200150500` onde estão três números. Um `n2` de 21 metros não é
cota, é leitura errada — e o extrator diz o que recusou, em vez de engolir.

**O nome diz o DN2.** Na GSD 125-250 o 125 é a descarga e o 250 é o rotor — a
mesma regra do folheto da KSB, já homologada aqui. Onde a tabela discorda do
nome, quem manda é o nome.

**`f1` e `f2` pertencem ao grupo.** São cotas medidas do flange do motor, então
valem o mesmo em todo o grupo do suporte. A moda do grupo corrige quem herdou
do vizinho errado.

Resultado: **34 modelos** dos 38 lidos, e os 4 que ficaram fora saíram por não
ter cota essencial — o extrator nomeia quais.

### O que o teste da GSD pergunta

`tools/conferir_gsd.py` fecha em zero, e uma das perguntas nasceu errada: eu
cobrava que a sucção fosse **um tamanho acima** da descarga, e a folha reprovava
em duas bombas. A folha estava certa: na EBARA a 40-125 tem sucção DN50 e a
40-200 tem DN65 — não é regra fixa. O invariante que dá para cobrar é só a
desigualdade, e os pares que a folha dá ficaram registrados no relatório:
32→50, 40→50, 40→65, 50→65, 65→80, 80→100, 100→125, 125→150, 150→200.

### A potência sai da lista, não de fórmula

A folha dimensional não cota potência por bomba — a tabela de CV dela é por
carcaça de motor. Mas a **lista** cota: `EBARA GSD 125-200 30CV` é um item de
verdade. Então a folha de símbolos escolhe, entre as 34, uma das **11 que a casa
compra**, e a potência sai de lá. Foi o que corrigiu uma GSD 150-200 saindo com
carcaça 315 e 100 CV — proporção minha, e over-motorizada.

Três modelos do catálogo não estão nesta folha (100-200, 150-400L, 150-500).
Esses recusam com o motivo dito, em vez de sair estimados. A base viga da GS
está extraída em `data/bases_gs.csv` — 105 combinações de bomba e potência — e
ainda não é usada: ela é da GS mancalizada, e a GSD é monobloco.

## 4.15 O motor: a peça que ninguém conferia

O motor era a peça menos conferida do caderno, e por um motivo estrutural: ele
não tem flange, então a conferência de face a face não o alcança, e não tem
torre, então a de altura total não o alcança também. Passou meses desenhado com
uma medida errada sem que nenhum teste tivesse como reclamar.

### O corpo estava desenhado com uma medida de largura

Eu usava o `r1` do manual da Megabloc como diâmetro do corpo. Cruzando o manual
com o dimensional da EBARA, `r1` bate **exato** com o `A` do IEC e `n5` com o
`AB`, nas seis carcaças que as duas folhas compartilham:

| quadro | `r1` (KSB) | `A` (EBARA) | `n5` (KSB) | `AB` (EBARA) |
|---|---|---|---|---|
| 90 | 140 | 140 | 164 | 164 |
| 100 | 160 | 160 | 188 | 188 |
| 112 | 190 | 190 | 220 | 220 |
| 132 | 216 | 216 | 248 | 248 |
| 200 | 318 | 318 | 385 | 385 |
| 225 | 356 | 356 | 436 | 436 |

`A` e `AB` são medidas de **largura** — vão entre os furos dos pés e largura
sobre os pés. As duas se veem de **frente**, e o caderno é de lado. Numa
carcaça 90 o `r1` dá 140 onde o corpo tem 180. Isso também encerra a pergunta
que ficou registrada em `tools/motores_iec.py` — "n5 é maior que r1 e não dá
para dizer o que é" — com a resposta vindo de fora: é o `AB`.

### O DXF resolve o que o PDF não deixava

Eu tinha escrito aqui que o traçado automático do perfil da 406.1 vinha com as
linhas de cota dentro do contorno, porque o PDF não expõe camada por entidade.
Os DXF da W22 que a casa mandou — 16 desenhos, 10 a 250 CV, 4 polos — **têm
camada**:

| camada | o que tem |
|---|---|
| `MOTOR` | contorno, aletas, caixa de ligação, olhais, pés |
| `EIXO` | ponta de eixo e chaveta |
| `COTAS` | `L`, `E`, `C`, `B`, `H`, `HD`, `ØAC`, `ØD`, com o valor medido |
| `DETALHE` | os eixos dos furos do pé |
| `EIXO_CENTRO` | a linha de centro |

Então o motor deixou de ser proporcionado e passou a ser **transcrito**.
`tools/extrair_weg.py` lê a forma e `data/motores_weg.csv` guarda ela, e cada
desenho se confere contra as próprias cotas dele antes de entrar: raio × 2 =
`ØAC`, plano do pé = `H`, primeiro furo a `C` da face, vão dos furos = `B`, fim
do corpo = `L`, topo da caixa + `H` = `HD`, face do corpo = `E`. **16 de 16
passam nas sete.**

### Cinco coisas que só o desenho contava

**O corpo tem o raio da altura do eixo.** `AC/2 ÷ H` fica em 0,985 nas doze
carcaças. Motor IEC não tem perna — a carcaça quase encosta no chão. E quando o
raio passa do plano do pé (quadro 132: raio 136 com eixo 132) a fundição é
achatada na diferença. É por isso que existe uma banda embaixo do corpo: ela é
**relevo** quando o raio passa e **calço** quando o raio não chega.

**As aletas são radiais, e o passo delas é angular** — 15,1° nas dezesseis
folhas. No perfil elas caem em `R·sen(k·15,1°)`, que aperta perto do topo.
Espaçar igual era o que fazia o corpo parecer um radiador — e as minhas estavam
não só espaçadas igual, estavam **na vertical**, quando aleta longitudinal se
vê de lado como linha horizontal.

**A carcaça tem três juntas fundidas**: a tampa dianteira, o fim das aletas e a
tampa traseira. Só depois delas vem o defletor, que afina nos últimos 6% do
comprimento, de `R` para 0,72 `R`.

**A caixa de ligação tem chanfro na frente**, tampa e flange de assento, e dois
**olhais de suspensão**, um de cada lado dela, cada um no seu pedestal.

**Os pés são dois calços** no vão `B`, e o primeiro furo fica a `C` da face do
corpo — o que responde de onde o `C` do IEC é medido: da face, e não da ponta
do eixo. Os dois ficam simétricos em relação ao centro da carcaça.

### O comprimento é do manual da bomba, a forma é do desenho do motor

O `l` do manual da Megabloc e o `L` do DXF da W22 ficam a 3 a 6% um do outro
nas oito carcaças que compartilham. Não é erro de leitura: são dois motores
parecidos, não o mesmo motor. E `l` é o **total com a ponta de eixo**, não o
corpo — usá-lo como corpo era o que deixava a bomba 80 a 140 mm longa demais.

Daí a regra, em três degraus:

1. a folha da bomba, quando ela cota o motor dela — a GSD cota `L2`;
2. o manual da bomba, quando cota o motor inteiro — o corpo é `l − E`;
3. o próprio DXF, que é `L − E`.

E `L2` da EBARA bate com `L − E` da WEG em **cinco carcaças** (132M 409/410,
132M/L 434/435, 225 745/746, 250 825/825, 280 931/931). Duas folhas de
fabricantes diferentes chegando no mesmo número é o que confirma que as duas
medem a mesma coisa.

### O que mudou no papel

`tools/conferir_motor.py` fecha em **64 de 64 cotas a +0,0%** contra o DXF, e a
comparação com o bloco de CAD da própria casa saiu de **+10,8% para −0,8%** na
largura da METB 200-150-250, com a altura **exata** — antes o motor era baixo
demais porque o corpo tinha o diâmetro de uma medida de frente.

Uma divergência fica registrada e não escondida: no quadro **225**, o
dimensional da EBARA dá raio 228 e o DXF da W22 dá 201,5. A W22 monta a 225S/M
num casco quase igual ao da 200 (`ØAC` 403 contra 402), e o dimensional da
EBARA é de um motor IEC genérico. As duas folhas discordam de verdade; quem
decide é a casa, e o teste mostra o par.

## 4.16 Duas coisas que a casa viu no papel

### O manifold não tem essas duas flanges para cima

A casa apontou um manifold de 14" com dois bocais flangeados em cima e disse
que não tem. Estava certa, e o erro era meu de raiz: o símbolo punha
`derivacoes=2` **por padrão**. Inventar topologia é o mesmo erro de inventar
cota, só que na forma.

E a topologia não precisa ser inventada — ela está escrita no nome:

| descrição | o que tem em cima |
|---|---|
| `MNFD AZ D06 14" FL NBR PN16 C/ L2` | nada; uma luva de 2" |
| `MNFD AZ D12 8" FL C/ 2 LG2"` | nada; duas luvas |
| `MNFD AZ D09 12"X2,65X2100MM FL E 2 FL8"` | dois bocais de 8" flangeados |
| `MNFD AZ D10 12"X2,65X3260MM FL E 3 K8"` | três bocais de 8" com anel K |
| `MNFD AZ D20 20" FL X 1FL14" X 2FL12"` | um de 14" e dois de 12" |

`motor/manifold.py` lê isso. O que separa **bocal** de **ponta** é o que vem
antes: bocal vem com contagem, com `C/`, ou depois de um separador. Sem
nenhum dos três, o que está escrito é a ponta do próprio manifold — é o que
distingue `FLK14" 2K10"` (ponta de 14", dois bocais de 10") de `2K10"` sozinho.
E a aspa deixa de ser obrigatória **quando há contagem**: `2 FL10` é bocal
tanto quanto `2 FL10"`, mas `K10` sem contagem é classe de anel, não bitola.

### O código D é o desenho do barrilete, e quase sempre fixa a topologia

`tools/gabarito_manifold.py` levanta a tabela do próprio catálogo — 151
manifolds em 14 códigos — e mostra quem discorda do próprio código:

| código | bocais | luvas | itens | concordam |
|---|---|---|---|---|
| D04, D05, D07, D11 | 0 | 0 | 34 | 34 |
| D06 | 0 | 1 | 8 | 8 |
| D12 | 0 | 2 | 7 | 7 |
| D08 | 1 | 0 | 7 | 7 |
| D09 | 2 | 0 | 43 | 34 |
| D10, D13, D20 | varia | varia | 26 | — |

Oito códigos têm topologia única e servem de reserva para quem tem descrição
truncada na lista (`MNFD AZ D09 20"X4,75X2050MM FL FL12"FL8"` perde o começo da
conta). Os outros variam de verdade, e aí manda a descrição — não o código.

### O colar de PEAD tem lado

A casa viu um trecho de PEAD com a flange da esquerda invertida. O colar é uma
peça com lado: ponta lisa de um lado, que funde no tubo, e flange do outro, que
aparafusa na linha de aço. Num trecho os dois colares olham para **fora**, e eu
desenhava os dois iguais — o da esquerda ficava de costas. `colar_pead` ganhou
`lado`, e o da ponta de entrada é o mesmo desenho espelhado.

## 4.17 O Plasson: onde a cota é medida e onde ela é chute

A casa perguntou se as peças Plasson estão com as medidas certas. A resposta
curta é sim onde a casa mediu — `conferir_pvc.py` fecha em **102 de 102 cotas a
0,00%**. A resposta honesta é mais longa, e ela mostra dois problemas que o
próprio teste não conseguia ver.

### O teste não alcançava o problema dele

`conferir_pvc.py` compara o desenho contra o DXF da casa, então ele só olha as
peças que a casa mediu. Fechar 100% não quer dizer que a folha esteja medida —
quer dizer que **o que foi medido bate**. A peça que cai na estimativa não
aparecia ali de jeito nenhum.

E a folha estimava muito: das peças da seção PVC e Plasson, só **11 saem de
medida**, 2 saem da medida da outra junta, e **27 são estimativa**.

### Pior: a tarja dizia CASA em todas elas

Todas as peças em milímetro carregavam `fonte="casa"` **fixo no código**. O
desenho carimbava a fonte que não tinha — exatamente o que este projeto trata
como pecado capital, porque a tarja existe para dizer de onde a cota veio.

`_ou()` e `_fonte_mm()` corrigem: a peça anota quais cotas foram medidas e
quais foram estimadas, e a tarja diz `casa`, `casa em parte` ou `estimativa`.
A curva tem um terceiro caso, porque a casa mediu a bolsa e a soldável em
séries de DN diferentes (bolsa em 35/50/75/100/125/150, soldável em
75/90/110/125/160/225): quando só a outra junta tem a bitola, o envelope dela
serve de reserva e a tarja diz **`casa (outra junta)`**.

### A folha desenhava 27 peças que a lista não tem

A seção PVC ia até 14", usando a equivalência do PEAD — 10"→DN280, 12"→DN315,
14"→DN355. Mas a linha **Plasson do catálogo existe em 25, 32, 40, 50, 63, 75,
90, 110, 125, 140, 160 e 225, e acaba aí**. O PEAD sobe até 355; o Plasson não.
Eram 27 peças de três bitolas que não existem para comprar.

A seção agora para em DN225 e, nas bitolas acima, sai vazia **dizendo por quê** —
seção que some sem explicação faz o leitor supor que faltou desenhar.

É o mesmo erro do manifold, na mesma semana, e a mesma lição: a série do
milímetro não é uma série só, e tratar bitola como número é o que faz o
programa desenhar peça que não existe. É por isso que a `Bitola` da seção 2 é o
item 1 da ordem de implementação.

## 4.18 A folha da Plasson chegou, e ela resolve uma medida suspeita

Perguntar de onde vinha a cota do Plasson fez a casa mandar o que faltava: dez
desenhos do catálogo Plasson da linha soldável — 5010 luva, 5012 luva com
rosca, 5022/5062/5212 adaptadores, 5040 tê, 5050 curva 90, 5090 bucha,
5450 curva 45, 5510 colar, 5900 flange solta e 5910 flange cega.

São **folha de fabricante**, então entram acima do DXF da casa na ordem de
fonte, e a tarja passa a dizer `plasson`. Resultado na seção PVC da folha:

| antes | depois |
|---|---|
| 11 de medida, 27 estimadas | **23 de folha de fabricante**, 3 do DXF, 19 estimadas |

Nas bitolas soldáveis (6" e 8") são 7 de 9 peças com cota de fábrica.

### As duas folhas se confirmam, e é isso que dá confiança nas duas

| peça | DXF da casa | folha Plasson |
|---|---|---|
| tê soldável DN225 | 465 × 362 | H=465, Z+I+E/2 = **362** |
| tê soldável DN160 | 339 × 262 | H=339, Z+I+E/2 = **262** |
| colar 5510, E1 | 106 / 125 / 150 / 213 / 272 | **os mesmos cinco** |
| flange solta | 8 furos ⌀18 em 160 (3") | Dp/S/N da NBR 7675 PN16 |

A furação da flange solta casa com a de aço em **todas as bitolas que a casa
compra menos uma**: o d225 tem 8 furos ⌀22 em 297, e o 8" de aço tem **12** em
295. Mesmo furo, quase o mesmo círculo, mas 8 posições em 12 só coincidem em 4.
`tools/conferir_flanges.py` mostra a tabela inteira e marca essa. Não se
conserta aqui — é o mesmo caso da folha Netafim contra a NBR: pergunta para
quem compra. A lista continua comprando pela furação de aço, que tem mais
furos, porque comprar parafuso a mais é barato e comprar a menos deixa a junta
sem parafuso.

A altura do tê não está na folha: ela sai de `Z + I + E/2`, e o fato de essa
soma bater **exata** em duas bitolas independentes é o que valida a leitura das
letras.

### E resolvem uma medida que estava marcada como suspeita

Ficou registrado há tempo que **o tê soldável DN125 tinha sido medido idêntico
ao DN160** — 339 × 262 nos dois. Não era coincidência: era um rótulo grudado na
peça errada no bloco da casa. A folha dá o DN125 em **269 × 209**, que é a
progressão certa da série. Uma fonte nova resolveu uma dúvida velha sem precisar
remedir nada.

### Onde as duas discordam, fica dito

A curva 90 soldável bate exato em DN110 e DN225 e diverge de 4,6 a 7,1% em 75,
90, 125 e 160 — e sempre com a casa medindo **maior** (+10 mm em três delas,
+16 na de 160). A folha manda, porque é do fabricante; a divergência entra num
bloco próprio do relatório, com o par, para alguém olhar o bloco da casa.

`conferir_pvc.py` passou a separar as duas coisas: contra o DXF ele cobra
(62 cotas, 0,00%); contra a folha ele **informa**, que é a mesma regra do
`conferir_cad.py` — quem tem folha não é reprovado por desenho de projeto.

### O que ainda é estimativa, e por quê

- **luva de redução** — o catálogo mandado não tem a folha dela;
- **curva 45** — a folha 5450 cota a **perna** (E), não o envelope, e inventar
  o envelope a partir dela seria estimar com cara de folha;
- **bolsa (PBA) em 3", 4" e 5"** — é outra norma e outra série de DN; a única
  fonte continua sendo o DXF da casa.

## 4.18.1 O volante não cresce com a válvula

A casa apontou o volante da caixa redutora grande demais numa borboleta de 14",
e pediu que ficasse do mesmo tamanho em todas as bitolas. A folha da
Saint-Gobain confirma, e melhor do que confirmar: ela **cota**.

| bitola | alcance do acionamento |
|---|---|
| 8" | 185 mm |
| 10", 12", 14" | 280 mm |

Ou seja: o volante muda com o **modelo do redutor**, em degrau, e não com a
bitola da válvula — o mesmo redutor serve uma faixa, e o volante dele não muda
dentro dela. Nas bitolas em que a folha não cota (3" a 6") o desenho fazia
`corpo × 1,4`, que dava 130 mm em 3" — como se existisse caixa redutora sob
medida.

Agora, onde a folha não cota, o desenho pega o **degrau vizinho** em vez de
proporcionar: 185 mm de 3" a 8", 280 de 10" a 14". Duas medidas, que são as
duas que a folha dá.

## 4.19 A folha passa a sair da lista, e não de peça inventada

A casa foi direta: *"use apenas as peças que temos na LM com código"*. Está
certa, e por um motivo que já tinha aparecido duas vezes na mesma semana —
**peça inventada não se compra**. O manifold com dois bocais que não existem e
o PVC em DN280 são o mesmo erro que a curva de 60°.

Agora cada célula da folha sai de um **item do catálogo, com código SAP**, e a
tarja mostra o código e a descrição da lista. `pedidos(dn)` diz o que a folha
pede ao catálogo; `_escolher()` traz o item; quem não tem item não é desenhado.

### O que a lista não tem, e a folha passou a dizer

| falta | onde |
|---|---|
| **curva de 60°** | em bitola nenhuma — zero itens no catálogo inteiro |
| **válvula de pé em aço** | não existe; o que a lista tem é o `CRIVO AZ n" P/ VALV PE` e uma `VALVULA PE PVC 2 COM CRIVO` |
| gaveta, hidráulica e medidor | não existem em 14" |
| flange | não existe em 3" (só a FG sextavada e uma CPVC fêmea) |
| flange cega c/ luva 2" | não existe em 14" |
| curva 90° c/ escape 2" | não existe em 14" |
| bomba | nenhuma com recalque de 14" |
| PVC | nada em DN140 — a série Plasson existe, a casa não compra |

Cada seção imprime a sua lista de faltas embaixo dos desenhos. Some sem
explicação e o leitor supõe que faltou desenhar; dito, vira informação de
projeto — quem for especificar uma curva de 60° descobre antes, e não na
cotação.

A contagem por bitola virou uma medida do próprio catálogo:

| bitola | 3" | 4" | 5" | 6" | 8" | 10" | 12" | 14" |
|---|---|---|---|---|---|---|---|---|
| peças com código | 36 | 37 | **13** | 38 | 38 | 31 | 28 | 23 |

O 5" confirma o que a seção 2 já dizia: **é bocal, não é linha.**

### A flange solta era de PEAD, não de aço

Procurar `FLANGE SOLTA` no aço não achava nada porque ela não existe ali: na
lista, a flange solta é `FL P/COLAR. PEAD DN225 NBR PN16`, designada em
milímetro. Ela mudou de seção — está no PEAD, ao lado do colar que ela prende.

### A ventosa, que a casa tinha apontado que faltava

A regra de **onde** a ventosa entra já existia (`motor/ventosa.py`) e a luva
que a recebe também; a válvula em si nunca tinha sido desenhada. São **duas
peças diferentes com o mesmo nome**, e a medida da casa não deixa dúvida:

| classe | 2" | 1" |
|---|---|---|
| combinada (NAVC) | 483,6 × **518** | — |
| anti-vácuo (EMEK) | 73,3 × **122** | 58,6 × 125 |
| anti-vácuo (Netafim) | — | 76,4 × 286 |

Desenhar uma pela outra erraria por **quatro vezes** na altura. Por isso a
classe é parâmetro e a cota é procurada por `CLASSE/MARCA` — o DXF mediu
quatro modelos de três marcas. Onde a marca do item não foi medida, cai na
outra marca da mesma classe e a tarja diz qual: `casa (COMBINADA/NAVC)`.

### O acionamento é preferência, não filtro

Exigir borboleta com alavanca deixava a de 3" fora da folha, porque a lista só
tem caixa e volante nessa bitola. O catálogo já ordena alavanca → caixa →
volante; o pedido só precisa aceitar a ordem em vez de impor a primeira.

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
