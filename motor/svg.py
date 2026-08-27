"""O SVG: os primitivos de traco, e nada alem deles.

Estava dentro de tools/desenhar_simbolos.py, que e uma ferramenta. Subiu para
o motor porque a tela do programa precisa do mesmo traco da folha - e uma
ferramenta nao pode ser dependencia de um modulo do motor, so o contrario.

Tres camadas, como diz docs/MOTOR.md 4: a geometria sai em milimetro real
dentro de um <g transform="scale(...)">, o traco nao engorda
(vector-effect), e a anotacao vive fora da escala, em pixel fixo.
"""


def desenhar(elemento):
    abre = fecha = ""
    # o espelho vem por fora de tudo: ele reflete a peca ja montada, e nao
    # cada traco dela antes de girar
    if elemento.get("espelhar"):
        abre += '<g transform="scale(1,-1)">'
        fecha += "</g>"
    fora = elemento.get("girar_fora")
    if fora:
        abre += f'<g transform="rotate({fora:g})">'
        fecha += "</g>"
    girar = elemento.get("girar")
    if girar:
        abre += f'<g transform="rotate({girar[0]:g} {girar[1]:.1f} {girar[2]:.1f})">'
        fecha = "</g>" + fecha
    classe = elemento.get("classe", "corpo")
    if elemento["tipo"] == "path":
        corpo = f'<path class="{classe}" d="{elemento["d"]}"/>'
    elif elemento["tipo"] == "rect":
        # a quina arredondada e da carcaça fundida do motor
        raio = (f' rx="{elemento["rx"]:.1f}"' if elemento.get("rx") else "")
        corpo = (f'<rect class="{classe}" x="{elemento["x"]:.1f}" '
                 f'y="{elemento["y"]:.1f}" width="{elemento["w"]:.1f}" '
                 f'height="{elemento["h"]:.1f}"{raio}/>')
    elif elemento["tipo"] == "circulo":
        corpo = (f'<circle class="{classe}" cx="{elemento["cx"]:.1f}" '
                 f'cy="{elemento["cy"]:.1f}" r="{elemento["r"]:.1f}"/>')
    else:
        return ""
    return abre + corpo + fecha


def texto_no_eixo(x, y, texto, classe="cota", tamanho=8.0, gira=""):
    """A cota centrada NO eixo, com o eixo aparado atras dela.

    E a convencao de CAD, e a casa pediu as duas coisas juntas: a cota fica
    centrada no eixo e o eixo abre para ela passar. As duas andam juntas mesmo
    - encostada no eixo sem trim a cota fica ilegivel, e fugindo do eixo para o
    lado ela deixa de dizer a que peca pertence.

    O trim e um retangulo da cor do papel desenhado ANTES do texto: nao da para
    cortar um path em SVG, e mascara custa mais do que vale numa folha com
    trezentas pecas. Por isso o giro vai no grupo e nao no texto - o retangulo
    tem de girar com ele.
    """
    largura = len(texto) * tamanho * 0.62 + tamanho * 0.8
    altura = tamanho * 1.3
    return (f'<g{gira}><rect class="trim" x="{x - largura/2:.1f}" '
            f'y="{y - altura/2:.1f}" width="{largura:.1f}" '
            f'height="{altura:.1f}"/>'
            f'<text class="{classe}" x="{x:.1f}" y="{y:.1f}" '
            f'dominant-baseline="central">{texto}</text></g>')


# Os degrades do modo metalizado. Ficam num <defs> dentro do SVG porque
# gradiente e conteudo, nao estilo - CSS nao inventa `url(#aco)`, ele so
# aponta para ele.
#
# O degrade e VERTICAL na caixa da peca, e a caixa da peca vive dentro do
# grupo que gira: numa linha de pe o brilho gira junto e continua correndo ao
# longo do tubo, que e o que faz o cilindro parecer cilindro. Claro em cima,
# estouro logo abaixo do topo, escuro embaixo - e o desenho de luz de um
# tubo redondo iluminado de cima.
DEFS = """<defs>
<linearGradient id="aco" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#8d949c"/><stop offset=".16" stop-color="#ced3d9"/>
<stop offset=".36" stop-color="#f3f5f7"/><stop offset=".60" stop-color="#dee2e7"/>
<stop offset=".84" stop-color="#a5acb4"/><stop offset="1" stop-color="#7c838b"/>
</linearGradient>
<linearGradient id="azul" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#15406f"/><stop offset=".16" stop-color="#3f7ec2"/>
<stop offset=".36" stop-color="#6fa7e0"/><stop offset=".60" stop-color="#3b76b6"/>
<stop offset=".84" stop-color="#1d4d84"/><stop offset="1" stop-color="#123a63"/>
</linearGradient>
<linearGradient id="azul_medio" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#2a5f92"/><stop offset=".16" stop-color="#5b95cf"/>
<stop offset=".36" stop-color="#8fbde8"/><stop offset=".60" stop-color="#5589bd"/>
<stop offset=".84" stop-color="#33689b"/><stop offset="1" stop-color="#265679"/>
</linearGradient>
<linearGradient id="escuro" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#2b3037"/><stop offset=".16" stop-color="#565d66"/>
<stop offset=".36" stop-color="#767e88"/><stop offset=".60" stop-color="#4d545c"/>
<stop offset=".84" stop-color="#333940"/><stop offset="1" stop-color="#24282e"/>
</linearGradient>
<linearGradient id="claro" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#a8b0b8"/><stop offset=".16" stop-color="#dde2e7"/>
<stop offset=".36" stop-color="#f6f8fa"/><stop offset=".60" stop-color="#e2e6eb"/>
<stop offset=".84" stop-color="#bcc3cb"/><stop offset="1" stop-color="#9aa2ab"/>
</linearGradient>
<linearGradient id="chapa" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#99a0a8"/><stop offset=".3" stop-color="#e4e8eb"/>
<stop offset=".7" stop-color="#c7cdd3"/><stop offset="1" stop-color="#8a9198"/>
</linearGradient>
<linearGradient id="ferragem" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#757c84"/><stop offset=".35" stop-color="#c3c9cf"/>
<stop offset="1" stop-color="#6b7279"/>
</linearGradient>
</defs>"""


# A librea do equipamento: de que cor cada fabricante pinta a peca dele.
#
# E conhecimento de campo, do mesmo tipo que uma cota - por isso mora numa
# tabela e nao espalhado no CSS. A tubulacao continua aco; so o EQUIPAMENTO
# tem cor, que e como se ve numa casa de bomba de verdade.
LIVREA_MARCA = {"KSB": "azul_medio", "EBARA": "claro"}
LIVREA_FAMILIA = {"VALVULA_RETENCAO": "azul", "VALVULA_BORBOLETA": "azul",
                  "VALVULA_HIDRAULICA": "azul", "VALVULA_GAVETA": "escuro"}


def cor_de(simbolo):
    """A cor da peca no modo metalizado, ou None - e ai ela sai em aco.

    A marca manda na familia: uma bomba e uma bomba, mas a KSB pinta de azul e
    a EBARA deixa em cinza claro.
    """
    marca = (simbolo.params or {}).get("marca")
    return LIVREA_MARCA.get(marca) or LIVREA_FAMILIA.get(simbolo.familia)


ESTILO = """
:root{--tinta:#16181d;--eixo:#c0392b;--anota:#8c9099;--linha:#e6e8ec;
  --chapa:#f4f5f7;--fundo:#fff;--papel:#fff;--titulo:#3d424d}
*{box-sizing:border-box}
body{margin:0;padding:40px 32px 64px;background:var(--fundo);color:var(--tinta);
  font:400 13px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;
  -webkit-font-smoothing:antialiased}
.papel{max-width:1320px;margin:0 auto}
header{border-bottom:1.5px solid var(--tinta);padding-bottom:14px;
  margin-bottom:8px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
h1{font-size:17px;font-weight:600;letter-spacing:-.01em;margin:0}
header .dn{font:500 13px/1 ui-monospace,SFMono-Regular,monospace;
  color:var(--eixo);letter-spacing:.02em}
header .sub{margin-left:auto;color:var(--anota);font-size:11.5px}
.legenda{display:flex;gap:22px;flex-wrap:wrap;padding:10px 0 26px;
  border-bottom:1px solid var(--linha);margin-bottom:30px}
.legenda span{display:flex;align-items:center;gap:7px;color:var(--anota);
  font-size:11px}
.legenda svg{width:26px;height:8px;overflow:visible}
h2{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
  color:var(--titulo);margin:34px 0 0;padding-bottom:6px;
  border-bottom:1px solid var(--linha)}
h2 em{font-style:normal;font-weight:400;text-transform:none;letter-spacing:0;
  color:var(--anota);margin-left:10px;font-size:11.5px}
.folha{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));
  border-left:1px solid var(--linha)}
figure{margin:0;background:var(--fundo);padding:0 0 13px;
  border-right:1px solid var(--linha);border-bottom:1px solid var(--linha)}
figure.col2{grid-column:span 2}
@media (max-width:640px){figure.col2{grid-column:span 1}}
figure svg{display:block;width:100%;height:auto}
figcaption{padding:0 14px}
.nome{font-size:12px;font-weight:500;letter-spacing:-.005em;
  display:flex;gap:8px;align-items:baseline}
.nome b{font:500 12px/1 ui-monospace,SFMono-Regular,monospace;color:var(--eixo)}
.tarja{margin-top:3px;display:flex;gap:6px;flex-wrap:wrap;align-items:baseline;
  font:400 10.5px/1.5 ui-monospace,SFMono-Regular,monospace;color:var(--anota)}
.tarja i{font-style:normal}
.tarja i+i:before{content:"·";margin-right:6px}
.tarja .fonte{margin-left:auto;letter-spacing:.07em;text-transform:uppercase;
  font-size:9px;color:#b3b7bf}
.geo *{vector-effect:non-scaling-stroke;fill:none;stroke:var(--tinta);
  stroke-width:.85;stroke-linejoin:round;stroke-linecap:round}
.geo .flange,.geo .chapa_lisa,.geo .parafuso,.geo .porca{fill:var(--chapa)}
.geo .malha,.geo .furo,.geo .solda{stroke-width:.55;stroke:#8f949c}
.geo .centro{stroke:var(--eixo);stroke-width:.65;stroke-dasharray:12 3 1.5 3}
.geo .parafuso,.geo .porca{stroke-width:.65}
.geo .junta{stroke:var(--eixo);stroke-width:.9}
.geo .fluxo{fill:#8f949c;stroke:none}
text{font-family:ui-monospace,SFMono-Regular,monospace;fill:var(--anota)}
.cota{font-size:8px;text-anchor:middle}
.marca{font-size:9px;text-anchor:middle}
/* o trim: a cota nao foge do eixo, o eixo abre para ela */
.trim{fill:var(--papel);stroke:none}
/* a area de clique da peca na tela: invisivel no papel, alvo no programa */
.alvo{fill:transparent;stroke:none;pointer-events:all}
/* a anotacao nao e alvo de nada. Ela vive FORA da escala, por cima do
   desenho, e a cota de cada peca cai bem no meio dela - entao sem isto a
   propria cota come o clique da peca que ela cota */
.anota{pointer-events:none}

/* ------------------------------------------------------------ os tres modos

   O mesmo desenho, tres leituras. O que muda e SO a folha de estilo: a
   geometria e uma so, em milimetro real, e nenhum dos tres redesenha nada.

   traco  o desenho de projeto: linha preta, eixo vermelho traco-ponto.
   pb     tudo preto, para plotar e para fotocopia - o vermelho do eixo sai
          cinza numa impressora monocromatica, e ai ele some no meio do resto.
   metal  o corpo ganha o cilindro: claro em cima, escuro embaixo. E o
          `tubulo` que recebe a cor - a regiao entre as duas paredes, que a
          primitiva desenha e que fica invisivel nos outros dois modos.

   O tubulo NUNCA tem traco: a parede ja esta desenhada por cima dele, e um
   contorno a mais engrossaria a linha do desenho. */
.geo .tubulo{fill:none;stroke:none}

.modo-metal .geo .tubulo{fill:url(#aco);stroke:none}
.modo-metal .geo rect.corpo{fill:url(#aco)}
.modo-metal .geo .flange,.modo-metal .geo .chapa_lisa{fill:url(#chapa)}
.modo-metal .geo .parafuso,.modo-metal .geo .porca{fill:url(#ferragem)}
/* traco mais escuro e mais fino: com o corpo pintado, a linha nao precisa
   mais carregar sozinha a forma da peca */
/* `:not(.alvo)` porque o alvo e a area de clique, e nao geometria: sem isto
   o modo pinta o retangulo invisivel de cada peca e ele aparece na folha */
.modo-metal .geo *:not(.alvo){stroke:#3c424a}
.modo-metal .geo .malha,.modo-metal .geo .furo,.modo-metal .geo .solda{
  stroke:#6f757d}
/* o furo e um vazio na chapa: pintado de branco ele volta a ser buraco, e
   nao um circulo desenhado por cima do metal. So o CIRCULO - a classe malha
   tambem carrega a parede interna do cesto, que e traco e nao furo */
.modo-metal .geo circle.malha,.modo-metal .geo circle.furo{fill:#fff}
.modo-metal .geo .centro{stroke:var(--eixo)}
.modo-metal .geo .junta{stroke:var(--eixo)}
.modo-metal .geo .fluxo{fill:#6f757d;stroke:none}

/* o equipamento pintado. A tubulacao fica aco; a valvula e a bomba saem na
   cor do fabricante, que e como se ve numa casa de bomba de verdade. A
   ferragem da juncao nao entra: ela e desenhada FORA do grupo da peca, e
   parafuso zincado nao vai junto na pintura */
.modo-metal .peca[data-cor="azul"] .tubulo,
.modo-metal .peca[data-cor="azul"] rect.corpo,
.modo-metal .peca[data-cor="azul"] .flange,
.modo-metal .peca[data-cor="azul"] .chapa_lisa{fill:url(#azul)}
.modo-metal .peca[data-cor="azul_medio"] .tubulo,
.modo-metal .peca[data-cor="azul_medio"] rect.corpo,
.modo-metal .peca[data-cor="azul_medio"] .flange,
.modo-metal .peca[data-cor="azul_medio"] .chapa_lisa{fill:url(#azul_medio)}
.modo-metal .peca[data-cor="escuro"] .tubulo,
.modo-metal .peca[data-cor="escuro"] rect.corpo,
.modo-metal .peca[data-cor="escuro"] .flange,
.modo-metal .peca[data-cor="escuro"] .chapa_lisa{fill:url(#escuro)}
.modo-metal .peca[data-cor="claro"] .tubulo,
.modo-metal .peca[data-cor="claro"] rect.corpo,
.modo-metal .peca[data-cor="claro"] .flange,
.modo-metal .peca[data-cor="claro"] .chapa_lisa{fill:url(#claro)}
/* peca escura pede traco claro, senao o contorno some dentro dela */
.modo-metal .peca[data-cor="escuro"] *:not(.alvo):not(.centro){stroke:#9aa1a9}
.modo-metal .peca[data-cor="azul"] *:not(.alvo):not(.centro){stroke:#0f2c4c}

.modo-pb .geo *:not(.alvo){stroke:#000}
.modo-pb .geo .malha,.modo-pb .geo .furo,.modo-pb .geo .solda{stroke-width:.45}
.modo-pb .geo .flange,.modo-pb .geo .chapa_lisa,
.modo-pb .geo .parafuso,.modo-pb .geo .porca{fill:#fff}
.modo-pb .geo .tubulo{fill:none;stroke:none}
.modo-pb .geo .fluxo{fill:#000;stroke:none}
.modo-pb text{fill:#000}
.modo-pb .trim{fill:#fff}
.lista{display:flex;gap:8px;align-items:baseline;margin:1px 0 3px;
  font:400 10.5px/1.4 "IBM Plex Mono",ui-monospace,monospace;
  color:var(--anota,#8a8f98)}
.lista .sap{font-weight:500;color:var(--titulo,#3d424d);white-space:nowrap}
.lista span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.falta{font:400 11.5px/1.5 "Source Sans 3",system-ui,sans-serif;
  color:var(--anota,#8a8f98);margin:-14px 0 24px;max-width:78ch}
.falta::before{content:"";display:inline-block;width:6px;height:6px;
  border-radius:50%;background:var(--eixo,#c0392b);opacity:.55;
  margin-right:7px;vertical-align:middle}
.vazia{font:italic 12px/1.5 "Source Sans 3",system-ui,sans-serif;
  color:var(--anota,#8a8f98);margin:2px 0 22px;max-width:58ch}
"""


ESTILO_LINHA = """
.linha{border:1px solid var(--linha);margin:0 0 22px;padding:18px 20px 8px}
.linha figcaption{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
  margin-bottom:10px}
.linha figcaption b{font-size:13px;font-weight:600;letter-spacing:-.005em}
.linha figcaption em{font-style:normal;color:var(--anota);font-size:11.5px}
.linha figcaption span{margin-left:auto;color:var(--anota);
  font:400 10.5px/1 ui-monospace,SFMono-Regular,monospace}
.linha svg{width:100%;height:auto;display:block;margin:0 auto}
.geo .juncao{fill:none}
.geo .juncao.ruim{fill:var(--eixo);stroke:none}
"""
