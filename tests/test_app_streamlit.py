"""Teste de interface: sobe o app.py com o AppTest do Streamlit, MCP real e LLM simulado.

Rodar: python -m unittest tests.test_app_streamlit -v
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

from src.agent import dataops_agent as agente_mod
from src.agent.cache import limpar_tudo
from tests.test_resiliencia_cache import ClienteFalso, erro_api, resposta_ferramenta, resposta_texto

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SQL = "SELECT categoria, COUNT(*) AS total FROM loja GROUP BY categoria"


def roteiro_consulta(modelo, n):
    if n % 2 == 1:
        return resposta_ferramenta("executar_query_analitica", {"query": SQL})
    return resposta_texto("Há lojas em várias categorias; veja a tabela.")


class TestApp(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("GEMINI_API_KEY", "chave-falsa-para-teste")
        limpar_tudo()
        os.environ["GEMINI_MODELS"] = "m1,m2"
        import src.agent.resiliencia as r
        r._CADEIA = None  # recria a cadeia com os modelos do teste

    def _app(self, cliente):
        patch = mock.patch.object(agente_mod.genai, "Client", lambda api_key=None: cliente)
        patch.start()
        self.addCleanup(patch.stop)
        return AppTest.from_file(APP, default_timeout=60)

    def test_pagina_inicial_tem_sugestoes(self):
        at = self._app(ClienteFalso(roteiro_consulta)).run()
        self.assertFalse(at.exception)
        self.assertGreaterEqual(len([b for b in at.button if str(b.key).startswith("sug_")]), 8)

    def test_pergunta_gera_tabela_grafico_e_badges(self):
        at = self._app(ClienteFalso(roteiro_consulta)).run()
        at.chat_input[0].set_value("Quantas lojas por categoria?").run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(len(at.chat_message), 2)
        self.assertTrue(at.dataframe)  # tabela renderizada
        legendas = " ".join(c.value for c in at.caption)
        self.assertIn("chamada(s) ao LLM", legendas)

    def test_segunda_pergunta_igual_vem_do_cache(self):
        cliente = ClienteFalso(roteiro_consulta)
        at = self._app(cliente).run()
        at.chat_input[0].set_value("Quantas lojas por categoria?").run()
        antes = len(cliente.chamadas)
        at.chat_input[0].set_value("lojas por categoria, quantas?").run()
        self.assertEqual(len(cliente.chamadas), antes)
        self.assertIn("resposta do cache", " ".join(c.value for c in at.caption))

    def test_alta_demanda_mostra_aviso_e_nao_quebra(self):
        at = self._app(ClienteFalso(lambda m, n: erro_api(503))).run()
        at.chat_input[0].set_value("Quantas lojas existem?").run()
        self.assertFalse(at.exception, at.exception)
        self.assertTrue(any("instável" in w.value for w in at.warning))


if __name__ == "__main__":
    unittest.main(verbosity=2)
