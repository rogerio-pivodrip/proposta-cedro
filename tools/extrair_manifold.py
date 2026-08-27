#!/usr/bin/env python3
"""Le a folha do manifold (pagina 25 do caderno Netafim).

O cabecalho da folha e D L1 R F1 F2 F3 F4 G1 G2 G3 G4 e J1 J2 J3 J4 e2
X1 X2 X3 X4, e nem toda coluna serve para a vista lateral:

  D   diametro externo do corpo          J1  bitola da derivacao
  L1  comprimento do corpo               J2  raio do furo na parede
  e   parede do corpo                    J3  norma da flange da derivacao
  F1  a luva de ventosa - 2" BSP          J4  comprimento do pescoco
  F3  comprimento da luva (30)           e2  parede da derivacao
  F4  externo da luva (40)               G1..G4  a segunda luva, igual

G2 e a altura do topo da luva acima do eixo e sai de D/2 + 40 em todas as
bitolas da folha - conferido de 4" a 14". F2 e R sao alturas maiores, ligadas
entre si por F2 = (R + D/2)/2, mas sem a folha em imagem nao da para dizer o
que cada uma mede; ficam gravadas na tabela e fora do desenho. X1 a X4 sao o
gabarito da boca de lobo nos angulos 0, 15, 30 e 45 - servem ao caldeireiro,
nao a vista lateral.

Uso: python3 tools/extrair_manifold.py > data/manifold_netafim.csv
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
PAGINA = 25
DERIVACAO = "D02"     # o titulo da folha: Manifold AZ Des 02 __" K10 c/ LV __"

N = r"(\d+(?:,\d+)?)"
RX = re.compile(
    rf'^{N}\s*\[(\d+)"\]\s+'          # D e a bitola do corpo
    rf'{N}\s+{N}\s+'                  # L1 R
    rf'(2"\s?bsp)\s+{N}\s+{N}\s+{N}\s+'   # F1 F2 F3 F4
    rf'(2"\s?bsp)\s+{N}\s+{N}\s+{N}\s+'   # G1 G2 G3 G4
    rf'{N}\s+'                        # e
    rf'{N}\s*\[(\d+)"\]\s+{N}\s+'     # J1 (mm, pol) J2
    r'(NBR\s?7675\s?PN\s?16)\s+'      # J3
    rf'{N}\s+{N}\s+'                  # J4 e2
    rf'{N}\s+{N}\s+{N}\s+{N}',        # X1..X4
    re.I)


def num(t):
    return float(t.replace(",", "."))


def main():
    pdf = pdfplumber.open(CADERNO)
    texto = pdf.pages[PAGINA - 1].extract_text() or ""
    campos = ["derivacao", "dn_pol", "d_externo_mm", "comprimento_mm",
              "parede_mm", "luvas_ventosa", "luva_pol", "luva_comp_mm",
              "luva_externo_mm", "luva_altura_mm", "derivacao_pol",
              "derivacao_mm", "derivacao_pescoco_mm", "derivacao_parede_mm",
              "derivacao_norma", "r_mm", "f2_mm", "pagina"]
    escritor = csv.DictWriter(sys.stdout, campos)
    escritor.writeheader()
    achou = 0
    for linha in texto.splitlines():
        m = RX.match(linha.strip())
        if not m:
            continue
        g = m.groups()
        achou += 1
        escritor.writerow({
            "derivacao": DERIVACAO, "dn_pol": g[1], "d_externo_mm": num(g[0]),
            "comprimento_mm": num(g[2]), "parede_mm": num(g[12]),
            "luvas_ventosa": 2, "luva_pol": 2, "luva_comp_mm": num(g[6]),
            "luva_externo_mm": num(g[7]), "luva_altura_mm": num(g[9]),
            "derivacao_pol": g[14], "derivacao_mm": num(g[13]),
            "derivacao_pescoco_mm": num(g[17]), "derivacao_parede_mm": num(g[18]),
            "derivacao_norma": "NBR 7675 PN16",
            "r_mm": num(g[3]), "f2_mm": num(g[5]), "pagina": PAGINA})
    print(f"# {achou} linhas lidas da pagina {PAGINA}", file=sys.stderr)


if __name__ == "__main__":
    main()
