#!/usr/bin/env python3
"""A prancha: todas as bitolas numa pagina so, para publicar e olhar.

Nao desenha nada. Junta o que desenhar_simbolos.py e desenhar_linha.py ja
fazem - as pecas e as montagens - e poe as duas coisas atras de um seletor de
bitola, como o carimbo de uma prancha de verdade: quem olha escolhe a bitola e
ve o mesmo caderno naquela bitola.

Duas regras do carimbo, e as duas dizem algo verdadeiro:

  a tira de bitolas e uma SERIE - 3" a 14", na ordem em que a casa compra -
  entao ela e uma tira horizontal e nao um menu;
  as duas vistas sao as duas coisas que o programa faz: o catalogo da peca e
  a linha montada. Nao ha terceira.

Uso: python3 tools/prancha.py > prancha.html
"""
import argparse
import sys

sys.path.insert(0, ".")
from tools import desenhar_linha, desenhar_simbolos as ds  # noqa: E402

BITOLAS = (3, 4, 5, 6, 8, 10, 12, 14)

FONTES = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
          'family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;'
          '500&family=Source+Sans+3:wght@400;600&display=swap">')

# O ESTILO de desenhar_simbolos ja e o sistema da casa: traco fino preto, eixo
# vermelho traco-ponto, anotacao cinza. Aqui nao se troca nada dele - so se
# acrescenta o que a folha solta nao precisava: o carimbo, o seletor e o tema
# escuro, e as duas cores que estavam soltas no ESTILO viram token.
ESTILO_PRANCHA = """
:root{
  --papel:#fcfcfb;--fundo:#f1f0ec;--tinta:#16181d;--eixo:#b5382c;
  --anota:#8a8f98;--linha:#e4e4de;--chapa:#f2f2ee;--titulo:#3b4049;
  --malha:#8f949c;--tenue:#b3b7bf;--borda:#d8d8d1;
  --carimbo:#fffffe;--realce:#f6f5f0;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --papel:#1b1e23;--fundo:#121418;--tinta:#e7e8ea;--eixo:#df6d5e;
    --anota:#8b9099;--linha:#2c3037;--chapa:#23272e;--titulo:#aeb4bf;
    --malha:#7d838d;--tenue:#6b7079;--borda:#2c3037;
    --carimbo:#1f232a;--realce:#1f2329;
  }
}
:root[data-theme="dark"]{
  --papel:#1b1e23;--fundo:#121418;--tinta:#e7e8ea;--eixo:#df6d5e;
  --anota:#8b9099;--linha:#2c3037;--chapa:#23272e;--titulo:#aeb4bf;
  --malha:#7d838d;--tenue:#6b7079;--borda:#2c3037;
  --carimbo:#1f232a;--realce:#1f2329;
}
body{background:var(--fundo);padding:0;
  font-family:"Source Sans 3",ui-sans-serif,system-ui,sans-serif}
.papel{max-width:1360px;padding:26px 22px 70px}

/* o carimbo: cabecalho de prancha, nao hero */
.carimbo{background:var(--carimbo);border:1px solid var(--borda);
  display:grid;grid-template-columns:minmax(0,1fr) auto;
  align-items:stretch;margin-bottom:20px}
.carimbo .capa{padding:20px 22px 18px}
.carimbo h1{font-family:Archivo,sans-serif;font-size:26px;font-weight:700;
  letter-spacing:-.022em;margin:0;text-wrap:balance;color:var(--tinta)}
.carimbo p{margin:8px 0 0;max-width:62ch;color:var(--titulo);font-size:14px;
  line-height:1.6}
.carimbo dl{margin:0;border-left:1px solid var(--borda);display:grid;
  grid-template-columns:auto auto;align-content:start;gap:0;
  font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;
  font-variant-numeric:tabular-nums}
.carimbo dt{padding:7px 14px 7px 18px;color:var(--anota);
  text-transform:uppercase;letter-spacing:.09em;font-size:9.5px;
  border-bottom:1px solid var(--linha);white-space:nowrap}
.carimbo dd{margin:0;padding:7px 20px 7px 0;color:var(--tinta);
  border-bottom:1px solid var(--linha);text-align:right;white-space:nowrap}
.carimbo dt:last-of-type,.carimbo dd:last-of-type{border-bottom:0}
@media (max-width:760px){
  .carimbo{grid-template-columns:1fr}
  .carimbo dl{border-left:0;border-top:1px solid var(--borda)}
}

/* a tira de bitola: a serie que a casa compra, na ordem */
.controles{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end;
  margin-bottom:18px}
.grupo{display:flex;flex-direction:column;gap:6px}
.grupo>span{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:9.5px;
  text-transform:uppercase;letter-spacing:.1em;color:var(--anota)}
.tira{display:flex;flex-wrap:wrap;border:1px solid var(--borda);
  background:var(--carimbo)}
.tira button{appearance:none;border:0;border-right:1px solid var(--linha);
  background:transparent;color:var(--titulo);cursor:pointer;
  padding:8px 15px;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:12px;font-variant-numeric:tabular-nums;letter-spacing:.01em}
.tira button:last-child{border-right:0}
.tira button:hover{background:var(--realce);color:var(--tinta)}
.tira button:focus-visible{outline:2px solid var(--eixo);outline-offset:-2px}
.tira button[aria-selected="true"]{background:var(--tinta);color:var(--papel)}
.tira.vistas button{padding:8px 17px;font-family:Archivo,sans-serif;
  font-size:12px;font-weight:500;letter-spacing:.01em}

.prancha{background:var(--papel);border:1px solid var(--borda);
  padding:4px 22px 30px}
.vista[hidden]{display:none}
.vista>h2:first-of-type{margin-top:22px}
.nota-pe{margin:16px 0 0;color:var(--anota);font-size:11.5px;max-width:78ch}
.nota-pe b{color:var(--titulo);font-weight:600}

/* as duas cores que estavam soltas no ESTILO, agora em token */
.geo .malha,.geo .furo,.geo .solda{stroke:var(--malha)}
.geo .fluxo{fill:var(--malha)}
.tarja .fonte{color:var(--tenue)}
figure{background:transparent}
.legenda{padding:12px 0 20px;margin-bottom:0}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

TROCA = """
(function(){
  var tiras = document.querySelectorAll('.tira');
  function marcar(tira, valor, atributo){
    tira.querySelectorAll('button').forEach(function(b){
      b.setAttribute('aria-selected', b.dataset[atributo] === valor);
    });
  }
  function mostrar(){
    var dn = document.querySelector('.tira.bitolas [aria-selected="true"]');
    var vista = document.querySelector('.tira.vistas [aria-selected="true"]');
    document.querySelectorAll('.vista').forEach(function(v){
      v.hidden = !(v.dataset.dn === dn.dataset.dn
                   && v.dataset.vista === vista.dataset.vista);
    });
    try { localStorage.setItem('prancha',
      JSON.stringify({dn: dn.dataset.dn, vista: vista.dataset.vista})); }
    catch (e) {}
  }
  tiras.forEach(function(tira){
    var atributo = tira.classList.contains('bitolas') ? 'dn' : 'vista';
    tira.addEventListener('click', function(e){
      var b = e.target.closest('button');
      if (!b) return;
      marcar(tira, b.dataset[atributo], atributo);
      mostrar();
    });
  });
  try {
    var salvo = JSON.parse(localStorage.getItem('prancha') || 'null');
    if (salvo) {
      marcar(document.querySelector('.tira.bitolas'), salvo.dn, 'dn');
      marcar(document.querySelector('.tira.vistas'), salvo.vista, 'vista');
    }
  } catch (e) {}
  mostrar();
})();
"""


def _tira(classe, itens, atributo, escolhido):
    botoes = "".join(
        f'<button type="button" role="tab" data-{atributo}="{valor}" '
        f'aria-selected="{str(valor == escolhido).lower()}">{rotulo}</button>'
        for valor, rotulo in itens)
    return f'<div class="tira {classe}" role="tablist">{botoes}</div>'


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dn", type=float, default=8,
                   help="a bitola que abre a prancha")
    arg = p.parse_args()

    vistas, total_pecas = [], 0
    for dn in BITOLAS:
        pecas, quantas = ds.fragmento(dn)
        montagens, quantas_linhas = desenhar_linha.fragmento(dn)
        total_pecas = quantas
        vistas.append(
            f'<div class="vista" data-dn="{dn:g}" data-vista="pecas" hidden>'
            f'{ds.legenda()}{pecas}'
            f'<p class="nota-pe"><b>{quantas} peças em {dn:g}"</b> · a cota vem '
            f'da folha do fabricante, do desenho da casa ou nada — e a fonte '
            f'está escrita na tarja de cada peça. Dentro do desenho só cota; '
            f'o resto é fato da peça e mora embaixo dela.</p></div>')
        vistas.append(
            f'<div class="vista" data-dn="{dn:g}" data-vista="linhas" hidden>'
            f'{ds.legenda()}{montagens}'
            f'<p class="nota-pe"><b>{quantas_linhas} montagens em {dn:g}"</b> · '
            f'cada peça é desenhada uma vez, na origem, olhando para +x. '
            f'Encaixar é girar pelo ângulo corrente e transladar até o ponto '
            f'corrente — o tamanho vem da tabela, o ângulo vem da curva, e a '
            f'rotação é acumulada.</p></div>')

    carimbo = (
        '<div class="carimbo"><div class="capa">'
        '<h1>Peças de sucção e recalque</h1>'
        '<p>Cada peça é um símbolo paramétrico: a forma vem da família, a '
        'medida vem da tabela de cotas, e a mesma peça serve a folha e a '
        'linha montada. Vista lateral, milímetro real, traço da casa.</p>'
        '</div><dl>'
        f'<dt>bitolas</dt><dd>3" – 14" · DN35 – DN225</dd>'
        f'<dt>peças por bitola</dt><dd>{total_pecas}</dd>'
        '<dt>códigos que desenham</dt><dd>1.487 de 5.157</dd>'
        '<dt>cota conferida</dt><dd>102/102 em milímetro</dd>'
        '<dt>escala</dt><dd>ajustada à célula</dd>'
        '</dl></div>')

    controles = (
        '<div class="controles">'
        '<div class="grupo"><span>bitola de aço</span>'
        + _tira("bitolas", [(f"{d:g}", f'{d:g}"') for d in BITOLAS],
                "dn", f"{arg.dn:g}") +
        '</div><div class="grupo"><span>vista</span>'
        + _tira("vistas", [("pecas", "Peças"), ("linhas", "Linhas montadas")],
                "vista", "pecas") +
        '</div></div>')

    print(f'<title>Peças de sucção e recalque</title>{FONTES}'
          f'<style>{ds.ESTILO}{desenhar_linha.ESTILO_LINHA}{ESTILO_PRANCHA}'
          f'</style><div class="papel">{carimbo}{controles}'
          f'<div class="prancha">{"".join(vistas)}</div></div>'
          f'<script>{TROCA}</script>')
    print(f"# {len(BITOLAS)} bitolas x 2 vistas", file=sys.stderr)


if __name__ == "__main__":
    main()
