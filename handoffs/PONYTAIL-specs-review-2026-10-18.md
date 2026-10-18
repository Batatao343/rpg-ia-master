# Revisão independente das specs de poda (ponytail), 2026-10-18

> **Pedido do dono (2026-10-18):** "roda só um outro subagent opus que revisa todas as novas specs que
> foram criadas pelo ponytail para garantir que elas não vão acabar com nada".
> **Revisor:** Opus (estilo Astra, adversarial). **Base:** `main` @ `0784ff4`, worktree `prune-review`.
> **Escopo:** SPEC-263 a SPEC-274 + [relatório da auditoria](../docs/auditorias/ponytail-poda-2026-10-18.md).
> Nenhum código de produto foi alterado; só as specs (status segue `draft`), o relatório e este handoff.

## Método

- Cada afirmação de "não usado" foi refeita com `git grep -nw`/`-n` na árvore inteira (código, testes,
  `evals/`, `web/` incl. `e2e/` e `tests/`, `scripts/` incl. `staging/` e `release/`, workflows, `vercel.json`,
  `.vercelignore`, `Procfile`, `pyproject.toml`, `uv.lock`, `data/*.json`, `supabase/`, docs e specs), mais
  busca por uso dinâmico (`getattr(`, `importlib`, strings montadas, listas de exclusão).
- Deps: `uv tree --invert` por pacote e simulação de `uv lock --offline` numa cópia de scratch com a mudança
  da SPEC-263 aplicada; `uv export` para comparar com os `requirements*.txt` versionados.
- Pipelines de dados: leitura do que cada gerador escreve e de quem lê esses campos em runtime.
- Gates rodados depois das edições: `tests/test_spec_index.py`, `tests/test_spec_migration_safety.py`,
  `tests/test_agents_contract.py` (9 passed); `python -m project_index check` → `fresh_commit_drift`
  (árvore de código byte-idêntica).

## Vereditos

| Spec | Veredito | Risco principal encontrado | Mudanças feitas na spec |
|---|---|---|---|
| SPEC-263 deps | SAFE WITH CHANGES | R4 apagava o `requirements.txt` que a Vercel/Dependabot/pip-audit usam; os dois requirements estão defasados do lock (falta `pillow`), e regerar quebra a lista de banidos de `test_spec192_vercel_packaging.py:50`; `uv sync --extra openai` vira erro duro | R4 invertido (manter `requirements.txt`), R4b novo (drift + `pillow` no pip-audit), grep final ampliado, aceite ajustado |
| SPEC-264 arquivos soltos | SAFE as written | — (nada varre `assets/` por glob) | só §8 |
| SPEC-265 mana/stamina | SAFE WITH CHANGES | `web/tests/design.test.mjs:54-60` trava os tokens `--mana/--stamina`; `web/e2e/fixtures.ts:19` com as 4 chaves; HUD sem regra para `max_entropy == 0`; `mana_bonus` também existe em `origins.json` | R1a–R1d, R4 corrigido (os dois chips ficam), R5 com a lista real e a regra "inimigo fica", aceite de `npm test` sem editar o guard |
| SPEC-266 mídia | SAFE WITH CHANGES | `crossing_the_chasm.mp3` e `brag/play.mp4` são **insumos** do projeto Remotion (`Brag.tsx:355`, `package.json:11`); glob `**/*.mp4` ignoraria insumos; `proximas-specs` tem `MANIFEST_SHA256.txt` e links de SPEC-202/203/205 | só os 2 MP4 renderizados saem; `.gitignore` restrito; pacote `proximas-specs` fica inteiro |
| SPEC-267 frontend legado | SAFE WITH CHANGES | no CI o `pytest` roda antes do `npm run build`, logo hoje a suíte de CI roda **com** `frontend/` montado em `/`; depois roda sem mount (404 texto→JSON, 405→404). Nenhum teste depende disso, mas não estava dito | teste novo explícito, passo de rodar a suíte sem `web/dist`, R4 reescrito (`.vercelignore` incluído, exclusões opcionais) |
| SPEC-268 símbolos de jogo | SAFE WITH CHANGES | `_APEX_TAG` não fica órfão (`world_utils.py:573,799`); `save_custom_artifact` é o único escritor do overlay da SPEC-051 | `_APEX_TAG` mantido; `save_custom_artifact` vira opcional |
| SPEC-269 símbolos de infra | SAFE WITH CHANGES | **`infrastructure/file_blob.py` é importado por 5 testes** (apagar quebra a coleta); `sweep_synthetic_users` é ferramenta de limpeza do staging | os dois saem da lista; R2b sobre as citações de `infrastructure/testing.py` em SPEC-235/236 |
| SPEC-270 invariante | SAFE as written | — (string do código só em relatórios históricos) | só §8 |
| SPEC-271 exports web | SAFE WITH CHANGES | `currentPurchaseAdapter` é a porta de entrada da compra nativa (SPEC-198 `in-progress`); apagá-lo deixa `clientPlatform` importado e não usado → `noUnusedLocals` quebra o build | sai da lista; ficam 3 exports |
| SPEC-272 conflito só-testado | SAFE WITH CHANGES | apagar deixa critérios de specs `done` (064/065/068/069/070/072/073/075) falsos; cascatas: `generate_tactical_profile` (SPEC-069), `virtude_sugeridas.json` + `CARTAS.md:59`, follow-up da SPEC-226:165 | R5 (adendo obrigatório nas specs de origem), R6 (cascatas), R7 (default "ligar" o que tem valor de jogo) |
| SPEC-273 geradores | **UNSAFE as written** | `gen_tiers_5_plus.py` pós-processa `classes.json` (`late_entropy_curve`, `preview_card_ids`, lidos por `progression.py:67,73,219`) e carimba `tier/level_req/apex` nas Cartas; `gen_classes_v2`/`gen_cards_v4` (caminho documentado) não emitem esses campos. `gen_world_living_npcs.py` recoloca as 36 entidades `npc_mv_*` que `migrate_lore_nova.py` apaga ao regerar `entities.json`. R3 partia de premissa falsa (já usam `dotenv_values`) | header marcado "não recomendado"; R2 virou "documentar a ordem da pipeline em AUTORIA.md"; R3 virou dedup opcional |
| SPEC-274 env knobs | SAFE WITH CHANGES (escopo invertido) | virar constante tira válvula operacional (lote dos crons, raiz de backup que alimenta `rpg_backup_age_seconds`) por ganho de 0 linhas | R2: documentar em `.env.example`/`docs/spec192/cron.md` e manter |

## Riscos mais graves (se as specs fossem executadas como estavam)

1. **SPEC-273** quebraria silenciosamente a próxima regeneração de classes/Cartas (níveis 9–20 e previews de
   subclasse) e de lore (36 NPCs somem do grafo). Nenhum teste pega isso até alguém rodar o gerador.
2. **SPEC-269** apagaria `infrastructure/file_blob.py` e derrubaria 5 módulos de teste na coleta.
3. **SPEC-263** apagaria o `requirements.txt` que a Vercel lê segundo o teste da SPEC-192, e a regeneração
   pedida quebraria o próprio teste de empacotamento por causa do `pillow` faltante.
4. **SPEC-266** apagaria insumos do projeto de vídeo (não só saídas) e o manifesto SHA do pacote de prompts.
5. **SPEC-265** e **SPEC-271** quebrariam `npm test`/`tsc -b` (tokens de design e import órfão).

## Fora do escopo, mas visto

- O fallback `frontend/` hoje é o que o CI serve em `/` durante o pytest (ver SPEC-267).
- O frontend de compra nativa (adapters da SPEC-194) não está ligado a nenhuma tela; a `AccountScreen` chama o
  checkout Stripe direto. Tratar na SPEC-198.
- `data/origins.json` dá `mana_bonus`/`stamina_bonus` que não fazem nada no motor v4 e aparecem como chip na
  criação ("+10 Mana"). Pede spec de conteúdo de origens.
- 35 funções do motor de conflito entregues por specs `done` nunca foram ligadas (mesmo padrão da SPEC-050).
