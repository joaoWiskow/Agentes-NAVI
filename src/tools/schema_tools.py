from src.database.init_db import conectar


def _tabelas_existentes(conexao) -> list[str]:
    linhas = conexao.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [linha["name"] for linha in linhas]


def validar_tabela(conexao, nome_tabela: str) -> str:
    """Garante que o nome recebido e uma tabela real; caso contrario, explica quais existem."""
    tabelas = _tabelas_existentes(conexao)
    if nome_tabela not in tabelas:
        raise ValueError(f"Tabela '{nome_tabela}' nao existe. Tabelas validas: {', '.join(tabelas)}")
    return nome_tabela


def listar_tabelas() -> list[str]:
    """Lista os nomes de todas as tabelas de dados do banco. Use SEMPRE como primeiro passo."""
    with conectar() as conexao:
        # TODO: retorne _tabelas_existentes(conexao)
        ...


def descrever_schema_tabela(nome_tabela: str) -> dict:
    """Descreve as colunas de uma tabela: nome, tipo, se e obrigatoria e se e chave primaria."""
    with conectar() as conexao:
        validar_tabela(conexao, nome_tabela)
        colunas = []
        # TODO: percorra conexao.execute(f"PRAGMA table_info({nome_tabela})") e acrescente, para cada linha,
        #       {"nome": ..., "tipo": ..., "obrigatoria": bool(notnull), "chave_primaria": bool(pk)}
        return {"tabela": nome_tabela, "colunas": colunas}


def obter_chaves_estrangeiras(nome_tabela: str) -> list[dict]:
    """Lista as chaves estrangeiras de uma tabela. Use antes de escrever qualquer JOIN."""
    with conectar() as conexao:
        validar_tabela(conexao, nome_tabela)
        # TODO: percorra PRAGMA foreign_key_list e retorne
        #       [{"coluna_local": from, "tabela_referenciada": table, "coluna_referenciada": to}]
        ...


if __name__ == "__main__":
    print(listar_tabelas())
    print(descrever_schema_tabela("pedidos"))
    print(obter_chaves_estrangeiras("pedidos"))
    try:
        descrever_schema_tabela("pedidos; DROP TABLE clientes")
    except ValueError as erro:
        print("Bloqueado:", erro)