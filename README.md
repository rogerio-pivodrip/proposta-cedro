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

Girar é do conjunto e espelhar é da peça, e a diferença não é de interface: a
peça de uma linha **não tem posição própria** — ela cai onde a anterior deixou,
encadeada pelas portas. Girar uma peça no meio abriria a linha no ar. O que ela
tem é lado, e espelhar é trocá-lo; a pose (giro e espelho do conjunto) é do
documento, entra no desfazer e sai junto no DXF.

O zoom é da tela, e não do motor: o desenho continua saindo em milímetro real,
e ampliar mostra mais peça em vez de traço mais gordo.

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
