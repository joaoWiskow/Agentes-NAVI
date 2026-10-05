from pathlib import Path

try:
    from .init_db import conectar, criar_tabelas, resetar_banco
except ImportError:
    from init_db import conectar, criar_tabelas, resetar_banco


ANOMALIAS_ESPERADAS = {
    "queda_brusca_rendimento": 4,
    "custos_maiores_que_rendimento": 3,
    "movimentacao_fora_contrato": 3,
    "contratos_ativos_sobrepostos": 2,
    "discrepancia_fluxo_rendimento": 4,
    "lacunas_temporais": 3,
}


def gerar_lojas() -> list[tuple]:
    return [
        (1, "Aurora Moda", "Vestuario", 1, "2021-03-10 10:00:00"),
        (2, "Bistro Central", "Alimentacao", 1, "2020-08-20 11:00:00"),
        (3, "Tech Prime", "Eletronicos", 2, "2022-02-15 09:30:00"),
        (4, "Livraria Horizonte", "Livraria", 2, "2019-05-02 10:30:00"),
        (5, "Fit Club", "Esporte", 3, "2021-11-18 08:00:00"),
        (6, "Casa Viva", "Casa", 3, "2018-09-25 10:00:00"),
        (7, "Kids Play", "Infantil", 2, "2023-01-12 10:00:00"),
        (8, "Cafe Norte", "Alimentacao", 1, "2017-06-01 07:30:00"),
        (9, "Bella Joias", "Acessorios", 2, "2020-10-05 10:00:00"),
        (10, "Games Arena", "Entretenimento", 3, "2021-07-14 12:00:00"),
        (11, "Express Cell", "Servicos", 1, "2022-09-09 10:00:00"),
        (12, "Flor & Arte", "Decoracao", 2, "2023-04-22 10:00:00"),
    ]


def gerar_contratos() -> list[tuple]:
    contratos = [
        (1, 1, "2025-01-01", "2025-12-31", "Ativo", "contratos/loja-01-a.pdf"),
        (2, 1, "2025-06-01", "2025-11-30", "Ativo", "contratos/loja-01-b.pdf"),
        (3, 2, "2025-01-01", "2025-12-31", "Ativo", "contratos/loja-02-a.pdf"),
        (4, 2, "2025-05-01", "2025-10-31", "Ativo", "contratos/loja-02-b.pdf"),
    ]

    for contrato_id, loja_id in enumerate(range(3, 8), start=5):
        contratos.append(
            (
                contrato_id,
                loja_id,
                "2025-01-01",
                "2025-12-31",
                "Ativo",
                f"contratos/loja-{loja_id:02d}.pdf",
            )
        )

    contratos.extend(
        [
            (10, 8, "2024-01-01", "2025-03-31", "Encerrado", "contratos/loja-08.pdf"),
            (11, 9, "2024-01-01", "2025-03-31", "Encerrado", "contratos/loja-09.pdf"),
            (12, 10, "2024-01-01", "2025-03-31", "Encerrado", "contratos/loja-10.pdf"),
            (13, 11, "2025-01-01", "2025-12-31", "Ativo", "contratos/loja-11.pdf"),
            (14, 12, "2025-01-01", "2025-12-31", "Ativo", "contratos/loja-12.pdf"),
        ]
    )

    return contratos


def gerar_movimentacoes() -> list[tuple]:
    return [
        (1, 1, "2025-01-10", 10000.00, 3000.00, 300),
        (2, 1, "2025-01-11", 2000.00, 700.00, 250),
        (3, 1, "2025-01-20", 2500.00, 800.00, 260),
        (4, 2, "2025-01-10", 12000.00, 3500.00, 320),
        (5, 2, "2025-01-11", 2500.00, 900.00, 260),
        (6, 2, "2025-01-20", 2800.00, 1000.00, 270),
        (7, 3, "2025-01-10", 9000.00, 2800.00, 240),
        (8, 3, "2025-01-11", 1800.00, 650.00, 210),
        (9, 3, "2025-01-20", 2200.00, 700.00, 230),
        (10, 4, "2025-01-10", 11000.00, 3200.00, 280),
        (11, 4, "2025-01-11", 2500.00, 750.00, 230),
        (12, 5, "2025-01-10", 3000.00, 4500.00, 150),
        (13, 6, "2025-01-10", 3500.00, 4800.00, 160),
        (14, 7, "2025-01-10", 2800.00, 3600.00, 140),
        (15, 8, "2025-04-05", 5000.00, 2500.00, 180),
        (16, 9, "2025-04-05", 4200.00, 2100.00, 160),
        (17, 10, "2025-04-05", 6100.00, 2600.00, 200),
        (18, 11, "2025-01-10", 50.00, 20.00, 950),
        (19, 12, "2025-01-10", 80.00, 30.00, 1000),
        (20, 5, "2025-01-10", 12000.00, 3000.00, 2),
        (21, 6, "2025-01-10", 15000.00, 4000.00, 3),
    ]


def consultar_anomalias(conexao) -> dict[str, int]:
    consultas = {
        "queda_brusca_rendimento": """
            WITH ordenada AS (
                SELECT
                    loja_id,
                    data,
                    rendimento,
                    LAG(rendimento) OVER (
                        PARTITION BY loja_id
                        ORDER BY data, id
                    ) AS rendimento_anterior
                FROM movimentacao
            )
            SELECT COUNT(*)
            FROM ordenada
            WHERE rendimento_anterior IS NOT NULL
              AND rendimento < rendimento_anterior * 0.3
        """,
        "custos_maiores_que_rendimento": """
            SELECT COUNT(*)
            FROM movimentacao
            WHERE custos > rendimento
        """,
        "movimentacao_fora_contrato": """
            SELECT COUNT(*)
            FROM movimentacao AS m
            WHERE NOT EXISTS (
                SELECT 1
                FROM contrato AS c
                WHERE c.loja_id = m.loja_id
                  AND m.data BETWEEN c.data_inicio AND c.data_fim
            )
        """,
        "contratos_ativos_sobrepostos": """
            SELECT COUNT(DISTINCT c1.loja_id)
            FROM contrato AS c1
            JOIN contrato AS c2
              ON c1.loja_id = c2.loja_id
             AND c1.id < c2.id
            WHERE c1.status = 'Ativo'
              AND c2.status = 'Ativo'
              AND c1.data_inicio <= c2.data_fim
              AND c2.data_inicio <= c1.data_fim
        """,
        "discrepancia_fluxo_rendimento": """
            SELECT COUNT(*)
            FROM movimentacao
            WHERE (movimentacao >= 900 AND rendimento <= 100)
               OR (movimentacao <= 5 AND rendimento >= 10000)
        """,
        "lacunas_temporais": """
            WITH ordenada AS (
                SELECT
                    loja_id,
                    data,
                    JULIANDAY(data) - LAG(JULIANDAY(data)) OVER (
                        PARTITION BY loja_id
                        ORDER BY data, id
                    ) AS dias_desde_registro_anterior
                FROM movimentacao
            )
            SELECT COUNT(*)
            FROM ordenada
            WHERE dias_desde_registro_anterior > 7
        """,
    }

    return {
        nome: conexao.execute(sql).fetchone()[0]
        for nome, sql in consultas.items()
    }


def popular(caminho: Path | None = None) -> None:
    if caminho is None:
        resetar_banco()
        conexao = conectar()
    else:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if caminho.exists():
            caminho.unlink()
        conexao = conectar(caminho)

    try:
        with conexao:
            criar_tabelas(conexao)
            conexao.executemany(
                "INSERT INTO loja VALUES (?, ?, ?, ?, ?)",
                gerar_lojas(),
            )
            conexao.executemany(
                "INSERT INTO contrato VALUES (?, ?, ?, ?, ?, ?)",
                gerar_contratos(),
            )
            conexao.executemany(
                "INSERT INTO movimentacao VALUES (?, ?, ?, ?, ?, ?)",
                gerar_movimentacoes(),
            )
            conexao.commit()

            for tabela in ("loja", "contrato", "movimentacao"):
                total = conexao.execute(
                    f"SELECT COUNT(*) FROM {tabela}"
                ).fetchone()[0]
                print(f"{tabela}: {total} linhas")

            print("anomalias:", consultar_anomalias(conexao))
    finally:
        conexao.close()


if __name__ == "__main__":
    popular()
