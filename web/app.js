/* A tela. Ela não sabe nenhuma regra, e não guarda o documento.

   Cada comando devolve o documento inteiro e a tela repinta. O único estado
   que ela tem é `escolhida` - o id da peça selecionada - e mesmo esse é um id
   que veio do motor. Foi essa decisão que dispensou a sincronização: não há
   duas cópias para divergir.

   Ver docs/LOGICA.md 2. */

let documento = null;
/* A SELEÇÃO É UM CONJUNTO, e `escolhida` é a última dele.

   Um clique escolhe uma; shift ou ctrl acrescenta. Guardar as duas coisas -
   a lista e a última - evita reescrever todo comando que age sobre "a peça":
   o painel continua falando de uma peça (a última), e o comando manda a
   lista junto. Quem escolheu uma só manda uma lista de um. */
let escolhidas = [];
let escolhida = null;
let modo = "inserir";        // o que um clique no catálogo faz com a escolhida

const $ = (id) => document.getElementById(id);

async function mandar(comando) {
  const resposta = await fetch("comando", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(comando),
  });
  const corpo = await resposta.json();
  // o documento vem junto até no erro: a tela que pediu algo inválido
  // continua mostrando o que existe
  if (corpo.documento) { documento = corpo.documento; pintar(); }
  recado(corpo.ok ? "" : corpo.erro);
  return corpo;
}

function recado(texto) {
  const p = $("recado");
  p.textContent = texto || "";
  p.hidden = !texto;
}

/* ---------------------------------------------------------------- pintar */
function pintar() {
  if (!documento) return;
  pintarAbas();
  pintarVista();
  pintarLista();
  pintarAvisos();
  pintarPainel();
  $("desfazer").disabled = !documento.pode_desfazer;
  $("refazer").disabled = !documento.pode_refazer;
  const modoDesenho = (documento.vista && documento.vista.modo) || "traco";
  document.querySelectorAll("[data-modo-desenho]").forEach((b) =>
    b.classList.toggle("ligado", b.dataset.modoDesenho === modoDesenho));
}

/* A TIRA DE MONTAGENS. Uma casa de bomba não é uma linha: tem a sucção, o
   recalque, o barrilete, o trecho que sai para o campo - e com duas bombas
   tem tudo isso duas vezes. Cada aba é uma montagem do projeto; os comandos
   de edição caem na aba aberta, e o ctrl+Z atravessa todas, porque desfaz o
   que se acabou de fazer e não o último comando desta aba. */
function pintarAbas() {
  const tira = $("abas");
  tira.innerHTML = "";
  (documento.montagens || []).forEach((m) => {
    const b = document.createElement("button");
    b.className = m.ativa ? "ativa" : "";
    b.innerHTML = `<span>${m.nome}</span><i>${m.pecas}</i>` +
      ((documento.montagens || []).length > 1
        ? '<span class="fechar" title="apagar esta montagem">×</span>' : "");
    b.addEventListener("click", (ev) => {
      if (ev.target.classList.contains("fechar")) {
        ev.stopPropagation();
        soltarEscolha();
        mandar({nome: "montagem", acao: "remover", alvo: m.id});
        return;
      }
      if (m.ativa) return;
      // trocar de montagem larga a seleção: o id escolhido era da outra
      soltarEscolha();
      mandar({nome: "montagem", acao: "escolher", alvo: m.id});
    });
    b.addEventListener("dblclick", () => {
      const nome = prompt("nome da montagem", m.nome);
      if (nome) mandar({nome: "montagem", acao: "renomear", alvo: m.id,
                        rotulo: nome});
    });
    tira.appendChild(b);
  });
  const nova = document.createElement("button");
  nova.className = "nova";
  nova.textContent = "+";
  nova.title = "montagem em branco";
  nova.addEventListener("click", () => {
    soltarEscolha();
    mandar({nome: "montagem", acao: "criar"});
  });
  tira.appendChild(nova);
}

function pintarVista() {
  const alvo = $("palco");
  const svg = documento.vista && documento.vista.svg;
  alvo.innerHTML = svg || '<p class="nada">Nada para desenhar ainda.</p>';
  // o SVG vem com viewBox e sem tamanho: dentro do palco, que é flex, isso
  // deixa a largura indefinida. Fixar aqui o tamanho natural faz o zoom ser a
  // única coisa que muda a escala na tela
  const desenhado = alvo.querySelector("svg");
  if (desenhado) {
    const [, , w, h] = desenhado.getAttribute("viewBox").split(/\s+/).map(Number);
    desenhado.style.width = w + "px";
    desenhado.style.height = h + "px";
    desenhado.style.maxWidth = "none";
  }
  alvo.querySelectorAll("g.peca[data-id]").forEach((g) => {
    const id = g.dataset.id;
    if (escolhidas.includes(id)) g.classList.add("escolhida");
    // o arrasto é estado DA TELA, como a seleção: cada repintura o reaplica.
    // A tela repinta a cada comando - inclusive o `simular` do próprio
    // arrasto - então guardar elemento em vez de id perderia o arrasto no
    // meio dele. Foi o que aconteceu na primeira versão.
    if (arrasto && id === arrasto.id) g.classList.add("arrastando");
    if (arrasto && id === arrasto.sobre && id !== arrasto.id) {
      g.classList.add(arrasto.recusa ? "recusa" : "recebe");
    }
    g.addEventListener("click", (ev) =>
      escolher(id, ev.shiftKey || ev.ctrlKey || ev.metaKey));
    g.addEventListener("pointerdown", (ev) => comecarArrasto(ev, id));
  });
  // o balão é da mesma peça que o traço - clicar num e noutro escolhe a
  // mesma coisa. Arrastar o balão, porém, não move peça nenhuma: move o
  // número dela na folha
  alvo.querySelectorAll("g.balao[data-id]").forEach((g) => {
    const id = g.dataset.id;
    if (escolhidas.includes(id)) g.classList.add("escolhida");
    // soltar o arrasto dispara um `click` logo atrás. Sem isto, terminar de
    // arrastar o balão trocava a seleção de brinde - e quem arrasta o balão
    // não pediu para selecionar nada
    g.addEventListener("click", (ev) => {
      if (balaoAndou) return;
      escolher(id, ev.shiftKey || ev.ctrlKey || ev.metaKey);
    });
    g.addEventListener("pointerdown", (ev) => comecarBalao(ev, id));
  });
  aplicarZoom();
  const recusadas = (documento.vista && documento.vista.recusadas) || [];
  if (recusadas.length) {
    recado(recusadas.map((r) => `${r.sap}: ${r.motivo}`).join(" · "));
  }
}

function pintarLista() {
  const corpo = $("lista").querySelector("tbody");
  corpo.innerHTML = "";
  // a lista mostra as peças da linha na ordem em que estão, e depois o que
  // elas puxaram - ferragem e contra-flange são consequência, não escolha
  const porSap = new Map();
  // o NÚMERO DO ITEM não se consome: duas curvas do mesmo código são a mesma
  // linha da lista e levam o mesmo número, no desenho e aqui. Ele vinha do
  // mesmo mapa de que a linha era apagada, e a segunda curva saía sem número
  const numeros = new Map();
  documento.lista.forEach((r) => { porSap.set(r.sap, r); numeros.set(r.sap, r.item); });
  documento.pecas.forEach((peca) => {
    const registro = porSap.get(peca.sap);
    corpo.appendChild(linhaDaTabela({
      id: peca.id, sap: peca.sap, descricao: peca.descricao,
      qtd: registro ? registro.qtd : 1,
      item: numeros.get(peca.sap) || null, balao: peca.balao,
    }));
    porSap.delete(peca.sap);
  });
  documento.lista.forEach((r) => {
    if (!porSap.has(r.sap)) return;
    corpo.appendChild(linhaDaTabela(r, true));
  });
}

function linhaDaTabela(registro, derivada) {
  const tr = document.createElement("tr");
  if (derivada) tr.className = "derivada";
  if (escolhidas.includes(registro.id)) tr.classList.add("escolhida");
  // o número do item é o do balão: o mesmo número, nos dois lugares
  const semBalao = registro.balao === false ? " class=\"sem\"" : "";
  tr.innerHTML =
    `<td class="item">${registro.item
      ? `<span${semBalao}>${registro.item}</span>` : ""}</td>` +
    `<td class="qtd">${registro.qtd}</td>` +
    `<td class="sap">${registro.sap || ""}</td>` +
    `<td>${registro.descricao || ""}</td>` +
    // só a peça da linha tem × : ferragem é consequência, e some sozinha
    // quando a peça que a puxou sai
    `<td class="apagar">${registro.id ? "×" : ""}</td>`;
  if (registro.id) {
    tr.addEventListener("click", (ev) =>
      escolher(registro.id, ev.shiftKey || ev.ctrlKey || ev.metaKey));
    tr.querySelector("td.apagar").addEventListener("click", (ev) => {
      ev.stopPropagation();
      apagar(registro.id);
    });
  }
  return tr;
}

function pintarAvisos() {
  $("avisos").innerHTML = (documento.avisos || [])
    .map((a) => `<p>${a}</p>`).join("");
  // peça de uma ponta só no lugar errado: o motor descobre, a tela mostra por
  // extenso. Um ponto vermelho na junção não diz o que está errado
  const pontas = documento.pontas || [];
  if (pontas.length) recado(pontas.map((p) => p.motivo).join(" · "));
}

/* ------------------------------------------------------ zoom e pan

   O motor desenha em milímetro real, já escalado para caber na janela. O zoom
   é da TELA: uma transformação no palco, sem ida ao motor. Duas consequências
   boas: responde na hora, e o traço não engorda - `vector-effect` faz a
   espessura ser em pixel, então ampliar mostra mais peça e não linha mais
   grossa, que é o que se espera de um CAD.

   Como a seleção e o arrasto, isto é estado DA TELA: o documento não sabe em
   que zoom alguém está olhando, e não deve saber.

   E o zoom não desenha nada por cima: a única marca no desenho é a peça
   selecionada, no traço dela. Contorno, retângulo de alvo e etiqueta saíram -
   o desenho é o desenho, e o que a interface precisa dizer ela diz no painel
   ao lado. */
let zoom = 1;
let pan = {x: 0, y: 0};
const ZOOM_MIN = 0.2, ZOOM_MAX = 40;

function aplicarZoom() {
  $("palco").style.transform =
    `translate(${pan.x.toFixed(1)}px, ${pan.y.toFixed(1)}px) scale(${zoom})`;
  $("zoom_texto").textContent = Math.round(zoom * 100) + "%";
}

function ajustar() {
  // zoom 1 e pan zero É o enquadramento: o motor já escalou o desenho para
  // caber na janela que a tela avisou
  zoom = 1;
  pan = {x: 0, y: 0};
  aplicarZoom();
}

function ampliar(fator, alvoX, alvoY) {
  const caixa = $("vista").getBoundingClientRect();
  // sem ponto de referência, amplia pelo meio da janela
  const px = (alvoX === undefined ? caixa.width / 2 : alvoX - caixa.left);
  const py = (alvoY === undefined ? caixa.height / 2 : alvoY - caixa.top);
  const novo = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom * fator));
  // o ponto sob o cursor não pode se mexer: é o que faz o zoom parecer que
  // aproxima o desenho, e não que o empurra para fora da tela
  pan.x = px - (px - pan.x) * (novo / zoom);
  pan.y = py - (py - pan.y) * (novo / zoom);
  zoom = novo;
  aplicarZoom();
}

/* ------------------------------------------------------- mover a folha

   Arrastar o FUNDO move a folha; arrastar uma PEÇA a reposiciona na sequência.
   São dois gestos com o mesmo botão, e o que os separa é onde o dedo desceu -
   por isso este listener fica na .vista e desiste quando o alvo é uma peça. */
let folha = null;

function comecarFolha(ev) {
  if (ev.button === 0 && ev.target.closest &&
      ev.target.closest("g.peca, g.balao")) return;
  if (ev.button !== 0 && ev.button !== 1) return;
  ev.preventDefault();
  folha = {x: ev.clientX, y: ev.clientY, px: pan.x, py: pan.y};
  $("vista").classList.add("arrastando_folha");
  addEventListener("pointermove", moverFolha);
  addEventListener("pointerup", soltarFolha, {once: true});
}

function moverFolha(ev) {
  if (!folha) return;
  pan.x = folha.px + (ev.clientX - folha.x);
  pan.y = folha.py + (ev.clientY - folha.y);
  aplicarZoom();
}

function soltarFolha() {
  folha = null;
  $("vista").classList.remove("arrastando_folha");
  removeEventListener("pointermove", moverFolha);
}

function pecaEscolhida() {
  return (documento.pecas || []).find((p) => p.id === escolhida) || null;
}

function pintarPainel() {
  const peca = pecaEscolhida();
  $("painel").hidden = !peca;
  if (!peca) {
    // sem peça escolhida não há o que substituir: o catálogo volta a só
    // acrescentar, senão o próximo clique num código não teria alvo
    modo = "inserir";
    $("modo").hidden = true;
    pintarModo();
    return;
  }
  $("painel_nome").textContent = peca.descricao;
  $("painel_sap").textContent =
    `${peca.sap} · ${peca.familia}` +
    (peca.fonte_cota ? ` · cota ${peca.fonte_cota}` : " · cota estimada");
  $("comprimento").value = Math.round(peca.comprimento_mm || 0);
  pintarBarras(peca);
  const fonte = $("fonte");
  if (!fonte.options.length) {
    ["IRRIGAFOUR", "NETAFIM", "MP", "RAN", "ARAD", "DOROT", "SAINT-GOBAIN"]
      .forEach((f) => fonte.add(new Option(f, f)));
  }
  fonte.value = peca.fonte || "IRRIGAFOUR";
  $("espelhar").classList.toggle("ligado", peca.sentido < 0);
  $("balao").classList.toggle("ligado", peca.balao !== false);
  // com várias escolhidas o painel continua mostrando UMA - a última - e
  // avisa que o botão vale para todas. Mostrar campo em branco "porque são
  // várias" esconderia o que a pessoa acabou de clicar
  const varias = $("painel_varias");
  varias.hidden = escolhidas.length < 2;
  varias.textContent = `${escolhidas.length} peças escolhidas — o que mudar `
    + `aqui muda todas`;
  $("trocar_bitola").value = "";
  $("modo").hidden = false;
  pintarModo();
}

/* No tubo o comprimento é uma ESCOLHA entre as barras que a lista tem, e não
   um número livre: a medida do desenho tem de ser a medida que se compra, e um
   número sem código atrás não é uma barra - é um corte.

   O campo livre continua ali, e cortar continua sendo legítimo. O que não é
   legítimo é cortar CALADO: o documento passa a trazer a divergência, e ela
   aparece aqui embaixo e nos avisos da folha. */
function pintarBarras(peca) {
  const barras = peca.barras || [];
  $("rotulo_barras").hidden = barras.length < 2;
  const caixa = $("barras");
  caixa.innerHTML = "";
  barras.forEach((mm) => caixa.add(new Option(`${mm / 1000} m`, mm)));
  const doCodigo = (documento.divergencias || [])
    .find((d) => d.id === peca.id);
  caixa.value = String(doCodigo ? doCodigo.do_codigo_mm
                                : Math.round(peca.comprimento_mm || 0));
  const recado = $("painel").querySelector(".corte");
  if (recado) recado.remove();
  if (!doCodigo) return;
  const p = document.createElement("p");
  p.className = "corte";
  p.textContent = `desenhado com ${doCodigo.desenhado_mm / 1000} m — corte da ` +
    `barra de ${doCodigo.do_codigo_mm / 1000} m que o código traz`;
  $("painel").appendChild(p);
}

function pintarModo() {
  document.querySelectorAll("#modo button").forEach((b) =>
    b.classList.toggle("ligado", b.dataset.modo === modo));
  $("titulo_candidatos").textContent =
    modo === "substituir" ? "trocar por" : "acrescentar";
}

function escolher(id, junto) {
  if (junto) {
    // shift ou ctrl: acrescenta, e clicar de novo tira - é o gesto de
    // qualquer lista, e o mesmo do CAD
    escolhidas = escolhidas.includes(id)
      ? escolhidas.filter((x) => x !== id) : escolhidas.concat([id]);
  } else {
    escolhidas = (escolhidas.length === 1 && escolhidas[0] === id) ? [] : [id];
  }
  escolhida = escolhidas.length ? escolhidas[escolhidas.length - 1] : null;
  pintar();
}

/* Os alvos de um comando: a seleção inteira. O comando é o mesmo para uma e
   para doze - ver api/nucleo._alvos - e por isso a tela não tem duas
   versões de cada botão. */
function alvos() {
  return escolhidas.slice();
}

function soltarEscolha() {
  escolhidas = [];
  escolhida = null;
}

/* Esticar e substituir TROCAM a peça - outro comprimento é outro código SAP -
   e o id vai junto. A seleção segue a peça nova, senão o painel fica
   apontando para uma que já saiu da linha. */
function seguir(antigo, novo) {
  if (!novo) return;
  escolhidas = escolhidas.map((x) => (x === antigo ? novo : x));
  escolhida = escolhidas[escolhidas.length - 1] || null;
}

/* -------------------------------------------------------------- comandos */
async function acrescentar(familia, dnPedido) {
  const dn = dnPedido !== undefined ? dnPedido : Number($("bitola").value);
  const resposta = await mandar({nome: "catalogo", familia, dn, limite: 12});
  const caixa = $("candidatos");
  caixa.innerHTML = "";
  const itens = resposta.itens || [];
  if (!itens.length) {
    caixa.innerHTML =
      `<p class="nada">a lista não tem ${familia} de ${dn}"</p>`;
    return;
  }
  itens.forEach((item) => {
    const b = document.createElement("button");
    b.innerHTML = `<span class="codigo">${item.sap}</span>${item.descricao}`;
    b.addEventListener("click", () => {
      // substituir não é remover e inserir: o comando é um só, ele volta num
      // desfazer só, e a peça nova cai exatamente onde a velha estava
      if (modo === "substituir" && escolhida) {
        const saindo = escolhida;
        mandar({nome: "substituir", alvo: escolhida, sap: item.sap})
          .then((r) => { if (r.ok) { seguir(saindo, r.peca); pintar(); } });
        return;
      }
      mandar({nome: "inserir", sap: item.sap,
              pos: escolhida ? posicaoDe(escolhida) + 1 : null});
    });
    caixa.appendChild(b);
  });
}

async function apagar(id) {
  if (!id) return;
  const juntas = escolhidas.includes(id) ? alvos() : [id];
  escolhidas = escolhidas.filter((x) => !juntas.includes(x));
  escolhida = escolhidas[escolhidas.length - 1] || null;
  await mandar({nome: "remover", alvo: id, alvos: juntas});
}

function trocar() {
  const peca = pecaEscolhida();
  if (!peca) return;
  // já abre o catálogo na família e na bitola da própria peça: quem quer
  // trocar uma curva de 8" quer ver as outras curvas de 8"
  modo = "substituir";
  $("familia").value = peca.familia;
  const dn = (peca.dn || [])[0];
  if (dn !== undefined) {
    const opcao = [...$("bitola").options].find((o) => Number(o.value) === dn);
    if (opcao) $("bitola").value = opcao.value;
  }
  pintarModo();
  acrescentar(peca.familia, dn);
}

function posicaoDe(id) {
  return documento.pecas.findIndex((p) => p.id === id);
}

/* ------------------------------------------------------------- arrastar

   Arrastar uma peça sobre outra a coloca na posição dela. E antes de soltar, a
   tela PERGUNTA ao motor o que aconteceria - comando `simular`, que executa e
   desfaz. A tela não sabe se duas peças encaixam, e não deve saber: a regra é
   do motor, e um "validador" no navegador seria a mesma regra escrita duas
   vezes, com duas chances de estar diferente. */
let arrasto = null;

function comecarArrasto(ev, id) {
  if (ev.button !== 0) return;
  arrasto = {id, x: ev.clientX, y: ev.clientY, sobre: null, recusa: null,
             andou: false};
  addEventListener("pointermove", moverArrasto);
  addEventListener("pointerup", soltarArrasto, {once: true});
}

async function moverArrasto(ev) {
  if (!arrasto) return;
  if (!arrasto.andou) {
    if (Math.abs(ev.clientX - arrasto.x) +
        Math.abs(ev.clientY - arrasto.y) < 6) return;
    arrasto.andou = true;
    marcarArrasto();
  }
  const sob = alvoSob(ev.clientX, ev.clientY);
  if (sob === arrasto.sobre) return;
  arrasto.sobre = sob;
  arrasto.recusa = null;
  esconderPrevisao();
  marcarArrasto();
  if (!sob || sob === arrasto.id) return;
  const pedido = arrasto.id + ">" + sob;
  // pergunta ao MOTOR o que aconteceria. A tela não sabe se duas peças
  // encaixam, e não deve saber: a regra é do motor, e uma segunda cópia dela
  // aqui seria a mesma regra com duas chances de estar diferente
  const resposta = await mandar({nome: "simular", comando: {
    nome: "mover", alvo: arrasto.id, para: posicaoDe(sob)}});
  if (!arrasto || arrasto.id + ">" + arrasto.sobre !== pedido) return;
  arrasto.recusa = resposta.recusa || null;
  marcarArrasto();
  mostrarPrevisao(arrasto.recusa || veredicto(resposta.seria),
                  Boolean(arrasto.recusa));
}

/* ---------------------------------------------------------- mover o balão

   Arrastar o balão não move peça nenhuma: move onde o número dela pousa na
   folha. Por isso ele não pergunta nada ao motor no meio do caminho - não há
   o que simular, nada pode ser recusado - e vira UM comando ao soltar, e não
   um por pixel, senão desfazer teria de ser apertado sessenta vezes.

   O que se vê enquanto o dedo está em cima é uma PRÉVIA, movida aqui na tela.
   O desenho de verdade volta do motor ao soltar, com o fio parando na borda
   do círculo como em toda folha. */
let balao = null;
let balaoAndou = false;      // o arrasto acabou de soltar: o clique não conta

function comecarBalao(ev, id) {
  if (ev.button !== 0) return;
  ev.stopPropagation();
  const g = ev.target.closest("g.balao");
  const pouso = g.querySelector("circle.pouso");
  balao = {id, g, svg: g.ownerSVGElement, centro: null,
           pouso: {x: Number(pouso.getAttribute("cx")),
                   y: Number(pouso.getAttribute("cy"))}};
  addEventListener("pointermove", moverBalao);
  addEventListener("pointerup", soltarBalao, {once: true});
}

function noDesenho(svg, x, y) {
  // o palco tem zoom e rolagem, e o SVG tem viewBox: quem converte pixel de
  // tela em unidade do desenho é a matriz do próprio SVG, e não uma conta
  // paralela aqui, que envelheceria no primeiro ajuste do zoom
  const ponto = svg.createSVGPoint();
  ponto.x = x;
  ponto.y = y;
  return ponto.matrixTransform(svg.getScreenCTM().inverse());
}

function moverBalao(ev) {
  if (!balao) return;
  balao.centro = noDesenho(balao.svg, ev.clientX, ev.clientY);
  const bola = balao.g.querySelector("circle.bola");
  const numero = balao.g.querySelector("text.n");
  const fio = balao.g.querySelector("line.fio");
  const alto = Number(numero.getAttribute("y")) - Number(bola.getAttribute("cy"));
  bola.setAttribute("cx", balao.centro.x);
  bola.setAttribute("cy", balao.centro.y);
  numero.setAttribute("x", balao.centro.x);
  numero.setAttribute("y", balao.centro.y + alto);
  const raio = Number(bola.getAttribute("r"));
  const dx = balao.centro.x - balao.pouso.x;
  const dy = balao.centro.y - balao.pouso.y;
  const anda = Math.hypot(dx, dy) || 1;
  fio.setAttribute("x2", balao.centro.x - (dx / anda) * raio);
  fio.setAttribute("y2", balao.centro.y - (dy / anda) * raio);
}

function soltarBalao() {
  removeEventListener("pointermove", moverBalao);
  const solto = balao;
  balao = null;
  balaoAndou = Boolean(solto && solto.centro);
  setTimeout(() => { balaoAndou = false; }, 0);
  if (!solto || !solto.centro) return;
  const dx = solto.centro.x - solto.pouso.x;
  const dy = solto.centro.y - solto.pouso.y;
  // o ângulo é o do croqui - anti-horário, 0 para a direita. O y do SVG
  // cresce para BAIXO, e é por isso que ele entra negado
  mandar({nome: "balao", alvo: solto.id,
          angulo: Math.round(Math.atan2(-dy, dx) * 1800 / Math.PI) / 10,
          distancia: Math.round(Math.hypot(dx, dy) * 10) / 10});
}

function marcarArrasto() {
  limparArrasto();
  if (!arrasto || !arrasto.andou) return;
  const saindo = document.querySelector(`g.peca[data-id="${arrasto.id}"]`);
  if (saindo) saindo.classList.add("arrastando");
  if (!arrasto.sobre || arrasto.sobre === arrasto.id) return;
  const recebendo = document.querySelector(
    `g.peca[data-id="${arrasto.sobre}"]`);
  if (recebendo) {
    recebendo.classList.add(arrasto.recusa ? "recusa" : "recebe");
  }
}

function limparArrasto() {
  document.querySelectorAll("g.peca.recebe, g.peca.recusa, g.peca.arrastando")
    .forEach((g) => g.classList.remove("recebe", "recusa", "arrastando"));
}

function veredicto(seria) {
  if (!seria) return "";
  const ruins = (seria.juncoes || []).filter((j) => j.acao !== "direta");
  if (!ruins.length) return "encaixa direto em todas as junções";
  return ruins.map((j) => `${j.acao} entre ${j.de} e ${j.para}`).join(" · ");
}

function alvoSob(x, y) {
  // elementFromPoint em SVG cai no <rect class="alvo">, que é a área de
  // clique que o motor desenha em cada peça
  const el = document.elementFromPoint(x, y);
  const g = el && el.closest ? el.closest("g.peca[data-id]") : null;
  return g ? g.dataset.id : null;
}

function mostrarPrevisao(texto, ruim) {
  const p = $("previsao");
  p.textContent = texto;
  p.className = ruim ? "previsao ruim" : "previsao";
  p.hidden = !texto;
}

function esconderPrevisao() { $("previsao").hidden = true; }

async function soltarArrasto() {
  const atual = arrasto;
  arrasto = null;
  removeEventListener("pointermove", moverArrasto);
  limparArrasto();
  esconderPrevisao();
  if (!atual || !atual.andou) return;
  if (!atual.sobre || atual.sobre === atual.id) return;
  // arrastar uma peça que está NA ESCOLHA arrasta a escolha inteira: o
  // bloco sai junto e chega junto, na ordem em que estava. Arrastar uma de
  // fora da escolha move só ela - o gesto foi sobre ela
  const juntas = escolhidas.includes(atual.id) ? alvos() : [atual.id];
  await mandar({nome: "mover", alvo: atual.id, alvos: juntas,
                para: posicaoDe(atual.sobre)});
}

/* -------------------------------------------------------------- exportar */
async function exportar(formato) {
  baixar(await mandar({nome: "exportar", formato}));
}

/* Salva o que veio na resposta, se veio arquivo. Não pergunta QUAL comando
   foi: o botão de DXF e o `exportar dxf` digitado na barra chegam aqui pelo
   mesmo caminho, porque os dois devolvem a mesma resposta. */
function baixar(resposta) {
  if (!resposta.ok || !resposta.arquivo) return false;
  const dados = resposta.texto !== undefined
    ? new Blob([resposta.texto], {type: resposta.mime})
    : new Blob([Uint8Array.from(atob(resposta.base64), (c) => c.charCodeAt(0))],
               {type: resposta.mime});
  const url = URL.createObjectURL(dados);
  const a = document.createElement("a");
  a.href = url;
  a.download = resposta.arquivo;
  a.click();
  URL.revokeObjectURL(url);
  recado("");
  return true;
}

/* ------------------------------------------------------- barra de comando

   Como no CAD: digita-se o verbo, os argumentos vêm atrás, e o prefixo basta
   quando identifica um verbo só. `des` desfaz; `gir 90` gira.

   O VOCABULÁRIO VEM DO MOTOR, uma vez, no arranque. A tela completa o que se
   digita com essa lista - ela não tem lista própria, pelo mesmo motivo que
   não tem cópia do documento: um verbo novo no motor apareceria na barra
   sozinho, e um verbo removido deixaria de ser oferecido.

   A busca de peça é do motor também (`procurar`), e vai a cada tecla com
   freio. Não há índice no navegador: seriam mil e setecentas peças copiadas
   para divergir da lista na primeira atualização. */
let verbos = [];
let sugestoes = [];
let marcada = 0;
let dito = [];              // o que já foi digitado, para a seta para cima
let ondeNoDito = -1;
let buscaPendente = null;

function anotar(texto, classe) {
  const ul = $("historico");
  const li = document.createElement("li");
  li.className = classe || "";
  li.textContent = texto;
  ul.appendChild(li);
  while (ul.children.length > 40) ul.removeChild(ul.firstChild);
  ul.scrollTop = ul.scrollHeight;
}

async function dizer(texto) {
  if (!texto.trim()) return;
  anotar(texto, "dito");
  dito.push(texto);
  ondeNoDito = dito.length;
  if (texto.trim() === "?") { listarVerbos(); return; }
  const resposta = await mandar({nome: "dizer", texto, alvo: escolhida,
                                 alvos: alvos()});
  if (!resposta.ok) { anotar(resposta.erro, "ruim"); return; }
  if (baixar(resposta)) { anotar(`salvo ${resposta.arquivo}`); return; }
  anotar(contar(resposta));
}

/* O que dizer de volta. O motor devolve o documento inteiro a cada comando,
   então a barra não precisa saber o que cada verbo faz - ela lê o resultado. */
function contar(resposta) {
  const verbo = (resposta.entendido || {}).verbo || resposta.comando;
  if (resposta.itens) {
    return resposta.itens.length
      ? `${resposta.itens.length} peças — veja abaixo`
      : "a lista não tem nada com isso";
  }
  const pecas = (documento.pecas || []).length;
  const alvo = resposta.peca ? ` ${nomeDaPeca(resposta.peca)}` : "";
  return `${verbo}${alvo} · ${pecas} peça${pecas === 1 ? "" : "s"} na linha`;
}

function nomeDaPeca(id) {
  const peca = (documento.pecas || []).find((p) => p.id === id);
  return peca ? peca.descricao : id;
}

function listarVerbos() {
  verbos.forEach((v) => anotar(
    `${v.nome.padEnd(13)}${v.resumo}${v.precisa_alvo ? "  (peça escolhida)" : ""}`));
}

/* ---------------------------------------------------------- as sugestões */
async function sugerir() {
  const texto = $("comando").value;
  const primeira = texto.trim().split(/\s+/)[0].toLowerCase();
  const espaco = /\s/.test(texto.trim() === "" ? "" : texto);
  const achados = [];
  if (primeira && !espaco) {
    verbos.filter((v) => v.nome.startsWith(primeira))
      .forEach((v) => achados.push({tipo: "verbo", ...v}));
  }
  pintarSugestoes(achados, texto);
  // a peça vem do motor, com freio: uma ida por pausa de digitação, e não
  // uma por tecla
  clearTimeout(buscaPendente);
  const alvoBusca = alvoDaBusca(texto);
  if (alvoBusca.length < 2) return;
  buscaPendente = setTimeout(async () => {
    const r = await mandar({nome: "procurar", texto: alvoBusca, limite: 8});
    if ($("comando").value !== texto) return;      // já digitou outra coisa
    pintarSugestoes(
      achados.concat((r.itens || []).map((i) => ({tipo: "peca", ...i}))),
      texto);
  }, 140);
}

/* O que procurar no catálogo: o verbo sai da frente, porque `inserir curva 8`
   procura por "curva 8" e não por "inserir curva 8". */
function alvoDaBusca(texto) {
  const partes = texto.trim().split(/\s+/);
  if (partes.length > 1 && verbos.some((v) => v.nome.startsWith(partes[0].toLowerCase()))) {
    return partes.slice(1).join(" ");
  }
  return texto.trim();
}

function pintarSugestoes(lista, texto) {
  sugestoes = lista;
  const ul = $("sugestoes");
  ul.innerHTML = "";
  ul.hidden = !lista.length;
  if (!lista.length) return;
  marcada = Math.min(marcada, lista.length - 1);
  let secao = null;
  lista.forEach((item, i) => {
    if (item.tipo !== secao) {
      secao = item.tipo;
      const cabeca = document.createElement("li");
      cabeca.className = "cabeca";
      cabeca.textContent = item.tipo === "verbo" ? "comandos" : "peças da lista";
      ul.appendChild(cabeca);
    }
    const li = document.createElement("li");
    if (i === marcada) li.className = "marcada";
    li.innerHTML = item.tipo === "verbo"
      ? `<span class="verbo">${item.nome}</span>` +
        `<span class="texto">${item.resumo}</span>` +
        `<span class="nota">${item.exemplo}</span>`
      : `<span class="codigo">${item.sap}</span>` +
        `<span class="texto">${item.descricao}</span>`;
    li.addEventListener("mousedown", (ev) => { ev.preventDefault(); aceitar(i); });
    ul.appendChild(li);
  });
}

function aceitar(i) {
  const item = sugestoes[i];
  if (!item) return;
  const campo = $("comando");
  if (item.tipo === "verbo") {
    // verbo sem argumento roda na hora; com argumento, fica esperando ele
    if (!item.argumentos.length) { campo.value = ""; dizer(item.nome); }
    else { campo.value = item.nome + " "; sugerir(); }
    campo.focus();
    return;
  }
  campo.value = "";
  esconderSugestoes();
  dizer(`inserir ${item.sap}`);
  campo.focus();
}

function esconderSugestoes() {
  sugestoes = [];
  marcada = 0;
  $("sugestoes").hidden = true;
}

function ligarBarra() {
  const campo = $("comando");
  campo.addEventListener("input", sugerir);
  campo.addEventListener("blur", () => setTimeout(esconderSugestoes, 120));
  campo.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      if (sugestoes.length) {
        ev.preventDefault();
        marcada = (marcada + (ev.key === "ArrowDown" ? 1 : -1) +
                   sugestoes.length) % sugestoes.length;
        pintarSugestoes(sugestoes, campo.value);
        return;
      }
      // sem sugestão aberta, a seta anda no que já foi digitado - como no CAD
      if (!dito.length) return;
      ev.preventDefault();
      ondeNoDito = Math.max(0, Math.min(dito.length - 1,
        ondeNoDito + (ev.key === "ArrowDown" ? 1 : -1)));
      campo.value = dito[ondeNoDito];
      return;
    }
    if (ev.key === "Tab" && sugestoes.length) {
      ev.preventDefault(); aceitar(marcada); return;
    }
    if (ev.key === "Enter") {
      ev.preventDefault();
      if (sugestoes.length && sugestoes[marcada] &&
          sugestoes[marcada].tipo === "peca") { aceitar(marcada); return; }
      const texto = campo.value;
      campo.value = "";
      esconderSugestoes();
      dizer(texto);
      return;
    }
    if (ev.key === "Escape") {
      ev.preventDefault();
      if (sugestoes.length) esconderSugestoes(); else campo.blur();
    }
  });
  // qualquer LETRA cai na barra, como no CAD. Só letra: dígito, + - e 0
  // continuam sendo o zoom, e todo comando começa por letra
  addEventListener("keydown", (ev) => {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(ev.target.tagName)) return;
    if (!/^[a-zA-Z?]$/.test(ev.key)) return;
    campo.focus();
  });
}

function ligar() {
  $("succao").addEventListener("click", () => {
    soltarEscolha();
    mandar({nome: "template", template: $("prontas").value || "SUCCAO",
            dn: Number($("bitola").value)});
  });
  $("desfazer").addEventListener("click", () => mandar({nome: "desfazer"}));
  $("refazer").addEventListener("click", () => mandar({nome: "refazer"}));
  $("remover").addEventListener("click", () => apagar(escolhida));
  $("espelhar").addEventListener("click", () => mandar({
    nome: "espelhar", alvo: escolhida, alvos: alvos(),
  }));
  // a MESMA peça noutro tamanho, nas escolhidas. O que a lista não tiver
  // naquele tamanho fica como está e vira aviso - ver api/nucleo._bitola
  $("trocar_bitola").addEventListener("change", async (ev) => {
    const dn = Number(ev.target.value);
    ev.target.value = "";
    if (!dn) return;
    const r = await mandar({nome: "bitola", dn, alvos: alvos()});
    if (r.ok) {
      escolhidas = r.pecas && r.pecas.length ? r.pecas : escolhidas;
      escolhida = escolhidas[escolhidas.length - 1] || null;
      pintar();
      if ((r.recado || []).length) recado(r.recado.join(" · "));
    }
  });
  // sem ângulo nem distância o comando ALTERNA - é o gesto da caixinha
  $("balao").addEventListener("click", () => mandar({
    nome: "balao", alvo: escolhida, alvos: alvos(),
  }));
  $("trocar").addEventListener("click", trocar);
  // esticar TROCA a peça - outro comprimento é outro código SAP - então a
  // seleção tem de seguir a peça nova, senão o painel fica apontando para
  // uma peça que saiu da linha
  const esticar = (pedido) => {
    const saindo = alvos();
    return mandar({nome: "esticar", alvo: escolhida, alvos: saindo, ...pedido})
      .then((r) => {
        if (!r.ok) return r;
        // as peças novas vêm na ordem das antigas: a seleção anda junto
        (r.pecas || []).forEach((novo, i) => seguir(saindo[i], novo));
        pintar();
        if ((r.recado || []).length) recado(r.recado.join(" · "));
        return r;
      });
  };
  $("esticar").addEventListener("click", () => esticar({passos: 1}));
  $("encolher").addEventListener("click", () => esticar({passos: -1}));
  $("barras").addEventListener("change", (ev) =>
    esticar({para_mm: Number(ev.target.value)}));
  // a pose da linha na folha. Girar é do conjunto: a peça de uma linha não
  // tem posição própria, ela cai onde a anterior deixou
  $("girar_esq").addEventListener("click", () => mandar({
    nome: "girar", graus: -90,
  }));
  $("girar_dir").addEventListener("click", () => mandar({
    nome: "girar", graus: 90,
  }));
  $("espelhar_linha").addEventListener("click", () => mandar({
    nome: "espelhar",
  }));
  $("subir").addEventListener("click", () => mandar({
    nome: "mover", alvo: escolhida, alvos: alvos(),
    para: Math.max(0, posicaoDe(escolhida) - 1),
  }));
  $("descer").addEventListener("click", () => mandar({
    nome: "mover", alvo: escolhida, alvos: alvos(),
    para: posicaoDe(escolhida) + 1,
  }));
  $("comprimento").addEventListener("change", (ev) => mandar({
    nome: "alterar", alvo: escolhida, alvos: alvos(),
    campos: {comprimento_mm: Number(ev.target.value)},
  }));
  $("fonte").addEventListener("change", (ev) => mandar({
    nome: "alterar", alvo: escolhida, alvos: alvos(),
    campos: {fonte: ev.target.value},
  }));
  $("familia").addEventListener("change", (ev) => acrescentar(ev.target.value));
  $("bitola").addEventListener("change", () => {
    if ($("familia").value) acrescentar($("familia").value);
  });
  document.querySelectorAll("#modo button").forEach((b) =>
    b.addEventListener("click", () => {
      modo = b.dataset.modo;
      pintarModo();
    }));

  // ------------------------------------------------------------ o palco
  const vista = $("vista");
  vista.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    // exponencial: cada passo multiplica, para o zoom andar igual perto e
    // longe. Somar daria passos gigantes no fim e imperceptíveis no começo
    ampliar(Math.exp(-ev.deltaY * 0.0015), ev.clientX, ev.clientY);
  }, {passive: false});
  vista.addEventListener("pointerdown", comecarFolha);
  vista.addEventListener("dblclick", () => ajustar());
  $("mais").addEventListener("click", () => ampliar(1.35));
  $("menos").addEventListener("click", () => ampliar(1 / 1.35));
  $("zoom_texto").addEventListener("click", ajustar);
  // o fundo escuro é da TELA: não vai ao motor, não entra no desfazer e não
  // sai no arquivo. Fica guardado no navegador porque é preferência de quem
  // olha, e não estado do documento
  $("fundo").addEventListener("click", () => {
    const escuro = vista.classList.toggle("escuro");
    $("fundo").classList.toggle("ligado", escuro);
    try { localStorage.setItem("fundo_escuro", escuro ? "1" : ""); } catch (e) {}
  });
  try {
    if (localStorage.getItem("fundo_escuro")) {
      vista.classList.add("escuro");
      $("fundo").classList.add("ligado");
    }
  } catch (e) {}

  addEventListener("keydown", (ev) => {
    const digitando = /^(INPUT|SELECT|TEXTAREA)$/.test(ev.target.tagName);
    if (!ev.ctrlKey && !ev.metaKey && !digitando) {
      if (ev.key === "Delete" || ev.key === "Backspace") {
        if (escolhida) { ev.preventDefault(); apagar(escolhida); }
        return;
      }
      if (ev.key === "+" || ev.key === "=") { ev.preventDefault(); ampliar(1.35); }
      if (ev.key === "-") { ev.preventDefault(); ampliar(1 / 1.35); }
      if (ev.key === "0") { ev.preventDefault(); ajustar(); }
      if (ev.key === "Escape") { soltarEscolha(); pintar(); }
      return;
    }
    if (!(ev.ctrlKey || ev.metaKey)) return;
    if (ev.key === "a" && !digitando) {
      // escolher a linha inteira: é o gesto de quem vai trocar a bitola de
      // tudo, e o comando aceita a lista inteira do mesmo jeito
      ev.preventDefault();
      escolhidas = (documento.pecas || []).map((p) => p.id);
      escolhida = escolhidas[escolhidas.length - 1] || null;
      pintar();
    }
    if (ev.key === "z" && !ev.shiftKey) { ev.preventDefault(); mandar({nome: "desfazer"}); }
    if (ev.key === "y" || (ev.key === "z" && ev.shiftKey)) {
      ev.preventDefault(); mandar({nome: "refazer"});
    }
  });
  $("folha").addEventListener("click", async () =>
    abrirFolha(await mandar({nome: "folha"})));
  document.querySelectorAll("[data-modo-desenho]").forEach((b) =>
    b.addEventListener("click", () => mandar({
      nome: "modo", modo: b.dataset.modoDesenho,
    })));
  document.querySelectorAll("[data-exportar]").forEach((b) =>
    b.addEventListener("click", () => exportar(b.dataset.exportar)));
  // salvar é exportar como qualquer outro formato - o que muda é que este
  // volta a ser documento. Abrir troca o documento inteiro, e por isso a
  // seleção cai: o id escolhido era do projeto anterior
  $("salvar").addEventListener("click", () => exportar("linha"));
  $("abrir").addEventListener("click", () => $("arquivo").click());
  $("arquivo").addEventListener("change", async (ev) => {
    const ficheiro = ev.target.files[0];
    ev.target.value = "";     // reabrir o MESMO arquivo tem de disparar de novo
    if (!ficheiro) return;
    soltarEscolha();
    const resposta = await mandar({nome: "abrir", texto: await ficheiro.text()});
    // o que mudou desde o dia em que se salvou: peça que saiu da lista, cota
    // que a folha corrigiu. Aparece por escrito, e não calado
    if (resposta.ok && (resposta.recado || []).length) {
      recado(resposta.recado.join(" · "));
    }
  });
  addEventListener("resize", avisarTamanho);
}

const FAMILIAS = ["TUBO", "CURVA", "TE", "REDUCAO_CONCENTRICA",
  "REDUCAO_EXCENTRICA", "VALVULA_BORBOLETA", "VALVULA_GAVETA",
  "VALVULA_RETENCAO", "VALVULA_HIDRAULICA", "MEDIDOR", "CRIVO", "MANIFOLD",
  "FLANGE_CEGA", "ADAPTADOR"];

let tamanhoPendente = null;
function avisarTamanho() {
  clearTimeout(tamanhoPendente);
  tamanhoPendente = setTimeout(() => {
    // o motor escala o desenho para caber NESTA caixa - a de verdade, medida
    // agora. Antes ia uma fração da altura da janela, e sobrava papel branco
    const caixa = $("vista").getBoundingClientRect();
    mandar({nome: "janela", largura: Math.round(caixa.width),
            altura_max: Math.round(caixa.height)});
  }, 200);
}

async function comecar() {
  const estilo = await mandar({nome: "estilo"});
  if (estilo.css) $("desenho").textContent = estilo.css;
  const vocabulario = await mandar({nome: "vocabulario"});
  verbos = vocabulario.verbos || [];
  // as montagens prontas vêm do motor, como os verbos: uma montagem nova
  // aparece na lista sozinha, sem ninguém tocar nesta tela
  (vocabulario.montagens || []).forEach((m) =>
    $("prontas").add(new Option(m.nome, m.chave)));
  FAMILIAS.forEach((f) => $("familia").add(new Option(f.toLowerCase().replace(/_/g, " "), f)));
  ligar();
  ligarBarra();
  ajustar();
  anotar("digite ? para ver os comandos, ou o nome de uma peça");
  avisarTamanho();
}

comecar();
