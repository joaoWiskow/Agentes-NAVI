"""Testes de cache + cadeia de resiliencia. Nao usam a API do Gemini (cliente simulado).

Rodar: python -m unittest tests.test_resiliencia_cache -v
"""

import asyncio
import unittest

from google.genai import errors, types

from src.agent import cache as cache_mod
from src.agent import dataops_agent as agente_mod
from src.agent.cache import CACHE_FERRAMENTAS, CACHE_RESPOSTAS, normalizar_pergunta, parece_followup
from src.agent.resiliencia import CadeiaModelos, ErroAltaDemanda, classificar_erro


# ----------------------------------------------------------------------------- LLM simulado
def erro_api(codigo: int):
    corpo = {"error": {"code": codigo, "message": f"simulado {codigo}", "status": "SIMULADO"}}
    return (errors.ServerError if codigo >= 500 else errors.ClientError)(codigo, corpo)


def resposta_texto(texto: str) -> types.GenerateContentResponse:
    conteudo = types.Content(role="model", parts=[types.Part(text=texto)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=conteudo)])


def resposta_ferramenta(nome: str, args: dict) -> types.GenerateContentResponse:
    conteudo = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name=nome, args=args))])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=conteudo)])


class ClienteFalso:
    """roteiro: funcao (modelo, n_chamada) -> resposta ou excecao."""

    def __init__(self, roteiro):
        self.roteiro = roteiro
        self.chamadas: list[str] = []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.chamadas.append(model)
        resultado = self.roteiro(model, len(self.chamadas))
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado


def cadeia_rapida(**kw) -> CadeiaModelos:
    padrao = dict(modelos=["m1", "m2", "m3"], tentativas_por_modelo=2, espera_base_s=0.001, espera_max_s=0.005, timeout_s=2)
    padrao.update(kw)
    return CadeiaModelos(**padrao)


# ----------------------------------------------------------------------------- cache
class TestNormalizacao(unittest.TestCase):
    def test_variacoes_batem(self):
        a = normalizar_pergunta("Qual é o faturamento total de março?")
        b = normalizar_pergunta("faturamento TOTAL, março: qual é?")
        self.assertEqual(a, b)

    def test_mes_diferente_nao_bate(self):
        self.assertNotEqual(normalizar_pergunta("faturamento total de marco"), normalizar_pergunta("faturamento total de abril"))

    def test_followup(self):
        self.assertTrue(parece_followup("e no mês passado?"))
        self.assertTrue(parece_followup("mostre isso por categoria"))
        self.assertFalse(parece_followup("Quais contratos vencem nos próximos 30 dias?"))


# ----------------------------------------------------------------------------- cadeia
class TestClassificacao(unittest.TestCase):
    def test_codigos(self):
        self.assertEqual(classificar_erro(erro_api(503)), "retry")
        self.assertEqual(classificar_erro(erro_api(429)), "retry")
        self.assertEqual(classificar_erro(erro_api(404)), "proximo_modelo")
        self.assertEqual(classificar_erro(erro_api(401)), "fatal")
        self.assertEqual(classificar_erro(asyncio.TimeoutError()), "retry")


class TestCadeia(unittest.IsolatedAsyncioTestCase):
    async def test_retry_no_mesmo_modelo(self):
        cliente = ClienteFalso(lambda m, n: erro_api(503) if n == 1 else resposta_texto("ok"))
        r = await cadeia_rapida().gerar(cliente, [], None)
        self.assertEqual((r.modelo, r.tentativas, r.fallback), ("m1", 2, False))

    async def test_fallback_quando_primario_cai(self):
        cliente = ClienteFalso(lambda m, n: erro_api(503) if m == "m1" else resposta_texto("ok"))
        r = await cadeia_rapida().gerar(cliente, [], None)
        self.assertEqual(r.modelo, "m2")
        self.assertTrue(r.fallback)
        self.assertEqual(cliente.chamadas, ["m1", "m1", "m2"])

    async def test_modelo_inexistente_pula_sem_retry(self):
        cliente = ClienteFalso(lambda m, n: erro_api(404) if m == "m1" else resposta_texto("ok"))
        r = await cadeia_rapida().gerar(cliente, [], None)
        self.assertEqual(cliente.chamadas, ["m1", "m2"])
        self.assertEqual(r.modelo, "m2")

    async def test_erro_fatal_nao_insiste(self):
        cliente = ClienteFalso(lambda m, n: erro_api(401))
        with self.assertRaises(errors.ClientError):
            await cadeia_rapida().gerar(cliente, [], None)
        self.assertEqual(len(cliente.chamadas), 1)

    async def test_tudo_fora_levanta_alta_demanda(self):
        cliente = ClienteFalso(lambda m, n: erro_api(503))
        with self.assertRaises(ErroAltaDemanda) as ctx:
            await cadeia_rapida().gerar(cliente, [], None)
        self.assertEqual(len(cliente.chamadas), 6)  # 3 modelos x 2 tentativas
        self.assertTrue(ctx.exception.eventos)

    async def test_disjuntor_abre_e_pula_modelo(self):
        cadeia = cadeia_rapida(falhas_para_abrir=2, cooldown_s=30)
        cliente = ClienteFalso(lambda m, n: erro_api(503) if m == "m1" else resposta_texto("ok"))
        await cadeia.gerar(cliente, [], None)  # m1 falha 2x -> disjuntor abre
        self.assertEqual(cadeia.estado()[0]["estado"], "aberto")
        cliente.chamadas.clear()
        await cadeia.gerar(cliente, [], None)  # agora m1 e pulado, sem gastar chamada
        self.assertEqual(cliente.chamadas, ["m2"])

    async def test_timeout_vira_retry(self):
        async def lento(*a, **k):
            await asyncio.sleep(1)

        cliente = ClienteFalso(lambda m, n: resposta_texto("ok"))
        cliente.generate_content = lambda model, contents, config: lento()  # type: ignore[assignment]
        with self.assertRaises(ErroAltaDemanda):
            await cadeia_rapida(timeout_s=0.01, tentativas_por_modelo=1).gerar(cliente, [], None)


# ----------------------------------------------------------------------------- agente (MCP real + LLM simulado)
class TestAgenteIntegrado(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        CACHE_RESPOSTAS.limpar()
        CACHE_FERRAMENTAS.limpar()
        self._env = agente_mod.os.environ.setdefault("GEMINI_API_KEY", "chave-falsa-para-teste")

    def _roteiro_normal(self):
        def roteiro(modelo, n):
            if n == 1:
                return resposta_ferramenta("listar_tabelas", {})
            return resposta_texto("Existem 3 tabelas: contrato, loja e movimentacao.")
        return roteiro

    async def _agente(self, cliente, cadeia=None, **kw):
        agente = agente_mod.DataOpsAgent(**kw)
        agente.client = cliente
        if cadeia:
            agente.cadeia = cadeia
        return agente

    async def test_cache_de_resposta_evita_llm(self):
        cliente = ClienteFalso(self._roteiro_normal())
        async with await self._agente(cliente, cadeia_rapida()) as ag:
            r1 = await ag.perguntar("Liste as tabelas existentes")
            chamadas_1 = len(cliente.chamadas)
            r2 = await ag.perguntar("tabelas existentes, liste!")
        self.assertIsNone(r1["meta"]["cache"])
        self.assertEqual(r2["meta"]["cache"], "resposta")
        self.assertEqual(len(cliente.chamadas), chamadas_1)  # zero chamadas novas ao LLM
        self.assertEqual(r1["resposta"], r2["resposta"])
        self.assertEqual(r2["trace"][0]["ferramenta"], "listar_tabelas")

    async def test_cache_de_ferramenta_entre_perguntas_diferentes(self):
        def roteiro(modelo, n):
            return resposta_ferramenta("listar_tabelas", {}) if n % 2 == 1 else resposta_texto(f"resposta {n}")
        cliente = ClienteFalso(roteiro)
        async with await self._agente(cliente, cadeia_rapida()) as ag:
            r1 = await ag.perguntar("Quais tabelas existem no banco?")
            r2 = await ag.perguntar("Quantas tabelas o banco possui hoje?")
        self.assertFalse(r1["trace"][0]["cache"])
        self.assertTrue(r2["trace"][0]["cache"])

    async def test_followup_nao_usa_cache_de_resposta(self):
        cliente = ClienteFalso(self._roteiro_normal())
        async with await self._agente(cliente, cadeia_rapida()) as ag:
            await ag.perguntar("Liste as tabelas existentes")
            r2 = await ag.perguntar("e isso, liste as tabelas existentes")
        self.assertIsNone(r2["meta"]["cache"])

    async def test_fallback_aparece_no_meta(self):
        def roteiro(modelo, n):
            if modelo == "m1":
                return erro_api(503)
            return resposta_texto("respondido pelo fallback")
        async with await self._agente(ClienteFalso(roteiro), cadeia_rapida()) as ag:
            r = await ag.perguntar("Quantas lojas existem?")
        self.assertEqual(r["meta"]["modelo"], "m2")
        self.assertTrue(r["meta"]["fallback"])
        self.assertTrue(r["meta"]["eventos"])

    async def test_tudo_fora_degrada_com_mensagem_amigavel(self):
        async with await self._agente(ClienteFalso(lambda m, n: erro_api(503)), cadeia_rapida()) as ag:
            r = await ag.perguntar("Quantas lojas existem?")
            self.assertTrue(r["meta"]["degradado"])
            self.assertIn("alta demanda", r["resposta"])
            self.assertEqual(ag.historico, [])  # memoria nao ficou poluida

    async def test_tudo_fora_serve_cache_expirado(self):
        cliente_ok = ClienteFalso(self._roteiro_normal())
        async with await self._agente(cliente_ok, cadeia_rapida()) as ag:
            await ag.perguntar("Liste as tabelas existentes")
        CACHE_RESPOSTAS.ttl_s = -1  # tudo expira
        try:
            async with await self._agente(ClienteFalso(lambda m, n: erro_api(503)), cadeia_rapida()) as ag:
                r = await ag.perguntar("Liste as tabelas existentes")
            self.assertEqual(r["meta"]["cache"], "expirado")
            self.assertIn("3 tabelas", r["resposta"])
        finally:
            CACHE_RESPOSTAS.ttl_s = 900

    async def test_sql_repetido_que_falhou_nao_reexecuta(self):
        sql = {"query": "SELECT coluna_inexistente FROM loja"}
        def roteiro(modelo, n):
            return resposta_ferramenta("executar_query_analitica", sql) if n <= 2 else resposta_texto("desisti")
        async with await self._agente(ClienteFalso(roteiro), cadeia_rapida()) as ag:
            r = await ag.perguntar("Teste de loop de sql invalido")
        self.assertFalse(r["trace"][0]["sucesso"])
        self.assertIn("dica", r["trace"][1]["resultado"])  # segunda tentativa recebeu a dica anti-loop
        self.assertLess(r["trace"][1]["tempo_ms"], 50)

    async def test_pergunta_vazia_e_gigante(self):
        async with await self._agente(ClienteFalso(lambda m, n: resposta_texto("x")), cadeia_rapida()) as ag:
            self.assertIn("Escreva", (await ag.perguntar("   "))["resposta"])
            self.assertIn("resuma", (await ag.perguntar("x" * 5000))["resposta"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
