# DataOps agent

Aplicação Streamlit para exploração e auditoria de dados em SQLite, com guardrails, cache e ferramentas analíticas.

Como executar (resumido):

1. Criar e ativar ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependências

```bash
pip install -r requirements.txt
```

3. Inicializar banco e popular dados (opcional para desenvolvimento)

```bash
python src/database/init_db.py
python src/database/seed_data.py
```

4. Executar a aplicação

```bash
streamlit run app.py
```

5. Rodar testes

```bash
pytest -q
```

Notas:
- Defina `GEMINI_API_KEY` se for usar integrações com a API de modelos.
- A pasta `tests/` contém testes unitários e de integração rápidos.
