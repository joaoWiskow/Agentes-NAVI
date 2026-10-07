import re
import sqlite3
import time

from ..agent.guardrails import validar_query_segura

from ..database.init_db import CAMINHO_DB

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
        return f"{query} LIMIT {limite}"
    if int(correspondencia.group(1)) > limite:
        return re.sub(r"(\blimit\s+)\d+\s*$", rf"\1{limite}", query, flags=re.IGNORECASE)
    return query


def validar_query_analitica(query: str) -> str:
    """Valida a consulta antes de enviá-la ao banco."""
    aprovada, motivo = validar_query_segura(query)
    if not aprovada:
        raise ValueError(motivo)
    return query.strip()


def executar_query_analitica(query: str, limite_linhas: int = 50) -> dict:
    """Executa uma consulta SQL de LEITURA (SELECT) e retorna colunas, linhas e o tempo gasto.

    Use somente depois de consultar o schema. O resultado e limitado a no maximo 50 linhas.
    """
    limite = max(1, min(limite_linhas, LIMITE_MAXIMO))
    try:
        query_validada = validar_query_analitica(query)
    except ValueError as erro:
        motivo = str(erro)
        return {
            "sucesso": False,
            "erro": f"Guardrail: {motivo}",
            "query_executada": None,
            "guardrail": {"aprovada": False, "motivo": motivo},
        }
    motivo = "Query aprovada"
    query_final = garantir_limit(query_validada, limite)
    inicio = time.perf_counter()
    try:
        with conectar_somente_leitura() as conexao:
            cursor = conexao.execute(query_final)
            colunas = [desc[0] for desc in cursor.description] if cursor.description else []
            linhas = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    except sqlite3.Error as erro:
        return {"sucesso": False, "erro": f"{type(erro).__name__}: {erro}", "query_executada": query_final}
    tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
    return {
        "sucesso": True,
        "query_executada": query_final,
        "guardrail": {"aprovada": True, "motivo": motivo},
        "colunas": colunas,
        "linhas": linhas,
        "total_linhas": len(linhas),
        "tempo_ms": tempo_ms,
    }


if __name__ == "__main__":
    print(executar_query_analitica("SELECT categoria, COUNT(*) AS total FROM loja GROUP BY categoria"))
    print(executar_query_analitica("SELECT * FROM movimentacao LIMIT 500")["total_linhas"])
    print(executar_query_analitica("SELECT coluna_inexistente FROM loja"))
    # Prova da conexao somente leitura: tentamos escrever direto, sem passar pelo executor
    try:
        conectar_somente_leitura().execute("DELETE FROM loja")
    except sqlite3.OperationalError as erro:
        print("Escrita recusada:", erro)