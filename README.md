# Agentes-NAVI
## Como trabalhamos
- Piloto (teclado): escreve o codigo. Copilotos: pesquisam, revisam e testam ao vivo.
- O piloto muda todo dia. Escala: Dia 16 = <nome>, Dia 17 = <nome>, Dia 18 = <nome>, Dia 19 = <nome>, Dia 20 = <nome> (pitch: todos).
- Commits pequenos, mensagem no padrao "feat: ...", "fix: ...", "docs: ...".
- Ninguem faz push direto quebrando a execucao de outro: rode "python tests/smoke_test_db.py" antes de cada push.
- Ao comecar o dia: git pull. Ao terminar: git push e tag do dia (v0.1-setup no Dia 16).
- Conflito no Git: resolver juntos, na mesma tela.

## Como rodar
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/database/init_db.py
python src/database/seed_data.py
