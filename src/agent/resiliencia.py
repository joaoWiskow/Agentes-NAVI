"""Cadeia de chamadas ao LLM para sobreviver a alta demanda (429/503) e a erros comuns.

Ordem de defesa em cada chamada:
  1. Semaforo de concorrencia      -> nao disparamos rajadas que provocam 429.
  2. Timeout por tentativa         -> chamada pendurada nao trava o app.
  3. Retry com backoff + jitter    -> 429/500/502/503/504/timeouts sao transitorios.
  4. Fallback para o proximo modelo-> se o modelo primario segue indisponivel.
  5. Disjuntor (circuit breaker)   -> modelo que falhou N vezes seguidas fica "de molho" por um tempo.
  6. ErroAltaDemanda               -> o agente decide: cache expirado ou mensagem amigavel (degradacao graciosa).

Os modelos sao configuraveis por variavel de ambiente: GEMINI_MODELS="modelo-a,modelo-b,modelo-c"
"""

from __future__ import annotations

import asyncio
import os
import random
import time
import weakref
from dataclasses import dataclass, field
from typing import Any

MODELOS_PADRAO = "gemini-3.1-flash-lite,gemini-2.5-flash-lite,gemini-2.5-flash"
CODIGOS_TRANSITORIOS = {408, 429, 500, 502, 503, 504}
NOMES_ERRO_REDE = {"ReadTimeout", "ConnectTimeout", "ConnectError", "RemoteProtocolError", "ReadError", "PoolTimeout"}


def modelos_configurados() -> list[str]:
    bruto = os.getenv("GEMINI_MODELS", MODELOS_PADRAO)
    return [m.strip() for m in bruto.split(",") if m.strip()]


class ErroAltaDemanda(Exception):
    """Todos os modelos da cadeia falharam ou estao com o disjuntor aberto."""

    def __init__(self, mensagem: str, eventos: list[dict]):
        super().__init__(mensagem)
        self.eventos = eventos


def classificar_erro(erro: BaseException) -> str:
    """'retry' (transitorio) | 'proximo_modelo' (este modelo nao serve) | 'fatal' (nao adianta insistir)."""
    if isinstance(erro, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return "retry"
    if type(erro).__name__ in NOMES_ERRO_REDE:
        return "retry"
    codigo = getattr(erro, "code", None)
    if isinstance(codigo, int):
        if codigo in CODIGOS_TRANSITORIOS:
            return "retry"
        if codigo == 404:  # modelo inexistente/descontinuado: tenta o proximo da cadeia
            return "proximo_modelo"
        return "fatal"  # 400/401/403: chave invalida, request malformado... insistir so piora
    return "fatal"


def descrever_erro(erro: BaseException) -> str:
    codigo = getattr(erro, "code", None)
    texto = str(erro).strip().replace("\n", " ")
    return f"{type(erro).__name__}{f' {codigo}' if codigo else ''}: {texto[:140]}"


@dataclass
class Disjuntor:
    falhas_para_abrir: int = 3
    cooldown_s: float = 60.0
    falhas: int = 0
    aberto_ate: float = 0.0

    @property
    def aberto(self) -> bool:
        return time.monotonic() < self.aberto_ate

    def sucesso(self) -> None:
        self.falhas = 0
        self.aberto_ate = 0.0

    def falha(self) -> None:
        self.falhas += 1
        if self.falhas >= self.falhas_para_abrir:
            self.aberto_ate = time.monotonic() + self.cooldown_s
            self.falhas = 0

    @property
    def segundos_restantes(self) -> int:
        return max(0, int(self.aberto_ate - time.monotonic()))


@dataclass
class ResultadoChamada:
    resposta: Any
    modelo: str
    tentativas: int
    fallback: bool
    eventos: list[dict] = field(default_factory=list)


class CadeiaModelos:
    def __init__(
        self,
        modelos: list[str] | None = None,
        tentativas_por_modelo: int = 2,
        espera_base_s: float = 1.0,
        espera_max_s: float = 8.0,
        timeout_s: float = 45.0,
        max_concorrencia: int = 3,
        falhas_para_abrir: int = 3,
        cooldown_s: float = 60.0,
    ):
        self.modelos = modelos or modelos_configurados()
        self.tentativas_por_modelo = tentativas_por_modelo
        self.espera_base_s = espera_base_s
        self.espera_max_s = espera_max_s
        self.timeout_s = timeout_s
        self.max_concorrencia = max_concorrencia
        self.disjuntores = {m: Disjuntor(falhas_para_abrir, cooldown_s) for m in self.modelos}
        # asyncio.Semaphore pertence a um event loop; o Streamlit cria um loop novo por pergunta.
        self._semaforos: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
            weakref.WeakKeyDictionary()
        )

    def _semaforo(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if loop not in self._semaforos:
            self._semaforos[loop] = asyncio.Semaphore(self.max_concorrencia)
        return self._semaforos[loop]

    def _espera(self, tentativa: int) -> float:
        """Backoff exponencial com jitter: 1s, 2s, 4s... (teto espera_max_s), +- 25%."""
        base = min(self.espera_max_s, self.espera_base_s * (2 ** (tentativa - 1)))
        return base * random.uniform(0.75, 1.25)

    def estado(self) -> list[dict]:
        """Usado pela sidebar do Streamlit."""
        return [
            {"modelo": m, "estado": "aberto" if d.aberto else "ok", "retoma_em_s": d.segundos_restantes, "falhas": d.falhas}
            for m, d in self.disjuntores.items()
        ]

    def resetar(self) -> None:
        for d in self.disjuntores.values():
            d.sucesso()

    async def gerar(self, client, contents, config) -> ResultadoChamada:
        eventos: list[dict] = []
        total_tentativas = 0

        for indice, modelo in enumerate(self.modelos):
            disjuntor = self.disjuntores[modelo]
            if disjuntor.aberto:
                eventos.append({"modelo": modelo, "tipo": "disjuntor_aberto", "detalhe": f"pulado ({disjuntor.segundos_restantes}s)"})
                continue

            for tentativa in range(1, self.tentativas_por_modelo + 1):
                total_tentativas += 1
                try:
                    async with self._semaforo():
                        resposta = await asyncio.wait_for(
                            client.aio.models.generate_content(model=modelo, contents=contents, config=config),
                            timeout=self.timeout_s,
                        )
                    if not (resposta.candidates and resposta.candidates[0].content):
                        # resposta vazia/bloqueada pelo modelo: tratamos como transitoria
                        raise TimeoutError("resposta vazia do modelo")
                    disjuntor.sucesso()
                    return ResultadoChamada(resposta, modelo, total_tentativas, indice > 0, eventos)
                except Exception as erro:  # noqa: BLE001 - classificamos abaixo
                    tipo = classificar_erro(erro)
                    eventos.append({"modelo": modelo, "tipo": tipo, "tentativa": tentativa, "detalhe": descrever_erro(erro)})
                    if tipo == "fatal":
                        raise
                    if tipo == "proximo_modelo":
                        break
                    disjuntor.falha()
                    if disjuntor.aberto or tentativa == self.tentativas_por_modelo:
                        break
                    await asyncio.sleep(self._espera(tentativa))

        raise ErroAltaDemanda("Todos os modelos da cadeia estao indisponiveis no momento.", eventos)


# Singleton de processo: o estado dos disjuntores precisa sobreviver entre perguntas.
_CADEIA: CadeiaModelos | None = None


def obter_cadeia() -> CadeiaModelos:
    global _CADEIA
    if _CADEIA is None:
        _CADEIA = CadeiaModelos()
    return _CADEIA
