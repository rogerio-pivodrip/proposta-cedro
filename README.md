# Sucção & Recalque — desenho e lista sincronizados

Programa para montar linhas de sucção e recalque (aço zincado 3"–14" e Plasson
75–225 mm) a partir da lista de materiais Netafim, gerando desenho e lista de
materiais a partir de um único modelo.

A lógica completa está em [`docs/LOGICA.md`](docs/LOGICA.md).

## Rodar

```bash
pip install openpyxl pypdf
python3 tools/importar_catalogo.py           # xlsx -> data/catalogo_bruto.json
python3 tools/normalizar.py                  # -> data/catalogo.json (peças paramétricas)
python3 tools/demo_succao.py 8               # monta uma sucção de 8" e emite a lista
python3 tools/extrair_lista_pdf.py x.pdf     # lista de peças de um PDF do CAD
python3 tools/casar_lista.py data/projetos/*.csv   # nome de desenho -> código SAP
```

## O programa

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
`refazer`, `template`, `catalogo`, `documento`. Cada um devolve
`{"ok": …, "documento": {…}}` com as duas projeções — peças, geometria,
junções, lista de materiais e avisos.

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
