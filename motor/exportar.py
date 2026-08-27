"""O que sai do programa: DXF, planilha e SVG - todos do mesmo documento.

Devolve CONTEUDO e nao caminho. No navegador o conteudo vira um download; no
Electron o processo pai escolhe onde salvar. Gravar aqui obrigaria a inventar
uma pasta, e a pasta e de quem usa.

Duas coisas que valem dizer sobre escala:

**O DXF sai 1:1 em milimetro.** A geometria dos simbolos ja e em milimetro
real - e a vista da tela que e escalada, dentro de um <g transform="scale()">.
Entao exportar nao converte nada: e a mesma geometria, sem o escalonamento da
tela. Quem abre no CAD mede a peca e acha a cota do fabricante.

**A planilha sai nas colunas da aba Orcamento** - Area, Cod. SAP, Qtd - que e o
que o comercial da casa ja usa. Ver docs/LOGICA.md 1: os dois formatos convivem,
e o programa entrega os dois.
"""
import csv
import io

from . import dxf, vista

CABECALHO_ORCAMENTO = ("Area", "Cod. SAP", "Descricao", "Qtd", "Origem")


def para_dxf(linha, rotulo=None):
    """A linha montada em DXF, 1:1 em milimetro. (texto, recusadas)"""
    postos, recusadas = vista.postos_da_linha(linha)
    doc = dxf.linha_em_dxf(postos, rotulo)
    return dxf.texto_do_dxf(doc), recusadas


def para_svg(linha, largura=1600, altura_max=1000):
    """A vista lateral em SVG, com o estilo dentro - abre em qualquer lugar."""
    desenhada = vista.vista(linha, largura=largura, altura_max=altura_max)
    if not desenhada["svg"]:
        return "", desenhada["recusadas"]
    corpo = desenhada["svg"].replace(
        "<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    estilo = f"<style>{vista.ESTILO}{vista.ESTILO_LINHA}</style>"
    corpo = corpo.replace(">", ">" + estilo, 1)
    return corpo, desenhada["recusadas"]


def _linhas_do_orcamento(linha):
    itens, avisos = linha.lista_materiais()
    return ([[linha.area, r["sap"], r["descricao"], r["qtd"], r["origem"]]
             for r in itens], avisos)


def para_csv(linha):
    """A lista de materiais em CSV, para quem so quer colar na planilha."""
    corpo, avisos = _linhas_do_orcamento(linha)
    fluxo = io.StringIO()
    escritor = csv.writer(fluxo)
    escritor.writerow(CABECALHO_ORCAMENTO)
    escritor.writerows(corpo)
    return fluxo.getvalue(), avisos


def para_xlsx(linha):
    """A aba Orcamento como a casa a usa. (bytes, avisos)

    Os avisos entram numa aba propria e nao numa coluna: aviso e sobre o
    PEDIDO - "pedir a valvula em NBR PN16, 12 furos" - e nao sobre a
    quantidade. Misturar os dois faria o comercial somar o que e recado.
    """
    import openpyxl

    corpo, avisos = _linhas_do_orcamento(linha)
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Orcamento"
    aba.append(list(CABECALHO_ORCAMENTO))
    for registro in corpo:
        aba.append(registro)
    for coluna, largura in zip("ABCDE", (8, 16, 52, 7, 16)):
        aba.column_dimensions[coluna].width = largura
    aba.freeze_panes = "A2"
    if avisos:
        recados = livro.create_sheet("Avisos")
        recados.append(["O que conferir no pedido"])
        for aviso in avisos:
            recados.append([aviso])
        recados.column_dimensions["A"].width = 110
    fluxo = io.BytesIO()
    livro.save(fluxo)
    return fluxo.getvalue(), avisos


FORMATOS = {
    "dxf": ("text", "dxf", "application/dxf"),
    "svg": ("text", "svg", "image/svg+xml"),
    "csv": ("text", "csv", "text/csv"),
    "xlsx": ("binario", "xlsx", "application/vnd.openxmlformats-"
                               "officedocument.spreadsheetml.sheet"),
}
