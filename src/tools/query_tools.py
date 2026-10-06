import re
import sqlite3
import time

from src.database.init_db import CAMINHO_DB

LIMITE_MAXIMO = 50


def conectar_somente_leitura() -> sqlite3.Connection:
    """Abre o banco em modo read-only: mesmo que uma query maliciosa passe, o SQLite recusa a escrita."""
    conexao = sqlite3.connect(f"file:{CAMINHO_DB}?mode=ro", uri=True)
    conexao.row_factory = sqlite3.Row
    return conexao


def garantir_limit(query: str, limite: int) -> str:
    """Remove o ';' final e assegura uma cláusula LIMIT que nunca exceda `limite`."""
    query = query.strip().rstrip(";").strip()
    correspondencia = re.search(r"\blimit\s+(\d+)\s*$", query, flags=re.IGNORECASE)
    if correspondencia is None:
        # TODO: retorne a query com " LIMIT {limite}" acrescentado ao final
        ...
    if int(correspondencia.group(1)) > limite:
        # TODO: substitua o valor do LIMIT existente por `limite` e retorne a query
        ...
    return query


def executar_query_analitica(query: str, limite_linhas: int = 50) -> dict:
    """Executa uma consulta SQL de LEITURA (SELECT) e retorna colunas, linhas e o tempo gasto.

    Use somente depois de consultar o schema. O resultado e limitado a no maximo 50 linhas.
    """
    limite = max(1, min(limite_linhas, LIMITE_MAXIMO))
    query_final = garantir_limit(query, limite)
    inicio = time.perf_counter()
    try:
        with conectar_somente_leitura() as conexao:
            cursor = conexao.execute(query_final)
            # TODO: leia os nomes das colunas de cursor.description (primeiro item de cada tupla)
            colunas = []
            # TODO: converta cada linha de cursor.fetchall() em dict {coluna: valor}
            linhas = []
    except sqlite3.Error as erro:
        return {"sucesso": False, "erro": f"{type(erro).__name__}: {erro}", "query_executada": query_final}
    tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
    return {
        "sucesso": True,
        "query_executada": query_final,
        "colunas": colunas,
        "linhas": linhas,
        "total_linhas": len(linhas),
        "tempo_ms": tempo_ms,
    }


if __name__ == "__main__":
    print(executar_query_analitica("SELECT cidade, COUNT(*) AS total FROM clientes GROUP BY cidade"))
    print(executar_query_analitica("SELECT * FROM pedidos LIMIT 500")["total_linhas"])
    print(executar_query_analitica("SELECT coluna_inexistente FROM clientes"))
    # Prova da conexao somente leitura: tentamos escrever direto, sem passar pelo executor
    try:
        conectar_somente_leitura().execute("DELETE FROM clientes")
    except sqlite3.OperationalError as erro:
        print("Escrita recusada:", erro)