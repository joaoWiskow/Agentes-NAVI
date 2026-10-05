import sqlite3
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_DB = RAIZ / "data" / "dataops.db"


def conectar(caminho: Path = CAMINHO_DB) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row

    # Ativa as chaves estrangeiras do SQLite em toda conexao.
    conexao.execute("PRAGMA foreign_keys = ON;")

    return conexao


DDL = """
CREATE TABLE IF NOT EXISTS loja (
    id              INTEGER PRIMARY KEY,
    nome            VARCHAR(150) NOT NULL,
    categoria       VARCHAR(100) NOT NULL,
    piso            INTEGER NOT NULL,
    inaugurada_em   TIMESTAMP NOT NULL
);


CREATE TABLE IF NOT EXISTS movimentacao (
    id              INTEGER PRIMARY KEY,
    loja_id         INTEGER NOT NULL,
    data            DATE NOT NULL,
    rendimento      NUMERIC(12, 2) NOT NULL,
    custos          NUMERIC(12, 2) NOT NULL,
    movimentacao    INTEGER,

    CONSTRAINT fk_movimentacao_loja
        FOREIGN KEY (loja_id)
        REFERENCES loja(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);


CREATE TABLE IF NOT EXISTS contrato (
    id              INTEGER PRIMARY KEY,
    loja_id         INTEGER NOT NULL,
    data_inicio     DATE NOT NULL,
    data_fim        DATE NOT NULL,
    status          VARCHAR(50) NOT NULL,
    documento_url   TEXT,

    CONSTRAINT fk_contrato_loja
        FOREIGN KEY (loja_id)
        REFERENCES loja(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_movimentacao_loja
ON movimentacao(loja_id);


CREATE INDEX IF NOT EXISTS idx_movimentacao_data
ON movimentacao(data);


CREATE INDEX IF NOT EXISTS idx_contrato_loja
ON contrato(loja_id);


CREATE INDEX IF NOT EXISTS idx_contrato_datas
ON contrato(data_inicio, data_fim);
"""


def criar_tabelas(conexao: sqlite3.Connection) -> None:
    """Cria as tabelas, relacionamentos e indices do banco."""

    conexao.executescript(DDL)
    conexao.commit()


def resetar_banco() -> None:
    """Apaga o arquivo do banco, se existir, para recomecar do zero."""

    if CAMINHO_DB.exists():
        CAMINHO_DB.unlink()


if __name__ == "__main__":
    resetar_banco()

    with conectar() as conexao:
        criar_tabelas(conexao)

        tabelas = conexao.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        print("Tabelas criadas:", [linha["name"] for linha in tabelas])
        print(
            "Chaves estrangeiras ativas:",
            conexao.execute("PRAGMA foreign_keys").fetchone()[0],
        )
