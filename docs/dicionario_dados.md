# Dicionario de Dados: Gestao de Shopping Center

Trio: AgenteDeVarejo | Banco: data/dataops.db (SQLite)

Este dicionario substitui o dominio anterior e passa a ser a fonte de verdade
para o schema, a carga de dados e os testes automatizados do projeto.

## Tabela: loja

Descricao: uma linha por loja ou estabelecimento presente no shopping.

| Coluna | Tipo | Restricoes | Descricao |
| --- | --- | --- | --- |
| id | INTEGER | PRIMARY KEY | Identificador unico da loja |
| nome | VARCHAR(150) | NOT NULL | Nome comercial da loja |
| categoria | VARCHAR(100) | NOT NULL | Categoria comercial da loja |
| piso | INTEGER | NOT NULL | Piso onde a loja esta localizada |
| inaugurada_em | TIMESTAMP | NOT NULL | Data de inauguracao do estabelecimento |

## Tabela: movimentacao

Descricao: registros financeiros e operacionais de uma loja em uma data.

| Coluna | Tipo | Restricoes | Descricao |
| --- | --- | --- | --- |
| id | INTEGER | PRIMARY KEY | Identificador unico do registro de movimentacao |
| loja_id | INTEGER | FOREIGN KEY -> loja.id, NOT NULL | Referencia a loja |
| data | DATE | NOT NULL | Data a qual se refere a movimentacao |
| rendimento | NUMERIC(12, 2) | NOT NULL | Faturamento ou receita da loja |
| custos | NUMERIC(12, 2) | NOT NULL | Custos operacionais registrados |
| movimentacao | INTEGER |  | Indicador quantitativo do fluxo de pessoas ou transacoes |

## Tabela: contrato

Descricao: historico de contratos vinculados a cada loja.

| Coluna | Tipo | Restricoes | Descricao |
| --- | --- | --- | --- |
| id | INTEGER | PRIMARY KEY | Identificador unico do contrato |
| loja_id | INTEGER | FOREIGN KEY -> loja.id, NOT NULL | Referencia a loja |
| data_inicio | DATE | NOT NULL | Inicio da vigencia do contrato |
| data_fim | DATE | NOT NULL | Termino da vigencia do contrato |
| status | VARCHAR(50) | NOT NULL | Situacao atual do contrato |
| documento_url | TEXT |  | Link ou caminho para o documento digitalizado |

## Relacionamentos

- loja 1 --- N movimentacao
- loja 1 --- N contrato

## Perguntas de negocio que o assistente precisara responder

1. Qual e o faturamento total de todas as lojas somadas em um determinado mes?
2. Quais contratos de locacao vencem nos proximos 30 dias?
3. Qual loja gerou o maior rendimento acumulado no ultimo trimestre?
4. Quais lojas estao com contratos em negociacao ou encerrados, mas continuam operando?
5. Qual e a media de custos operacionais diarios agrupados por categoria de loja?
6. Quais lojas registraram queda consecutiva no rendimento nos ultimos meses?
7. Qual e o ranking das categorias de lojas mais presentes no shopping?
8. Qual e o comportamento historico de fluxo e rendimento de uma loja especifica em finais de semana comparado aos dias uteis?

## Anomalias que planejamos injetar

- 4 quedas bruscas de rendimento.
- 3 casos de custos superiores ao rendimento.
- 3 movimentacoes depois do fim do contrato.
- 2 lojas com contratos ativos sobrepostos.
- 4 discrepancias entre movimentacao e rendimento.
- 3 lacunas temporais no historico de movimentacao.
