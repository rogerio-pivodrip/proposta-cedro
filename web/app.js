/* A tela. Ela não sabe nenhuma regra, e não guarda o documento.

   Cada comando devolve o documento inteiro e a tela repinta. O único estado
   que ela tem é `escolhida` - o id da peça selecionada - e mesmo esse é um id
   que veio do motor. Foi essa decisão que dispensou a sincronização: não há
   duas cópias para divergir.

   Ver docs/LOGICA.md 2. */

let documento = null;
let escolhida = null;

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
}

function pintarVista() {
  const alvo = $("vista");
  const svg = documento.vista && documento.vista.svg;
  alvo.innerHTML = svg || '<p class="nada">Nada para desenhar ainda.</p>';
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
    `<td>${registro.descricao || ""}</td>`;
  if (registro.id) tr.addEventListener("click", () => escolher(registro.id));
  return tr;
}

function pintarAvisos() {
  $("avisos").innerHTML = (documento.avisos || [])
    .map((a) => `<p>${a}</p>`).join("");
}

function pecaEscolhida() {
  return (documento.pecas || []).find((p) => p.id === escolhida) || null;
}

function pintarPainel() {
  const peca = pecaEscolhida();
  $("painel").hidden = !peca;
  if (!peca) return;
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
}

function escolher(id) {
  escolhida = (escolhida === id) ? null : id;
  pintar();
}

/* -------------------------------------------------------------- comandos */
async function acrescentar(familia) {
  const dn = Number($("bitola").value);
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
    b.addEventListener("click", () => mandar({
      nome: "inserir", sap: item.sap,
      pos: escolhida ? posicaoDe(escolhida) + 1 : null,
    }));
    caixa.appendChild(b);
  });
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
  $("remover").addEventListener("click", async () => {
    const id = escolhida;
    escolhida = null;
    await mandar({nome: "remover", alvo: id});
  });
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
  addEventListener("keydown", (ev) => {
    if (!(ev.ctrlKey || ev.metaKey)) return;
    if (ev.key === "z" && !ev.shiftKey) { ev.preventDefault(); mandar({nome: "desfazer"}); }
    if (ev.key === "y" || (ev.key === "z" && ev.shiftKey)) {
      ev.preventDefault(); mandar({nome: "refazer"});
    }
  });
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
    const caixa = $("vista").getBoundingClientRect();
    mandar({nome: "janela", largura: Math.round(caixa.width) - 20,
            altura_max: Math.round(innerHeight * 0.62)});
  }, 200);
}

async function comecar() {
  const estilo = await mandar({nome: "estilo"});
  if (estilo.css) $("desenho").textContent = estilo.css;
  FAMILIAS.forEach((f) => $("familia").add(new Option(f.toLowerCase().replace(/_/g, " "), f)));
  ligar();
  avisarTamanho();
}

comecar();
