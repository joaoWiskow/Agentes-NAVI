import asyncio
import sqlite3
import pandas as pd
import streamlit as st
from src.agent.cache import CACHE_FERRAMENTAS, CACHE_RESPOSTAS, limpar_tudo
from src.agent.dataops_agent import DataOpsAgent
from src.agent.guardrails import validar_query_segura
from src.agent.resiliencia import obter_cadeia
from src.database.init_db import CAMINHO_DB

st.set_page_config(
    page_title="DataOps Agent | Shopping",
    page_icon="",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Perguntas sugeridas

# ---------------------------------------------------------------------------
SUGESTOES = [
    (
        "Faturamento mensal",
        "Qual é o faturamento total de todas as lojas somadas em cada mês?",
    ),
    (
        "Top 3 lojas",
        "Quais são as 3 lojas com maior rendimento total? "
        "Mostre o nome da loja e o valor.",
    ),
    (
        "Contratos a vencer",
        "Quais contratos de locação vencem nos próximos 30 dias?",
    ),
    (
        "Inconsistências operacionais",
        "Quais lojas estão com contratos em negociação ou encerrados, "
        "mas continuam operando?",
    ),
]

# ---------------------------------------------------------------------------
# Estado e agente

# ---------------------------------------------------------------------------

def inicializar_estado() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("historico_llm", [])
    st.session_state.setdefault("usar_cache", True)
    st.session_state.setdefault(
        "sessao",
        {
            "perguntas": 0,
            "do_cache": 0,
            "chamadas_llm": 0,
            "fallbacks": 0,
            "tempo_ms": 0.0,
        },
    )


async def _consultar(
    pergunta: str,
    historico_llm: list,
    usar_cache: bool,
) -> dict:
    async with DataOpsAgent(
        historico=historico_llm,
        usar_cache=usar_cache,
    ) as agente:
        return await agente.perguntar(pergunta)


def perguntar_ao_agente(pergunta: str) -> dict:
    """Abre o agente e o servidor MCP para executar uma consulta."""
    return asyncio.run(
        _consultar(
            pergunta,
            st.session_state.historico_llm,
            st.session_state.usar_cache,
        )
    )


def registrar_sessao(meta: dict) -> None:
    s = st.session_state.sessao
    s["perguntas"] += 1
    s["do_cache"] += 1 if meta.get("cache") else 0
    s["chamadas_llm"] += meta.get("chamadas_llm", 0)
    s["fallbacks"] += 1 if meta.get("fallback") else 0
    s["tempo_ms"] += meta.get("tempo_total_ms", 0.0)


def definir_pendente(texto: str) -> None:
    st.session_state.pendente = texto


# ---------------------------------------------------------------------------
# Formatação

# ---------------------------------------------------------------------------

def fmt_br(valor) -> str:
    if isinstance(valor, float) or (
        isinstance(valor, int) and abs(valor) >= 1000
    ):
        texto = (
            f"{valor:,.2f}"
            if isinstance(valor, float)
            else f"{valor:,}"
        )
        return texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return str(valor)


def linha_de_badges(meta: dict) -> str:
    if not meta:
        return ""
    partes = []
    if meta.get("cache") == "resposta":
        partes.append("**resposta do cache** (0 chamadas ao LLM)")
    elif meta.get("cache") == "expirado":
        partes.append("**cache expirado** (modo degradado)")
    elif meta.get("modelo"):
        partes.append(f"`{meta['modelo']}`")
    if meta.get("fallback"):
        partes.append("**fallback de modelo**")
    if meta.get("chamadas_llm"):
        partes.append(
            f"{meta['chamadas_llm']} chamada(s) ao LLM"
        )
    if meta.get("tentativas", 0) > meta.get("chamadas_llm", 0):
        partes.append(
            f"{meta['tentativas'] - meta['chamadas_llm']} retentativa(s)"
        )
    partes.append(f"{meta.get('tempo_total_ms', 0) / 1000:.2f} s")
    return " · ".join(partes)


# ---------------------------------------------------------------------------
# Renderização dos resultados

# ---------------------------------------------------------------------------

def _coluna_temporal(df: pd.DataFrame) -> str | None:
    for coluna in df.columns:
        if (
            df[coluna].dtype == object
            and df[coluna]
            .astype(str)
            .str.match(r"^\d{4}-\d{2}(-\d{2})?$")
            .all()
        ):
            return coluna
    return None


def desenhar_grafico(df: pd.DataFrame) -> bool:
    """Desenha linhas temporais ou barras para dados categóricos."""
    numericas = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c])
    ]
    if not numericas or len(df) < 2:
        return False
    temporal = _coluna_temporal(df)
    if temporal:
        st.line_chart(
            df.sort_values(temporal).set_index(temporal)[numericas[:3]]
        )
        return True
    categoricas = [c for c in df.columns if c not in numericas]
    if len(categoricas) == 1 and len(df) <= 30:
        st.bar_chart(
            df,
            x=categoricas[0],
            y=numericas[:3],
        )
        return True
    return False


def renderizar_dados(trace: list[dict], chave: str) -> None:
    """Exibe os dados da última consulta analítica bem-sucedida."""
    perfis = [
        p for p in trace
        if p["ferramenta"] == "contar_nulos_e_distintos"
        and p["sucesso"]
        and isinstance(p["resultado"], dict)
    ]
    if perfis:
        r = perfis[-1]["resultado"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Linhas", fmt_br(r["total_linhas"]))
        c2.metric("Nulos", fmt_br(r["nulos"]))
        c3.metric("Distintos", fmt_br(r["distintos"]))
        c4.metric("Preenchido", f"{r['percentual_preenchido']}%")
    consultas = [
        p for p in trace
        if p["ferramenta"] == "executar_query_analitica"
        and p["sucesso"]
        and isinstance(p["resultado"], dict)
    ]
    if not consultas:
        return
    resultado = consultas[-1]["resultado"]
    df = pd.DataFrame(resultado.get("linhas", []))
    if df.empty:
        st.info("A consulta foi executada, mas não retornou linhas.")
        return
    if df.shape == (1, 1):
        st.metric(df.columns[0], fmt_br(df.iat[0, 0]))
    else:
        tem_grafico = (
            len(df) > 1
            and any(
                pd.api.types.is_numeric_dtype(df[c])
                for c in df.columns
            )
        )
        if tem_grafico:
            aba_tabela, aba_grafico = st.tabs(
                ["Tabela", "Gráfico"]
            )
            with aba_tabela:
                st.dataframe(df, width="stretch")
            with aba_grafico:
                if not desenhar_grafico(df):
                    st.caption(
                        "Sem gráfico adequado para este formato de resultado."
                    )
        else:
            st.dataframe(df, width="stretch")
    esquerda, direita = st.columns([1, 4])
    esquerda.download_button(
        "Baixar CSV",
        df.to_csv(index=False).encode("utf-8"),
        "resultado.csv",
        "text/csv",
        key=f"csv_{chave}",
    )
    direita.caption(
        f"{len(df)} linha(s) · "
        f"consulta em {resultado.get('tempo_ms', '?')} ms"
    )


def renderizar_trace(trace: list[dict], chave: str) -> None:
    with st.expander(
        f"Rastro de ferramentas ({len(trace)} chamadas)",
        expanded=False,
    ):
        for i, passo in enumerate(trace):
            selo = "OK" if passo["sucesso"] else "ERRO"
            cache = " · cache" if passo.get("cache") else ""
            st.markdown(
                f"{selo} **Turno {passo['turno']}: "
                f"`{passo['ferramenta']}`** · "
                f"{passo['tempo_ms']} ms{cache}"
            )
            if passo["argumentos"] and not passo.get("query_sql"):
                st.json(passo["argumentos"], expanded=False)
            guardrail = passo.get("guardrail")
            if guardrail is not None:
                if guardrail["aprovada"]:
                    st.success("Aprovado pelo guardrail")
                else:
                    st.error(
                        f"Bloqueado pelo guardrail: {guardrail['motivo']}"
                    )
            if passo.get("query_sql"):
                st.code(passo["query_sql"], language="sql")
            if not passo["sucesso"]:
                resultado = passo["resultado"]
                erro = (
                    resultado.get("erro")
                    if isinstance(resultado, dict)
                    else resultado
                )
                st.warning(f"A ferramenta retornou erro: {erro}")
                if isinstance(resultado, dict) and resultado.get("dica"):
                    st.info(f"💡 Anti-loop: {resultado['dica']}")
            if i < len(trace) - 1:
                st.divider()


def renderizar_eventos(meta: dict) -> None:
    eventos = meta.get("eventos") or []
    if not eventos:
        return
    with st.expander(
        f"Resiliência: {len(eventos)} evento(s) tratado(s)",
        expanded=False,
    ):
        st.dataframe(
            pd.DataFrame(eventos),
            width="stretch",
            hide_index=True,
        )


def renderizar_mensagem(mensagem: dict, indice: int) -> None:
    with st.chat_message(mensagem["role"]):
        meta = mensagem.get("meta") or {}
        if meta.get("degradado") and not meta.get("cache"):
            st.warning("Modo degradado: o serviço de IA está instável.")
        st.markdown(mensagem["content"])
        if mensagem["role"] == "assistant":
            if mensagem.get("trace"):
                renderizar_dados(mensagem["trace"], str(indice))
                renderizar_trace(mensagem["trace"], str(indice))
            renderizar_eventos(meta)
            if meta:
                st.caption(linha_de_badges(meta))


# ---------------------------------------------------------------------------
# Sidebar: métricas e configurações

# ---------------------------------------------------------------------------

def metricas_do_banco() -> dict:
    """Lê os metadados do banco sem alterar seus dados."""
    if not CAMINHO_DB.exists():
        return {
            "status": "ausente",
            "tabelas": 0,
            "registros": 0,
        }
    with sqlite3.connect(f"file:{CAMINHO_DB}?mode=ro", uri=True) as conexao:
        tabelas = [
            linha[0]
            for linha in conexao.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                """
            )
        ]
        registros = sum(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in tabelas
        )
    return {
        "status": "conectado",
        "tabelas": len(tabelas),
        "registros": registros,
    }


def renderizar_sidebar() -> None:
    sb = st.sidebar
    # Sugestões disponíveis durante toda a conversa (sempre visíveis).
    sb.markdown("**Sugestões de perguntas**")
    for i, (rotulo, texto) in enumerate(SUGESTOES):
        sb.button(
            rotulo,
            key=f"sug_sidebar_{i}",
            on_click=definir_pendente,
            args=(texto,),
            width="stretch",
        )
    # Saúde da base: permanece sempre visível.
    # Saúde da base: gaveta recolhida por padrão.
    with sb.expander("Saúde da base", expanded=False):
        m = metricas_do_banco()
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Status",
            "Conectado" if m["status"] == "conectado" else "Ausente",
            help=m["status"],
        )
        c2.metric("Tabelas", m["tabelas"])
        c3.metric("Registros", fmt_br(m["registros"]))

    # Cache: recolhido por padrão.
    with sb.expander("Cache", expanded=False):
        st.session_state.usar_cache = st.toggle(
            "Usar cache",
            value=st.session_state.usar_cache,
            help="Reaproveita respostas e consultas repetidas.",
        )
        est = CACHE_RESPOSTAS.stats
        s = st.session_state.sessao
        a, b = st.columns(2)
        a.metric("Taxa de acerto", f"{est.taxa_acerto}%")
        b.metric(
            "Itens",
            f"{len(CACHE_RESPOSTAS)} / {len(CACHE_FERRAMENTAS)}",
            help="Respostas / ferramentas",
        )
        st.caption(
            f"Sessão: {s['perguntas']} pergunta(s) · "
            f"{s['do_cache']} do cache · "
            f"{s['chamadas_llm']} chamada(s) ao LLM"
        )
        if st.button("Limpar cache", width="stretch"):
            limpar_tudo()
            st.rerun()
    # Cadeia de modelos: recolhida por padrão.
    with sb.expander("Cadeia de modelos", expanded=False):
        s = st.session_state.sessao
        for item in obter_cadeia().estado():
            icone = "OK" if item["estado"] == "ok" else "ERRO"
            extra = (
                f" (retoma em {item['retoma_em_s']}s)"
                if item["estado"] == "aberto"
                else ""
            )
            st.markdown(f"{icone} `{item['modelo']}`{extra}")
        st.caption(f"Fallbacks nesta sessão: {s['fallbacks']}")
        if st.button("Resetar disjuntores", width="stretch"):
            obter_cadeia().resetar()
            st.rerun()
    # Guardrail: recolhido por padrão.
    with sb.expander("Testar guardrail", expanded=False):
        sql = st.text_area(
            "SQL",
            value="SELECT * FROM loja; DROP TABLE loja",
            height=80,
            key="sql_teste",
        )
        if st.button("Validar", key="btn_validar"):
            aprovada, motivo = validar_query_segura(sql)
            resultado = "Aprovada: " if aprovada else "Bloqueada: "
            (st.success if aprovada else st.error)(resultado + motivo)
    # Ação da conversa, mantida separada dos diagnósticos.
    if sb.button("Limpar conversa", width="stretch"):
        st.session_state.messages = []
        st.session_state.historico_llm = []
        st.rerun()


# ---------------------------------------------------------------------------
# Página principal

# ---------------------------------------------------------------------------

def main() -> None:
    st.title("DataOps Agent")
    st.caption(
        "Auditoria de dados de um shopping center: somente leitura, "
        "com guardrails, cache e rastreabilidade de cada ferramenta."
    )
    inicializar_estado()
    renderizar_sidebar()
    for indice, mensagem in enumerate(st.session_state.messages):
        renderizar_mensagem(mensagem, indice)
    pergunta = (
        st.chat_input("Pergunte algo sobre os dados...")
        or st.session_state.pop("pendente", None)
    )
    if not pergunta:
        return
    st.session_state.messages.append(
        {"role": "user", "content": pergunta}
    )
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.spinner("Consultando o agente..."):
        try:
            saida = perguntar_ao_agente(pergunta)
            resposta = {
                "role": "assistant",
                "content": saida["resposta"],
                "trace": saida["trace"],
                "meta": saida.get("meta", {}),
            }
        except Exception as erro:  # noqa: BLE001
            resposta = {
                "role": "assistant",
                "content": f"Não consegui concluir: {erro}",
                "trace": [],
                "meta": {"degradado": True},
            }
    st.session_state.messages.append(resposta)
    registrar_sessao(resposta["meta"])
    st.rerun()

if __name__ == "__main__":
    main()
