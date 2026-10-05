import sqlite3
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_DB = RAIZ / "data" / "dataops.db"


def conectar(caminho: Path = CAMINHO_DB) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row

    # Ativa as chaves estrangeiras do SQLite em toda conexão.
    conexao.execute("PRAGMA foreign_keys = ON;")

    return conexao


DDL = """
CREATE TABLE IF NOT EXISTS pisos (
    id          INTEGER PRIMARY KEY,
    numero      INTEGER NOT NULL,
    descricao   TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS lojas (
    id              INTEGER PRIMARY KEY,
    piso_id         INTEGER NOT NULL,
    nome            TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    area_m2         REAL NOT NULL,
    aluguel_mensal  REAL NOT NULL,
    inaugurada_em   DATETIME NOT NULL,

    FOREIGN KEY (piso_id) REFERENCES pisos(id)
);


CREATE TABLE IF NOT EXISTS vendas (
    id          INTEGER PRIMARY KEY,
    loja_id     INTEGER NOT NULL,
    valor       REAL NOT NULL,
    quantidade  INTEGER NOT NULL,
    data_venda  DATETIME NOT NULL,

    FOREIGN KEY (loja_id) REFERENCES lojas(id)
);


CREATE TABLE IF NOT EXISTS fluxo_visitantes (
    id          INTEGER PRIMARY KEY,
    piso_id     INTEGER NOT NULL,
    data        DATETIME NOT NULL,
    periodo     TEXT NOT NULL,
    visitantes  INTEGER NOT NULL,

    FOREIGN KEY (piso_id) REFERENCES pisos(id)
);


-- Índices para acelerar consultas frequentes.

CREATE INDEX IF NOT EXISTS idx_lojas_piso
ON lojas(piso_id);


CREATE INDEX IF NOT EXISTS idx_vendas_loja
ON vendas(loja_id);


CREATE INDEX IF NOT EXISTS idx_vendas_data
ON vendas(data_venda);


CREATE INDEX IF NOT EXISTS idx_fluxo_piso
ON fluxo_visitantes(piso_id);


CREATE INDEX IF NOT EXISTS idx_fluxo_data
ON fluxo_visitantes(data);
"""


def criar_tabelas(conexao: sqlite3.Connection) -> None:
    """
    Cria as tabelas, relacionamentos e índices do banco.
    """

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

        print(
            "Tabelas criadas:",
            [linha["name"] for linha in tabelas]
        )

        print(
            "Chaves estrangeiras ativas:",
            conexao.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
        )