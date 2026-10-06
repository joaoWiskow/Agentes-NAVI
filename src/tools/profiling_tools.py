from src.database.init_db import conectar
from src.tools.schema_tools import validar_tabela


def _validar_coluna(conexao, nome_tabela: str, nome_coluna: str) -> str:
    colunas = [
        linha["name"]
        for linha in conexao.execute(
            f"PRAGMA table_info({nome_tabela})"
        )
    ]

    if nome_coluna not in colunas:
        raise ValueError(
            f"Coluna '{nome_coluna}' nao existe em '{nome_tabela}'. "
            f"Colunas validas: {', '.join(colunas)}"
        )

    return nome_coluna


def contar_nulos_e_distintos(
    nome_tabela: str,
    nome_coluna: str
) -> dict:
    """Mede a qualidade de uma coluna."""

    with conectar() as conexao:
        validar_tabela(conexao, nome_tabela)
        _validar_coluna(conexao, nome_tabela, nome_coluna)

        linha = conexao.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN {nome_coluna} IS NULL THEN 1
                        ELSE 0
                    END
                ) AS nulos,
                COUNT(DISTINCT {nome_coluna}) AS distintos
            FROM {nome_tabela}
            """
        ).fetchone()

        total = linha["total"]
        nulos = linha["nulos"] or 0

        percentual_preenchido = (
            0.0
            if total == 0
            else round((total - nulos) / total * 100, 2)
        )

        return {
            "tabela": nome_tabela,
            "coluna": nome_coluna,
            "total_linhas": total,
            "nulos": nulos,
            "distintos": linha["distintos"],
            "percentual_preenchido": percentual_preenchido,
        }


def calcular_estatisticas_coluna(
    nome_tabela: str,
    nome_coluna: str
) -> dict:
    """Calcula minimo, maximo, media e soma de uma coluna numerica."""

    with conectar() as conexao:
        validar_tabela(conexao, nome_tabela)
        _validar_coluna(conexao, nome_tabela, nome_coluna)

        linha = conexao.execute(
            f"""
            SELECT
                MIN({nome_coluna}) AS minimo,
                MAX({nome_coluna}) AS maximo,
                AVG({nome_coluna}) AS media,
                SUM({nome_coluna}) AS soma
            FROM {nome_tabela}
            """
        ).fetchone()

        return {
            "tabela": nome_tabela,
            "coluna": nome_coluna,
            "minimo": linha["minimo"],
            "maximo": linha["maximo"],
            "media": (
                None
                if linha["media"] is None
                else round(linha["media"], 2)
            ),
            "soma": (
                None
                if linha["soma"] is None
                else round(linha["soma"], 2)
            ),
        }


def amostrar_linhas(
    nome_tabela: str,
    qtd: int = 5
) -> list[dict]:
    """Retorna ate 20 linhas de exemplo de uma tabela."""

    qtd = max(1, min(qtd, 20))

    with conectar() as conexao:
        validar_tabela(conexao, nome_tabela)

        linhas = conexao.execute(
            f"SELECT * FROM {nome_tabela} LIMIT ?",
            (qtd,)
        ).fetchall()

        return [dict(linha) for linha in linhas]


if __name__ == "__main__":

    print(
        contar_nulos_e_distintos(
            "contrato",
            "documento_url"
        )
    )

    print(
        calcular_estatisticas_coluna(
            "movimentacao",
            "rendimento"
        )
    )

    print(
        amostrar_linhas(
            "loja",
            3
        )
    )