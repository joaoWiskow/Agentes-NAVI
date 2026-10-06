"""Testes das ferramentas de inspeção do schema SQLite."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.init_db import conectar, criar_tabelas
from tools import schema_tools


class TestSchemaTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conexao = conectar(Path(self.tmp.name) / "schema.db")
        criar_tabelas(self.conexao)
        self.patch_conectar = mock.patch.object(
            schema_tools, "conectar", return_value=self.conexao
        )
        self.patch_conectar.start()

    def tearDown(self):
        self.patch_conectar.stop()
        self.conexao.close()
        self.tmp.cleanup()

    def test_listar_tabelas_retorna_tabelas_de_dados_em_ordem(self):
        self.assertEqual(
            schema_tools.listar_tabelas(),
            ["contrato", "loja", "movimentacao"],
        )

    def test_descrever_schema_tabela_retorna_colunas_e_restricoes(self):
        self.assertEqual(
            schema_tools.descrever_schema_tabela("loja"),
            {
                "tabela": "loja",
                "colunas": [
                    {
                        "nome": "id",
                        "tipo": "INTEGER",
                        "obrigatoria": False,
                        "chave_primaria": True,
                    },
                    {
                        "nome": "nome",
                        "tipo": "VARCHAR(150)",
                        "obrigatoria": True,
                        "chave_primaria": False,
                    },
                    {
                        "nome": "categoria",
                        "tipo": "VARCHAR(100)",
                        "obrigatoria": True,
                        "chave_primaria": False,
                    },
                    {
                        "nome": "piso",
                        "tipo": "INTEGER",
                        "obrigatoria": True,
                        "chave_primaria": False,
                    },
                    {
                        "nome": "inaugurada_em",
                        "tipo": "TIMESTAMP",
                        "obrigatoria": True,
                        "chave_primaria": False,
                    },
                ],
            },
        )

    def test_obter_chaves_estrangeiras_retorna_relacionamentos(self):
        self.assertEqual(
            schema_tools.obter_chaves_estrangeiras("contrato"),
            [
                {
                    "coluna_local": "loja_id",
                    "tabela_referenciada": "loja",
                    "coluna_referenciada": "id",
                }
            ],
        )

    def test_obter_chaves_estrangeiras_retorna_lista_vazia_quando_nao_existirem(self):
        self.assertEqual(schema_tools.obter_chaves_estrangeiras("loja"), [])

    def test_operacoes_rejeitam_tabela_inexistente_e_injecao(self):
        nome_invalido = "loja; DROP TABLE contrato"

        for operacao in (
            schema_tools.descrever_schema_tabela,
            schema_tools.obter_chaves_estrangeiras,
        ):
            with self.subTest(operacao=operacao.__name__):
                with self.assertRaisesRegex(ValueError, "Tabela '.*' nao existe"):
                    operacao(nome_invalido)


if __name__ == "__main__":
    unittest.main(verbosity=2)