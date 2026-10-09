import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.agent.cache import (
    CACHE_FERRAMENTAS,
    CACHE_RESPOSTAS,
    FERRAMENTAS_CACHEAVEIS,
    chave_ferramenta,
    normalizar_pergunta,
    parece_followup,
)
from src.agent.resiliencia import ErroAltaDemanda, classificar_erro, obter_cadeia

load_dotenv()
MAX_CHARS_PERGUNTA = 1000
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
    def __init__(self, max_turnos: int = 6, historico: list | None = None, usar_cache: bool = True):
        self.max_turnos = max_turnos
        self.usar_cache = usar_cache
        self.cadeia = obter_cadeia()
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
            system_instruction=INSTRUCAO, tools=cast(Any, converter_tools(catalogo.tools))
        )
        return self

    async def __aexit__(self, *erro):
        await self._pilha.aclose()

    # ------------------------------------------------------------------ cache de resposta
    def _registrar_turno_no_historico(self, pergunta: str, resposta: str) -> None:
        """Mantem a memoria do modelo coerente mesmo quando a resposta veio do cache."""
        self.historico.append(types.Content(role="user", parts=[types.Part(text=pergunta)]))
        self.historico.append(types.Content(role="model", parts=[types.Part(text=resposta)]))

    def _resposta_do_cache(self, pergunta: str, chave: str, aceitar_expirado: bool, inicio: float) -> dict | None:
        acerto = CACHE_RESPOSTAS.buscar(chave, aceitar_expirado=aceitar_expirado)
        if acerto is None:
            return None
        guardado, situacao = acerto
        self._registrar_turno_no_historico(pergunta, guardado["resposta"])
        meta = {
            "cache": "resposta" if situacao == "fresco" else "expirado",
            "modelo": None, "fallback": False, "tentativas": 0, "chamadas_llm": 0,
            "eventos": [], "degradado": situacao == "expirado",
            "tempo_total_ms": round((time.perf_counter() - inicio) * 1000, 2),
        }
        return {"resposta": guardado["resposta"], "trace": guardado["trace"], "meta": meta}

    # ------------------------------------------------------------------ execucao de ferramenta
    async def _executar_ferramenta(self, nome: str, argumentos: dict, falhas_vistas: dict) -> tuple[Any, bool, bool]:
        """Retorna (conteudo, falhou, veio_do_cache). Nunca levanta excecao: erro vira observacao para o modelo."""
        if self._sessao is None:
            raise RuntimeError("Sessao MCP nao inicializada")
        chave = chave_ferramenta(nome, argumentos)

        # ANTI-LOOP: o modelo repetiu exatamente uma chamada que ja falhou -> nao gastamos outra ida ao banco.
        if chave in falhas_vistas:
            anterior = falhas_vistas[chave]
            conteudo = dict(anterior) if isinstance(anterior, dict) else {"sucesso": False, "erro": str(anterior)}
            conteudo["dica"] = (
                "Voce ja tentou exatamente esta chamada e ela falhou. Nao repita: consulte o schema "
                "(descrever_schema) ou reescreva a consulta de forma diferente."
            )
            return conteudo, True, False

        if self.usar_cache and nome in FERRAMENTAS_CACHEAVEIS:
            acerto = CACHE_FERRAMENTAS.buscar(chave)
            if acerto is not None:
                return acerto[0], False, True

        try:
            resultado_mcp = await self._sessao.call_tool(nome, argumentos)
            conteudo = ler_resultado(resultado_mcp)
            falhou = bool(resultado_mcp.isError) or (isinstance(conteudo, dict) and conteudo.get("sucesso") is False)
        except Exception as erro:  # noqa: BLE001 - falha de transporte/MCP vira observacao, nao derruba o turno
            conteudo = {"sucesso": False, "erro": f"Falha ao executar '{nome}': {type(erro).__name__}: {erro}"}
            falhou = True

        if falhou:
            falhas_vistas[chave] = conteudo
        elif self.usar_cache and nome in FERRAMENTAS_CACHEAVEIS:
            CACHE_FERRAMENTAS.guardar(chave, conteudo)
        return conteudo, falhou, False

    # ------------------------------------------------------------------ loop principal
    async def perguntar(self, pergunta: str) -> dict:
        """Retorna {"resposta": str, "trace": list[dict], "meta": dict}."""
        inicio_total = time.perf_counter()
        pergunta = (pergunta or "").strip()
        meta: dict = {
            "cache": None, "modelo": None, "fallback": False, "tentativas": 0, "chamadas_llm": 0,
            "eventos": [], "degradado": False, "tempo_total_ms": 0.0,
        }

        def _fechar(resposta: str, trace: list[dict]) -> dict:
            meta["tempo_total_ms"] = round((time.perf_counter() - inicio_total) * 1000, 2)
            return {"resposta": resposta, "trace": trace, "meta": meta}

        # Validacao de entrada barata, antes de gastar qualquer chamada.
        if not pergunta:
            return _fechar("Escreva uma pergunta sobre os dados para eu poder ajudar.", [])
        if len(pergunta) > MAX_CHARS_PERGUNTA:
            return _fechar(f"A pergunta tem {len(pergunta)} caracteres; resuma para ate {MAX_CHARS_PERGUNTA}.", [])

        # ELO 1 da cadeia: cache de resposta (so para perguntas autocontidas).
        chave_resposta = normalizar_pergunta(pergunta)
        cacheavel = self.usar_cache and not parece_followup(pergunta) and bool(chave_resposta)
        if cacheavel:
            do_cache = self._resposta_do_cache(pergunta, chave_resposta, aceitar_expirado=False, inicio=inicio_total)
            if do_cache is not None:
                return do_cache

        self.historico.append(types.Content(role="user", parts=[types.Part(text=pergunta)]))
        tamanho_antes = len(self.historico) - 1  # para desfazer o historico se a pergunta falhar de vez
        trace: list[dict] = []
        falhas_vistas: dict = {}

        try:
            for turno in range(1, self.max_turnos + 1):
                # ELOS 2..N: retry/backoff -> modelos de fallback -> disjuntor (ver resiliencia.py)
                chamada = await self.cadeia.gerar(self.client, cast(Any, self.historico), self._config)
                response = chamada.resposta
                meta["chamadas_llm"] += 1
                meta["tentativas"] += chamada.tentativas
                meta["modelo"] = chamada.modelo
                meta["fallback"] = meta["fallback"] or chamada.fallback
                meta["eventos"].extend(chamada.eventos)

                self.historico.append(response.candidates[0].content)

                if not response.function_calls:
                    texto = response.text or "O modelo nao retornou texto. Tente reformular a pergunta."
                    # So guardamos respostas conclusivas e sem erro de ferramenta pendente.
                    if cacheavel and response.text:
                        CACHE_RESPOSTAS.guardar(chave_resposta, {"resposta": texto, "trace": trace})
                    return _fechar(texto, trace)

                partes = []
                for chamada_ferramenta in response.function_calls:
                    nome_ferramenta = chamada_ferramenta.name
                    if nome_ferramenta is None:
                        raise RuntimeError("Chamada de ferramenta sem nome")
                    argumentos = dict(chamada_ferramenta.args or {})

                    inicio = time.perf_counter()
                    conteudo, falhou, do_cache = await self._executar_ferramenta(nome_ferramenta, argumentos, falhas_vistas)
                    tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)

                    # AUTO-RECUPERACAO: o erro (do guardrail ou do SQLite) volta ao modelo como observacao normal;
                    # ele le a mensagem, ajusta o SQL e tenta de novo no proximo turno.
                    trace.append({
                        "turno": turno,
                        "ferramenta": nome_ferramenta,
                        "argumentos": argumentos,
                        "resultado": conteudo,
                        "sucesso": not falhou,
                        "guardrail": conteudo.get("guardrail") if isinstance(conteudo, dict) else None,
                        "query_sql": argumentos.get("query"),
                        "tempo_ms": tempo_ms,
                        "cache": do_cache,
                    })
                    partes.append(types.Part.from_function_response(name=nome_ferramenta, response={"result": conteudo}))
                self.historico.append(types.Content(role="user", parts=partes))

            return _fechar("Limite de turnos atingido sem resposta conclusiva. Tente uma pergunta mais especifica.", trace)

        except ErroAltaDemanda as erro:
            meta["eventos"].extend(erro.eventos)
            meta["degradado"] = True
            del self.historico[tamanho_antes:]  # a pergunta nao foi respondida: nao poluimos a memoria
            # ULTIMO ELO: cache expirado e melhor que nada.
            if self.usar_cache and chave_resposta and not parece_followup(pergunta):
                velho = self._resposta_do_cache(pergunta, chave_resposta, aceitar_expirado=True, inicio=inicio_total)
                if velho is not None:
                    velho["meta"]["eventos"] = meta["eventos"]
                    velho["resposta"] = "(Servico de IA sobrecarregado: mostrando a ultima resposta salva.)\n\n" + velho["resposta"]
                    return velho
            return _fechar(
                "O servico de IA esta com alta demanda agora e nao consegui concluir. "
                "Nada foi alterado nos dados. Tente novamente em alguns instantes.",
                trace,
            )
        except Exception as erro:  # noqa: BLE001
            del self.historico[tamanho_antes:]
            meta["degradado"] = True
            meta["eventos"].append({"tipo": classificar_erro(erro), "detalhe": f"{type(erro).__name__}: {str(erro)[:160]}"})
            return _fechar(f"Nao consegui concluir esta pergunta ({type(erro).__name__}). Tente reformular.", trace)


async def demo() -> None:
    async with DataOpsAgent() as agente:
        saida = await agente.perguntar("Liste as tabelas existentes")
        print(saida["resposta"])
        for passo in saida["trace"]:
            print(f"  turno {passo['turno']}: {passo['ferramenta']} {passo['argumentos']} ({passo['tempo_ms']} ms)")


if __name__ == "__main__":
    asyncio.run(demo())