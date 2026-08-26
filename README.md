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
