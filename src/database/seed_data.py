import random
from datetime import date, timedelta

from init_db import conectar, criar_tabelas, resetar_banco

rng = random.Random(42)

ANOMALIAS_ESPERADAS = {
    "clientes_sem_email": 6,
    "emails_duplicados": 3,
    "produtos_preco_zero": 4,
    "pedidos_valor_negativo": 5,
    "pedidos_data_futura": 3,
}

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fabio", "Gisele", "Hugo", "Iara", "Jonas"]
SOBRENOMES = ["Silva", "Souza", "Lima", "Costa", "Rocha", "Alves", "Pereira", "Martins"]
CIDADES = ["Porto Alegre", "Canoas", "Gramado", "Pelotas", "Caxias do Sul"]
CATEGORIAS = ["Eletronicos", "Livros", "Casa", "Esporte", "Moda"]


def gerar_clientes(qtd: int = 80) -> list[tuple]:
    linhas = []
    for i in range(1, qtd + 1):
        nome = f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}"
        email = f"cliente{i}@exemplo.com"
        criado = date(2025, 1, 1) + timedelta(days=rng.randint(0, 600))
        linhas.append([i, nome, email, rng.choice(CIDADES), criado.isoformat()])
    # Anomalia 1: e-mails nulos nos 6 primeiros clientes
    for linha in linhas[: ANOMALIAS_ESPERADAS["clientes_sem_email"]]:
        linha[2] = None
    # TODO: Anomalia 2: faca os clientes de indice 10, 11 e 12 usarem o MESMO e-mail ("duplicado@exemplo.com")
    return [tuple(linha) for linha in linhas]


def gerar_produtos(qtd: int = 60) -> list[tuple]:
    # TODO: gere `qtd` produtos (id, nome, categoria, preco entre 10.0 e 900.0 com 2 casas)
    # TODO: Anomalia 3: zere o preco dos 4 primeiros produtos
    ...


def gerar_pedidos(qtd: int, clientes: list[tuple], produtos: list[tuple]) -> list[tuple]:
    # TODO: para cada pedido, sorteie um cliente e um produto EXISTENTES (respeite as FKs; sorteie apenas produtos com preco > 0,
    #       senao o valor_total negativo da anomalia 4 viraria zero),
    #       quantidade de 1 a 5, valor_total = preco * quantidade (2 casas) e data nos ultimos 300 dias
    # TODO: Anomalia 4: valor_total negativo (estorno mal lancado) em 5 pedidos
    # TODO: Anomalia 5: data_pedido no futuro (ano 2030) em 3 pedidos DIFERENTES dos anteriores
    ...


def popular() -> None:
    resetar_banco()
    with conectar() as conexao:
        criar_tabelas(conexao)
        clientes = gerar_clientes()
        produtos = gerar_produtos()
        pedidos = gerar_pedidos(150, clientes, produtos)
        conexao.executemany("INSERT INTO clientes VALUES (?, ?, ?, ?, ?)", clientes)
        # TODO: insira produtos e pedidos com executemany e placeholders "?" (nunca f-strings em SQL)
        conexao.commit()
        for tabela in ("clientes", "produtos", "pedidos"):
            total = conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            print(f"{tabela}: {total} linhas")


if __name__ == "__main__":
    popular()
