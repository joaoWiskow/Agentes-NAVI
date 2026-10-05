# Especificação Completa do Banco de Dados - Sistema de Gestão de Shopping Center

Este documento abrange uma sugestão de mudança de dominio que se aprovada ira ser usada como a base para o desenvolvimento do trabalho e consolida a modelagem do banco de dados sugerido para a gestão de estabelecimentos em um shopping center, abrangendo o modelo conceitual, lógico, físico (DDL) e as perguntas de negócio (consultas analíticas).

---

## 1. Modelo Conceitual (DER)

O modelo conceitual define as três entidades centrais do sistema, seus atributos principais e as cardinalidades dos relacionamentos.

### Entidades e Atributos
* **`LOJA`**
  * `id` (PK)
  * `nome`
  * `categoria`
  * `piso`
  * `inaugurada_em`

* **`MOVIMENTACAO`**
  * `id` (PK)
  * `loja_id` (FK $\rightarrow$ `Loja`)
  * `data`
  * `rendimento`
  * `custos`
  * `movimentacao`

* **`CONTRATO`**
  * `id` (PK)
  * `loja_id` (FK $\rightarrow$ `Loja`)
  * `data_inicio`
  * `data_fim`
  * `status`
  * `documento_url`

### Relacionamentos e Cardinalidade
* **`Loja` (1) $\longleftrightarrow$ (N) `Movimentacao`**: Uma loja possui múltiplos registros de movimentação ao longo do tempo, mas cada registro pertence a uma única loja.
* **`Loja` (1) $\longleftrightarrow$ (N) `Contrato`**: Uma loja pode possuir um histórico de múltiplos contratos ao longo dos anos, mas cada contrato está vinculado a uma única loja.

---

## 2. Modelo Lógico Relacional

No modelo lógico, detalhamos os tipos de dados, as chaves primárias (PK) e as chaves estrangeiras (FK).

* **`loja`**
  * `id` : `INTEGER` (PK) — Identificador único da loja.
  * `nome` : `VARCHAR(150)` [NOT NULL] — Nome comercial da loja.
  * `categoria` : `VARCHAR(100)` [NOT NULL] — Categoria comercial (ex: Vestuário, Alimentação).
  * `piso` : `INTEGER` [NOT NULL] — Andar/piso onde a loja está localizada.
  * `inaugurada_em` : `TIMESTAMP` [NOT NULL] — Data de inauguração do estabelecimento.

* **`movimentacao`**
  * `id` : `INTEGER` (PK) — Identificador único do registro de movimentação.
  * `loja_id` : `INTEGER` (FK references `loja(id)`) [NOT NULL] — Referência à loja.
  * `data` : `DATE` [NOT NULL] — Data a qual se refere a movimentação.
  * `rendimento` : `DECIMAL(12, 2)` [NOT NULL] — Faturamento ou receita da loja.
  * `custos` : `DECIMAL(12, 2)` [NOT NULL] — Custos operacionais registrados.
  * `movimentacao` : `INTEGER` — Indicador quantitativo do fluxo de pessoas ou transações.

* **`contrato`**
  * `id` : `INTEGER` (PK) — Identificador único do contrato.
  * `loja_id` : `INTEGER` (FK references `loja(id)`) [NOT NULL] — Referência à loja.
  * `data_inicio` : `DATE` [NOT NULL] — Início da vigência do contrato.
  * `data_fim` : `DATE` [NOT NULL] — Término da vigência do contrato.
  * `status` : `VARCHAR(50)` [NOT NULL] — Situação atual (ex: 'Ativo', 'Encerrado').
  * `documento_url` : `TEXT` — Link ou caminho para o documento digitalizado (PDF).

---

## 3. Modelo Físico (Script SQL DDL)

```sql
-- Criação da tabela LOJA
CREATE TABLE loja (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    piso INTEGER NOT NULL,
    inaugurada_em TIMESTAMP NOT NULL
);

-- Criação da tabela MOVIMENTACAO
CREATE TABLE movimentacao (
    id SERIAL PRIMARY KEY,
    loja_id INTEGER NOT NULL,
    data DATE NOT NULL,
    rendimento NUMERIC(12, 2) NOT NULL,
    custos NUMERIC(12, 2) NOT NULL,
    movimentacao INTEGER,
    CONSTRAINT fk_movimentacao_loja 
        FOREIGN KEY (loja_id) 
        REFERENCES loja(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

-- Criação da tabela CONTRATO
CREATE TABLE contrato (
    id SERIAL PRIMARY KEY,
    loja_id INTEGER NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE NOT NULL,
    status VARCHAR(50) NOT NULL,
    documento_url TEXT,
    CONSTRAINT fk_contrato_loja 
        FOREIGN KEY (loja_id) 
        REFERENCES loja(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

```

---

## 4. Perguntas de Negócio (Consultas Analíticas e Operacionais)

As seguintes questões representam as principais necessidades de informação que a administração do shopping center pode extrair utilizando a estrutura do banco de dados:

1. **Qual é o faturamento total (rendimento) de todas as lojas somadas em um determinado mês?**
* *Objetivo:* Medir a saúde financeira global do shopping e o volume de circulação de capital.


2. **Quais são os contratos de locação que vencem nos próximos 30 dias?**
* *Objetivo:* Permitir ações preventivas da equipe jurídica e comercial para renovações ou reajustes.


3. **Qual é a loja que gerou o maior rendimento acumulado no último trimestre?**
* *Objetivo:* Identificar os estabelecimentos de melhor performance no mix comercial.


4. **Quais lojas estão com contratos em status de negociação ou encerrados, mas continuam operando?**
* *Objetivo:* Garantir o compliance jurídico e evitar ocupações irregulares.


5. **Qual é a média de custos operacionais diários agrupados por categoria de loja?**
* *Objetivo:* Analisar quais setores possuem maior peso de manutenção ou operação interna.


6. **Quais lojas registraram queda consecutiva no rendimento nos últimos meses?**
* *Objetivo:* Identificar lojistas em risco financeiro para ações de suporte ou renegociação.


7. **Qual é o ranking das categorias de lojas mais presentes no shopping com base na quantidade de estabelecimentos?**
* *Objetivo:* Monitorar a diversidade do mix comercial e evitar a saturação de segmentos.


8. **Qual é o comportamento histórico de fluxo e rendimento de uma loja específica em finais de semana comparado aos dias úteis?**
* *Objetivo:* Avaliar o impacto de dias de pico na operação do estabelecimento.



```

```
