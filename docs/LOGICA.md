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

Comandos (única porta de escrita): `inserir`, `remover`, `substituir`,
`alterar`, `mover`. Cada comando → valida → recalcula junções e ferragem →
redesenha as duas views. Undo/redo é a pilha de comandos. O balão do desenho e a
linha da tabela são a mesma peça, com o mesmo id.

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
2n × arruela
```

**Bitola** (`data/regras_ferragem.csv`), regra da casa:

| contexto | até 5" | acima de 5" |
|---|---|---|
| aço zincado × aço zincado | 5/8" × 2½" | 3/4" × 2½" |
| qualquer × flange da bomba | 5/8" × 3½" | 3/4" × 3½" |

No Plasson o comprimento é pelo diâmetro do tubo, com a quebra em 110 mm:

| tubo | parafuso |
|---|---|
| 75, 90 e 110 mm | 5/8" × **4"** |
| 140 mm | 5/8" × **5"** |
| 160 e 225 mm | 3/4" × **5"** |

O comprimento está confirmado; a bitola no PVC ainda segue a regra de DN do aço
e está marcada `homologado=NAO`.

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

### 4.2.1 Barra roscada

Válvula wafer é presa por tirante. A regra de compra é **3 barras roscadas
inteiras por válvula** de retenção ou borboleta — o corte acontece na montagem e
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

Achado nos projetos: **flange de PVC é sempre par**.

| projeto | `FL PVC` | `ADAPTADOR P/FL … SOLDA` |
|---|---|---|
| Marcelo Amorim | 90 mm × 9 | 90 mm × 9 |
| Marcelo Amorim | 110 mm × 4 | 110 mm × 4 |
| Lincoln Junqueira | 160 mm × 14 | 160 mm × 14 |

Quantidades idênticas nos dois projetos. Logo: `FLANGE_PVC` é um kit
(flange + adaptador de solda + junta + ferragem), lançado como uma peça só e
explodido na lista. Vale o mesmo para conjuntos como `Retrolavagem 90mm`, que
aparece na lista de peças como um item mas é uma montagem.

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

Os **manifolds já são desenhos padrão** no catálogo: `MNFD AZ D02 … D20`,
14 tipos, 151 itens; só o `D09` tem 43 variações de DN e comprimento. O conceito
já existe na Netafim — o programa formaliza.

Um template é a mesma estrutura de `Linha`, com DN paramétrico:

```python
SUCCAO_CANAL = [
    ("CRIVO", {}), ("TUBO", {"comprimento_mm": 1000}),
    ("CURVA", {"angulo": 90}), ("TUBO", {"comprimento_mm": 3000}),
    ("CURVA", {"angulo": 45}), ("TUBO", {"comprimento_mm": 1500}),
    ("REDUCAO_EXCENTRICA", {"dn_saida": dn - 2}),
]
```

Escolhe o DN → resolve inteiro contra o catálogo → sai a lista.
`tools/demo_succao.py` já faz isso.

## 8. Decisões em aberto

1. **Quantas porcas e arruelas por barra roscada?** Hoje o motor conta 2, como
   suposição avisada.
2. **Bitola do parafuso no Plasson.** O comprimento está definido (4" até 110 mm,
   5" acima); a bitola ainda segue a regra de DN do aço.
3. **Comprimento do prisioneiro em NBR.** A ficha mede a versão ASME 150, cujo
   flange é mais grosso que o NBR — o tirante em NBR sai um pouco mais curto.
   Mantive o número da ficha, que erra para mais.
4. **Homologar EN e ANSI.** As linhas NBR estão medidas; EN 1092-1 e ASME B16.5
   ainda são norma escrita — e são justamente as do lado da bomba.

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
tools/demo_succao.py          demonstração ponta a ponta (sucção, bomba, recalque)
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
