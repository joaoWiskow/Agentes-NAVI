"""Cache em memoria para perguntas repetidas e chamadas de ferramentas.

Duas camadas:
  1. CACHE_RESPOSTAS  -> pergunta (normalizada) -> resposta final + trace. Evita TODAS as chamadas ao LLM.
  2. CACHE_FERRAMENTAS -> (ferramenta + argumentos) -> resultado MCP. Evita reexecutar schema/SQL iguais.

Regras de seguranca do cache:
  - A chave inclui a "versao" do banco (mtime + tamanho do arquivo): se os dados mudarem, o cache invalida sozinho.
  - Cada entrada tem TTL. Entradas expiradas so sao servidas em modo degradado (LLM fora do ar).
  - A chave da pergunta e um "saco de palavras significativas": "Qual o faturamento total?" e
    "faturamento total, qual e?" batem; "faturamento de marco" e "faturamento de abril" NAO batem.
"""

from __future__ import annotations

import copy
import json
import re
import threading
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from src.database.init_db import CAMINHO_DB

# Palavras que nao mudam o sentido da pergunta. NUNCA entram: numeros, meses, nomes de loja/coluna.
STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "e", "ou", "que", "qual", "quais", "quanto", "quantos", "quantas", "quanta", "me", "mostre", "mostra",
    "liste", "listar", "diga", "dizer", "por", "favor", "pode", "poderia", "para", "pra", "eh", "ao", "aos",
    "sao", "foi", "foram", "tem", "ha", "existem", "existe", "voce", "gostaria", "saber", "quero",
}

# Perguntas que dependem da conversa anterior nao podem ser reaproveitadas fora de contexto.
MARCADORES_FOLLOWUP = re.compile(
    r"\b(isso|isto|essa|esse|esses|essas|ela|ele|elas|eles|anterior|mesma|mesmo|mesmos|mesmas|acima|"
    r"tambem|ainda|agora|entao)\b|^\s*e\s",
    flags=re.IGNORECASE,
)


def normalizar_pergunta(pergunta: str) -> str:
    """Minusculas, sem acento, sem pontuacao, sem stopwords, palavras ordenadas e unicas."""
    sem_acento = unicodedata.normalize("NFKD", pergunta).encode("ascii", "ignore").decode("ascii")
    palavras = re.findall(r"[a-z0-9_]+", sem_acento.lower())
    significativas = sorted({p for p in palavras if p not in STOPWORDS})
    return " ".join(significativas)


def parece_followup(pergunta: str) -> bool:
    sem_acento = unicodedata.normalize("NFKD", pergunta).encode("ascii", "ignore").decode("ascii")
    return bool(MARCADORES_FOLLOWUP.search(sem_acento))


def versao_do_banco() -> str:
    try:
        info = CAMINHO_DB.stat()
        return f"{info.st_mtime_ns}-{info.st_size}"
    except OSError:
        return "sem-banco"


@dataclass
class _Entrada:
    valor: Any
    criado_em: float
    versao_db: str


@dataclass
class EstatisticasCache:
    acertos: int = 0
    falhas: int = 0
    acertos_expirados: int = 0  # servidos em modo degradado
    gravacoes: int = 0
    historico: list = field(default_factory=list)

    @property
    def taxa_acerto(self) -> float:
        total = self.acertos + self.falhas
        return round(self.acertos / total * 100, 1) if total else 0.0


class CacheTTL:
    """LRU com TTL, thread-safe, que invalida quando a versao do banco muda."""

    def __init__(self, nome: str, ttl_s: float = 900, max_itens: int = 128):
        self.nome = nome
        self.ttl_s = ttl_s
        self.max_itens = max_itens
        self._dados: OrderedDict[str, _Entrada] = OrderedDict()
        self._lock = threading.Lock()
        self.stats = EstatisticasCache()

    def buscar(self, chave: str, aceitar_expirado: bool = False) -> tuple[Any, str] | None:
        """Retorna (valor, situacao) com situacao in {"fresco", "expirado"} ou None."""
        agora = time.time()
        with self._lock:
            entrada = self._dados.get(chave)
            if entrada is None or entrada.versao_db != versao_do_banco():
                if entrada is not None:  # dados mudaram: a entrada e invalida de verdade
                    del self._dados[chave]
                self.stats.falhas += 1
                return None
            fresco = (agora - entrada.criado_em) <= self.ttl_s
            if fresco:
                self._dados.move_to_end(chave)
                self.stats.acertos += 1
                return copy.deepcopy(entrada.valor), "fresco"
            if aceitar_expirado:
                self.stats.acertos_expirados += 1
                return copy.deepcopy(entrada.valor), "expirado"
            self.stats.falhas += 1
            return None

    def guardar(self, chave: str, valor: Any) -> None:
        with self._lock:
            self._dados[chave] = _Entrada(copy.deepcopy(valor), time.time(), versao_do_banco())
            self._dados.move_to_end(chave)
            while len(self._dados) > self.max_itens:
                self._dados.popitem(last=False)
            self.stats.gravacoes += 1

    def limpar(self) -> None:
        with self._lock:
            self._dados.clear()
            self.stats = EstatisticasCache()

    def __len__(self) -> int:
        return len(self._dados)


# ---------- singletons de processo (o Streamlit recria o agente a cada pergunta, o cache sobrevive) ----------
CACHE_RESPOSTAS = CacheTTL("respostas", ttl_s=900, max_itens=128)
CACHE_FERRAMENTAS = CacheTTL("ferramentas", ttl_s=600, max_itens=256)

# Ferramentas deterministicas sobre um banco somente leitura: seguras para cachear.
FERRAMENTAS_CACHEAVEIS = {
    "listar_tabelas",
    "descrever_schema",
    "obter_relacionamentos",
    "executar_query_analitica",
    "calcular_estatisticas_coluna",
    "contar_nulos_e_distintos",
    "amostrar_linhas",
}


def chave_ferramenta(nome: str, argumentos: dict) -> str:
    args = {k: (re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v) for k, v in dict(argumentos).items()}
    return f"{nome}:{json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)}"


def limpar_tudo() -> None:
    CACHE_RESPOSTAS.limpar()
    CACHE_FERRAMENTAS.limpar()


if __name__ == "__main__":
    for p in ["Qual o faturamento total de março?", "faturamento TOTAL, março: qual é?", "Qual o faturamento total de abril?"]:
        print(f"{normalizar_pergunta(p)!r:45} <- {p}")
