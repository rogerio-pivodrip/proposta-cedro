"""O SVG: os primitivos de traco, e nada alem deles.

Estava dentro de tools/desenhar_simbolos.py, que e uma ferramenta. Subiu para
o motor porque a tela do programa precisa do mesmo traco da folha - e uma
ferramenta nao pode ser dependencia de um modulo do motor, so o contrario.

Tres camadas, como diz docs/MOTOR.md 4: a geometria sai em milimetro real
dentro de um <g transform="scale(...)">, o traco nao engorda
(vector-effect), e a anotacao vive fora da escala, em pixel fixo.
"""
import math



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
    # o estilo e posto pelo desenhista da linha, e nao pelo simbolo: e por
    # ele que um gomo recebe o degrade do proprio eixo
    estilo = f' style="{elemento["estilo"]}"' if elemento.get("estilo") else ""
    if elemento["tipo"] == "path":
        # caminho FECHADO ganha uma segunda classe. E o que permite pintar a
        # carcaca do motor, que e um poligono com os cantos chanfrados e nao
        # um retangulo - sem isso o motor ficava branco ao lado da bomba
        # pintada. Caminho aberto continua sem preenchimento: fechar um traco
        # solto por dentro faria o SVG inventar uma reta e pintar um triangulo
        fechado = " fechado" if "Z" in elemento["d"].upper() else ""
        corpo = (f'<path class="{classe}{fechado}"{estilo} '
                 f'd="{elemento["d"]}"/>')
    elif elemento["tipo"] == "rect":
        # a quina arredondada e da carcaça fundida do motor
        raio = (f' rx="{elemento["rx"]:.1f}"' if elemento.get("rx") else "")
        corpo = (f'<rect class="{classe}"{estilo} x="{elemento["x"]:.1f}" '
                 f'y="{elemento["y"]:.1f}" width="{elemento["w"]:.1f}" '
                 f'height="{elemento["h"]:.1f}"{raio}/>')
    elif elemento["tipo"] == "circulo":
        corpo = (f'<circle class="{classe}"{estilo} cx="{elemento["cx"]:.1f}" '
                 f'cy="{elemento["cy"]:.1f}" r="{elemento["r"]:.1f}"/>')
    else:
        return ""
    return abre + corpo + fecha


def texto_no_eixo(x, y, texto, classe="cota", tamanho=8.0, gira=""):
    """A cota centrada NO eixo, com o eixo aparado atras dela.

    E a convencao de CAD, e a casa pediu as duas coisas juntas: a cota fica
    centrada no eixo e o eixo abre para ela passar. As duas andam juntas mesmo
    - encostada no eixo sem aparo a cota fica ilegivel, e fugindo do eixo para o
    lado ela deixa de dizer a que peca pertence.

    O APARO E UM HALO NA LETRA, e nao um retangulo atras dela. O retangulo era
    pintado da cor do papel, e isso valia enquanto a cota caia sobre papel: no
    modo metalizado ela passou a cair sobre o corpo PINTADO, e um retangulo cor
    de papel em cima de metal claro virou um buraco - no fundo escuro, uma
    tarja preta atravessada no desenho.

    O halo nao tem esse problema porque ele acompanha a LETRA: abre o eixo
    justo onde a letra passa, e some no resto. Sai por `paint-order: stroke`,
    que manda desenhar o contorno antes do preenchimento - sem isso o contorno
    comeria metade da letra por dentro.
    """
    # o tamanho vai no `style`, e nao num atributo: regra de CSS vence
    # atributo de apresentacao, entao `font-size="2.7"` perderia para a
    # folha - e na prancha impressa o viewBox e em MILIMETRO, onde o
    # `font-size:9px` da folha valeria 9 mm e a cota sairia maior que o tubo
    return (f'<g{gira}><text class="{classe}" x="{x:.2f}" y="{y:.2f}" '
            f'style="font-size:{tamanho:.2f}px;'
            f'stroke-width:{tamanho * 0.16:.2f}px" '
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
<linearGradient id="pvc" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#8f959b"/><stop offset=".2" stop-color="#bdc2c7"/>
<stop offset=".42" stop-color="#d2d6da"/><stop offset=".68" stop-color="#b4b9be"/>
<stop offset="1" stop-color="#8a9096"/>
</linearGradient>
<linearGradient id="pead" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#1e2125"/><stop offset=".2" stop-color="#3f454b"/>
<stop offset=".42" stop-color="#525960"/><stop offset=".68" stop-color="#33383e"/>
<stop offset="1" stop-color="#191c1f"/>
</linearGradient>
<linearGradient id="claro" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#a8b0b8"/><stop offset=".16" stop-color="#dde2e7"/>
<stop offset=".36" stop-color="#f6f8fa"/><stop offset=".60" stop-color="#e2e6eb"/>
<stop offset=".84" stop-color="#bcc3cb"/><stop offset="1" stop-color="#9aa2ab"/>
</linearGradient>
<linearGradient id="nylon" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#2b2f34"/><stop offset=".18" stop-color="#4d545b"/>
<stop offset=".40" stop-color="#6b737b"/><stop offset=".64" stop-color="#474e55"/>
<stop offset="1" stop-color="#282c31"/>
</linearGradient>
<linearGradient id="verde" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#11582a"/><stop offset=".16" stop-color="#2a9247"/>
<stop offset=".36" stop-color="#4fbc6c"/><stop offset=".60" stop-color="#2c8c48"/>
<stop offset=".84" stop-color="#186234"/><stop offset="1" stop-color="#104b27"/>
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
# O medidor tem cor de FABRICANTE, e nao de familia: o ARAD que a casa compra e
# verde, o tangencial WI da Akvometer e azul - "pintura eletrostatica epoxi
# anticorrosiva (azul)", nas palavras da folha dele. Por isso os dois entram
# aqui em cima, onde a marca manda, e nao na tabela de familia.
LIVREA_MARCA = {"KSB": "azul_medio", "EBARA": "claro",
                "ARAD": "verde", "DOROT": "verde", "AKVOMETER": "azul",
                # A.R.I. e polimero preto - ventosa e retencao NR-010. Ela
                # precisa entrar pela MARCA e nao pelo material: a familia
                # VALVULA_RETENCAO manda azul, e a marca e quem passa na frente
                # nylon e nao `pead`: o degrade do tubo de PEAD e quase
                # chapado de preto, e sobre ele a nervura do corpo sumia. Esta
                # peca e casca moldada e precisa do relevo aparecendo
                "ARI": "nylon"}
LIVREA_FAMILIA = {"VALVULA_RETENCAO": "azul", "VALVULA_BORBOLETA": "azul",
                  "VALVULA_HIDRAULICA": "azul", "VALVULA_GAVETA": "escuro",
                  # sem marca conhecida o medidor cai em azul, que e a cor da
                  # unica folha que diz a cor em texto
                  "MEDIDOR": "azul",
                  # ventosa e polimero preto em toda marca da lista - ARI,
                  # Dorot/Netafim, EMEK, Barak. Saia em aco, que e o padrao de
                  # quem nao declara nada, e parecia peca usinada
                  "VENTOSA": "nylon"}
# plastico nao brilha como aco: o PVC sai cinza fosco e o PEAD, preto
LIVREA_MATERIAL = {"PVC": "pvc", "PEAD": "pead"}


def luz_de(cor, giro=0.0, espelhado=False):
    """O degrade desta peca, com a luz sempre do lado de cima da folha.

    Devolve (estilo, defs): o estilo entra no grupo da peca como variavel CSS,
    e os defs sao os gradientes novos que ele precisou.

    O degrade e TRANSVERSAL ao eixo - claro na geratriz de cima, escuro na de
    baixo - e ele vive dentro do grupo que gira, entao ele acompanha a peca.
    Isso e certo: numa linha de pe o brilho tem de continuar correndo ao longo
    do tubo, e nao atravessado nele.

    O que estava errado era o SENTIDO. Girar a peca 180 graus, ou espelha-la,
    poe o lado claro do degrade para baixo - a peca fica iluminada por debaixo,
    o que nao acontece em lugar nenhum. Entao a conta e uma so: para onde
    aponta, na folha, o "para baixo" da peca?

        para_baixo = m * cos(giro),  m = -1 se espelhada

    Positivo, esta em pe; negativo, esta de cabeca para baixo e o degrade sai
    invertido. Em 90 graus o cosseno e zero: a peca esta deitada, nao ha lado
    de cima, e tanto faz.

    As variantes herdam as PARADAS do gradiente base por `href` - o que muda e
    so o sentido, e as cores continuam declaradas num lugar so.
    """
    corpo = cor or "aco"
    # a chapa segue a peca, menos no PEAD: a flange solta do colar e de aco
    chapa = "chapa" if cor in (None, "pead") else cor
    m = -1.0 if espelhado else 1.0
    if m * math.cos(math.radians(float(giro))) >= -1e-9:
        return f"--luz:url(#{corpo});--luz-chapa:url(#{chapa})", {}
    defs = {}
    # `dict.fromkeys` e nao `set`: a ordem de um conjunto de strings muda de
    # processo para processo (o hash e aleatorizado), e com ela mudava a ordem
    # dos <defs> - dois processos gerariam SVG diferente para o mesmo
    # documento. conferir_api cobra justamente isso
    for base in dict.fromkeys((corpo, chapa)):
        defs[f"{base}-v"] = (
            f'<linearGradient id="{base}-v" href="#{base}" '
            f'xlink:href="#{base}" gradientTransform="translate(0 1) '
            f'scale(1 -1)"/>')
    return f"--luz:url(#{corpo}-v);--luz-chapa:url(#{chapa}-v)", defs


def luz_local(cor, luz, giro=0.0, espelhado=False):
    """O degrade de UMA regiao que tem eixo proprio - o gomo da curva.

    Aqui o gradiente sai em coordenada da peca (`userSpaceOnUse`), e nao na
    caixa dela: o gomo e uma faixa inclinada, e a caixa dele nao diz nada
    sobre para onde ele aponta. O vetor vem pronto do simbolo, do meio de uma
    parede ao meio da outra.

    O sentido e conferido do mesmo jeito de sempre: o vetor tem de apontar
    para BAIXO na folha depois do giro e do espelho da peca. Se apontar para
    cima, troca-se ponta por ponta.
    """
    base = cor or "aco"
    x1, y1, x2, y2 = luz
    rad = math.radians(float(giro))
    m = -1.0 if espelhado else 1.0
    dx, dy = x2 - x1, m * (y2 - y1)
    if dx * math.sin(rad) + dy * math.cos(rad) < 0:      # aponta para cima
        x1, y1, x2, y2 = x2, y2, x1, y1
    eixo = (f"{x1:g}_{y1:g}_{x2:g}_{y2:g}"
            .replace(".", "p").replace("-", "n"))
    nome = f"{base}-l{eixo}"
    return (f"--luz:url(#{nome})",
            {nome: f'<linearGradient id="{nome}" href="#{base}" '
                   f'xlink:href="#{base}" gradientUnits="userSpaceOnUse" '
                   f'x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}"/>'})


def desenhar_peca(elementos, cor=None, giro=0.0, espelhado=False, defs=None):
    """Desenha os elementos de uma peca, dando a cada gomo o brilho do eixo dele.

    Quase todo elemento herda o `--luz` do grupo da peca. So quem declara eixo
    proprio - o gomo da curva - ganha um degrade so dele, e e aqui que ele e
    resolvido: o simbolo diz a direcao em milimetro, a librea diz a cor, e o
    giro da peca diz para que lado e "para baixo".
    """
    saida = []
    for elemento in elementos:
        if elemento.get("luz"):
            estilo, novos = luz_local(cor, elemento["luz"], giro, espelhado)
            if defs is not None:
                defs.update(novos)
            elemento = dict(elemento, estilo=estilo)
        saida.append(desenhar(elemento))
    return "".join(saida)


def cor_de(simbolo):
    """A cor da peca no modo metalizado, ou None - e ai ela sai em aco.

    Tres degraus, do mais especifico ao mais geral. A MARCA manda na familia:
    uma bomba e uma bomba, mas a KSB pinta de azul e a EBARA deixa em cinza
    claro. A FAMILIA manda no material: uma valvula hidraulica de plastico e
    azul do mesmo jeito que a de ferro. E o MATERIAL responde pelo resto - o
    tubo, a luva, a curva, que nao tem cor propria alem da do plastico.
    """
    params = simbolo.params or {}
    return (LIVREA_MARCA.get(params.get("marca"))
            or LIVREA_FAMILIA.get(simbolo.familia)
            or LIVREA_MATERIAL.get(params.get("material")))


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
/* linha oculta: o que existe dentro da peca e nao se ve de fora - a cunha da
   gaveta, o furo por tras da parede. Tracejada, que e a convencao, e mais
   clara: ela informa, nao desenha o contorno */
.geo .oculto{stroke:#9aa1a9;stroke-width:.6;stroke-dasharray:9 6;fill:none}
.geo .parafuso,.geo .porca{stroke-width:.65}
.geo .junta{stroke:var(--eixo);stroke-width:.9}
.geo .fluxo{fill:#8f949c;stroke:none}
/* a haste da seta: e traco, e nao area - por isso ela nao pode herdar o
   fill:none da seta cheia nem o stroke do corpo */
.geo .fluxo_haste{fill:none;stroke:#8f949c;stroke-width:2.4}
text{font-family:ui-monospace,SFMono-Regular,monospace;fill:var(--anota)}
.cota{font-size:8px;text-anchor:middle}
.marca{font-size:9px;text-anchor:middle}
/* o aparo do eixo: um halo da cor do papel em volta da LETRA, e nao um
   retangulo atras dela. `paint-order:stroke` desenha o contorno antes do
   preenchimento - sem isso ele comeria metade da letra por dentro */
.cota,.marca{paint-order:stroke;stroke:var(--papel);stroke-linejoin:round}
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

/* A COR VEM EM VARIAVEL, e nao em regra por peca.

   Quem escolhe a cor e o motor (svg.cor_de) e quem a vira para a luz e
   svg.luz_de - os dois poem o resultado em `--luz` no grupo da peca. A folha
   so diz QUE PARTE recebe o corpo e que parte recebe a chapa. Antes disso
   havia um bloco de quatro seletores para cada librea, e cada cor nova pedia
   mais quatro. */
.modo-metal .geo .tubulo{fill:var(--luz,url(#aco));stroke:none}
.modo-metal .geo rect.corpo,
.modo-metal .geo path.corpo.fechado,
/* acionamento e haste: o volante, a caixa redutora, a barra do registro de
   gaveta. Sao peca de metal como o resto, e sem isto ficavam brancas ao lado
   do corpo pintado */
.modo-metal .geo rect.acionamento,
.modo-metal .geo path.acionamento.fechado,
.modo-metal .geo rect.haste,
.modo-metal .geo path.haste.fechado{fill:var(--luz,url(#aco))}
.modo-metal .geo .flange,
.modo-metal .geo .chapa_lisa{fill:var(--luz-chapa,url(#chapa))}
.modo-metal .geo .parafuso,.modo-metal .geo .porca{fill:url(#ferragem)}
/* as exclusoes nao sao decoracao: cada `:not` sobe a especificidade desta
   regra, e sem elas ela passa por cima da cor do eixo e da junta - que sao
   vermelhas por convencao, em qualquer modo */
.modo-metal .geo *:not(.alvo):not(.centro):not(.junta):not(.oculto){
  stroke:#3c424a}
.modo-metal .geo .malha,.modo-metal .geo .furo,.modo-metal .geo .solda{
  stroke:#6f757d}
/* o furo e um vazio na chapa: pintado de branco ele volta a ser buraco, e
   nao um circulo desenhado por cima do metal. So o CIRCULO - a classe malha
   tambem carrega a parede interna do cesto, que e traco e nao furo */
.modo-metal .geo circle.malha,.modo-metal .geo circle.furo{fill:#fff}
.modo-metal .geo .centro{stroke:var(--eixo)}
.modo-metal .geo .junta{stroke:var(--eixo)}
.modo-metal .geo .fluxo{fill:#6f757d;stroke:none}
.modo-metal .geo .fluxo_haste{fill:none;stroke:#6f757d;stroke-width:2.4}
/* No metalizado a cota nao cai sobre o papel: cai sobre o CORPO pintado, que
   e claro. Entao o halo dela e claro tambem - ele tem de ser da cor do que
   esta atras, e nao da cor do papel. Com halo escuro em volta de letra escura
   o numero virava um borrao. */
.modo-metal .cota,.modo-metal .marca{fill:#3a4047;stroke:#eef0f3}

/* peca escura pede traco claro, senao o contorno some dentro dela */
.modo-metal .peca[data-cor="escuro"] *:not(.alvo):not(.centro):not(.oculto){
  stroke:#9aa1a9}
.modo-metal .peca[data-cor="pead"] *:not(.alvo):not(.centro):not(.oculto){
  stroke:#98a0a8}
.modo-metal .peca[data-cor="azul"] *:not(.alvo):not(.centro):not(.oculto){
  stroke:#0f2c4c}
/* dentro de peca escura a linha oculta some no preto: ali ela clareia */
.modo-metal .peca[data-cor="escuro"] .oculto,
.modo-metal .peca[data-cor="pead"] .oculto{stroke:#aab1b9}

.modo-pb .geo *:not(.alvo){stroke:#000}
.modo-pb .geo .malha,.modo-pb .geo .furo,.modo-pb .geo .solda{stroke-width:.45}
.modo-pb .geo .flange,.modo-pb .geo .chapa_lisa,
.modo-pb .geo .parafuso,.modo-pb .geo .porca{fill:#fff}
.modo-pb .geo .tubulo{fill:none;stroke:none}
.modo-pb .geo .fluxo{fill:#000;stroke:none}
.modo-pb .geo .fluxo_haste{fill:none;stroke:#000;stroke-width:2.4}
.modo-pb text{fill:#000}
.modo-pb .cota,.modo-pb .marca{stroke:#fff}
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
