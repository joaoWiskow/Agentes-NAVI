Abaixo, apresento a lista estruturada de problemas por domínio de e-commerce, detalhando para cada um deles o **Evento X (Disparador)** e o **Artefato** técnico envolvido que provoca a falha:

---

### 1. Domínio: Clientes (*Customers / Users*)

* **Problema 1: Duplicidade de Cadastros por Concorrência**
* **Artefato Afetado:** Script de ingestão/pipeline de consolidação de usuários (ETL em Python/SQL) e tabela dimensão `dim_customers`.
* **Evento X:** Duas solicitações de cadastro simultâneas (ex: App mobile e Web) vindas de microsserviços distintos chegam no mesmo segundo sem chave de idempotência, gerando IDs diferentes para o mesmo cliente.


* **Problema 2: Exposição Inadequada de Dados Sensíveis (LGPD)**
* **Artefato Afetado:** Script de anonimização/máscara de dados e tabela de logs de acesso de usuários.
* **Evento X:** Uma alteração em uma função utilitária de mascaramento de strings é enviada para produção sem testes unitários, fazendo com que dados de CPF e telefone passem a ser gravados em texto plano.


* **Problema 3: Tempos de Espera Longos (Latência no Perfil)**
* **Artefato Afetado:** Consulta SQL analítica de segmentação e tabela de fatos de clientes no Data Warehouse.
* **Evento X:** Um volume atípico de consultas pesadas de marketing roda simultaneamente em uma tabela volumosa de clientes que não possui particionamento ou índices adequados, estourando o *timeout* da API.



---

### 2. Domínio: Catálogo de Produtos e Categorias (*Products & Catalog*)

* **Problema 1: Órfãos de Categoria por Deleção Indevida**
* **Artefato Afetado:** Tabela dimensão de produtos (`dim_products`), tabelas fato e script de carga incremental.
* **Evento X:** Um produto é excluído ou reestruturado diretamente no banco de dados do ERP de origem, rompendo o relacionamento de chave estrangeira com a árvore de categorias no Data Lake.


* **Problema 2: Inconsistência de Moeda ou Casas Decimais**
* **Artefato Afetado:** Script de transformação de preços e tabela de catálogo de produtos.
* **Evento X:** O sistema de origem altera acidentalmente o formato de envio do preço de um inteiro em centavos (ex: `1999`) para um float com ponto (ex: `19.99`), distorcendo os cálculos subsequentes.


* **Problema 3: Tempos de Espera Longos (Sincronização de Catálogo Massivo)**
* **Artefato Afetado:** Rotina de carga *Full Load* (ETL diário) conectada ao banco de dados transacional.
* **Evento X:** O job de extração executa uma varredura completa (*Full Table Scan*) sem paginação em um catálogo com milhões de SKUs, bloqueando tabelas operacionais (*table locks*) e travando o sistema.



---

### 3. Domínio: Pedidos e Transações (*Orders & Payments*)

* **Problema 1: Quebra de Schema por Alteração no Gateway de Pagamento**
* **Artefato Afetado:** Pipeline de ingestão de pagamentos (DAG do Airflow/script de API) e schema da tabela de transações.
* **Evento X:** A API do gateway de pagamento parceiro é atualizada e o campo de retorno `transaction_id` é renomeado para `payment_reference` sem aviso prévio, fazendo o pipeline falhar.


* **Problema 2: Pedidos Fantasmas (Falta de Idempotência)**
* **Artefato Afetado:** Tabela transacional de pedidos (`fact_orders`) e rotina de gravação no banco.
* **Evento X:** Uma falha de rede temporária faz com que o cliente ou o microsserviço de checkout reenvie o mesmo payload de pedido duplicado antes de receber a confirmação de sucesso.


* **Problema 3: Tempos de Espera Longos (Gatilho de Confirmação Bloqueado)**
* **Artefato Afetado:** Fila de mensagens (ex: RabbitMQ/Kafka) e microsserviço de faturamento.
* **Evento X:** Um pico repentino de compras (ex: Black Friday) sobrecarrega a fila de eventos de pagamento, criando um gargalo que atrasa em horas a confirmação da compra para o usuário.



---

### 4. Domínio: Estoque e Logística (*Inventory & Fulfillment*)

* **Problema 1: Divergência de Inventário (Venda Sem Estoque)**
* **Artefato Afetado:** Tabela de estoque atual (`dim_inventory`) e API de checagem do carrinho.
* **Evento X:** O atraso na propagação de eventos de baixa de estoque em tempo real entre o armazém físico e o site faz com que múltiplos clientes comprem o último item simultaneamente.


* **Problema 2: Corrupção na Linhagem de Rastreio**
* **Artefato Afetado:** Tabela de rastreamento de entregas e pipeline de integração com a transportadora.
* **Evento X:** Webhooks da transportadora chegam fora de ordem cronológica (ex: o evento de "Entregue" é processado antes de "Saiu para entrega"), corrompendo métricas de prazo.


* **Problema 3: Tempos de Espera Longos (Lock de Reserva de Carrinho)**
* **Artefato Afetado:** Banco de dados transacional e stored procedures de travamento de estoque.
* **Evento X:** Concorrência extrema em itens de alta demanda gera bloqueios cruzados (*deadlocks*) no banco de dados relacional no momento do checkout, congelando a tela do usuário.



---

### 5. Domínio: Eventos de Clique e Navegação (*Clickstream / Web Analytics*)

* **Problema 1: Explosão de Volume por Bots (Anomalia de Ingestão)**
* **Artefato Afetado:** Pipeline de ingestão de *stream* (ex: Kafka/Spark Streaming) e storage de logs brutos no Data Lake.
* **Evento X:** Um ataque de *scrapers/bots* automatizados dispara milhões de acessos falsos por minuto, inundando o pipeline e elevando drasticamente o custo de processamento.


* **Problema 2: Perda de Rastreamento de UTMs**
* **Artefato Afetado:** Script de captura de tags no front-end e tabela de eventos de clique.
* **Evento X:** Uma alteração no layout da página web remove acidentalmente os parâmetros de URL de campanhas (*UTMs*), fazendo o sistema registrar todo o tráfego como "Direto".


* **Problema 3: Tempos de Espera Longos (Demora na Compactação Parquet)**
* **Artefato Afetado:** Diretório de arquivos brutos no Data Lake e consultas analíticas *ad-hoc*.
* **Evento X:** O acúmulo excessivo de pequenos arquivos de log gerados a cada minuto sem uma rotina de compactação (*compaction job*) obriga o motor de consulta a varrer milhares de arquivos miúdos, multiplicando o tempo de resposta.



---

### 6. Domínio: Marketing e Campanhas (*Marketing & Attribution*)

* **Problema 1: Duplicação de Atribuição de Canais**
* **Artefato Afetado:** Tabela de atribuição de vendas e modelo de cruzamento de dados de anúncios.
* **Evento X:** Múltiplas plataformas de anúncios (Google e Meta) enviam relatórios de conversão sobrepostos que não utilizam uma chave de desduplicação unificada, superestimando o ROI.


* **Problema 2: Desatualização de Custos de Anúncios**
* **Artefato Afetado:** Tabela de custos de marketing (`fact_marketing_spend`) e pipeline de integração via API de mídias.
* **Evento X:** A chave de acesso (*token*) da API de uma rede social expira silenciosamente, travando a ingestão diária de custos enquanto os dados de conversão continuam entrando.


* **Problema 3: Tempos de Espera Longos (Modelos de Atribuição Multitoque Complexos)**
* **Artefato Afetado:** Script de Machine Learning / processamento em lote (ex: modelo Markov Chain ou Shapley Value).
* **Evento X:** O volume da jornada de cliques de milhões de usuários processados em conjunto excede a capacidade de memória do cluster de processamento (ex: Spark/Databricks), fazendo o job rodar por horas ou falhar por falta de recursos.



---

### 7. Domínio: Atendimento ao Cliente e Pós-Venda (*Customer Support / CRM*)

* **Problema 1: Cruzamento Órfão de Devoluções**
* **Artefato Afetado:** Tabela de tickets de suporte/devoluções e tabela fato de pedidos.
* **Evento X:** Um atendente digita incorretamente o ID do pedido ao registrar uma solicitação de troca, quebrando o relacionamento analítico entre o suporte e a venda original.


* **Problema 2: Estouro de Conexão em Webhooks de Chat**
* **Artefato Afetado:** Microsserviço receptor de webhooks e tabela de satisfação do cliente (*CSAT*).
* **Evento X:** O sistema externo de atendimento envia um lote massivo de atualizações acumuladas de uma só vez, sobrecarregando as conexões ativas com o banco de dados.


* **Problema 3: Tempos de Espera Longos (Processamento de NLP em Reviews)**
* **Artefato Afetado:** Pipeline de análise de sentimentos e tabela de avaliações de produtos.
* **Evento X:** Uma campanha promocional gera um pico enorme de novas avaliações de produtos em texto, e o job de processamento de linguagem natural (NLP) em lote roda em uma única thread síncrona, deixando o painel de qualidade desatualizado por dias.
