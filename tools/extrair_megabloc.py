#!/usr/bin/env python3
"""Le a tabela de dimensoes da KSB Megabloc do manual tecnico A2744.

Substitui a transcricao a mao do folheto (tools/bombas_ksb.py), que fica como
segunda fonte. O manual e melhor por tres motivos: e extraivel, cota por
potencia de motor em vez de so por tamanho, e usa as letras da EN 733 - as
mesmas da Meganorm, o que liga as duas linhas sem tradutor:

  h1  do eixo a base            h2  do eixo a face do flange de descarga
  a   da face da succao ao eixo da descarga
  h   carcaca IEC do motor      l   comprimento do MOTOR

O folheto antigo chamava essas tres de a, b e c. Que sao a mesma coisa esta
conferido em 26 dos 28 tamanhos comuns - ver tools/conferir_bomba_ksb.py.

E o l NAO e o comprimento do conjunto, como parece: e o do motor. As colunas
da tabela se partem em duas metades pelo que as faz variar - umas dependem so
do tamanho da bomba, outras so da carcaca do motor - e l esta na segunda, com
um valor so por carcaca em 22 de 22. Ver tools/motores_iec.py.

O nome do tamanho aqui vem nos tres grupos da lista (050-032-200 = succao 50,
recalque 32, rotor 200), e nao nos dois do folheto antigo (32-200). Grava os
dois, porque a lista da casa usa o de tres e o folheto da Meganorm o de dois.

As demais letras (m1..m4, n1..n5, q, r1, s1, s2, t1, t2, b, w) sao a furacao
do pe e do motor. Vao gravadas com o nome da folha e nada mais - sem a figura
em resolucao maior nao da para afirmar qual e qual, e chutar isso e o que
essas tabelas existem para evitar.

Uso: python3 tools/extrair_megabloc.py > data/bombas_ksb_megabloc.csv
"""
import csv
import re
import sys
import types

for _m in ("cryptography", "cryptography.hazmat", "cryptography.hazmat.primitives",
           "cryptography.hazmat.primitives.ciphers", "cryptography.hazmat.backends",
           "cryptography.hazmat.primitives.ciphers.algorithms",
           "cryptography.hazmat.primitives.ciphers.modes"):
    sys.modules[_m] = types.ModuleType(_m)
sys.modules["cryptography.hazmat.primitives.ciphers"].Cipher = object
sys.modules["cryptography.hazmat.primitives.ciphers"].algorithms = object
sys.modules["cryptography.hazmat.primitives.ciphers"].modes = object
sys.modules["cryptography.hazmat.backends"].default_backend = lambda: None

import pdfplumber  # noqa: E402

MANUAL = "data/fichas/KSB_megabloc_manual_tecnico_A2744.pdf"
PAGINAS = {2: (8, 9), 4: (10, 11)}   # polos -> paginas do manual
FONTE = "KSB Megabloc manual tecnico A2744.0.3P/2, 60 Hz"
# o nome pode vir com o rodape "(1)" numa segunda linha da celula, e e esse
# marcador que diz que o flange e ANSI B16.1 250# FF em vez de 125# FF
RX_TAMANHO = re.compile(r"^(\d{3}-\d{3}-\d{3,4}(?:\.\d)?)\s*(\(1\))?$")
RX_LETRA = re.compile(r"^[a-z]\d?$")
# cotas que o desenho usa, com o nome que a folha da
PRINCIPAIS = ["h1", "h2", "a", "h", "l"]


def limpa(celula):
    return celula.replace("\n", "").strip() if celula else ""


def nome(celula):
    return (celula or "").replace("\n", " ").strip()


def numero(texto):
    texto = (texto or "").replace(",", ".")
    return texto if re.fullmatch(r"\d+(\.\d+)?", texto) else ""


def cabecalho(tabela):
    """A linha de letras da tabela -> {letra: indice da coluna}."""
    for linha in tabela:
        celulas = [limpa(c) for c in linha]
        if celulas.count("h1") == 1 and "h2" in celulas and "l" in celulas:
            return {c: i for i, c in enumerate(celulas) if RX_LETRA.fullmatch(c)}
    return {}


def ler(pdf, pagina, polos, letras_vistas):
    tabela = pdf.pages[pagina - 1].extract_table(
        {"vertical_strategy": "lines", "horizontal_strategy": "lines"})
    mapa = cabecalho(tabela or [])
    letras_vistas.update(mapa)
    tamanho = ""
    ansi250 = False
    fixo = {}
    for bruta in tabela or []:
        celulas = [limpa(c) for c in bruta]
        if not celulas:
            continue
        marca = RX_TAMANHO.fullmatch(nome(bruta[0]))
        if marca:
            tamanho = marca.group(1)
            ansi250 = bool(marca.group(2))
            fixo = {letra: numero(celulas[i]) for letra, i in mapa.items()
                    if i < len(celulas) and numero(celulas[i])}
            fixo["dn1"], fixo["dn2"] = celulas[1], celulas[2]
        if not tamanho or not celulas[3]:
            continue
        carcaca, cv, peso = celulas[3], numero(celulas[4]), numero(celulas[5])
        if not cv:
            continue
        linha = {"tamanho": tamanho,
                 "tamanho_folheto": "-".join(
                     [str(int(tamanho.split("-")[1])), tamanho.split("-")[2]]),
                 "polos": polos, "carcaca_motor": carcaca, "cv": cv,
                 "peso_kg": peso,
                 "dn_succao_pol": fixo.get("dn1", ""),
                 "dn_recalque_pol": fixo.get("dn2", ""),
                 "norma_flange": "ANSI 250" if ansi250 else "ANSI 125",
                 "fonte": FONTE}
        for letra, i in mapa.items():
            valor = numero(celulas[i]) if i < len(celulas) else ""
            linha[f"{letra}_mm"] = valor or fixo.get(letra, "")
        yield linha


def main():
    pdf = pdfplumber.open(MANUAL)
    letras = {}
    linhas = []
    for polos, paginas in sorted(PAGINAS.items()):
        for pagina in paginas:
            linhas += list(ler(pdf, pagina, polos, letras))
    ordem = ["tamanho", "tamanho_folheto", "polos", "dn_succao_pol",
             "dn_recalque_pol", "carcaca_motor", "cv", "peso_kg"]
    resto = PRINCIPAIS + sorted(l for l in letras if l not in PRINCIPAIS)
    campos = ordem + [f"{l}_mm" for l in resto] + ["norma_flange", "fonte"]
    escritor = csv.DictWriter(sys.stdout, campos, extrasaction="ignore")
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow(linha)
    tamanhos = len({ln["tamanho"] for ln in linhas})
    print(f"# {len(linhas)} linhas, {tamanhos} tamanhos", file=sys.stderr)


if __name__ == "__main__":
    main()
