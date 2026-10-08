import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.tools.profiling_tools import amostrar_linhas, calcular_estatisticas_coluna, contar_nulos_e_distintos
from src.tools.query_tools import executar_query_analitica
from src.tools.schema_tools import descrever_schema_tabela, listar_tabelas, obter_chaves_estrangeiras

load_dotenv()
MODEL = "gemini-3.5-flash-lite"
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

INSTRUCAO = (
    "Voce e um assistente de DataOps. Antes de escrever qualquer SQL, consulte o schema com as ferramentas. "
    "Nunca invente tabelas ou colunas. Responda em portugues, citando os numeros encontrados."
)

FERRAMENTAS = [
    # TODO: liste as 7 funcoes importadas acima (passe as funcoes Python, sem chama-las)
    amostrar_linhas,
    calcular_estatisticas_coluna,
    contar_nulos_e_distintos,
    executar_query_analitica,
    descrever_schema_tabela,
    listar_tabelas,
    obter_chaves_estrangeiras,
]

PERGUNTAS = [
    "Quantos registros nulos existem na coluna documento_url da tabela contrato?",
    "Qual é a média, o menor e o maior rendimento da tabela movimentacao?",
    "Quais são as 3 lojas com maior rendimento total? Mostre o nome da loja e o valor total.",
]

if __name__ == "__main__":
    config = types.GenerateContentConfig(system_instruction=INSTRUCAO, tools=FERRAMENTAS)
    for pergunta in PERGUNTAS:
        print("PERGUNTA:", pergunta)
        response = client.models.generate_content(model=MODEL, contents=pergunta, config=config)
        print("RESPOSTA:", response.text)
        # TODO: imprima o historico de chamadas automaticas: percorra response.automatic_function_calling_history
        #       e mostre o nome de cada function_call feita pelo modelo
        for item in response.automatic_function_calling_history or []:
            for part in item.parts or []:
                function_call = getattr(part, "function_call", None)
                if function_call:
                    print("CHAMADA:", function_call.name)
        print("-" * 60)