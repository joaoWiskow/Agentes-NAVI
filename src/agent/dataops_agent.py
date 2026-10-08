import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
MODEL = "gemini-3.1-flash-lite"
RAIZ = Path(__file__).resolve().parents[2]

INSTRUCAO = (
    "Voce e o DataOps Agent, um assistente de auditoria de dados em SQLite. "
    "1) Descubra o schema com as ferramentas ANTES de escrever SQL; nunca invente tabelas ou colunas. "
    "2) So use consultas SELECT. 3) Se uma ferramenta retornar erro, leia a mensagem, corrija e tente de novo. "
    "4) Se o usuario pedir para alterar, apagar ou limpar dados, recuse e explique que o agente e somente leitura. "
    "Responda em portugues, citando os numeros encontrados."
)


def converter_tools(mcp_tools) -> list[types.Tool]:
    declaracoes = [
        types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.inputSchema)
        for t in mcp_tools
    ]
    return [types.Tool(function_declarations=declaracoes)]


def ler_resultado(resultado_mcp):
    """Extrai o conteudo estruturado de uma resposta de ferramenta MCP."""
    if getattr(resultado_mcp, "structuredContent", None):
        dados = resultado_mcp.structuredContent
        return dados.get("result", dados) if isinstance(dados, dict) else dados
    texto = resultado_mcp.content[0].text if resultado_mcp.content else ""
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return texto


class DataOpsAgent:
    def __init__(self, max_turnos: int = 6, historico: list | None = None):
        self.max_turnos = max_turnos
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        # O historico pode ser injetado: o Streamlit (Dia 19) recria o agente a cada pergunta e reaproveita a conversa
        self.historico: list[types.Content] = historico if historico is not None else []
        self._pilha = AsyncExitStack()
        self._sessao: ClientSession | None = None
        self._config: types.GenerateContentConfig | None = None

    async def __aenter__(self):
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "src.mcp_server.dataops_mcp"], cwd=str(RAIZ)
        )
        leitura, escrita = await self._pilha.enter_async_context(stdio_client(params))
        self._sessao = await self._pilha.enter_async_context(ClientSession(leitura, escrita))
        await self._sessao.initialize()
        catalogo = await self._sessao.list_tools()
        self._config = types.GenerateContentConfig(
            system_instruction=INSTRUCAO, tools=converter_tools(catalogo.tools)
        )
        return self

    async def __aexit__(self, *erro):
        await self._pilha.aclose()

    async def perguntar(self, pergunta: str) -> dict:
        """Retorna {"resposta": str, "trace": list[dict]}."""
        self.historico.append(types.Content(role="user", parts=[types.Part(text=pergunta)]))
        trace: list[dict] = []

        for turno in range(1, self.max_turnos + 1):
            response = await self.client.aio.models.generate_content(
                model=MODEL, contents=self.historico, config=self._config
            )
            self.historico.append(response.candidates[0].content)

            # TODO: se NAO houver response.function_calls, retorne {"resposta": response.text, "trace": trace}
            if not response.function_calls:
                return {"resposta": response.text, "trace": trace}

            partes = []
            for chamada in response.function_calls:
                inicio = time.perf_counter()
                if self._sessao is None:
                    raise RuntimeError("Sessao MCP nao inicializada")
                # TODO: execute a ferramenta com self._sessao.call_tool(chamada.name, dict(chamada.args))
                #       e guarde o retorno em resultado_mcp
                resultado_mcp = await self._sessao.call_tool(chamada.name, dict(chamada.args))
                tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
                conteudo = ler_resultado(resultado_mcp)
                falhou = bool(resultado_mcp.isError) or (isinstance(conteudo, dict) and conteudo.get("sucesso") is False)

                # AUTO-RECUPERACAO: o erro (do guardrail ou do SQLite) volta ao modelo como observacao normal;
                # ele le a mensagem, ajusta o SQL e tenta de novo no proximo turno.
                trace.append({
                    "turno": turno,
                    "ferramenta": chamada.name,
                    "argumentos": dict(chamada.args),
                    "resultado": conteudo,
                    "sucesso": not falhou,
                    "guardrail": conteudo.get("guardrail") if isinstance(conteudo, dict) else None,
                    "query_sql": dict(chamada.args).get("query"),
                    "tempo_ms": tempo_ms,
                })
                partes.append(types.Part.from_function_response(name=chamada.name, response={"result": conteudo}))
            self.historico.append(types.Content(role="user", parts=partes))

        return {"resposta": "Limite de turnos atingido sem resposta conclusiva.", "trace": trace}


async def demo() -> None:
    async with DataOpsAgent() as agente:
        saida = await agente.perguntar("Liste as tabelas existentes")
        print(saida["resposta"])
        for passo in saida["trace"]:
            print(f"  turno {passo['turno']}: {passo['ferramenta']} {passo['argumentos']} ({passo['tempo_ms']} ms)")


if __name__ == "__main__":
    asyncio.run(demo())