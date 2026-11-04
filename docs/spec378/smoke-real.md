# SPEC-378 — smoke real (§6), 04/11/2026

Comando (perfil `legacy`, `ROUTES` default, chave lida só por nome de variável):
`playtest run --profile explorador --turns 4 --seed 0 --real --max-cost 0.10 --max-requests 25`

| Medida | Valor |
|---|---|
| Turnos concluídos / erros / violações | 4 / 0 / 0 |
| Provider | só `deepseek` (`deepseek-v4-flash`), tiers smart e fast |
| Chamadas de LLM | 14 (3 na abertura), 14 sucessos, 0 falhas, 0 puladas |
| Fallback (`fell_back`) | nenhum turno |
| Custo medido pelo hook | US$ 0,00392 (teto 0,10) |
| Eventos de abertura | `structured=true`, `attempt_index=0`, `fell_back=false` |

Cobre o caminho `RoutedLLM.invoke` (`_attempt`/`_prepare_candidate`) com o provider real.
Não exercitado em rede real: o fallback com `RPG_ROUTES` inválido na frente (passo 4 da §6);
ele está coberto pelo golden `llm_attempts*.json` (build/apply error, 429, timeout,
`tool_use_failed`, retry semântico, hedge), gerado na base e idêntico na HEAD.
