"""Smoke tests dos modulos de banco.

Roda com: python tests/smoke_test_db.py
Nunca toca no banco real (data/dataops.db): cada teste usa um diretorio
temporario e passa o caminho explicitamente para conectar() ou popular().
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.init_db import conectar, criar_tabelas, resetar_banco
from database.seed_data import ANOMALIAS_ESPERADAS, consultar_anomalias, popular


TABELAS_ESPERADAS = {"loja", "movimentacao", "contrato"}
INDICES_ESPERADOS = {
    "idx_movimentacao_loja",
    "idx_movimentacao_data",
    "idx_contrato_loja",
    "idx_contrato_datas",
}


class SmokeTestBanco(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.caminho_db = Path(self.tmp.name) / "dataops.db"
        self.conexao = conectar(self.caminho_db)
        criar_tabelas(self.conexao)

    def tearDown(self):
        self.conexao.close()
        self.tmp.cleanup()

    def _nomes_no_sqlite_master(self, tipo: str) -> set:
        linhas = self.conexao.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = ? AND name NOT LIKE 'sqlite_%'",
            (tipo,),
        ).fetchall()
        return {linha["name"] for linha in linhas}

    def _inserir_loja(self) -> int:
        cursor = self.conexao.execute(
            "INSERT INTO loja (nome, categoria, piso, inaugurada_em)"
            " VALUES (?, ?, ?, ?)",
            ("Loja A", "Moda", 1, "2024-01-15 10:00:00"),
        )
        self.conexao.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def test_conectar_cria_diretorio_pai_e_arquivo_do_banco(self):
        caminho_novo = Path(self.tmp.name) / "aninhado" / "outro.db"

        conexao = conectar(caminho_novo)
        try:
            self.assertTrue(caminho_novo.exists())
            self.assertEqual(conexao.execute("SELECT 1").fetchone()[0], 1)
        finally:
            conexao.close()

    def test_conectar_configura_row_factory_e_chaves_estrangeiras(self):
        self.assertIs(self.conexao.row_factory, sqlite3.Row)
        self.assertEqual(
            self.conexao.execute("PRAGMA foreign_keys").fetchone()[0], 1
        )

    def test_criar_tabelas_cria_as_tres_tabelas(self):
        self.assertEqual(
            self._nomes_no_sqlite_master("table"), TABELAS_ESPERADAS
        )

    def test_criar_tabelas_cria_os_indices_de_apoio(self):
        self.assertEqual(
            self._nomes_no_sqlite_master("index"), INDICES_ESPERADOS
        )

    def test_criar_tabelas_e_idempotente(self):
        criar_tabelas(self.conexao)
        self.assertEqual(
            self._nomes_no_sqlite_master("table"), TABELAS_ESPERADAS
        )

    def test_roundtrip_loja_movimentacao_e_contrato(self):
        loja_id = self._inserir_loja()

        self.conexao.execute(
            "INSERT INTO movimentacao"
            " (loja_id, data, rendimento, custos, movimentacao)"
            " VALUES (?, ?, ?, ?, ?)",
            (loja_id, "2025-01-10", 2500.0, 900.0, 180),
        )
        self.conexao.execute(
            "INSERT INTO contrato"
            " (loja_id, data_inicio, data_fim, status, documento_url)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                loja_id,
                "2025-01-01",
                "2025-12-31",
                "Ativo",
                "contratos/loja-a.pdf",
            ),
        )
        self.conexao.commit()

        movimentacao = self.conexao.execute(
            "SELECT * FROM movimentacao"
        ).fetchone()
        self.assertEqual(movimentacao["loja_id"], loja_id)
        self.assertEqual(movimentacao["rendimento"], 2500.0)

        contrato = self.conexao.execute("SELECT * FROM contrato").fetchone()
        self.assertEqual(contrato["loja_id"], loja_id)
        self.assertEqual(contrato["status"], "Ativo")

    def test_movimentacao_com_loja_inexistente_viola_chave_estrangeira(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conexao.execute(
                "INSERT INTO movimentacao"
                " (loja_id, data, rendimento, custos, movimentacao)"
                " VALUES (?, ?, ?, ?, ?)",
                (999, "2025-01-10", 10.0, 1.0, 5),
            )

    def test_contrato_com_loja_inexistente_viola_chave_estrangeira(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conexao.execute(
                "INSERT INTO contrato"
                " (loja_id, data_inicio, data_fim, status, documento_url)"
                " VALUES (?, ?, ?, ?, ?)",
                (999, "2025-01-01", "2025-12-31", "Ativo", None),
            )

    def test_loja_sem_nome_viola_not_null(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conexao.execute(
                "INSERT INTO loja (nome, categoria, piso, inaugurada_em)"
                " VALUES (?, ?, ?, ?)",
                (None, "Moda", 1, "2024-01-01"),
            )

    def test_excluir_loja_remove_movimentacoes_e_contratos_em_cascata(self):
        loja_id = self._inserir_loja()
        self.conexao.execute(
            "INSERT INTO movimentacao"
            " (loja_id, data, rendimento, custos, movimentacao)"
            " VALUES (?, ?, ?, ?, ?)",
            (loja_id, "2025-01-10", 100.0, 10.0, 20),
        )
        self.conexao.execute(
            "INSERT INTO contrato"
            " (loja_id, data_inicio, data_fim, status, documento_url)"
            " VALUES (?, ?, ?, ?, ?)",
            (loja_id, "2025-01-01", "2025-12-31", "Ativo", None),
        )
        self.conexao.execute("DELETE FROM loja WHERE id = ?", (loja_id,))
        self.conexao.commit()

        total_movimentacoes = self.conexao.execute(
            "SELECT COUNT(*) FROM movimentacao"
        ).fetchone()[0]
        total_contratos = self.conexao.execute(
            "SELECT COUNT(*) FROM contrato"
        ).fetchone()[0]

        self.assertEqual(total_movimentacoes, 0)
        self.assertEqual(total_contratos, 0)

    def test_seed_cria_as_anomalias_planejadas_no_dicionario(self):
        self.conexao.close()

        popular(self.caminho_db)

        conexao = conectar(self.caminho_db)
        try:
            self.assertEqual(consultar_anomalias(conexao), ANOMALIAS_ESPERADAS)

            totais = {
                tabela: conexao.execute(
                    f"SELECT COUNT(*) FROM {tabela}"
                ).fetchone()[0]
                for tabela in TABELAS_ESPERADAS
            }
        finally:
            conexao.close()

        self.assertEqual(totais, {"loja": 12, "contrato": 14, "movimentacao": 21})

    def test_resetar_banco_apaga_o_arquivo_do_banco(self):
        self.conexao.close()

        with mock.patch("database.init_db.CAMINHO_DB", self.caminho_db):
            resetar_banco()

        self.assertFalse(self.caminho_db.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
