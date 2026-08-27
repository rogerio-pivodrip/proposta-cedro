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

## 4. O que a peça puxa: um mecanismo só

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

## 5. O catálogo tem dois modos, e isso precisa ser explícito

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

## 6. Ordem de implementação

1. **`Bitola`** — é a base de tudo e a fonte de mais bugs.
2. **Gabarito por família** — dá topologia a 340 itens que hoje têm uma lista.
3. **Negociação com quatro saídas** — inclui a troca de peça.
4. **`derivar()` unificado** — junta o que está espalhado.
5. **Modo do catálogo explícito** — encerra a busca que traz a coisa errada.

Nada disso muda as regras de montagem já levantadas. Muda onde elas moram.

## 7. Desktop ou web?

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
