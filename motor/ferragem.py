"""Resolve os itens derivados (junta, parafuso, porca, arruela) em codigo SAP."""
import re
from fractions import Fraction


def _pol_texto(valor):
    """2.5 -> '2 1/2' ; 3 -> '3' ; 0.75 -> '3/4'."""
    fr = Fraction(valor).limit_denominator(16)
    inteiro, resto = divmod(fr, 1)
    if resto == 0:
        return str(int(inteiro))
    if inteiro == 0:
        return f"{resto.numerator}/{resto.denominator}"
    return f"{int(inteiro)} {resto.numerator}/{resto.denominator}"


def _procurar(catalogo, padrao):
    rx = re.compile(padrao, re.I)
    achados = [i for i in catalogo.itens if rx.search(i["descricao"])]
    achados.sort(key=lambda i: len(i["descricao"]))
    return achados[0] if achados else None


def resolver(catalogo, papel, esp):
    """(papel, especificacao) -> item do catalogo ou None."""
    if papel == "JUNTA_PLANA":
        dn = _pol_texto(esp["dn"]).replace(" ", "")
        return _procurar(catalogo, rf'^JUNTA PLANA\s+{re.escape(dn)}"')
    if papel == "PARAFUSO":
        bit = re.escape(esp["bitola_pol"]).replace(r"\ ", r"\s*")
        comp = re.escape(_pol_texto(esp["comprimento_pol"])).replace(r"\ ", r"\s*")
        return _procurar(catalogo, rf'^PARAFUSO SX AC UNC {bit}"\s*X\s*{comp}"')
    if papel == "PORCA":
        bit = re.escape(esp["bitola_pol"]).replace(r"\ ", r"\s*")
        return _procurar(catalogo, rf'^PORCA SX AC UNC {bit}"')
    if papel == "ARRUELA":
        bit = re.escape(esp["bitola_pol"]).replace(r"\ ", r"\s*")
        return _procurar(catalogo, rf'^ARRUELA LISA AC {bit}"')
    return None
