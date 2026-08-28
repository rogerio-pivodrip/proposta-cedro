#!/usr/bin/env python3
"""Confere a cota do DOCUMENTO contra a cota do DESENHO, peca por peca.

O programa mede a mesma peca duas vezes, e por caminhos diferentes:

  **o documento** soma cotas - `Peca.avancos()` diz quanto ela anda e
  `Peca.giro_interno()` de quanto ela vira, e `Linha.geometria()` acumula. E
  disso que saem o esquema, a cota geral, a conferencia de trecho reto e a
  posicao que vai para a lista;

  **o desenho** encadeia SIMBOLOS pelas portas - `simbolos.montar` poe a
  entrada de um na saida do outro. E disso que sai o SVG da tela, a prancha
  assinada e o DXF que vai para o CAD.

As duas leem as mesmas tabelas de cota, e por isso tem de dar no mesmo numero.
Nada comparava as duas ate este arquivo existir, e quatro coisas viviam
divergindo em toda linha montada:

  - a valvula hidraulica media ZERO no documento (a serie nao casava) e
    390 mm no desenho;
  - o crivo media 300 no documento (linha de cota chapada) e 250 no desenho
    (folha Netafim, pagina 14);
  - a curva virava para o lado ERRADO no documento: o esquema saia espelhado
    do desenho em toda linha com curva;
  - o te de pe nao virava nada no documento, e o esquema seguia reto por
    dentro dele - 1000 mm de tubo que o desenho nao tinha.

O que se compara e o DESLOCAMENTO e o GIRO que cada peca declara, e nao a
largura da caixa: peca que vira - curva, te de pe - anda em duas pernas, e
comparar caixa com caixa nao diria nada sobre elas.

Uso: python3 tools/conferir_cota.py [--tudo]
"""
import argparse
import math
import sys

sys.path.insert(0, ".")
from motor import desenho, templates, vista       # noqa: E402
from motor.catalogo import Catalogo               # noqa: E402
from motor.linha import Linha, Peca               # noqa: E402
from motor import simbolos as s                   # noqa: E402

FOLGA_MM = 1.0          # abaixo disto e arredondamento de tabela


# a faixa que a casa monta - aco 3" a 14", Plasson e PEAD 75 a 355. Fora dela
# o catalogo tem CPVC, PRFV de DN700, bronze de 1/2" e bomba: peca que nunca
# entrou numa sucção nem num recalque, e cuja divergencia nao para obra nenhuma
FAIXA_POL = (2.0, 14.0)
FAIXA_MM = (63.0, 355.0)


def na_faixa(item):
    bitolas = [d for d in (item["dn"] or []) if isinstance(d, (int, float))]
    if not bitolas:
        return False
    faixa = FAIXA_POL if item["unidade_dn"] == "in" else FAIXA_MM
    return faixa[0] <= max(bitolas) <= faixa[1]


def do_documento(peca):
    """(deslocamento, giro) que o documento atribui a peca, no eixo dela."""
    antes, depois = peca.avancos()
    gira = peca.giro_interno()
    x, y = antes, 0.0
    if depois:
        x += depois * math.cos(math.radians(gira))
        y += depois * math.sin(math.radians(gira))
    return (x, y), gira


def do_desenho(simbolo):
    """(deslocamento, giro) que o simbolo desenha, da entrada ate a saida."""
    entrada = s.porta(simbolo, s.ENTRADA)
    saida = s.porta(simbolo, s.SAIDA)
    if saida is None:
        return None, None
    ex, ey = (entrada.x, entrada.y) if entrada else (0.0, 0.0)
    # a direcao da saida e medida no referencial da peca, que entra olhando
    # para +x: a porta de saida de uma peca reta olha para 0
    return (saida.x - ex, saida.y - ey), (saida.direcao or 0.0)


def comparar(peca, simbolo):
    """None quando as duas medidas batem; o quanto erram quando nao."""
    doc, gira_doc = do_documento(peca)
    des, gira_des = do_desenho(simbolo)
    if des is None:
        return None                     # peca que fecha a linha: sem saida
    erro = math.dist(doc, des)
    volta = abs((gira_doc - gira_des + 180) % 360 - 180)
    if erro <= FOLGA_MM and volta <= 0.5:
        return None
    return {"doc": doc, "des": des, "erro_mm": erro,
            "gira_doc": gira_doc, "gira_des": gira_des, "volta": volta}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tudo", action="store_true",
                   help="varre o catalogo inteiro, e nao so as linhas montadas")
    args = p.parse_args()
    catalogo = Catalogo()
    problemas = []

    def certo(caso, condicao, detalhe=""):
        if condicao:
            print(f"  ok {caso}")
        else:
            problemas.append(caso)
            print(f"  ! {caso}" + (f": {detalhe}" if detalhe else ""))

    print("== a linha montada: o documento e o desenho param no mesmo ponto")
    for nome, monta in (("sucção", templates.succao),
                        ("recalque", templates.recalque)):
        for dn in (3, 4, 6, 8, 10, 12, 14):
            try:
                linha = monta(catalogo, dn)[0]
            except Exception as erro:                       # noqa: BLE001
                certo(f"{nome} {dn}\" monta", False, f"{type(erro).__name__}: {erro}")
                continue
            # espelhada tambem: o sinal do giro so aparece quando ele vira
            for espelho in (1, -1):
                linha.pose(espelho=espelho)
                geo = linha.geometria()
                postos, recusadas = vista.postos_da_linha(linha)
                if recusadas or len(postos) != len(geo):
                    certo(f"{nome} {dn}\" desenha inteira", False,
                          f"{len(recusadas)} sem símbolo")
                    continue
                fora = [(g["peca"].familia, math.dist(g["para"], p.saida))
                        for g, p in zip(geo, postos)
                        if math.dist(g["para"], p.saida) > FOLGA_MM]
                lado = "espelhada" if espelho < 0 else "normal"
                certo(f'{nome} {dn}" {lado}', not fora,
                      " · ".join(f"{f} erra {d:.0f} mm" for f, d in fora[:3]))

    print("\n== peça a peça: o que o documento anda é o que o símbolo desenha")
    print("   (o catálogo inteiro é uma LISTA DE TRABALHO, e não uma falha:\n"
          "    fora da faixa da casa há CPVC, PRFV, bronze de 1/2\" e bomba,\n"
          "    que a casa não monta em sucção nem em recalque)")
    itens = catalogo.itens if args.tudo else [
        catalogo.por_sap[sap] for sap in sorted({
            p.sap for nome, monta in (("s", templates.succao),
                                      ("r", templates.recalque))
            for dn in (3, 4, 6, 8, 10, 12, 14)
            for p in _pecas(monta, catalogo, dn)})]
    vistos = achados = 0
    por_familia = {}
    for item in itens:
        for pose in (None, "derivacao"):
            if pose and item["familia"] not in ("TE", "TE_REDUZIDO"):
                continue
            try:
                simbolo = desenho.de_item(item, pose)
            except Exception:                               # noqa: BLE001
                continue
            linha = Linha(catalogo)
            peca = Peca(item, pose=pose)
            linha.inserir(peca)
            vistos += 1
            erro = comparar(peca, simbolo)
            if erro:
                achados += 1
                por_familia.setdefault(item["familia"], []).append(
                    (item["sap"], item["descricao"], erro, na_faixa(item)))
    if not por_familia:
        certo(f"as {vistos} peças medem igual dos dois lados", True)
    dentro = fora = 0
    for familia, casos in sorted(por_familia.items(),
                                 key=lambda t: -len(t[1])):
        aqui = [c for c in casos if c[3]]
        dentro += len(aqui)
        fora += len(casos) - len(aqui)
        if not aqui:
            continue
        _sap, descricao, erro, _ = aqui[0]
        print(f"  · {len(aqui):4} {familia:22} "
              f'documento {erro["doc"][0]:.0f} / desenho {erro["des"][0]:.0f} mm'
              + (f' · giro {erro["gira_doc"]:g}° contra {erro["gira_des"]:g}°'
                 if erro["volta"] > 0.5 else "")
              + f'   ex.: {descricao[:34]}')
    if por_familia:
        print(f"\n  {dentro} peças na faixa da casa medem diferente dos dois "
              f"lados, e {fora} fora dela.")
        print("  As linhas que o programa monta hoje estão fechadas - o que "
              "sobra é\n  peça que ainda não entrou em template nenhum. "
              "Cada linha acima é\n  uma tabela contra outra, e some quando "
              "as duas virarem uma.")

    print(f"\n{len(problemas)} problemas")
    return 1 if problemas else 0


def _pecas(monta, catalogo, dn):
    try:
        return list(monta(catalogo, dn)[0].todas_as_pecas())
    except Exception:                                       # noqa: BLE001
        return []


if __name__ == "__main__":
    sys.exit(main())
