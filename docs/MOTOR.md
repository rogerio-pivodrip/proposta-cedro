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
