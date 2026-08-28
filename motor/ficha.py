"""O que o programa SABE de uma peca, junto e com a fonte de cada coisa.

O motor sabe muito de cada peca - a furacao da flange, a espessura da chapa,
o parafuso que fecha a junta, o face a face da valvula, a folha de onde a cota
saiu - e ate aqui esse conhecimento so aparecia de esguelha: um pedaco no
desenho, outro num aviso da lista, outro em lugar nenhum. Quem escolhia a
peca na tela via o codigo e o comprimento, e mais nada.

**Cada linha da ficha diz de onde veio.** E a mesma regra da cota: folha de
fabricante, desenho de projeto, norma, estimativa - nesta ordem. Uma ficha que
mistura o que a folha diz com o que o programa supos vale menos que nenhuma,
porque quem le nao sabe em que confiar.

O que ela NAO faz e calcular coisa nova. Tudo aqui ja e sabido em outro lugar
do motor; esta funcao so vai buscar e nomeia.
"""
from . import cotas, pressao, regras


def _linha(rotulo, valor, fonte=None):
    return {"rotulo": rotulo, "valor": valor, "fonte": fonte}


def _bitola(dn, unidade="in"):
    if dn is None:
        return "—"
    return f'{dn:g}"' if unidade == "in" else f"DN{dn:g}"


def da_peca(peca, catalogo=None):
    """As linhas da ficha desta peca, na ordem em que se le."""
    item = peca.item
    unidade = peca.unidade_dn
    saida = [_linha("código", peca.sap, "lista"),
             _linha("família", (peca.familia or "—").replace("_", " ").lower())]
    if peca.material:
        saida.append(_linha("material", peca.material.replace("_", " ").lower()))
    saida += _classe(peca)
    saida += _bocas(peca, unidade)
    saida += _medida(peca)
    saida += _flanges(peca, unidade)
    saida += _por_familia(peca, unidade)
    return [l for l in saida if l["valor"] not in (None, "", "—")]


def _classe(peca):
    """Quanto a peca aguenta - e em que escala isso esta escrito.

    O rotulo do PVC de irrigacao sai com a conversao junto ("PN 80 (7.8 bar)")
    porque o numero cru engana: PN 80 num tubo de PVC e 80 metros de coluna
    d'agua, e nao 80 bar. Ver `motor/pressao.py`.
    """
    classe = peca.classe_pressao()
    if not classe:
        return []
    da_bomba = peca.familia == "BOMBA" and peca.flange_bomba
    return [_linha("classe de pressão", classe["rotulo"],
                   "flange pedida" if da_bomba else "lista")]


def _bocas(peca, unidade):
    """As pontas: bitola, tipo e NORMA de cada uma.

    A norma por face e o que separa a peca comum da peca especifica - na boca
    da bomba a linha corre em NBR e a maquina entrega ANSI, e e por isso que
    a casa compra reducao com uma face de cada. Ver docs/LOGICA.md 4.2.2.
    """
    portas = peca.portas or []
    if not portas:
        return []
    papeis = ("entrada", "saída") if len(portas) == 2 else \
        tuple(f"boca {i + 1}" for i in range(len(portas)))
    saida = []
    for papel, porta in zip(papeis, portas):
        tipo = (porta.get("tipo") or "").replace("_", " ").lower()
        norma = porta.get("norma")
        texto = f'{_bitola(porta.get("dn"), unidade)} {tipo}'.strip()
        if norma:
            texto += f" · {norma}"
        saida.append(_linha(papel, texto,
                            "folha da bomba" if peca.familia in
                            getattr(type(peca), "PELO_SIMBOLO", ()) else None))
    return saida


def _medida(peca):
    comp = peca.comprimento_mm or 0
    if not comp:
        return []
    do_codigo = peca.item.get("comprimento_mm")
    cortado = bool(do_codigo and abs(do_codigo - comp) > 1)
    # tubo cortado nao mede o que o codigo diz, e a fonte da medida passa a
    # ser o PROJETO - dizer "codigo" ali seria apontar para o numero que a
    # peca justamente nao tem
    fonte = ("projeto" if cortado else
             peca.fonte_cota or ("código" if do_codigo else "estimativa"))
    linhas = [_linha("face a face" if peca.familia != "TUBO" else "comprimento",
                     f"{comp:.0f} mm", fonte)]
    if cortado:
        # o corte e decisao de projeto, e a folha tem de dizer de que barra
        linhas.append(_linha("corte", f"da barra de {do_codigo/1000:g} m",
                             "projeto"))
    return linhas


def _flanges(peca, unidade):
    """A furacao da ponta flangeada, e o parafuso que fecha a junta."""
    from . import simbolos as s

    porta = next((p for p in (peca.portas or [])
                  if p.get("tipo") in regras.TIPOS_FLANGE), None)
    if porta is None or unidade != "in" or porta.get("dn") is None:
        return []
    dn = porta["dn"]
    norma = porta.get("norma") or "NBR PN16"
    furacao = regras.furacao(norma, dn)
    saida = []
    if furacao:
        saida.append(_linha("furação",
                            f"{furacao[0]} furos ⌀{furacao[1]:g} "
                            f"em ⌀{furacao[2]:g}", norma))
    # A CHAPA SO SAI QUANDO A FOLHA E DAQUELA NORMA. `s.flange` tira a
    # FURACAO da norma pedida, mas o externo e a espessura vem sempre da
    # folha Netafim, que e NBR: numa face ANSI isso seria a chapa errada
    # dita com cara de certa. Uma ANSI 150 de 6" e ⌀279,4 × 25,4, e nao a
    # ⌀285 × 16 da NBR. O desenho pode viver com isso (a chapa e a mesma no
    # traco); uma ficha que alguem le antes de comprar, nao.
    if norma.startswith("NBR"):
        try:
            chapa = s.flange(dn, norma)
        except Exception:                                   # noqa: BLE001
            chapa = None
        if chapa:
            saida.append(_linha(
                "flange", f'⌀{chapa["externo"]:g} × {chapa["espessura"]:g} mm',
                chapa.get("fonte")))
    else:
        saida.append(_linha("flange", "a casa não tem a folha desta norma",
                            None))
    try:
        parafuso = regras.parafuso_da_junta(dn, "AZ_AZ")
    except Exception:                                       # noqa: BLE001
        parafuso = None
    if parafuso:
        saida.append(_linha("parafuso da junta",
                            f'{parafuso["bitola_pol"]}" × '
                            f'{parafuso["comprimento_pol"]}"',
                            "regra da casa" if parafuso.get("homologado")
                            else "estimativa"))
    return saida


def _por_familia(peca, unidade):
    """O que so aquela familia tem."""
    familia = peca.familia
    if familia in getattr(type(peca), "PELO_SIMBOLO", ()):
        return _da_bomba(peca)
    if familia in regras.BARRAS_ROSCADAS_POR_PECA and unidade == "in":
        return _da_wafer(peca)
    if familia == "CURVA" and peca.angulo:
        return [_linha("ângulo", f"{peca.angulo:g}°", "lista")]
    return []


def _da_bomba(peca):
    ficha = regras.flange_da_bomba(peca.descricao)
    furacao = peca.flange_bomba or ficha["furacao"]
    origem = ficha["fonte"] or ("assumida" if not peca.flange_bomba
                                else "informada")
    # a CLASSE e da folha, e so vale enquanto a folha valer: dizer que a boca
    # veio EN PN16 e dizer que ela nao e a Classe 125 da folha
    classe = None if peca.flange_bomba else ficha["classe"]
    saida = [_linha("furação da boca",
                    furacao + (f" · {classe}" if classe else ""), origem)]
    # e a norma acompanha a furacao escolhida - com EN PN16 na boca, a norma
    # e a EN 1092-2, e nao a ASME B16.1 que a folha trazia
    norma = (regras.FURACOES_DE_BOMBA.get(furacao) if peca.flange_bomba
             else ficha["norma"])
    if norma:
        saida.append(_linha("norma do flange", norma, origem))
    bocas = [p["dn"] for p in (peca.portas or [])]
    if regras.pode_vir_roscada(bocas[0] if bocas else None, peca.descricao):
        saida.append(_linha("pode vir rosqueada", "BSP, conforme o pedido",
                            "KSB Megabloc A2744 nota 1"))
    return saida


def _da_wafer(peca):
    dn = peca.item["dn"][0] if peca.item["dn"] else None
    ficha = regras.ficha_wafer(dn) if dn else None
    if not ficha:
        return []
    saida = [
        _linha("aperto", f'{regras.BARRAS_ROSCADAS_POR_PECA[peca.familia]} '
                         f'barras roscadas de {ficha["bitola_pol"]}" · '
                         f'tirante de {ficha["comp_prisioneiro_mm"]:.0f} mm',
               "ficha MP"),
    ]
    # O TIRANTE FOI CALCULADO PARA O CORPO DA FICHA. Quando a valvula da
    # lista mede outra coisa - uma BRAY 250LB nao e a wafer da MP - o tirante
    # sai para a valvula errada, e isso tem de aparecer para quem le antes de
    # aparecer na obra, com a barra curta na mao
    corpo = peca.comprimento_mm or 0
    if corpo and abs(corpo - float(ficha["esp_corpo_mm"])) > 1:
        saida.append(_linha(
            "conferir", f'a ficha MP é de um corpo de '
                        f'{ficha["esp_corpo_mm"]:g} mm e esta válvula mede '
                        f"{corpo:.0f} - o tirante saiu pela ficha",
            "divergência"))
    return saida
