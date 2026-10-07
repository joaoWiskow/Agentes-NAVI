"""Testes dos guardrails e da execucao de consultas analiticas."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.database.init_db import conectar, criar_tabelas
from src.tools import query_tools


class TestQueryTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.caminho_db = Path(self.tmp.name) / "dataops.db"
        with conectar(self.caminho_db) as conexao:
            criar_tabelas(conexao)
            conexao.executemany(
                "INSERT INTO loja (nome, categoria, piso, inaugurada_em) VALUES (?, ?, ?, ?)",
                [
                    ("Loja A", "Moda", 1, "2025-01-01"),
                    ("Loja B", "Casa", 2, "2025-01-02"),
                    ("Loja C", "Alimentacao", 3, "2025-01-03"),
                ],
            )
            conexao.commit()
        self.patch_caminho = mock.patch.object(query_tools, "CAMINHO_DB", self.caminho_db)
        self.patch_caminho.start()

    def tearDown(self):
        self.patch_caminho.stop()
        self.tmp.cleanup()

    def test_executor_rejeita_escrita_e_multiplas_instrucoes(self):
        for consulta in ("DELETE FROM loja", "SELECT * FROM loja; DROP TABLE loja"):
            with self.subTest(consulta=consulta):
                resultado = query_tools.executar_query_analitica(consulta)
                self.assertFalse(resultado["sucesso"])
                self.assertIn("Guardrail", resultado["erro"])

        with conectar(self.caminho_db) as conexao:
            self.assertEqual(conexao.execute("SELECT COUNT(*) FROM loja").fetchone()[0], 3)

    def test_executor_retorna_colunas_linhas_e_respeita_limite(self):
        resultado = query_tools.executar_query_analitica(
            "SELECT nome, piso FROM loja ORDER BY id",
            limite_linhas=2,
        )

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["colunas"], ["nome", "piso"])
        self.assertEqual(
            resultado["linhas"],
            [{"nome": "Loja A", "piso": 1}, {"nome": "Loja B", "piso": 2}],
        )
        self.assertEqual(resultado["total_linhas"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)