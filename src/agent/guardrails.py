import re

# Padroes proibidos. REPLACE so e perigoso como "REPLACE INTO" (escrita); a funcao replace(coluna, a, b) e leitura.
PADROES_PROIBIDOS = [
    r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b", r"\bALTER\b", r"\bTRUNCATE\b",
    r"\bATTACH\b", r"\bDETACH\b", r"\bCREATE\b", r"\bREPLACE\s+INTO\b", r"\bEXEC\b", r"\bVACUUM\b",
    r"\bPRAGMA\b", r"\bLOAD_EXTENSION\b",
]


def _remover_literais(sql: str) -> str:
    """Troca o conteudo de strings 'entre aspas simples' por vazio (trata '' como aspas escapada)."""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def validar_query_segura(query: str) -> tuple[bool, str]:
    """Retorna (True, "Query aprovada") ou (False, "motivo do bloqueio")."""
    if not isinstance(query, str) or not query.strip():
        return False, "Query vazia"

    texto = query.strip()

    # Regra 1: comentarios SQL escondem intencoes; nao aceitamos nenhum
    if "--" in texto or "/*" in texto or "*/" in texto:
        # TODO: retorne (False, "Comentarios SQL nao sao permitidos")
        ...

    limpo = _remover_literais(texto)
    normalizado = re.sub(r"\s+", " ", limpo).strip().upper()

    # Regra 2: um unico statement (aceitamos no maximo um ';' e somente no final)
    sem_ponto_final = normalizado.rstrip(";").strip()
    if ";" in sem_ponto_final:
        # TODO: retorne (False, "Multiplos statements nao sao permitidos")
        ...

    # Regra 3: lista de permissoes: apenas SELECT ou WITH
    if not (sem_ponto_final.startswith("SELECT ") or sem_ponto_final.startswith("WITH ")):
        # TODO: retorne (False, "Apenas consultas SELECT/WITH sao permitidas")
        ...

    # Regra 4: lista de proibicoes, aplicada dentro do statement unico (protege "WITH ... DELETE")
    for padrao in PADROES_PROIBIDOS:
        if re.search(padrao, sem_ponto_final):
            # TODO: retorne (False, f"Comando proibido detectado: {padrao}") com o padrao sem as barras de regex
            ...

    return True, "Query aprovada"


if __name__ == "__main__":
    exemplos = [
        "SELECT * FROM clientes",
        "select cidade, count(*) from clientes group by cidade;",
        "SELECT * FROM clientes WHERE nome = 'DELETE; DROP'",
        "WITH t AS (SELECT * FROM pedidos) SELECT COUNT(*) FROM t",
        "DROP TABLE clientes",
        "SELECT 1; DELETE FROM pedidos",
        "WITH x AS (SELECT 1) DELETE FROM clientes",
        "SELECT 1 -- ; DROP TABLE clientes",
    ]
    for exemplo in exemplos:
        aprovada, motivo = validar_query_segura(exemplo)
        print(f"{'APROVADA ' if aprovada else 'BLOQUEADA'} | {motivo:<45} | {exemplo}")