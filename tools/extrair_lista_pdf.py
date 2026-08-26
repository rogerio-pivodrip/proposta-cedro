#!/usr/bin/env python3
"""Extrai a "Lista de pecas" dos PDFs de casa de maquinas gerados pelo CAD.

Os PDFs do SolidWorks trazem a tabela como texto, entao da para ler o acervo de
projetos ja desenhados sem redigitar nada.

Uso: python3 tools/extrair_lista_pdf.py arquivo.pdf [outro.pdf ...]
"""
import csv
import re
import sys
import types

# a lib cryptography do ambiente esta quebrada e o pypdf so a usa em PDF cifrado
sys.modules.setdefault("cryptography", types.ModuleType("cryptography"))
from pypdf import PdfReader  # noqa: E402

RX_LINHA = re.compile(r"^(\d{1,3})\s+(.+?)\s+(\d{1,4})$")
RX_CABECALHO = re.compile(r"Item\s+N", re.I)
RX_META = re.compile(r"^(CLIENTE|DESENHO|PROJETISTA|VENDEDOR|DATA|ESCALA|FOLHA):", re.I)


def extrair(caminho):
    leitor = PdfReader(caminho)
    itens, cabecalho = [], False
    meta = {}
    for pagina in leitor.pages:
        linhas = (pagina.extract_text() or "").splitlines()
        for i, bruta in enumerate(linhas):
            linha = bruta.strip()
            if RX_CABECALHO.search(linha):
                cabecalho = True
                continue
            if not cabecalho:
                continue
            m = RX_LINHA.match(linha)
            if m:
                nome = m.group(2).strip()
                # a regua da moldura do desenho ("21 3 4 5 ... 16") casa com o
                # padrao de linha da tabela; nome de peca sempre tem letra
                if len(nome) > 2 and not RX_META.match(nome) \
                        and re.search(r"[A-Za-z]", nome):
                    itens.append({"item": int(m.group(1)), "nome_peca": nome,
                                  "qtd": int(m.group(3))})
            elif linha and not linha.isdigit() and len(itens) > 3:
                cabecalho = False   # a tabela acabou
    return itens, meta


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for caminho in sys.argv[1:]:
        itens, _ = extrair(caminho)
        nome_curto = caminho.split("/")[-1]
        print(f"# {nome_curto}: {len(itens)} itens")
        escritor = csv.DictWriter(sys.stdout, fieldnames=["item", "nome_peca", "qtd"])
        escritor.writeheader()
        escritor.writerows(itens)


if __name__ == "__main__":
    main()
