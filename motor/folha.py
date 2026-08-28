"""A prancha de impressao: o desenho, a lista e o carimbo numa folha so.

O programa ja entrega DXF e planilha - os dois formatos de quem vai continuar
trabalhando no arquivo. Falta o formato de quem vai ASSINAR: uma folha em
escala, com carimbo, que se imprime, se dobra e vai para a obra.

Tres coisas separam esta folha da vista de tela:

**A ESCALA E NOMEADA.** Na tela o desenho e enquadrado - "o que couber" - e
isso e certo, porque a janela muda de tamanho. Numa folha impressa nao existe
"o que couber": existe 1:25, e quem mede com escalimetro tem de achar a cota.
Entao a folha escolhe a maior escala da NBR 8196 em que o desenho cabe, e
escreve qual foi no carimbo. Ver vista.escala_que_cabe.

**A UNIDADE E O MILIMETRO DE PAPEL.** O viewBox da tela e em pixel; o desta e
em milimetro da folha, e por isso a anotacao encolhe junto (`anota`): cota de
9 px na tela vira 2,7 mm no papel, que e a altura de escrita da ISO 3098.

**O FORMATO E A MOLDURA SAO DA NBR 10068** - margem esquerda de 25 mm para
arquivar, as demais de 7 (ate A2) ou 10 (A1 e A0), e a legenda de 178 mm no
canto inferior direito. Os 178 nao sao arbitrarios: e a largura util de uma A4
em pe, e a legenda e a mesma em todos os formatos.

A saida e HTML com `@page`, e nao PDF: o navegador imprime, e o programa
continua rodando sem instalar nada.
"""
import datetime

from . import vista
from .svg import DEFS, ESTILO

# NBR 10068 - a serie A, em milimetro, sempre (menor, maior)
FORMATOS = {"A4": (210, 297), "A3": (297, 420), "A2": (420, 594),
            "A1": (594, 841), "A0": (841, 1189)}
MARGEM_ESQUERDA = 25.0          # para arquivar em pasta
CARIMBO = (178.0, 40.0)         # a legenda da norma
ANOTA = 0.3                     # 9 px de cota na tela -> 2,7 mm no papel


def margens(formato):
    """(esquerda, outras) em mm. A folha grande pede moldura mais larga."""
    return MARGEM_ESQUERDA, (10.0 if formato in ("A1", "A0") else 7.0)


def medidas(formato="A3", orientacao="paisagem"):
    menor, maior = FORMATOS.get(formato.upper(), FORMATOS["A3"])
    return (maior, menor) if orientacao.startswith("pais") else (menor, maior)


def _bitola_da_linha(linha):
    """A bitola que mais aparece - e o que vai no carimbo como 'linha'."""
    contagem = {}
    for peca in linha.pecas:
        for dn in (peca.item.get("dn") or []):
            if isinstance(dn, (int, float)):
                contagem[dn] = contagem.get(dn, 0) + 1
    if not contagem:
        return ""
    maior = max(contagem, key=lambda d: (contagem[d], d))
    return f'{maior:g}"' if maior < 60 else f"DN{maior:g}"


def _fontes(linha):
    """De onde vieram as cotas desta linha - a tarja de procedencia.

    Vai no carimbo porque e informacao de PROJETO: uma folha em que metade das
    cotas e estimativa nao vale o mesmo que uma em que todas sao de fabricante,
    e quem assina precisa ver isso sem abrir o programa.
    """
    contagem = {}
    for peca in linha.pecas:
        # o TUBO nao e estimativa: o comprimento dele e o do CODIGO que se
        # compra, que e a fonte mais firme que existe nesta folha. Contá-lo
        # como estimativa fazia a tarja pintar de duvidosa a única cota que
        # nao tem duvida nenhuma
        if peca.familia == "TUBO" and peca.item.get("comprimento_mm"):
            chave = "código"
        else:
            chave = peca.fonte_cota or "estimativa"
        contagem[chave] = contagem.get(chave, 0) + 1
    return " · ".join(f"{n} {fonte}" for fonte, n in
                      sorted(contagem.items(), key=lambda t: -t[1]))


def montar(linha, formato="A3", orientacao="paisagem", titulo=None,
           modo="traco", data=None):
    """A prancha inteira em HTML, do tamanho da folha. (html, ficha)"""
    largura, altura = medidas(formato, orientacao)
    esq, fora = margens(formato.upper())
    moldura = (esq, fora, largura - esq - fora, altura - 2 * fora)

    # a coluna da lista fica a direita, alinhada com o carimbo; o desenho pega
    # o resto, descontada a faixa do carimbo, que e mais larga que a coluna
    coluna = min(CARIMBO[0], moldura[2] * 0.34)
    caixa = (moldura[0], moldura[1],
             moldura[2] - coluna - 4, moldura[3] - CARIMBO[1] - 4)

    postos, recusadas = vista.postos_da_linha(linha)
    ext_x, ext_y = vista.extensao(postos) if postos else (1.0, 1.0)
    folga = 2 * vista.MARGEM * ANOTA
    divisor = vista.escala_que_cabe(caixa[2] - folga, caixa[3] - folga,
                                    ext_x, ext_y)
    desenhada = vista.vista(linha, modo=modo, escala=1 / divisor, anota=ANOTA)
    svg = (desenhada["svg"] or "").replace(
        'width="', 'width_mm="', 1).replace('height="', 'height_mm="', 1)
    # o SVG sai com o tamanho em unidade de viewBox, que aqui E milimetro:
    # anexar "mm" e o que faz o navegador imprimir no tamanho de verdade
    svg = svg.replace("width_mm=\"", "width=\"").replace(
        "height_mm=\"", "height=\"")
    svg = _em_milimetro(svg)

    itens, avisos = linha.lista_materiais()
    hoje = data or datetime.date.today().strftime("%d/%m/%Y")
    ficha = {"formato": formato.upper(), "orientacao": orientacao,
             "escala": f"1:{divisor:g}", "divisor": divisor,
             "bitola": _bitola_da_linha(linha), "data": hoje,
             "recusadas": recusadas, "itens": len(itens)}

    # o NUMERO DO ITEM abre a linha: e ele que o balao do desenho repete, e
    # sem ele na lista o balao aponta para lugar nenhum
    linhas_lista = "".join(
        f'<tr><td class="i"><span>{r["item"]}</span></td>'
        f'<td class="q">{r["qtd"]}</td><td class="c">{r["sap"]}</td>'
        f'<td>{r["descricao"]}</td></tr>' for r in itens)
    recado = ""
    if recusadas:
        recado = ('<p class="recusadas">sem símbolo: '
                  + ", ".join(r["sap"] for r in recusadas) + "</p>")

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>{linha.tipo} {linha.area} · {formato.upper()} {ficha["escala"]}</title>
<style>{ESTILO}{_ESTILO_FOLHA}
@page {{ size: {largura:g}mm {altura:g}mm; margin: 0 }}
.prancha {{ width:{largura:g}mm; height:{altura:g}mm }}
.moldura {{ left:{moldura[0]:g}mm; top:{moldura[1]:g}mm;
  width:{moldura[2]:g}mm; height:{moldura[3]:g}mm }}
.desenho {{ left:{caixa[0]:g}mm; top:{caixa[1]:g}mm;
  width:{caixa[2]:g}mm; height:{caixa[3]:g}mm }}
.materiais {{ left:{moldura[0] + moldura[2] - coluna:g}mm; top:{moldura[1]:g}mm;
  width:{coluna:g}mm; height:{moldura[3] - CARIMBO[1] - 4:g}mm }}
.carimbo {{ left:{moldura[0] + moldura[2] - CARIMBO[0]:g}mm;
  top:{moldura[1] + moldura[3] - CARIMBO[1]:g}mm;
  width:{CARIMBO[0]:g}mm; height:{CARIMBO[1]:g}mm }}
</style></head><body>
<svg width="0" height="0" style="position:absolute">{DEFS}</svg>
<div class="acoes"><button onclick="print()">imprimir</button>
  <span>{formato.upper()} {orientacao} · {ficha["escala"]} · a folha sai no
  tamanho de verdade: escolha "tamanho original" e sem margem</span></div>
<div class="prancha">
  <div class="moldura"></div>
  <div class="desenho">{svg}</div>
  <div class="materiais">
    <h2>lista de materiais</h2>
    <table>{linhas_lista}</table>
  </div>
  <div class="carimbo">
    <div class="titulo">{titulo or f"{linha.tipo.title()} — {linha.area}"}</div>
    <div class="campos">
      <span><i>linha</i>{ficha["bitola"]}</span>
      <span><i>escala</i>{ficha["escala"]}</span>
      <span><i>formato</i>{ficha["formato"]}</span>
      <span><i>data</i>{ficha["data"]}</span>
      <span><i>itens</i>{ficha["itens"]}</span>
    </div>
    <div class="procedencia">cotas: {_fontes(linha) or "—"}</div>
  </div>
  {recado}
</div></body></html>""", ficha


def _em_milimetro(svg):
    """Poe `mm` no width e no height do SVG - o viewBox dele ja e em mm."""
    import re
    return re.sub(r'(width|height)="(\d+(?:\.\d+)?)"',
                  lambda m: f'{m.group(1)}="{m.group(2)}mm"', svg, count=2)


_ESTILO_FOLHA = """
body{margin:0;padding:0;background:#8d9096;
  font:400 3mm/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif}
.prancha{position:relative;background:#fff;margin:0 auto;overflow:hidden}
.prancha>div{position:absolute;box-sizing:border-box}
.moldura{border:.6mm solid #16181d}
.desenho{display:flex;align-items:center;justify-content:center;overflow:hidden}
.desenho svg{display:block}
.materiais{padding:2mm 2.5mm;overflow:hidden}
.materiais h2{margin:0 0 1.5mm;padding:0 0 1mm;font-size:2.6mm;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:#3d424d;
  border-bottom:.3mm solid #16181d}
.materiais table{width:100%;border-collapse:collapse;font-size:2.5mm}
.materiais td{padding:.5mm 1mm;border-bottom:.15mm solid #d8dade;
  vertical-align:top;line-height:1.25}
/* o numero do item vem no circulo do balao: aqui ele repete o circulo, para
   que o olho ache na lista o que achou na folha */
.materiais td.i{width:6mm;padding:.4mm 0}
/* o circulo e do SPAN, e nao da celula: com border-collapse a borda da
   celula e da tabela, e nao arredonda */
.materiais td.i span{display:block;width:3.8mm;height:3.8mm;margin:0 auto;
  border:.2mm solid #16181d;border-radius:50%;text-align:center;
  font-size:2.2mm;line-height:3.4mm;color:#16181d}
.materiais td.q{text-align:right;width:6mm;color:#6d737b}
.materiais td.c{font-family:ui-monospace,monospace;white-space:nowrap;
  width:22mm;color:#6d737b}
.carimbo{border:.6mm solid #16181d;padding:2mm 2.5mm;
  display:flex;flex-direction:column;gap:1.5mm;background:#fff}
.carimbo .titulo{font-size:4mm;font-weight:600;letter-spacing:-.01em}
.carimbo .campos{display:flex;gap:6mm;flex-wrap:wrap;font-size:3mm}
.carimbo .campos i{font-style:normal;color:#8c9099;margin-right:1.5mm;
  font-size:2.4mm;text-transform:uppercase;letter-spacing:.06em}
.carimbo .procedencia{margin-top:auto;font-size:2.4mm;color:#8c9099}
.recusadas{position:absolute;left:26mm;bottom:2mm;margin:0;font-size:2.5mm;
  color:#b23b32}
.acoes{position:fixed;left:0;right:0;top:0;z-index:9;display:flex;gap:4mm;
  align-items:center;padding:2.5mm 4mm;background:#16181d;color:#c6cbd2;
  font-size:3mm}
.acoes button{font:inherit;color:#16181d;background:#e8eaed;border:none;
  border-radius:1mm;padding:1.5mm 4mm;cursor:pointer}
.prancha{margin:14mm auto 6mm}
@media print{body{background:#fff}.prancha{margin:0}.acoes{display:none}}
"""
