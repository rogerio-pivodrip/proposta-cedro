# Sucção & Recalque — desenho e lista sincronizados

Programa para montar linhas de sucção e recalque (aço zincado 3"–14" e Plasson
75–225 mm) a partir da lista de materiais Netafim, gerando desenho e lista de
materiais a partir de um único modelo.

A lógica completa está em [`docs/LOGICA.md`](docs/LOGICA.md).

## Conferir e regerar

```bash
python3 tools/conferir_tela.py     # o programa inteiro, num navegador de verdade
python3 tools/conferir_comandos.py # desfazer devolve o documento exato
python3 tools/conferir_bitola.py   # os três bugs de bitola, e o catálogo inteiro
python3 tools/conferir_pvc.py      # o desenho contra a folha da Plasson
python3 tools/conferir_motor.py    # o motor contra o DXF da W22
python3 tools/conferir_flanges.py  # a chapa da flange contra a folha Netafim
python3 tools/conferir_barra.py    # a barra digitada e o botão dão no mesmo
python3 tools/conferir_folha.py    # a escala da prancha é a maior que cabe
```

```bash
pip install openpyxl pypdf
python3 tools/importar_catalogo.py           # xlsx -> data/catalogo_bruto.json
python3 tools/normalizar.py                  # -> data/catalogo.json (peças paramétricas)
python3 tools/demo_succao.py 8               # monta uma sucção de 8" e emite a lista
python3 tools/extrair_lista_pdf.py x.pdf     # lista de peças de um PDF do CAD
python3 tools/casar_lista.py data/projetos/*.csv   # nome de desenho -> código SAP
```

## Rodar o programa

**Não precisa instalar nada.** O desenho, a lista e a tela são Python puro —
só a exportação precisa de biblioteca, e só na hora de exportar.

```bash
git clone -b claude/netafim-pecas-memorias-x9ayop \
    https://github.com/rogerio-pivodrip/proposta-cedro
cd proposta-cedro
python3 -m api.http --abrir          # abre o navegador no programa
```

Se aparecer "porta em uso", troque: `--porta 8770`.

Dois templates prontos: `montar succao 8` e `montar recalque 6`.

O **recalque** é o que fica depois do filtro, na ordem que a casa monta:
curva 90 · válvula hidráulica · tubo · hidrômetro · tubo · válvula de retenção ·
**tê de pé** · curva 90 · tubo 1 m. Os dois trechos de tubo são a única cota
calculada ali, e vêm em **diâmetros** — 10 D antes do hidrômetro e 5 D depois,
que é o que a medição pede. A barra escolhida é a menor da escada que **cobre**
o exigido: arredondar para a mais próxima poderia entregar 1 m onde a norma
pede 1,5.

O **tê fica de pé sobre a derivação**: a linha chega pela boca do meio, a de
cima recebe a flange cega com a luva de 2" da ventosa, e a de baixo desce para
a curva. É o único lugar do programa em que uma peça da corrente carrega outra
— a boca que sobra não continua a linha, **termina**, e o que fecha ela é um
**acessório**, não um ramo. Ele conta na lista como qualquer peça e sai junto
quando a peça que o carrega sai.

Na tela: escolha a bitola, **montar sucção** — ela nasce de pé, com o crivo no
fundo do poço — e daí em diante clique numa peça, no desenho ou na lista.

| o que fazer | como |
| --- | --- |
| ver de perto | roda do mouse, ou `+` `−`; `0` ou duplo clique volta ao enquadramento |
| mover a folha | arrastar o fundo |
| mudar a ordem | arrastar uma peça sobre outra — antes de soltar, o programa diz o que aconteceria |
| trocar a peça | selecionar e **trocar peça…**: o catálogo abre na família e bitola dela |
| virar uma peça | **⇅ espelhar** no painel — a curva que descia, sobe |
| girar o conjunto | **⟲ ⟳** na barra de cima |
| apagar | tecla `Delete`, o **×** na linha da lista, ou **remover** no painel |
| desfazer / refazer | `Ctrl+Z` e `Ctrl+Y` |
| tudo isso digitando | a **barra de comando**, no pé do desenho |
| fundo escuro | o **◐** no canto do desenho — como o espaço de modelo do CAD |
| a prancha | **folha**; na barra, `folha a4 retrato` |
| esticar um tubo | o **−  barra  +** no painel; na barra, `esticar` / `encolher` |
| trocar a leitura | **traço · P&B · metal** na barra de cima |

Girar é do conjunto e espelhar é da peça, e a diferença não é de interface: a
peça de uma linha **não tem posição própria** — ela cai onde a anterior deixou,
encadeada pelas portas. Girar uma peça no meio abriria a linha no ar. O que ela
tem é lado, e espelhar é trocá-lo; a pose (giro e espelho do conjunto) é do
documento, entra no desfazer e sai junto no DXF.

O zoom é da tela, e não do motor: o desenho continua saindo em milímetro real,
e ampliar mostra mais peça em vez de traço mais gordo.

### A folha de impressão

O programa já entregava DXF e planilha — os dois formatos de quem vai
**continuar trabalhando** no arquivo. A folha é o formato de quem vai
**assinar**: uma prancha em escala, com moldura, lista de materiais e carimbo,
que se imprime, se dobra e vai para a obra.

Três coisas a separam da vista de tela:

**A escala é nomeada.** Na tela o desenho é enquadrado — "o que couber" — e
isso está certo, porque a janela muda de tamanho. Numa folha impressa não
existe "o que couber": existe **1:25**, e quem mede com escalímetro tem de
achar a cota. Então a folha escolhe a maior escala da NBR 8196 em que o
desenho cabe e escreve qual foi no carimbo. `conferir_folha.py` cobra as duas
metades — que cabe *e* que a escala imediatamente maior estouraria; sem a
segunda, 1:1000 passaria em todo teste.

**A unidade é o milímetro de papel.** O `viewBox` da tela é em pixel; o da
folha é em milímetro, e a anotação encolhe junto — cota de 9 px na tela vira
2,7 mm no papel, que é a altura de escrita da ISO 3098.

**O formato e a moldura são da NBR 10068** — margem esquerda de 25 mm para
arquivar, as demais de 7 (até A2) ou 10 (A1 e A0), e a legenda de 178 mm no
canto inferior direito. Os 178 não são arbitrários: é a largura útil de uma A4
em pé, e a legenda é a mesma em todos os formatos.

No carimbo vai também **de onde vieram as cotas** — "3 estimativa · 2
IRRIGAFOUR". É informação de projeto: uma folha em que metade das cotas é
estimativa não vale o mesmo que uma em que todas são de fabricante, e quem
assina precisa ver isso sem abrir o programa.

A saída é HTML com `@page`, e não PDF: o navegador imprime, e o programa
continua rodando sem instalar nada.

### O fundo escuro

O **◐** troca o papel branco pelo escuro do espaço de modelo. É só uma troca
de tokens: o traço vira claro, o eixo continua vermelho — a convenção não muda
com a luz da sala — e os três modos continuam valendo por dentro.

Isto é da **tela** e não do documento, e por isso não tem verbo na barra nem
entra no desfazer: ninguém imprime branco sobre preto, e o SVG exportado e a
folha saem como papel, sempre.

### A barra de comando

Como no CAD: digita-se o verbo, os argumentos vêm atrás, e **o prefixo basta**
quando identifica um verbo só — `des` desfaz, `gir 90` gira. Qualquer letra
digitada na página cai na barra; `?` lista tudo.

```
montar succao 8          monta a sucção de pé
inserir curva 90 8       procura na lista e insere a que achou
comprimento 1500         muda a peça escolhida
modo metal · girar 90 · espelhar · exportar dxf
borboleta caixa 8        sem verbo: procura peça e oferece
```

Duas decisões que valem dizer:

**O vocabulário vem do motor**, uma vez, no arranque. A tela completa o que
você digita com essa lista — ela não tem lista própria, pelo mesmo motivo que
não tem cópia do documento: um verbo novo no motor aparece na barra sozinho, e
um verbo removido deixa de ser oferecido.

**A barra e o botão seguem o mesmo caminho.** `girar 90` digitado e o botão de
girar deixam o documento idêntico, histórico incluído — então um desfazer volta
igual dos dois lados. Uma segunda porta para os mesmos comandos é onde nascem
duas verdades, e `conferir_barra.py` cobra que não nasçam: ele compara os dois
caminhos e confere que **o exemplo de cada verbo funciona** — o exemplo é o que
a pessoa vai copiar, e um exemplo que não roda é pior que exemplo nenhum.

**O argumento vai pelo tipo, e não pela posição.** `montar succao 8` e
`montar 8 succao` são a mesma coisa, e `montar 8` também: o número é a bitola,
a palavra é o template, e o que falta cai no padrão.

Na busca, **número solto é bitola** e não pedaço de texto — procurar `curva 8`
por substring devolveria 18" e 20", e o código `01523-000048` na frente das
duas.

### Os três modos

O mesmo desenho, três leituras — e o que muda é **só a folha de estilo**: a
geometria é uma só, em milímetro real, e nenhum dos três redesenha nada.

- **traço** — o desenho de projeto: linha preta, eixo vermelho traço-ponto.
- **P&B** — tudo preto, para plotar e para fotocópia. O vermelho do eixo sai
  cinza numa impressora monocromática e some no meio do resto.
- **metal** — o corpo ganha o cilindro (claro em cima, escuro embaixo) e o
  equipamento sai na cor do fabricante: válvula de retenção, borboleta e
  hidráulica em azul, gaveta em cinza escuro, bomba KSB em azul médio, EBARA
  em cinza claro. A tubulação continua aço, e a ferragem da junção também —
  parafuso zincado não vai junto na pintura.

Quem pinta é a região entre as duas paredes da peça, e ela não estava
desenhada em lugar nenhum: um desenho de tubulação é feito de linhas, e entre
a parede de cima e a de baixo não havia figura para receber cor. O motor
reconhece o par de paredes de cada peça e fecha a região — uma vez, para as
1.636 peças, em vez de ensinar isso a vinte e cinco famílias. Ela não tem
traço e some nos outros dois modos; e fica fora do DXF, que é desenho de
linha.

O degradê corre **no sentido do eixo**: as faixas de luz e sombra são
paralelas ao eixo da peça, claras em cima e escuras embaixo, que é o desenho
de luz de um tubo redondo iluminado de cima. E o **reflexo acompanha a peça**
quando ela vira — numa linha de pé ele corre ao longo do tubo, e numa curva
de gomos cada gomo é um cilindro reto com o brilho no eixo dele, de modo que
o reflexo dá a volta em vez de atravessá-la.

O que **não** acompanha é o sentido: girar 180° ou espelhar poria o lado claro
para baixo, e peça nenhuma é iluminada por debaixo. A conta é uma só — para
onde aponta, na folha, o "para baixo" da peça — e quando ela aponta para cima
o degradê sai invertido de volta.

O SVG exportado sai no modo em que você está vendo. O DXF não tem modo: lá a
cor é da camada, e quem abre no CAD escolhe a pena — e nem a região nem a
hachura entram nele, que é desenho de linha.

Para ver as peças **separadas**, uma por célula, com código SAP e a cota de
cada uma:

```bash
python3 tools/desenhar_simbolos.py --dn 8 --modo metal > folha.html
```

### A medida do tubo bate com o código

O tubo é a única peça que se **corta** — o comprimento dela é decisão de
projeto, e não vem preso ao código. Por isso é a única que leva medida no
desenho, e a única que se estica.

**Esticar não é alterar, é substituir.** Um tubo de 8" de 1 m e um de 2 m são
dois códigos SAP diferentes na lista da Netafim: o comprimento não é um
parâmetro da mesma peça, é a peça. Então o id muda, como mudaria trocando a
peça à mão.

E os passos **vêm do que a lista tem** para aquele tubo, naquela bitola, com
aquelas pontas — em 8" flangeado são 0,5 · 1 · 1,2 · 1,5 · 2 · 2,5 · 3 · 6 m;
em K10 a lista não tem o 0,5 nem o 1,2, e aí o passo pula. Uma tabela fixa
ofereceria barra que ninguém vende. A ponta entra na conta junto com a bitola:
sem isso, esticar um tubo flangeado podia devolver uma barra de ponta lisa —
mesma bitola, mesmo comprimento, e nada onde parafusar.

**Cortar continua legítimo — calado é que não.** Para um comprimento que a
lista não tem (a barra de 6 m cortada em 2,35), o campo `comprimento` mantém o
código, e o documento passa a trazer a divergência: ela aparece em vermelho no
painel e vira aviso na folha — *"desenhado com 2,35 m, cortado da barra de 6 m
que o código traz"*. Sem isso o desenho vai para a obra dizendo 2,35 e a lista
vai para a compra dizendo 6, e as duas estão certas cada uma por si.

### A cota

Ela fica **no eixo da peça**, e o eixo abre para ela passar — as duas coisas
andam juntas: encostada no eixo sem aparo a cota fica ilegível, e fugindo do
eixo para o lado ela deixa de dizer a que peça pertence.

Duas correções que valem registrar, porque as duas eram invisíveis até o
desenho mudar de fundo:

**O aparo é um halo na letra, e não um retângulo atrás dela.** O retângulo era
pintado da cor do papel, e isso valia enquanto a cota caía sobre papel. No modo
metalizado ela passou a cair sobre o corpo **pintado**, e um retângulo cor de
papel em cima de metal claro virou um buraco — no fundo escuro, uma tarja preta
atravessada no desenho. O halo acompanha a letra: abre o eixo justo onde ela
passa e some no resto.

**A cota cai no meio do EIXO, e não no meio entre as duas portas.** Numa peça
reta é a mesma coisa. Numa curva não: o meio entre as portas cai na **corda**,
que passa por fora do tubo, e a cota ia parar no ar ao lado da peça. E o eixo
diz também a direção dele ali, que é como a cota sabe em que ângulo deitar —
numa curva ela acompanha a volta.

A **única marca no desenho é a peça selecionada**, e ela é o traço da própria
peça em azul — nenhum retângulo, nenhum contorno, nenhuma tarja por cima. O
eixo fica de fora: ele é vermelho por convenção e sai um pouco para além da
peça. O que a interface precisa dizer, ela diz no painel ao lado.

Para exportar DXF e planilha:

```bash
pip install -r requirements.txt      # ezdxf e openpyxl, só para exportar
```

Sem elas o programa roda igual e os botões de DXF e planilha dizem o que
falta instalar.

## O motor por fora

O motor é uma biblioteca: ele não sabe onde roda. Quem o expõe é a camada
`api/`, que traduz JSON em comando e devolve o documento inteiro recalculado —
e ela tem duas cascas sobre o mesmo núcleo:

```bash
python3 -m api.http --porta 8765   # abra http://127.0.0.1:8765 — o programa
python3 -m api.stdio               # um JSON por linha; é assim que o Electron fala
```

```bash
echo '{"nome":"template","template":"SUCCAO","dn":8}' | python3 -m api.stdio
```

Comandos: `inserir`, `remover`, `substituir`, `alterar`, `mover`, `desfazer`,
`refazer`, `template`, `catalogo`, `simular`, `exportar`, `documento`. Cada um
devolve `{"ok": …, "documento": {…}}` com as duas projeções — peças, geometria,
junções, lista de materiais e avisos.

Exporta em **DXF 1:1 em milímetro** (um bloco por código SAP, nas camadas do
desenho), **XLSX** nas colunas da aba Orçamento, SVG e CSV.

## Estrutura

| caminho | o que é |
|---|---|
| `data/LM_CANAL_REV1_JUL26.xlsx` | lista de materiais de origem (base jul/2026) |
| `data/regras_furacao.csv` | furação por norma e DN — NBR 7675 medida, EN e ANSI a homologar |
| `data/regras_ferragem.csv` | bitola e comprimento de parafuso por contexto de junta |
| `data/valvulas_wafer.csv` | ficha das válvulas wafer: corpo, furos, parafuso, prisioneiro |
| `data/fichas/` | fichas técnicas do fabricante que originaram as tabelas |
| `data/depara_nomes.csv` | vocabulário do desenho → vocabulário do catálogo |
| `data/projetos/` | listas de peças extraídas de projetos reais (casos de teste) |
| `tools/` | importação, normalização, extração de PDF, casamento, demonstração |
| `motor/` | catálogo indexado, regras de montagem, corte, tradução, modelo da linha |
| `api/` | camada fina: comando → documento. `nucleo.py` decide, `stdio.py` e `http.py` só transportam |
| `web/` | a tela: desenho em SVG à esquerda, lista de materiais à direita, o mesmo id nos dois |
