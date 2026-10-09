# Melhorias: cache, cadeia de resiliência e front

## 1. Cache (src/agent/cache.py)
| Camada | Chave | O que evita |
| --- | --- | --- |
| Resposta | pergunta normalizada (sem acento/pontuação/stopwords, palavras ordenadas) | TODAS as chamadas ao LLM |
| Ferramenta | nome + argumentos | reexecutar schema/SQL idênticos entre perguntas diferentes |

- TTL (15 min respostas / 10 min ferramentas), LRU e **invalidação automática** quando o arquivo do banco muda (mtime + tamanho).
- "faturamento de março" ≠ "faturamento de abril" (não usamos similaridade fuzzy de propósito: risco de resposta errada).
- Follow-ups ("e no mês passado?", "isso") **não** usam cache de resposta (dependem do contexto).
- Cache expirado só é servido em modo degradado (LLM fora do ar).
- Próximo passo: cache semântico com embeddings + Redis/SQLite para persistir entre reinícios.

## 2. Cadeia de chamadas (src/agent/resiliencia.py)
```
pergunta -> [validação] -> [cache resposta] -> LLM modelo 1 (timeout, retry + backoff/jitter)
                                             -> LLM modelo 2 (fallback) -> LLM modelo 3
                                             -> [cache expirado] -> mensagem amigável
```
- Semáforo de concorrência (evita rajadas que causam 429) e timeout por tentativa.
- Retry só em erros transitórios (408/429/5xx/timeout); 404 pula para o próximo modelo; 400/401/403 falham rápido.
- Disjuntor (circuit breaker): 3 falhas seguidas => modelo em "molho" por 60 s (visível na sidebar).
- Erros comuns tratados: SQL inválido repetido (anti-loop com dica), falha do MCP vira observação (não derruba o turno),
  resposta vazia, pergunta vazia/gigante, memória do modelo não é poluída quando a pergunta falha.
- Modelos configuráveis: `GEMINI_MODELS="modelo-a,modelo-b,modelo-c"` no .env.

## 3. Front (app.py)
Sugestões de perguntas (as 8 do dicionário), KPI para resultado único, abas Tabela/Gráfico (linha p/ séries temporais,
barras p/ categorias), download CSV, badges por resposta (cache, modelo, fallback, tempo, nº de chamadas),
painel de resiliência, métricas de cache e de sessão, cadeia de modelos com status do disjuntor,
playground do guardrail e perfil de coluna (nulos/distintos). Ferramentas `contar_nulos_e_distintos` e
`amostrar_linhas` agora estão expostas no servidor MCP.

## Testes
`python -m unittest tests.test_resiliencia_cache tests.test_app_streamlit -v` (LLM simulado: não gasta cota).
