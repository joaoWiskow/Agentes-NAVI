# Dicionario de Dados: Gestão Comercial de Shopping Center - Iguatemi

Trio: AgenteDeVarejo  |  Banco: data/dataops.db (SQLite)

## Tabela: lojas

Descricao: uma linha por loja ou estabelecimento presente no shopping.

| Coluna | Tipo | Restricoes | Descricao |
| --- | --- | --- | --- |
| id | INTEGER | PRIMARY KEY | Identificador da loja |
| nome | TEXT | NOT NULL | Nome da loja |
| categoria | TEXT | NOT NULL | Categoria comercial da loja |
| piso | INTEGER | NOT NULL | Piso onde a loja está localizada |
| area_m2 | REAL | NOT NULL | Area ocupada pela loja em metros quadrados |
| aluguel_mensal | REAL | NOT NULL | Valor mensal do aluguel da loja |
| inaugurada_em | DATETIME | NOT NULL | Data de inauguracao da loja |

## Tabela: vendas

Descricao: registros de vendas realizadas pelas lojas do shopping.

| Coluna | Tipo | Restricoes | Descricao |
| --- | --- | --- | --- |
| id | INTEGER | PRIMARY KEY | Identificador da venda |
| loja_id | INTEGER | FOREIGN KEY -> lojas.id, NOT NULL | Identificador da loja que realizou a venda |
| valor | REAL | NOT NULL | Valor total da venda |
| quantidade | INTEGER | NOT NULL | Quantidade de itens vendidos |
| data_venda | DATETIME | NOT NULL | Data em que a venda foi realizada |

## Tabela: fluxo_visitantes

Descricao: registros do fluxo de visitantes no shopping em diferentes períodos e pisos.

| Coluna | Tipo | Restricoes | Descricao |
| --- | --- | --- | --- |
| id | INTEGER | PRIMARY KEY | Identificador do registro de fluxo |
| data | DATETIME | NOT NULL | Data da medicao |
| periodo | TEXT | NOT NULL | Periodo do dia da medicao |
| visitantes | INTEGER | NOT NULL | Quantidade de visitantes registrada |
| piso | INTEGER | NOT NULL | Piso onde o fluxo foi registrado |

## Relacionamentos

- lojas 1 --- N vendas
- lojas 1 --- N fluxo_visitantes

## Perguntas de negocio que o assistente precisara responder

1. Qual loja apresentou o maior faturamento no periodo?
2. Qual categoria de lojas gera o maior faturamento?
3. Qual piso apresenta o maior fluxo de visitantes?
4. Qual loja possui o maior faturamento por metro quadrado?
5. Qual e o ticket medio das vendas por categoria?
6. Existem lojas com faturamento abaixo da media do shopping?
7. Existem registros de vendas com valores negativos?
8. Existe relacao entre o fluxo de visitantes e o faturamento das lojas?

## Anomalias que planejamos injetar (para o agente encontrar)

- 4 lojas com aluguel mensal negativo
- 3 lojas com area igual a zero
- 5 vendas com valor negativo
- 3 vendas com data no futuro
- 4 registros de vendas duplicados
- 5 registros de fluxo de visitantes com quantidade negativa
- 2 lojas sem categoria