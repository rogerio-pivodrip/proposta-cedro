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
| Plasson × Plasson | 5/8" × 4" | 3/4" × 5" |

A bitola no Plasson e o critério entre 4" e 5" ainda não foram confirmados —
as linhas estão marcadas `homologado=NAO`.

**Furação** (`data/regras_furacao.csv`): 8" = 12 furos, confirmado. O resto é
referência EN 1092-1 PN16, marcado `homologado=NAO`.

Milímetro e polegada usam a **mesma tabela**: a flange de 225 mm do Plasson é a
`FL. AZ - 225 - ABNT 16 - 12 FUROS` (`01542-099000`) — 225 mm ↔ 8" ↔ 12 furos.
A equivalência comercial está em `motor/traducao.py`.

**Engate K não é usado.** Continua reconhecido no catálogo (204 conexões) só
para o motor apontar quando uma peça escolhida tem ponta K, em vez de aceitar em
silêncio. Junções por rosca e solda também não geram ferragem.

### 4.2.1 Barra roscada

Válvula wafer é presa por tirante: **3 barras roscadas por válvula de retenção
ou válvula borboleta**, na mesma bitola da regra acima, mais 2 porcas e 2
arruelas por tirante.

O catálogo vende a barra em 1 m (`BARRA ROSCA FG 5/8"` `01542-000191`,
`3/4"` `01542-000190`). Enquanto o **comprimento do tirante** não for definido,
a lista conta 3 barras inteiras por válvula e emite aviso; definido o
comprimento, o planejador de corte converte para barras como faz com o tubo.

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
tem — e 1 é erro de digitação no próprio desenho (`Red Con AZ 3" x 1".1.4"`). As duas
flanges de aço deixaram de faltar: o catálogo as chama de `FL 6" (152MM) NBR
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

1. **Comprimento do tirante** de barra roscada — sem ele a lista conta 3 barras
   inteiras de 1 m por válvula, que deve estar sobrando.
2. **As 3 barras roscadas substituem 3 dos parafusos da junta, ou entram além
   deles?** Hoje o motor soma as duas coisas.
3. **Plasson** — a bitola do parafuso (assumi a mesma regra de DN do aço) e o
   critério entre 4" e 5" de comprimento.
4. **Furação** das demais bitolas — só 8" = 12 furos está confirmado.

## 9. Estado do código

```
tools/importar_catalogo.py    xlsx  -> data/catalogo_bruto.json   (5.157 itens)
tools/normalizar.py           texto -> data/catalogo.json          (peças paramétricas)
tools/extrair_lista_pdf.py    PDF do CAD -> lista de peças em CSV
tools/casar_lista.py          nome de desenho -> código SAP
tools/demo_succao.py          demonstração ponta a ponta (sucção e recalque)
motor/catalogo.py             índice por (família, DN, norma)
motor/regras.py               compatibilidade + ferragem
motor/ferragem.py             ferragem -> código SAP
motor/corte.py                cortes -> barras de estoque
motor/traducao.py             vocabulário do desenho -> vocabulário do catálogo
motor/linha.py                documento, comandos, junções, geometria, lista
```

Cobertura do interpretador no escopo de sucção/recalque (aço ≥ 3" e
Plasson ≥ 75 mm): **732 de 732 itens** com família identificada.
