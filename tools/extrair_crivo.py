#!/usr/bin/env python3
"""Le a folha do crivo (pagina 14 do caderno Netafim).

Cabecalho: D L e k1 k2 k2 d - e as tres ultimas sao o que faz o crivo ser um
crivo e nao um tubo furado:

  D   diametro externo do cesto      k1  margem lisa antes do primeiro furo
  L   comprimento do cesto           k2  espacamento entre furos, nas duas
  e   parede da chapa                    direcoes - 3 mm em toda a folha
                                      d  diametro do furo - 6 mm em toda a folha

O fundo e chapa lisa: a vista inferior da folha diz isso e e o que separa o
crivo de um tubo aberto. A agua entra so pela parede.

Uso: python3 tools/extrair_crivo.py > data/crivos_netafim.csv
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

CADERNO = "data/fichas/NETAFIM_desenhos_tubos_conexoes_aco_PN16_rev20.pdf"
PAGINA = 14
N = r"(\d+(?:,\d+)?)"
RX = re.compile(rf'^{N}\s*\[(\d+)"\]\s+{N}\s+{N}\s+{N}\s+{N}\s+{N}\s+{N}\s+'
                r'FL\s+(NBR\s?7675\s+PN\s?16)\s+(\S+)')


def num(t):
    return float(t.replace(",", "."))


def main():
    pdf = pdfplumber.open(CADERNO)
    texto = pdf.pages[PAGINA - 1].extract_text() or ""
    campos = ["dn_pol", "d_externo_mm", "comprimento_mm", "parede_mm",
              "margem_mm", "passo_mm", "furo_mm", "fundo", "norma", "sap",
              "pagina"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    n = 0
    for linha in texto.splitlines():
        m = RX.match(linha.strip())
        if not m:
            continue
        g = m.groups()
        n += 1
        escritor.writerow({
            "dn_pol": g[1], "d_externo_mm": num(g[0]), "comprimento_mm": num(g[2]),
            "parede_mm": num(g[3]), "margem_mm": num(g[4]),
            "passo_mm": num(g[5]), "furo_mm": num(g[7]),
            "fundo": "CHAPA_LISA", "norma": "NBR 7675 PN16",
            "sap": "" if g[9] == "CADASTRAR" else g[9], "pagina": PAGINA})
    print(f"# {n} linhas lidas da pagina {PAGINA}", file=sys.stderr)


if __name__ == "__main__":
    main()
