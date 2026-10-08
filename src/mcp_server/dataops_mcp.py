import sys

from mcp.server.mcpserver import MCPServer

from src.agent.guardrails import validar_query_segura
from src.tools import profiling_tools, query_tools, schema_tools


mcp = MCPServer("dataops-agent")


@mcp.tool()
def listar_tabelas() -> list[str]:
    """Lista as tabelas de dados do banco. Use SEMPRE como primeiro passo."""
    return schema_tools.listar_tabelas()


@mcp.tool()
def descrever_schema(nome_tabela: str) -> dict:
    """Descreve colunas, tipos e chave primaria de uma tabela."""
    return schema_tools.descrever_schema_tabela(nome_tabela)


@mcp.tool()
def obter_relacionamentos(nome_tabela: str) -> list[dict]:
    """Lista as chaves estrangeiras de uma tabela; use antes de escrever JOINs."""
    return schema_tools.obter_chaves_estrangeiras(nome_tabela)


@mcp.tool()
def executar_query_analitica(query: str, limite: int = 50) -> dict:
    """Executa uma consulta SQL SELECT (somente leitura) e retorna colunas, linhas e tempo gasto."""

    aprovada, motivo = validar_query_segura(query)

    if not aprovada:
        return {
            "sucesso": False,
            "erro": f"Bloqueado pelo guardrail: {motivo}",
            "query_executada": None,
            "guardrail": {
                "aprovada": False,
                "motivo": motivo,
            },
        }
    resultado = query_tools.executar_query_analitica(query, limite)
    resultado["guardrail"] = {"aprovada": True, "motivo": motivo}
    return resultado


@mcp.tool()
def calcular_estatisticas_coluna(
    nome_tabela: str,
    nome_coluna: str
) -> dict:
    """Calcula minimo, maximo, media e soma de uma coluna numerica."""

    return profiling_tools.calcular_estatisticas_coluna(
        nome_tabela,
        nome_coluna
    )


if __name__ == "__main__":
    print(
        "dataops-agent MCP iniciado (stdio)",
        file=sys.stderr
    )

    mcp.run(transport="stdio")