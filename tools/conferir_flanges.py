#!/usr/bin/env python3
"""Confere a flange que o programa DESENHA contra as folhas que ele tem.

A flange e a peca mais repetida do desenho - cada junta tem duas - e e a que
tem menos margem para errar: o externo decide a altura de quase toda peca na
vista lateral, e a espessura decide o comprimento do parafuso que entra na
lista de materiais. Errar 10% no externo nao aparece olhando; errar a
espessura aparece na obra.

Tres perguntas, e cada uma tem uma resposta separada:

  **De onde veio o externo?** Folha de fabricante, catalogo, ou estimativa. A
  estimativa e `DE_TUBO * 1,7`, um chute que serve para nao deixar buraco no
  desenho - e a coluna diz onde ele ainda esta em uso.

  **A espessura bate com a folha?** A folha Netafim cota a chapa: 16 mm ate
  10", 21 ate 16", 27,5 acima. A tabela da MP cota outra coisa - a flange
  INTEGRAL de uma valvula de ferro fundido, que e mais grossa. Sao duas pecas
  diferentes com o mesmo nome, e misturar as duas engorda a flange solta.

  **A furacao bate com a norma?** Circulo, quantidade e diametro do furo.
  Aqui a folha Netafim e a NBR da casa DISCORDAM de 10" para cima - o caderno
  desenha EN PN16 e a tabela e NBR. Isso nao e defeito deste programa e nao se
  conserta aqui: quem compra pela NBR e monta contra peca Netafim nao fecha o
  parafuso. Ver tools/conferir_flanges_netafim.py.

Uso: python3 tools/conferir_flanges.py
"""
import csv
import sys

sys.path.insert(0, ".")
from motor import simbolos as s                      # noqa: E402

BITOLAS = (1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 24)
# fios por polegada da rosca UNC, para dizer a sobra em FIOS e nao so em mm -
# dois fios aparentes e o minimo de aperto com garantia, e dois fios de 5/8"
# nao sao o mesmo tanto de milimetro que dois fios de 1 1/8"
_TPI = {"3/8": 16, "1/2": 13, "5/8": 11, "3/4": 10, "7/8": 9, "1": 8,
        "1 1/8": 7, "1 1/4": 7}
TOLERANCIA = 0.6            # mm: a folha cota em milimetro inteiro


def _mdc(a, b):
    while b:
        a, b = b, a % b
    return a


def folhas():
    netafim, irrigafour = {}, {}
    with open("data/flanges_netafim.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["tipo"] == "SOLDAR":
                netafim[float(r["dn_pol"])] = r
    with open("data/flanges_irrigafour.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["norma"] == "DIN 2533 PN 16":
                irrigafour[float(r["dn_pol"])] = r
    return netafim, irrigafour


def main():
    netafim, irrigafour = folhas()
    problemas, estimadas, divergem = [], [], []

    print("== o que o programa desenha, e de onde veio")
    print(f'{"pol":>5}  {"externo":>7} {"folha":>6} {"cat.":>6}  '
          f'{"esp":>5} {"folha":>6}  {"circulo":>7} {"furos":>7}  fonte')
    for dn in BITOLAS:
        f = s.flange(dn)
        n, i = netafim.get(dn), irrigafour.get(dn)
        e_folha = float(n["d_externo_mm"]) if n else None
        e_cat = float(i["d_externo_mm"]) if i else None
        t_folha = float(n["esp_mm"]) if n else None
        print(f'{dn:>5g}  {f["externo"]:>7.0f} '
              f'{e_folha if e_folha else 0:>6.0f} {e_cat if e_cat else 0:>6.0f}  '
              f'{f["espessura"]:>5.1f} {t_folha if t_folha else 0:>6.1f}  '
              f'{f["circulo"]:>7.0f} {f["furos"]:>3g}x{f["furo"]:>3.0f}  '
              f'{f["fonte"]}')
        if f["fonte"] == "estimativa":
            estimadas.append(dn)
        if e_folha and abs(f["externo"] - e_folha) > TOLERANCIA:
            problemas.append(f'{dn:g}" externo {f["externo"]:.0f} '
                             f'contra {e_folha:.0f} da folha')
        if t_folha and abs(f["espessura"] - t_folha) > TOLERANCIA:
            problemas.append(f'{dn:g}" espessura {f["espessura"]:.1f} '
                             f'contra {t_folha:.1f} da folha')
        if e_folha and e_cat and abs(e_folha - e_cat) > TOLERANCIA:
            divergem.append((dn, e_folha, e_cat))

    print("\n== a norma pedida e a norma entregue")
    # o cache era um so, montado com a norma da PRIMEIRA chamada. Este caso
    # cobra que pedir ANSI nao envenene a NBR seguinte
    ansi = s.flange(8, "ANSI 150")
    nbr = s.flange(8, "NBR PN16")
    if ansi["furos"] == nbr["furos"] and ansi["circulo"] == nbr["circulo"]:
        problemas.append("ANSI 150 e NBR PN16 devolvem a MESMA furação em 8\" "
                         "- o cache está compartilhado entre normas")
        print("  ! ANSI 150 e NBR PN16 dão a mesma furação em 8\"")
    else:
        print(f'  ok 8" ANSI 150 = {ansi["furos"]}x{ansi["furo"]:.0f} em '
              f'{ansi["circulo"]:.1f} · NBR PN16 = {nbr["furos"]}x'
              f'{nbr["furo"]:.0f} em {nbr["circulo"]:.0f}')

    print("\n== a junta desenhada e a chapa da folha")
    # a junta flangeada desenha DUAS chapas encostadas: o vao entre as faces
    # das duas pecas tem de ser duas espessuras, nem mais nem menos
    for dn in (3, 8, 14):
        f = s.flange(dn)
        placa = s.placa(0, dn)
        alto = max(e["h"] for e in placa if e["tipo"] == "rect")
        largo = max(e["w"] for e in placa if e["tipo"] == "rect")
        ok_alto = abs(alto - f["externo"]) < TOLERANCIA
        ok_largo = abs(largo - f["espessura"]) < TOLERANCIA
        marca = "ok" if ok_alto and ok_largo else " !"
        print(f'  {marca} {dn:g}" a chapa desenhada mede '
              f'{largo:.1f} x {alto:.0f} mm '
              f'(folha: {f["espessura"]:.1f} x {f["externo"]:.0f})')
        if not (ok_alto and ok_largo):
            problemas.append(f'{dn:g}" a chapa desenhada não é a da ficha')

    print("\n== o parafuso da tabela fecha a junta?")
    # o desenho saiu em escala de verdade - o parafuso no comprimento do codigo
    # que a lista compra - e escala de verdade da para MEDIR.
    #
    # E "a junta" nao e sempre duas chapas: a ponta Plasson e feita de DUAS
    # pecas (o colar 5510, com ressalto B, e a flange solta 5900, de espessura
    # H), entao um encontro Plasson-Plasson tem QUATRO camadas. Enquanto a
    # folha da Plasson nao estava ligada, esses casos nao eram mensuraveis e o
    # programa se calava; agora eles entram aqui junto com o aco.
    from motor import regras                            # noqa: E402
    curtos = []
    for contexto in ("AZ_AZ", "ACO_PLASSON", "PLASSON_PLASSON"):
        print(f"  · {contexto}")
        for dn in BITOLAS:
            aperto = regras.aperto_da_junta(dn, contexto)
            if not aperto:
                continue
            ficha = regras.parafuso_da_junta(dn, contexto)
            meio = aperto["mm"] / 2
            _el, sobra = s.parafuso_sextavado(
                -meio, meio, 0.0, ficha["bitola_mm"], ficha["comprimento_mm"])
            fios = sobra / (25.4 / _TPI[ficha["bitola_pol"]])
            marca = "ok" if fios >= 2 else " !"
            pilha = " + ".join(f"{v:.0f}" for _n, v in aperto["camadas"])
            print(f'    {marca} {dn:>4g}"  {pilha:>18} = {aperto["mm"]:>3.0f}  '
                  f'{ficha["bitola_pol"]}" x {ficha["comprimento_pol"]}"  '
                  f'→ sobra {sobra:+5.1f} mm ({fios:.1f} fios)')
            if fios < 2:
                curtos.append(f'{contexto} {dn:g}"')
    if curtos:
        print("     ↑ estas o programa AVISA, e não conserta: a tabela de "
              "ferragem é regra da casa.\n"
              "       " + ", ".join(curtos)
              + " pedem um parafuso mais longo.")

    print("\n== a furação da flange solta Plasson e a da linha de aço")
    # As duas tem de casar: numa junta aço-Plasson o parafuso passa pelos dois
    # furos ao mesmo tempo. Em vez de comparar so contra o DN que a conversao
    # de bitola aponta, aqui se procura em TODA a tabela NBR qual DN tem aquela
    # furacao - assim "d50 é furado como DN40" sai como informacao, e o que
    # sobra sem par e o que merece bandeira.
    from motor import bitola as _bitola                  # noqa: E402
    from motor import cotas as _cotas                    # noqa: E402
    nbr = {dn: reg for (norma, dn), reg in regras.FUROS.items()
           if norma == "NBR PN16"}
    # as bitolas que a CASA compra em Plasson (motor/bitola.LINHA_PLASSON, em
    # DN nominal) - o resto da folha existe mas nao entra em montagem daqui
    da_casa = {_bitola.METRICO.get(dn) for dn in _bitola.LINHA_PLASSON}
    orfas = []
    print(f'  {"d":>5} {"casa":>5}  {"plasson":>16}  qual DN de aço tem essa furação')
    for d in _cotas.bitolas_flangeadas_plasson():
        par = _cotas.par_flangeado_plasson(d)
        igual = [dn for dn, reg in sorted(nbr.items())
                 if abs(par["circulo"] - reg["circulo_mm"]) <= 2
                 and par["furo"] == reg["furo_mm"]
                 and par["furos"] == reg["furos"]]
        usada = d in da_casa
        desenho = f'{par["furos"]}x{par["furo"]:.0f} em {par["circulo"]:.0f}'
        if igual:
            resposta = ", ".join(f"DN{dn:g}" for dn in igual)
        else:
            resposta = "NENHUM"
            if usada:
                orfas.append((d, par))
        print(f'  {"!" if (usada and not igual) else " "} {d:>3g} '
              f'{"sim" if usada else "-":>5}  {desenho:>16}  {resposta}')
    if orfas:
        for d, par in orfas:
            pol = _bitola.em_polegada(d, "mm")
            aco = nbr.get(_bitola.nominal(d, "mm"))
            print(f'\n  ! a flange solta Plasson d{d:g} não casa com nenhuma\n'
                  f'    flange de aço da tabela. Ela tem {par["furos"]}x'
                  f'{par["furo"]:.0f} em {par["circulo"]:.0f}; o {pol:g}" de aço\n'
                  f'    tem {aco["furos"]}x{aco["furo_mm"]:.0f} em '
                  f'{aco["circulo_mm"]:.0f} - mesmo furo e quase o mesmo\n'
                  f'    círculo, mas {aco["furos"]} furos contra '
                  f'{par["furos"]}, e só {_mdc(par["furos"], aco["furos"])}\n'
                  f'    das posições coincidem.')
        print("\n    Isto NÃO se conserta aqui, do mesmo jeito que a folha\n"
              "    Netafim contra a NBR: é uma pergunta para quem compra. A\n"
              "    lista continua comprando pela furação de aço, que tem MAIS\n"
              "    furos - comprar parafuso a mais é barato, comprar a menos\n"
              "    deixa a junta sem parafuso.")
    else:
        print("\n  ok toda flange Plasson que a casa compra casa com uma de aço")

    print("\n== toda linha da tabela de ferragem tem codigo na lista")
    # A tabela e regra da casa, mas ela COMPRA - e nao adianta a regra pedir
    # 7/8" x 4 1/2" se a lista so tem 4" e 5". Um comprimento que nao existe
    # so aparece quando alguem vai comprar, e ai o desenho ja saiu. Aqui cada
    # linha da csv e resolvida em SAP como a lista de materiais resolve.
    from motor import ferragem                          # noqa: E402
    from motor.catalogo import Catalogo                 # noqa: E402
    cat = Catalogo()
    sem_codigo = []
    for contexto, faixas in sorted(regras.FERRAGENS.items()):
        for faixa in faixas:
            bit, comp = faixa["bitola_pol"], faixa["comprimento_pol"]
            achados = {
                "PARAFUSO": ferragem.resolver(
                    cat, "PARAFUSO",
                    {"bitola_pol": bit, "comprimento_pol": comp}),
                "PORCA": ferragem.resolver(cat, "PORCA", {"bitola_pol": bit}),
                "ARRUELA": ferragem.resolver(cat, "ARRUELA",
                                             {"bitola_pol": bit}),
            }
            faltam = [papel for papel, item in achados.items() if not item]
            marca = " !" if faltam else "ok"
            saps = " ".join(i["sap"] for i in achados.values() if i)
            print(f'  {marca} {contexto:>16} ate {faixa["dn_max"]:>4g}   '
                  f'{bit}" x {comp}"  {saps}'
                  + (f'  SEM CODIGO: {", ".join(faltam)}' if faltam else ""))
            if faltam:
                sem_codigo.append(f'{contexto} ate {faixa["dn_max"]:g}": '
                                  f'{bit}" x {comp}" não tem '
                                  + ", ".join(faltam) + " na lista")
    problemas.extend(sem_codigo)

    print("\n== o desenho e a lista contam a mesma arruela")
    desenhado = sum(1 for e in s.parafuso_sextavado(-16, 16, 0, 19.05, 63.5)[0]
                    if e.get("classe") == "arruela")
    da_lista = next(q for papel, _e, q in regras.ferragem_da_junta(8, "NBR PN16")
                    if papel == "ARRUELA")
    furos = s.flange(8)["furos"]
    if desenhado * furos == da_lista:
        print(f"  ok {desenhado} arruela por parafuso, no desenho e na compra "
              f"({da_lista} numa junta de 8\")")
    else:
        problemas.append("o desenho e a lista contam arruelas diferentes")
        print(f"  ! o desenho poe {desenhado} por parafuso "
              f"({desenhado * furos} na junta) e a lista compra {da_lista}")

    if divergem:
        print("\n== onde a folha e o catálogo discordam")
        for dn, e_folha, e_cat in divergem:
            print(f'  · {dn:g}"  folha Netafim {e_folha:.0f}  ·  '
                  f'catálogo Irrigafour {e_cat:.0f}  → o desenho usa a folha')

    if estimadas:
        print(f'\n{len(estimadas)} bitolas sem folha, no chute de DE_TUBO*1,7: '
              + ", ".join(f'{d:g}"' for d in estimadas))

    print(f"\n{len(problemas)} problemas")
    for p in problemas:
        print(f"  ! {p}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
