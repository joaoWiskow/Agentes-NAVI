import asyncio
import sqlite3

import pandas as pd
import streamlit as st

from src.agent.cache import CACHE_FERRAMENTAS, CACHE_RESPOSTAS, limpar_tudo
from src.agent.dataops_agent import DataOpsAgent
from src.agent.guardrails import validar_query_segura
from src.agent.resiliencia import obter_cadeia
from src.database.init_db import CAMINHO_DB

st.set_page_config(page_title="DataOps Agent | Shopping", page_icon="🛍️", layout="wide")

# Perguntas de negocio do dicionario de dados (docs/dicionario_dados.md)
SUGESTOES = [
    ("💰 Faturamento por mês", "Qual é o faturamento total de todas as lojas somadas em cada mês?"),
    ("📄 Contratos a vencer", "Quais contratos de locação vencem nos próximos 30 dias?"),
    ("🏆 Top 3 lojas", "Quais são as 3 lojas com maior rendimento total? Mostre o nome da loja e o valor."),
    ("⚠️ Contrato encerrado, loja ativa", "Quais lojas estão com contratos em negociação ou encerrados, mas continuam operando?"),
    ("🧾 Custo médio por categoria", "Qual é a média de custos operacionais diários agrupados por categoria de loja?"),
    ("📉 Queda de rendimento", "Quais lojas registraram queda consecutiva no rendimento nos últimos meses?"),
    ("🏬 Categorias mais presentes", "Qual é o ranking das categorias de lojas mais presentes no shopping?"),
    ("🧪 Qualidade: documento_url", "Quantos registros nulos existem na coluna documento_url da tabela contrato?"),
]


# ----------------------------------------------------------------------------- estado e agente
def inicializar_estado() -> None:
    st.session_state.setdefault("messages", [])      # o que aparece na tela: {"role", "content", "trace", "meta"}
    st.session_state.setdefault("historico_llm", [])  # a memoria do modelo (types.Content)
    st.session_state.setdefault("usar_cache", True)
    st.session_state.setdefault("sessao", {"perguntas": 0, "do_cache": 0, "chamadas_llm": 0, "fallbacks": 0, "tempo_ms": 0.0})


async def _consultar(pergunta: str, historico_llm: list, usar_cache: bool) -> dict:
    async with DataOpsAgent(historico=historico_llm, usar_cache=usar_cache) as agente:
        return await agente.perguntar(pergunta)


def perguntar_ao_agente(pergunta: str) -> dict:
    """O Streamlit e sincrono: abrimos o agente (e o servidor MCP) a cada pergunta e fechamos ao final."""
    return asyncio.run(_consultar(pergunta, st.session_state.historico_llm, st.session_state.usar_cache))


def registrar_sessao(meta: dict) -> None:
    s = st.session_state.sessao
    s["perguntas"] += 1
    s["do_cache"] += 1 if meta.get("cache") else 0
    s["chamadas_llm"] += meta.get("chamadas_llm", 0)
    s["fallbacks"] += 1 if meta.get("fallback") else 0
    s["tempo_ms"] += meta.get("tempo_total_ms", 0.0)


def definir_pendente(texto: str) -> None:
    st.session_state.pendente = texto


# ----------------------------------------------------------------------------- formatacao
def fmt_br(valor) -> str:
    if isinstance(valor, float) or (isinstance(valor, int) and abs(valor) >= 1000):
        texto = f"{valor:,.2f}" if isinstance(valor, float) else f"{valor:,}"
        return texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return str(valor)


def linha_de_badges(meta: dict) -> str:
    if not meta:
        return ""
    partes = []
    if meta.get("cache") == "resposta":
        partes.append("⚡ **resposta do cache** (0 chamadas ao LLM)")
    elif meta.get("cache") == "expirado":
        partes.append("🕓 **cache expirado** (modo degradado)")
    elif meta.get("modelo"):
        partes.append(f"🤖 `{meta['modelo']}`")
    if meta.get("fallback"):
        partes.append("🔁 **fallback de modelo**")
    if meta.get("chamadas_llm"):
        partes.append(f"📞 {meta['chamadas_llm']} chamada(s) ao LLM")
    if meta.get("tentativas", 0) > meta.get("chamadas_llm", 0):
        partes.append(f"♻️ {meta['tentativas'] - meta['chamadas_llm']} retentativa(s)")
    partes.append(f"⏱ {meta.get('tempo_total_ms', 0) / 1000:.2f} s")
    return " · ".join(partes)


# ----------------------------------------------------------------------------- renderizacao do resultado
def _coluna_temporal(df: pd.DataFrame) -> str | None:
    for coluna in df.columns:
        if df[coluna].dtype == object and df[coluna].astype(str).str.match(r"^\d{4}-\d{2}(-\d{2})?$").all():
            return coluna
    return None


def desenhar_grafico(df: pd.DataFrame) -> bool:
    """Linha para series temporais; barras para 1 coluna categorica + numericas. Retorna True se desenhou."""
    numericas = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numericas or len(df) < 2:
        return False
    temporal = _coluna_temporal(df)
    if temporal:
        st.line_chart(df.sort_values(temporal).set_index(temporal)[numericas[:3]])
        return True
    categoricas = [c for c in df.columns if c not in numericas]
    if len(categoricas) == 1 and len(df) <= 30:
        st.bar_chart(df, x=categoricas[0], y=numericas[:3])
        return True
    return False


def renderizar_dados(trace: list[dict], chave: str) -> None:
    """Mostra o resultado da ULTIMA consulta analitica bem-sucedida (ou o perfil de uma coluna)."""
    perfis = [p for p in trace if p["ferramenta"] == "contar_nulos_e_distintos" and p["sucesso"] and isinstance(p["resultado"], dict)]
    if perfis:
        r = perfis[-1]["resultado"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Linhas", fmt_br(r["total_linhas"]))
        c2.metric("Nulos", fmt_br(r["nulos"]))
        c3.metric("Distintos", fmt_br(r["distintos"]))
        c4.metric("Preenchido", f"{r['percentual_preenchido']}%")

    consultas = [p for p in trace if p["ferramenta"] == "executar_query_analitica" and p["sucesso"] and isinstance(p["resultado"], dict)]
    if not consultas:
        return
    resultado = consultas[-1]["resultado"]
    df = pd.DataFrame(resultado.get("linhas", []))
    if df.empty:
        st.info("A consulta foi executada, mas não retornou linhas.")
        return

    if df.shape == (1, 1):  # um unico numero: KPI
        st.metric(df.columns[0], fmt_br(df.iat[0, 0]))
    else:
        tem_grafico = len(df) > 1 and any(pd.api.types.is_numeric_dtype(df[c]) for c in df.columns)
        if tem_grafico:
            aba_tabela, aba_grafico = st.tabs(["📋 Tabela", "📊 Gráfico"])
            with aba_tabela:
                st.dataframe(df, width="stretch")
            with aba_grafico:
                if not desenhar_grafico(df):
                    st.caption("Sem gráfico adequado para este formato de resultado.")
        else:
            st.dataframe(df, width="stretch")

    esquerda, direita = st.columns([1, 4])
    esquerda.download_button("⬇️ Baixar CSV", df.to_csv(index=False).encode("utf-8"), "resultado.csv", "text/csv", key=f"csv_{chave}")
    direita.caption(f"{len(df)} linha(s) · consulta em {resultado.get('tempo_ms', '?')} ms")


def renderizar_trace(trace: list[dict], chave: str) -> None:
    with st.expander(f"🔎 Rastro de ferramentas ({len(trace)} chamadas)", expanded=False):
        for i, passo in enumerate(trace):
            selo = "✅" if passo["sucesso"] else "❌"
            cache = " · ⚡ cache" if passo.get("cache") else ""
            st.markdown(f"{selo} **Turno {passo['turno']}: `{passo['ferramenta']}`** · {passo['tempo_ms']} ms{cache}")
            if passo["argumentos"] and not passo.get("query_sql"):
                st.json(passo["argumentos"], expanded=False)
            guardrail = passo.get("guardrail")
            if guardrail is not None:
                if guardrail["aprovada"]:
                    st.success("Aprovado pelo guardrail")
                else:
                    st.error(f"Bloqueado pelo guardrail: {guardrail['motivo']}")
            if passo.get("query_sql"):
                st.code(passo["query_sql"], language="sql")
            if not passo["sucesso"]:
                resultado = passo["resultado"]
                erro = resultado.get("erro") if isinstance(resultado, dict) else resultado
                st.warning(f"A ferramenta retornou erro: {erro}")
                if isinstance(resultado, dict) and resultado.get("dica"):
                    st.info(f"💡 Anti-loop: {resultado['dica']}")
            if i < len(trace) - 1:
                st.divider()


def renderizar_eventos(meta: dict) -> None:
    eventos = meta.get("eventos") or []
    if not eventos:
        return
    with st.expander(f"🛡️ Resiliência: {len(eventos)} evento(s) tratado(s)", expanded=False):
        st.dataframe(pd.DataFrame(eventos), width="stretch", hide_index=True)


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


# ----------------------------------------------------------------------------- sidebar
def metricas_do_banco() -> dict:
    """Le metadados do banco sem alterar nada (modo read-only)."""
    if not CAMINHO_DB.exists():
        return {"status": "ausente", "tabelas": 0, "registros": 0}
    with sqlite3.connect(f"file:{CAMINHO_DB}?mode=ro", uri=True) as conexao:
        tabelas = [l[0] for l in conexao.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        registros = sum(conexao.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabelas)
    return {"status": "conectado", "tabelas": len(tabelas), "registros": registros}


def renderizar_sidebar() -> None:
    sb = st.sidebar
    m = metricas_do_banco()
    sb.header("🗄️ Saúde da base")
    c1, c2, c3 = sb.columns(3)
    c1.metric("Status", "🟢" if m["status"] == "conectado" else "🔴", help=m["status"])
    c2.metric("Tabelas", m["tabelas"])
    c3.metric("Registros", fmt_br(m["registros"]))

    sb.divider()
    sb.header("⚡ Cache")
    st.session_state.usar_cache = sb.toggle("Usar cache", value=st.session_state.usar_cache, help="Reaproveita respostas e consultas repetidas.")
    est = CACHE_RESPOSTAS.stats
    s = st.session_state.sessao
    a, b = sb.columns(2)
    a.metric("Taxa de acerto", f"{est.taxa_acerto}%")
    b.metric("Itens", f"{len(CACHE_RESPOSTAS)} / {len(CACHE_FERRAMENTAS)}", help="respostas / ferramentas")
    sb.caption(f"Sessão: {s['perguntas']} pergunta(s) · {s['do_cache']} do cache · {s['chamadas_llm']} chamada(s) ao LLM")
    if sb.button("Limpar cache", width="stretch"):
        limpar_tudo()
        st.rerun()

    sb.divider()
    sb.header("🛡️ Cadeia de modelos")
    for item in obter_cadeia().estado():
        icone = "🟢" if item["estado"] == "ok" else "🔴"
        extra = f" (retoma em {item['retoma_em_s']}s)" if item["estado"] == "aberto" else ""
        sb.markdown(f"{icone} `{item['modelo']}`{extra}")
    sb.caption(f"Fallbacks nesta sessão: {s['fallbacks']}")
    if sb.button("Resetar disjuntores", width="stretch"):
        obter_cadeia().resetar()
        st.rerun()

    sb.divider()
    with sb.expander("🧪 Testar guardrail"):
        sql = st.text_area("SQL", value="SELECT * FROM loja; DROP TABLE loja", height=80, key="sql_teste")
        if st.button("Validar", key="btn_validar"):
            aprovada, motivo = validar_query_segura(sql)
            (st.success if aprovada else st.error)(("Aprovada: " if aprovada else "Bloqueada: ") + motivo)

    if sb.button("🧹 Limpar conversa", width="stretch"):
        st.session_state.messages = []
        st.session_state.historico_llm = []
        st.rerun()


# ----------------------------------------------------------------------------- pagina
def renderizar_boas_vindas() -> None:
    st.markdown("#### Pergunte sobre lojas, contratos e movimentação financeira — ou comece por uma sugestão:")
    colunas = st.columns(2)
    for i, (rotulo, texto) in enumerate(SUGESTOES):
        colunas[i % 2].button(rotulo, key=f"sug_{i}", on_click=definir_pendente, args=(texto,), width="stretch")


def main() -> None:
    st.title("🛍️ DataOps Agent")
    st.caption("Auditoria de dados de um shopping center: somente leitura, com guardrails, cache e rastreabilidade de cada ferramenta.")
    inicializar_estado()
    renderizar_sidebar()

    if not st.session_state.messages:
        renderizar_boas_vindas()
    for indice, mensagem in enumerate(st.session_state.messages):
        renderizar_mensagem(mensagem, indice)

    pergunta = st.chat_input("Pergunte algo sobre os dados...") or st.session_state.pop("pendente", None)
    if not pergunta:
        return

    st.session_state.messages.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.spinner("Consultando o agente..."):
        try:
            saida = perguntar_ao_agente(pergunta)
            resposta = {"role": "assistant", "content": saida["resposta"], "trace": saida["trace"], "meta": saida.get("meta", {})}
        except Exception as erro:  # noqa: BLE001
            resposta = {"role": "assistant", "content": f"Não consegui concluir: {erro}", "trace": [], "meta": {"degradado": True}}
    st.session_state.messages.append(resposta)
    registrar_sessao(resposta["meta"])
    st.rerun()  # redesenha tudo (inclusive a sidebar) com as metricas atualizadas


main()
