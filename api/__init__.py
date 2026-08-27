"""A camada fina entre o motor e a tela.

Ela nao tem regra nenhuma. Traduz JSON em comando e documento em JSON, e mais
nada - qualquer regra que aparecer aqui e regra no lugar errado, porque as
duas telas (a do navegador e a do Electron) teriam de repeti-la.
"""
from .nucleo import Sessao, executar          # noqa: F401
