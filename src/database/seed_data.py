from pathlib import Path
import random
from datetime import date, timedelta
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
    rng = random.Random(42)

    nomes = [
        ("Renner", "Vestuario"),
        ("Pampa Tech", "Eletronicos"),
        ("Café do Sul", "Alimentacao"),
        ("Livraria Gaúcha", "Livraria"),
        ("Trilha Ativa", "Esporte"),
        ("Casa Minuano", "Casa"),
        ("Mundo Kids", "Infantil"),
        ("Bella Prata", "Acessorios"),
        ("Arena Games", "Entretenimento"),
        ("Flor do Pampa", "Decoracao"),
        ("Estacao Gourmet", "Alimentacao"),
        ("Sul Digital", "Servicos"),
        ("Moda Serrana", "Vestuario"),
        ("Tech Nativo", "Eletronicos"),
        ("Doce Fronteira", "Alimentacao"),
        ("Ponto Esportivo", "Esporte"),
        ("Livros & Ideias", "Livraria"),
        ("Vitrine Sul", "Vestuario"),
        ("Conecta RS", "Servicos"),
        ("Casa das Araucarias", "Casa"),
        ("Brinca Sul", "Infantil"),
        ("Cafe da Serra", "Alimentacao"),
        ("Pixel Store", "Eletronicos"),
        ("Mundo Fitness", "Esporte"),
        ("Estilo Gaucho", "Vestuario"),
        ("Sabores do Sul", "Alimentacao"),
        ("Universo Geek", "Entretenimento"),
        ("Decor Nativa", "Decoracao"),
        ("Papel & Arte", "Livraria"),
        ("Conecta Mobile", "Servicos"),
        ("Prata Fina RS", "Acessorios"),
        ("Gourmet 51", "Alimentacao"),
        ("Moda Central", "Vestuario"),
        ("Byte Shop", "Eletronicos"),
        ("Espaco Ativo", "Esporte"),
        ("Pequeno Mundo", "Infantil"),
        ("Canto da Casa", "Casa"),
        ("Cafe Mercado", "Alimentacao"),
        ("Game Point", "Entretenimento"),
        ("Arte & Flor", "Decoracao"),
        ("Estilo Urbano", "Vestuario"),
        ("Digital Center", "Eletronicos"),
        ("Doce Mania", "Alimentacao"),
        ("Sul Acessorios", "Acessorios"),
        ("Clube da Leitura", "Livraria"),
        ("Viva Bem", "Servicos"),
        ("Pampa Sport", "Esporte"),
        ("Cantinho Kids", "Infantil"),
        ("Casa Moderna", "Casa"),
        ("Estacao Fashion", "Vestuario"),
    ]

    lojas = []
    for loja_id, (nome, categoria) in enumerate(nomes, start=1):
        piso = rng.randint(1, 3)
        dia = rng.randint(1, 28)
        mes = rng.randint(1, 12)
        data_abertura = date(2018, mes, dia) + timedelta(
            days=365 * rng.randint(0, 7)
        )

        lojas.append((
            loja_id,
            nome,
            categoria,
            piso,
            data_abertura.strftime("%Y-%m-%d %H:%M:%S"),
        ))

    return lojas


def gerar_contratos() -> list[tuple]:
    contratos = []

    # Contratos regulares para as 50 lojas.
    for loja_id in range(1, 51):
        inicio = date(2025, 1, 1)
        fim = date(2025, 12, 31)

        contratos.append((
            loja_id,
            loja_id,
            inicio.isoformat(),
            fim.isoformat(),
            "Ativo",
            f"contratos/loja-{loja_id:02d}.pdf",
        ))

    # Sobreposição intencional: loja 1.
    contratos.append((
        51, 1,
        "2025-06-01", "2025-11-30",
        "Ativo", "contratos/loja-01-aditivo.pdf",
    ))

    # Sobreposição intencional: loja 2.
    contratos.append((
        52, 2,
        "2025-05-01", "2025-10-31",
        "Ativo", "contratos/loja-02-aditivo.pdf",
    ))

    # Contratos encerrados para testes históricos.
    for contrato_id, loja_id in enumerate(range(8, 13), start=53):
        contratos.append((
            contrato_id,
            loja_id,
            "2024-01-01",
            "2024-12-31",
            "Encerrado",
            f"contratos/historico-loja-{loja_id:02d}.pdf",
        ))

    return contratos


def gerar_movimentacoes() -> list[tuple]:
    rng = random.Random(42)
    movimentacoes = []
    registro_id = 1

    # Valores típicos por segmento: rendimento, custos e fluxo.
    parametros = {
        "Vestuario": (6500, 0.48, 220),
        "Alimentacao": (8000, 0.65, 380),
        "Eletronicos": (10000, 0.58, 180),
        "Livraria": (3500, 0.45, 100),
        "Esporte": (5000, 0.50, 160),
        "Casa": (6000, 0.55, 140),
        "Infantil": (4000, 0.48, 130),
        "Acessorios": (4500, 0.40, 120),
        "Entretenimento": (5500, 0.60, 300),
        "Decoracao": (4200, 0.50, 90),
        "Servicos": (3000, 0.42, 110),
    }

    lojas = gerar_lojas()

    for loja_id, nome, categoria, piso, abertura in lojas:
        rendimento_base, proporcao_custos, fluxo_base = (
            parametros[categoria]
        )

        # Registros semanais para todo o ano de 2025.
        for semana in range(52):
            dia = date(2025, 1, 1) + timedelta(days=semana * 7)

            variacao = rng.uniform(0.75, 1.25)
            rendimento = round(rendimento_base * variacao, 2)
            custos = round(
                rendimento * proporcao_custos
                * rng.uniform(0.85, 1.15),
                2,
            )
            fluxo = max(
                1,
                int(fluxo_base * rng.uniform(0.75, 1.25)),
            )

            movimentacoes.append((
                registro_id,
                loja_id,
                dia.isoformat(),
                rendimento,
                custos,
                fluxo,
            ))
            registro_id += 1

    return movimentacoes


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
