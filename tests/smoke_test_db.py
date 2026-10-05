"""Smoke tests do módulo src/database/init_db.py.

Roda com:  python3 tests/smoke_test_db.py
Nunca toca no banco real (data/dataops.db): cada teste usa um
diretório temporário e passa o caminho explicitamente para conectar().
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Torna src/database importável a partir dos testes (namespace package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.init_db import conectar, criar_tabelas, resetar_banco

TABELAS_ESPERADAS = {"pisos", "lojas", "vendas", "fluxo_visitantes"}
INDICES_ESPERADOS = {
    "idx_lojas_piso",
    "idx_vendas_loja",
    "idx_vendas_data",
    "idx_fluxo_piso",
    "idx_fluxo_data",
}


class SmokeTestBanco(unittest.TestCase):
    def setUp(self):
        # Arrange compartilhado: banco novo em diretório temporário.
        self.tmp = tempfile.TemporaryDirectory()
        self.caminho_db = Path(self.tmp.name) / "dataops.db"
        self.conexao = conectar(self.caminho_db)
        criar_tabelas(self.conexao)

    def tearDown(self):
        self.conexao.close()
        self.tmp.cleanup()

    # -- helpers --------------------------------------------------------

    def _nomes_no_sqlite_master(self, tipo: str) -> set:
        linhas = self.conexao.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = ? AND name NOT LIKE 'sqlite_%'",
            (tipo,),
        ).fetchall()
        return {linha["name"] for linha in linhas}

    def _inserir_piso(self, numero: int = 1) -> int:
        cursor = self.conexao.execute(
            "INSERT INTO pisos (numero, descricao) VALUES (?, ?)",
            (numero, "Piso térreo"),
        )
        self.conexao.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    # -- conectar ---------------------------------------------------------

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

    # -- criar_tabelas ----------------------------------------------------

    def test_criar_tabelas_cria_as_quatro_tabelas(self):
        self.assertEqual(
            self._nomes_no_sqlite_master("table"), TABELAS_ESPERADAS
        )

    def test_criar_tabelas_cria_os_cinco_indices(self):
        self.assertEqual(
            self._nomes_no_sqlite_master("index"), INDICES_ESPERADOS
        )

    def test_criar_tabelas_e_idempotente(self):
        criar_tabelas(self.conexao)  # segunda chamada não deve falhar
        self.assertEqual(
            self._nomes_no_sqlite_master("table"), TABELAS_ESPERADAS
        )

    # -- integridade ------------------------------------------------------

    def test_roundtrip_piso_loja_venda_e_fluxo(self):
        piso_id = self._inserir_piso()

        loja = self.conexao.execute(
            "INSERT INTO lojas (piso_id, nome, categoria, area_m2,"
            " aluguel_mensal, inaugurada_em) VALUES (?, ?, ?, ?, ?, ?)",
            (piso_id, "Loja A", "Moda", 50.0, 8000.0, "2024-01-15 10:00:00"),
        )
        self.conexao.execute(
            "INSERT INTO vendas (loja_id, valor, quantidade, data_venda)"
            " VALUES (?, ?, ?, ?)",
            (loja.lastrowid, 250.0, 3, "2024-02-01 12:00:00"),
        )
        self.conexao.execute(
            "INSERT INTO fluxo_visitantes (piso_id, data, periodo, visitantes)"
            " VALUES (?, ?, ?, ?)",
            (piso_id, "2024-02-01", "manha", 320),
        )
        self.conexao.commit()

        venda = self.conexao.execute("SELECT * FROM vendas").fetchone()
        self.assertEqual(venda["loja_id"], loja.lastrowid)
        self.assertEqual(venda["valor"], 250.0)

        fluxo = self.conexao.execute(
            "SELECT * FROM fluxo_visitantes"
        ).fetchone()
        self.assertEqual(fluxo["piso_id"], piso_id)
        self.assertEqual(fluxo["visitantes"], 320)

    def test_venda_com_loja_inexistente_viola_chave_estrangeira(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conexao.execute(
                "INSERT INTO vendas (loja_id, valor, quantidade, data_venda)"
                " VALUES (?, ?, ?, ?)",
                (999, 10.0, 1, "2024-02-01 12:00:00"),
            )

    def test_loja_com_piso_inexistente_viola_chave_estrangeira(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conexao.execute(
                "INSERT INTO lojas (piso_id, nome, categoria, area_m2,"
                " aluguel_mensal, inaugurada_em) VALUES (?, ?, ?, ?, ?, ?)",
                (999, "Loja Fantasma", "Moda", 10.0, 100.0, "2024-01-01"),
            )

    def test_loja_sem_nome_viola_not_null(self):
        piso_id = self._inserir_piso()

        with self.assertRaises(sqlite3.IntegrityError):
            self.conexao.execute(
                "INSERT INTO lojas (piso_id, nome, categoria, area_m2,"
                " aluguel_mensal, inaugurada_em) VALUES (?, ?, ?, ?, ?, ?)",
                (piso_id, None, "Moda", 10.0, 100.0, "2024-01-01"),
            )

    # -- resetar_banco -----------------------------------------------------

    def test_resetar_banco_apaga_o_arquivo_do_banco(self):
        self.conexao.close()

        with mock.patch("database.init_db.CAMINHO_DB", self.caminho_db):
            resetar_banco()

        self.assertFalse(self.caminho_db.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
