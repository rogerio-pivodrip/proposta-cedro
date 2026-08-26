# Lógica do programa de sucção e recalque

Documento de projeto. Descreve o modelo de dados, as regras de montagem e o
mecanismo que mantém desenho e lista sempre iguais.

## 1. O ponto central: não existe sincronização

A tentação é ter um desenho e uma planilha e sincronizar os dois. Isso sempre
diverge. Aqui a regra é:

> **Existe um único documento — a Linha. Desenho e lista são duas projeções
> dela.** Editar no desenho e editar na tabela são o mesmo comando atingindo o
> mesmo objeto.

```
                       ┌──────────────────┐
   arrastar peça ─────▶│                  │─────▶ desenho (SVG)
                       │   Linha (modelo) │
   editar linha  ─────▶│                  │─────▶ lista (aba Orçamento)
   da tabela           └──────────────────┘
```

Comandos (única porta de escrita): `inserir`, `remover`, `substituir`,
`alterar`, `mover`. Cada comando → valida → recalcula junções e ferragem →
redesenha as duas views. Undo/redo é a pilha de comandos.

## 2. Modelo de dados

### Peça
Toda peça do catálogo vira um registro paramétrico
(`tools/normalizar.py` faz isso a partir da descrição de texto livre):

| campo | exemplo |
|---|---|
| `sap` | `01523-134000` |
| `familia` | `CURVA`, `TUBO`, `TE`, `REDUCAO_CONCENTRICA`, `MANIFOLD`, … |
| `material` | `ACO_ZINCADO`, `PVC_PLASSON` |
| `dn` / `unidade_dn` | `[8.0]` / `in` — ou `[160]` / `mm` |
| `angulo` | `90` |
| `espessura_mm`, `comprimento_mm` | `2.65`, `3000` |
| `conexoes` | `[{dn:8, tipo:FLANGE, norma:"NBR PN16"} × 2]` |
| `derivacoes` | `[{qtd:2, dn:2, tipo:LUVA}]` (os `2 LG 2"` das descrições) |

### Porta
Cada peça expõe **portas** (as pontas). Uma porta é `(dn, tipo, norma)`:

- `tipo`: `FLANGE`, `ENGATE_K`, `ROSCA_MACHO`, `RANHURADA`, `SOLDA`, `PONTA_LISA`
- `norma`: `NBR PN16`, `NBR PN25`, `ANSI 150`, `ANSI 300`, `EN PN10/16/40`,
  `K6/K8/K10/K12`, `PVC SOLDÁVEL`

### Linha
Sequência ordenada de peças. Entre duas peças consecutivas há uma **junção**,
que é calculada, não digitada.

## 3. Regras de montagem

### 3.1 Compatibilidade (`motor/regras.py::resolver_juncao`)

| situação | resultado |
|---|---|
| DN igual, tipo igual, norma igual | **junção direta** |
| DN diferente | **inserir redução** (concêntrica por padrão; excêntrica na sucção, junto à bomba, para não formar bolsa de ar) |
| DN igual, normas diferentes (`NBR PN16` × `ANSI 150`) | **inserir adaptador** — o catálogo tem 42 adaptadores exatamente para isso |
| DN igual, tipos diferentes (`FLANGE` × `ENGATE_K`) | **inserir adaptador FL × K** |

O motor nunca "conserta" em silêncio: ele insere a peça de transição e
registra o motivo, ou levanta o problema na tela.

### 3.2 Ferragem derivada (`motor/regras.py::ferragem_da_junta`)

Nenhum parafuso é digitado. Cada **junção flangeada** gera automaticamente:

```
1 × junta plana DN
n × parafuso  (n = nº de furos da norma/DN)
n × porca
2n × arruela
```

Comprimento do parafuso:

```
L ≥ 2 × esp_flange + esp_junta + 2 × arruela + altura_porca + folga
```

arredondado para cima até o comprimento de estoque
(2", 2¼", 2½", 3", 3½", 4", 4½", 5", 6", 7").

Junções por engate K, rosca ou solda **não** geram ferragem.

> **Pendência:** a tabela `data/regras_flange.csv` (furos, bitola, espessura de
> flange por norma/DN) está preenchida com valores de referência EN 1092-1 e
> marcada `homologado=NAO`. Precisa ser substituída pela tabela oficial antes de
> gerar proposta. É um CSV justamente para vocês editarem sem mexer em código.

### 3.3 Barra roscada
Ainda não modelada — falta definir em que casos entra (tirante de junta de
expansão? flange cega com derivação?). Ver seção 7.

## 4. Do desenho à geometria

Não é CAD. Cada peça tem comprimento face-a-face; curvas têm ângulo. A linha é a
soma vetorial ao longo do eixo:

```
posição_n+1 = posição_n + comprimento_n · (cos θ, sen θ)
θ += ângulo da curva
```

Isso já dá um esquema 2D em escala, com cotas, sem nenhuma engine de CAD.
Traçado em SVG: peça = símbolo + balão com o item da lista.

## 5. Do desenho à lista

`Linha.lista_materiais()` agrega por SAP e devolve exatamente as colunas da aba
**Orçamento** da planilha atual (`Área | Cód. SAP | Qtd`) — descrição, grupo e
procedência continuam vindo do `VLOOKUP` na aba `Materiais`. Ou seja: a saída do
programa entra na planilha que já existe, sem mudar o processo comercial.

## 6. Desenhos padrão (templates)

Achado importante no catálogo: os **manifolds já são desenhos padrão** —
`MNFD AZ D02 … D20`, 14 tipos, 148 itens. `D09` sozinho tem 43 variações de DN e
comprimento. Então o conceito de "desenho básico padrão" já existe na Netafim;
o programa só precisa formalizá-lo.

Um template é a mesma estrutura de `Linha`, com DN paramétrico:

```python
SUCCAO_CANAL = [
    ("CRIVO", {}),
    ("TUBO", {"comprimento_mm": 1000}),
    ("CURVA", {"angulo": 90}),
    ("TUBO", {"comprimento_mm": 3000}),
    ("CURVA", {"angulo": 45}),
    ("TUBO", {"comprimento_mm": 1500}),
    ("REDUCAO_EXCENTRICA", {"dn_saida": dn - 2}),
]
```

Escolhe o DN → o template se resolve inteiro contra o catálogo → sai a lista.
`tools/demo_succao.py` já faz isso.

## 7. Decisões em aberto

1. **Tabela de furação oficial** (furos, bitola, espessura de flange por
   norma/DN). Sem ela a ferragem é estimativa.
2. **Barra roscada**: em que montagens entra e com que critério de quantidade.
3. **Curva K vs. flangeada**: o engate K (K8/K10) aparece em 204 conexões.
   Ele dispensa ferragem? Leva anel/trava com código próprio?
4. **Plasson**: junta soldável não leva ferragem, mas o flange PVC (`FL CEGA
   3" (90)`, `FL CEGA 8" (225)`) leva. Confirmar bitola dos parafusos em PVC.
5. **Plataforma**: web local (TypeScript + SVG, roda no navegador, offline) ou
   desktop Python. Recomendação: web — o desenho é SVG puro e a exportação para
   XLSX/PDF é trivial.

## 8. Estado atual do código

```
tools/importar_catalogo.py   xlsx  -> data/catalogo_bruto.json   (5.157 itens)
tools/normalizar.py          texto -> data/catalogo.json         (peças paramétricas)
motor/catalogo.py            índice por (família, DN, norma)
motor/regras.py              compatibilidade + ferragem
motor/ferragem.py            resolve ferragem em código SAP
motor/linha.py               documento, comandos, junções, geometria, BOM
tools/demo_succao.py         demonstração ponta a ponta
```

Cobertura do parser no escopo de sucção/recalque (aço ≥ 3" e Plasson ≥ 75 mm):
**732 de 732 itens** com família identificada, 726 com conexões. Os 6 restantes
são manifolds com notação irregular (`FLE1`, `FLK10`).
