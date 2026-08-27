/* A tela. Ela não sabe nenhuma regra, e não guarda o documento.

   Cada comando devolve o documento inteiro e a tela repinta. O único estado
   que ela tem é `escolhida` - o id da peça selecionada - e mesmo esse é um id
   que veio do motor. Foi essa decisão que dispensou a sincronização: não há
   duas cópias para divergir.

   Ver docs/LOGICA.md 2. */

let documento = null;
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
    if (id === escolhida) g.classList.add("escolhida");
    // o arrasto é estado DA TELA, como a seleção: cada repintura o reaplica.
    // A tela repinta a cada comando - inclusive o `simular` do próprio
    // arrasto - então guardar elemento em vez de id perderia o arrasto no
    // meio dele. Foi o que aconteceu na primeira versão.
    if (arrasto && id === arrasto.id) g.classList.add("arrastando");
    if (arrasto && id === arrasto.sobre && id !== arrasto.id) {
      g.classList.add(arrasto.recusa ? "recusa" : "recebe");
    }
    g.addEventListener("click", () => escolher(id));
    g.addEventListener("pointerdown", (ev) => comecarArrasto(ev, id));
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
  documento.lista.forEach((r) => porSap.set(r.sap, r));
  documento.pecas.forEach((peca) => {
    const registro = porSap.get(peca.sap);
    corpo.appendChild(linhaDaTabela({
      id: peca.id, sap: peca.sap, descricao: peca.descricao,
      qtd: registro ? registro.qtd : 1,
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
  if (registro.id === escolhida) tr.classList.add("escolhida");
  tr.innerHTML =
    `<td class="qtd">${registro.qtd}</td>` +
    `<td class="sap">${registro.sap || ""}</td>` +
    `<td>${registro.descricao || ""}</td>` +
    // só a peça da linha tem × : ferragem é consequência, e some sozinha
    // quando a peça que a puxou sai
    `<td class="apagar">${registro.id ? "×" : ""}</td>`;
  if (registro.id) {
    tr.addEventListener("click", () => escolher(registro.id));
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
  if (ev.button === 0 && ev.target.closest && ev.target.closest("g.peca")) return;
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
  const fonte = $("fonte");
  if (!fonte.options.length) {
    ["IRRIGAFOUR", "NETAFIM", "MP", "RAN", "ARAD", "DOROT", "SAINT-GOBAIN"]
      .forEach((f) => fonte.add(new Option(f, f)));
  }
  fonte.value = peca.fonte || "IRRIGAFOUR";
  $("espelhar").classList.toggle("ligado", peca.sentido < 0);
  $("modo").hidden = false;
  pintarModo();
}

function pintarModo() {
  document.querySelectorAll("#modo button").forEach((b) =>
    b.classList.toggle("ligado", b.dataset.modo === modo));
  $("titulo_candidatos").textContent =
    modo === "substituir" ? "trocar por" : "acrescentar";
}

function escolher(id) {
  escolhida = (escolhida === id) ? null : id;
  pintar();
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
        mandar({nome: "substituir", alvo: escolhida, sap: item.sap})
          .then((r) => { if (r.ok && r.peca) { escolhida = r.peca; pintar(); } });
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
  if (escolhida === id) escolhida = null;
  await mandar({nome: "remover", alvo: id});
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
  await mandar({nome: "mover", alvo: atual.id, para: posicaoDe(atual.sobre)});
}

/* -------------------------------------------------------------- exportar */
async function exportar(formato) {
  const resposta = await mandar({nome: "exportar", formato});
  if (!resposta.ok) return;
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
}

function ligar() {
  $("succao").addEventListener("click", () => mandar({
    nome: "template", template: "SUCCAO", dn: Number($("bitola").value),
  }));
  $("desfazer").addEventListener("click", () => mandar({nome: "desfazer"}));
  $("refazer").addEventListener("click", () => mandar({nome: "refazer"}));
  $("remover").addEventListener("click", () => apagar(escolhida));
  $("espelhar").addEventListener("click", () => mandar({
    nome: "espelhar", alvo: escolhida,
  }));
  $("trocar").addEventListener("click", trocar);
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
    nome: "mover", alvo: escolhida, para: Math.max(0, posicaoDe(escolhida) - 1),
  }));
  $("descer").addEventListener("click", () => mandar({
    nome: "mover", alvo: escolhida, para: posicaoDe(escolhida) + 1,
  }));
  $("comprimento").addEventListener("change", (ev) => mandar({
    nome: "alterar", alvo: escolhida,
    campos: {comprimento_mm: Number(ev.target.value)},
  }));
  $("fonte").addEventListener("change", (ev) => mandar({
    nome: "alterar", alvo: escolhida, campos: {fonte: ev.target.value},
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
      if (ev.key === "Escape") { escolhida = null; pintar(); }
      return;
    }
    if (!(ev.ctrlKey || ev.metaKey)) return;
    if (ev.key === "z" && !ev.shiftKey) { ev.preventDefault(); mandar({nome: "desfazer"}); }
    if (ev.key === "y" || (ev.key === "z" && ev.shiftKey)) {
      ev.preventDefault(); mandar({nome: "refazer"});
    }
  });
  document.querySelectorAll("[data-modo-desenho]").forEach((b) =>
    b.addEventListener("click", () => mandar({
      nome: "modo", modo: b.dataset.modoDesenho,
    })));
  document.querySelectorAll("[data-exportar]").forEach((b) =>
    b.addEventListener("click", () => exportar(b.dataset.exportar)));
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
  FAMILIAS.forEach((f) => $("familia").add(new Option(f.toLowerCase().replace(/_/g, " "), f)));
  ligar();
  ajustar();
  avisarTamanho();
}

comecar();
