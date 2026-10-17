# SPEC-211 — Menus Codex e Bestiário como dossiês vivos

> **Status:** `in-progress` — implementação + revisão Sol independente concluídas (17/10, [parecer](../handoffs/SPEC-211-SOL-independent-review.md)); falta só a autoria separada do eval de leak ([handoff](../handoffs/SPEC-211-eval-authoring.md)).
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-17
> **Depende de:** SPEC-204 `done` (shell), SPEC-206 `done` (rótulos de certeza), SPEC-208 `done` (tokens) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-212 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15`, prompt 06 (parte b — Codex e Bestiário)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — risco de vazamento de segredo/estado privado de NPC por dossiê, tooltip, prefetch ou contagem.
> **EVAL_AUTHORING_REQUIRED:** `true` — eval de leak de dossiê (fixtures com segredo `hidden`, trait oculto, carta/resistência não revelada, `hidden_traits`, estado privado de NPC; oráculo estruturado sobre o JSON da API e o DOM). Autoria em tarefa separada, nunca pelo executor desta spec.

---

## 1. Contexto & Objetivo

[D] Codex e Bestiário são **dossiês vivos**, não chatlogs acumulados (`DECISOES_PRODUTO.md`). Devem distinguir fato, suspeita, rumor, percepção e visibilidade do jogador, mostrar a relação com cada NPC e "o que o NPC parece saber" sem abrir segredos privados, e usar arte por ID canônico somente se foi efetivamente gerada e é permitida ao jogador. A SPEC-204 entrega o shell (5 abas: Codex, Personagem, Combate, Bestiário, Mapa); a SPEC-206 define a taxonomia/rótulos de certeza; esta spec define o **conteúdo e o contrato de dados** das abas Codex e Bestiário.

[F] Estado atual do código (HEAD 6b94f66):
- Backend: `GET /game/codex` (`api.py::get_player_codex`, ~l.1936) devolve `services/discovery.py::player_codex(state)` com cinco blocos: `locations` (visitados + `codex_body`), `factions` (só `faction_intel.known`; `goal` só se `knows_goal`), `characters` (só `known_by_player`; `revealed_traits` via `trait_names`; `knowledge_source` met/mentioned; `body` via `codex_body`), `creatures` (`bestiary_view`), `secrets` (`world_projection.revealed_facts`). **Não há** turno de atualização/`version`, rótulo de conhecimento (`knowledge_kind`), relação/disposição, histórico de encontros, nem arte nos blocos.
- `services/codex_loader.py::codex_body` só devolve corpo de `.md` com `visibility: public` (hidden/secret → `""`); truncado em `CODEX_BODY_MAX_CHARS`.
- Bestiário: `discovery.BESTIARY_TIERS` (1 Rumores/`seen`≥1, 2 Encontrada/`fought`≥1, 3 Estudada/`defeated`≥3, 4 Dominada/`defeated`≥7); `bestiary_view` revela campos por tier (descrição/tipo no 2; HP/defesa/nomes de ataque no 3; ataques completos, `behavior` e `loot` no 4). Contadores em `state["bestiary_knowledge"]` têm `first_seen_turn`/`last_update_turn`. `services/bestiary_knowledge.py` tem `public_panel`, `reveal_card`/`reveal_resistance`, `is_card_revealed`/`is_resistance_revealed` (persistência em overlay `data/runtime/`, por arquétipo); **a view de codex (`bestiary_view`) não expõe cartas/resistências reveladas** — só o painel de combate (`api.py::_combat_block`) as usa.
- NPCs: `services/npc_layers.py::visible_npc_view(npcs)` (usado em `api.py::_npcs_block`) devolve `name, role, location, home_location_id, relationship, knowledge_source, in_scene, revealed_traits, last_memory` — sem `hidden_traits`. [F, revisão] Atenção: (a) o filtro usa `npc.get("known_by_player", True)` — NPC **sem** a chave conta como conhecido; (b) `last_memory` é `memory[-1]` **bruto**, sem proveniência — já trafega hoje e pode conter conteúdo privado do NPC. `Hud.tsx::PeopleTab` (~l.220) renderiza isso; `FactionsTab` (~l.274) e `ChronicleTab` (~l.337, com busca e export) vivem no Hud; `QuestsTab.tsx` é separado.
- Frontend: `web/src/components/CodexTab.tsx` (5 categorias Locais/Fações/Personagens/Bestiário/Segredos; `codex-beast--tier{N}`, selo romano) refaz `getCodex` a cada `turnCount`; usa `dangerouslySetInnerHTML` com `mdLite(body)` para corpos.
- Crônica: `POST /game/chronicle/search` (`api.py` ~l.3677, híbrida com pgvector quando disponível) e `GET /game/chronicle/export` (~l.3710, .txt por capítulo; lê só `state["chronicle"]`).
- Arte: `services/visual_catalog.py::visual_for(subject_type, subject_id)` expõe só assets `visibility == "public"` (45 assets: raças, classes, locais, NPCs; sem criaturas) e `services/entity_identity.py` resolve ID canônico de NPC. [H] criatura sem asset curado só terá imagem se arte dinâmica (SPEC-125/188) foi gerada; não verificado nesta spec.

[F, revisão] A SPEC-206 (dependência) já define a taxonomia em `services/player_knowledge.py`: `KnowledgeKind = fact|report|rumor|suspicion|perception` (rótulos "Fato confirmado"/"Relato"/"Rumor"/"Suspeita"/"Percepção"), `KnowledgeStamp {knowledge_kind, certainty: MemoryConfidence, source_kind: MemoryProvenance, source_ref, label, first_seen_turn, last_updated_turn, stale}`, `notes[]` ancoradas, `meta.counts`, e os oráculos `entity_is_player_visible`/`assert_no_player_leak`; também acrescenta selo por entrada no `CodexTab`. Esta spec **consome** esses nomes literalmente; não cria vocabulário paralelo.

[D] D1 (default recomendado, ver §8): Facções e Crônica passam a ser **seções do Codex**; Missões vai para Personagem/Jornada (SPEC-209). Bestiário é aba própria.

## 2. Requisitos

### Contrato de dossiê (backend)
- **R1** — Novo endpoint aditivo `GET /game/codex/dossiers` (o `GET /game/codex` atual permanece, compatível) devolve `{version, generated_at_turn, sections: {npcs, locations, factions, chronicle_index}, bestiary: [...]}`. Cada dossiê tem `id` canônico, `last_updated_turn` (turno em que o dado visível mudou pela última vez), `version` (inteiro monotônico por dossiê, derivado do turno da última mudança visível — ver §3.2) e, por afirmação, o `knowledge: KnowledgeStamp` da SPEC-206 (não um campo `certainty` solto).
- **R2** — **Dossiê de NPC** (só NPCs com `entity_is_player_visible` da SPEC-206 verdadeiro; ausência de `known_by_player` segue a regra da SPEC-206, não o default `True` de `visible_npc_view`): identidade canônica (`entity_id` via `resolve_npc_entity_id`, nome, papel, local), `relationship` + rótulo de disposição derivado em Python da faixa numérica (sem LLM), `knowledge_source`, traits **revelados** apenas, afirmações do jogador sobre o NPC (`claims[]`: `{text, knowledge: KnowledgeStamp}` — turnos em `knowledge.first_seen_turn`/`last_updated_turn`, sem `source_turn` solto, conforme SPEC-206 §3.2b), `encounters[]` (resumo curto determinístico por encontro: turno, local, desfecho; teto 20, mais recentes; quando o encontro é combate, `encounter_id` e `outcome` vêm de `combat_result` da SPEC-203 R7 — nunca da prosa), `last_seen_turn`, `portrait` (R9).
- **R3** — **"O que o NPC parece saber"** (`appears_to_know[]`): lista derivada **exclusivamente** de fatos públicos já observáveis pelo jogador (ex.: o jogador contou algo ao NPC em cena — `npc_claim`/`player_observation` (o `MemoryFact.source_turn` vira `knowledge.last_updated_turn`, regra de `KnowledgeNote` da SPEC-206); o NPC reagiu/citou algo em fala já exibida). Cada item carrega `knowledge` com `knowledge_kind ∈ {perception, suspicion}` (nunca `fact`) e `certainty` derivada pela SPEC-206 (`speculative`/`reported`, nunca `confirmed`), e é apresentado como inferência do jogador. **Proibido** derivar de `hidden_traits`, `memory` bruta não exibida, `npc_secrets`, docs `hidden/secret` do Codex ou qualquer campo de estado privado do NPC. Se não há base pública, a lista é vazia (a UI mostra "Nada percebido ainda", nunca "nada sabe").
- **R4** — **Dossiê de local** (visitados, fog of war preservado): nome, região, corpo público (`codex_body`), NPCs conhecidos ali, criaturas avistadas ali (só tiers ≥1 do bestiário, sem revelar além do tier), eventos relevantes do jogador. **Dossiê de facção** (`faction_intel.known`): `goal` só se `knows_goal`; disposição/reputação como em `_factions_block` da API; progresso só se `knowledge.stale` (SPEC-206) for falso, senão rótulo "informação defasada". Local não visitado e facção desconhecida **não** aparecem nem contam em totais.
- **R5** — **Crônica** como seção do Codex: preserva busca (`POST /game/chronicle/search`) e export (`GET /game/chronicle/export`) **sem alterar seus contratos**; adiciona apenas navegação por capítulo (`arc_title`, `started_turn`, `location`) e vínculo `entity_id` quando o texto de milestone já referencia entidade conhecida. Nenhum conteúdo novo gerado por LLM.
- **R6** — **Dossiê de criatura** (Bestiário): estende `bestiary_view` com `last_updated_turn` (= `last_update_turn` do bestiário), `first_seen_turn`, tier e `tier_name` existentes (sem mudar limiares), e — **apenas se reveladas** pelo bestiário — `revealed_cards[]` e `revealed_resistances[]` via `is_card_revealed`/`is_resistance_revealed`. Campos acima do tier atual **não são enviados** (nem vazios com chave): ausência de chave, não máscara no cliente. Carta exclusiva de variante não revelada permanece fora. Criatura ad-hoc sem entrada no bestiário continua fora (comportamento atual de `normalize_bestiary_id`).
- **R7** — **Rótulo de certeza** visível por afirmação: `knowledge.label` da SPEC-206 (`fact|report|rumor|suspicion|perception` → "Fato confirmado"/"Relato"/"Rumor"/"Suspeita"/"Percepção"; legado → "Relato não verificado"); esta spec não redefine a taxonomia e reutiliza o selo de UI da SPEC-206 R13. Afirmação sem rótulo derivável é omitida, não rotulada por palpite.
- **R8** — **Novo/atualizado desde a última visita**: o backend fornece `last_updated_turn`/`version` por dossiê; o cliente guarda `last_seen_version` por `game_id` + aba (preferência de visualização; ver §3.4) e marca "novo" (dossiê inexistente na última visita) / "atualizado" (versão maior). A marcação é apenas visual; **nunca** é um contador agregado por categoria que revele existência de conteúdo oculto (ex.: "3 novos" só conta dossiês já visíveis ao jogador, e a UI não mostra totais de categorias ainda bloqueadas).
- **R9** — **Arte por ID canônico**: `portrait` / `art` de NPC, local e criatura só quando existe asset público no catálogo (`visual_for`) ou geração concluída e permitida ao jogador; senão ausente (a UI mostra placeholder honesto, nunca imagem inferida por nome). URL assinada expirada → um refetch e então fallback (padrão SPEC-209 R10); testado após reload.
- **R10** — **Não-vazamento (invariantes)**: `assert_no_player_leak` (SPEC-206) e `assert_no_private_fields` (allowlist desta spec) passam sobre o payload completo de `dossiers`. O payload nunca contém `hidden_traits`, docs `hidden/secret`, `npc.memory` bruto (dossiê **não** copia `last_memory`; memória só entra como `notes[]` com proveniência da SPEC-206), `behavior`/cartas/resistências acima do revelado, nem campos de `world_projection` não revelados. Nenhum dado oculto trafega para o cliente para ser "escondido na UI": sem dado em tooltip/`title`/`aria-label`/atributo `data-*`, sem prefetch de dossiê não visível, sem diferença de tamanho/latência/contagem entre "inexistente" e "oculto" (404 e vazio são indistinguíveis).
- **R11** — **Consistência**: dossiês corretos após turno, reload, troca de save e atualização assíncrona. Projeção derivada atrasada (SPEC-213, futura) é indicada como "atualizando…" via `version`/`generated_at_turn` menor que `turn_count`, **nunca** tratada como fato inexistente. Dossiê de save arquivado/memorial segue as regras de `_resolve_save_file`/`_reject_archived`.
- **R12** — **UI**: abas Codex e Bestiário utilizáveis em tela inteira e em ~50% (uma única região rolável por aba, cabeçalho fixo, lista + detalhe; sem scroll aninhado excessivo); sem trocar o chat; teclado (setas na lista, Enter abre dossiê, Esc volta), foco visível, alvo ≥44px, `prefers-reduced-motion`. Estado de navegação (categoria, dossiê aberto, busca) preservado ao alternar abas (estado local da SPEC-204 §3).
- **R13** — **Segurança de renderização**: corpos continuam renderizados por `mdLite`; é proibido `dangerouslySetInnerHTML` com texto de LLM não escapado (verificar que `mdLite` escapa HTML; ver risco §7).

### Fora de escopo
Taxonomia/rótulos de certeza (SPEC-206); modelo de conhecimento por NPC e propagação (SPEC-215 — aqui só se **lê** o que já é público); shell/split/resize (SPEC-204); mapa (SPEC-210); combate/deck (SPEC-209); Personagem/Jornada (SPEC-209); projeções assíncronas (SPEC-213); geração de arte nova ou novos assets; mobile single-pane (SPEC-216); alterar limiares de `BESTIARY_TIERS`; editar evaluator/dataset protegido.

## 3. Design técnico

### 3.1 Arquivos
- **Novo** `services/dossiers.py` — funções puras sobre `state` (sem LLM, sem I/O além do catálogo/Codex): `npc_dossier(state, npc_key)`, `location_dossier`, `faction_dossier`, `creature_dossier`, `build_dossiers(state) -> dict`. Reusa `discovery._characters_block/_locations_block/_factions_block/bestiary_view`, `npc_layers.visible_npc_view/trait_names`, `bestiary_knowledge`, `visual_catalog.visual_for`, `entity_identity`.
- **Novo** `services/dossier_visibility.py` — allowlist de campos por tipo de dossiê + `assert_no_private_fields(payload)` usado em teste e, em modo debug, no endpoint (defesa em profundidade; nunca como única barreira).
- **Alterado** `api.py` — rota `GET /game/codex/dossiers` (mesmo guard de `get_player_codex`: `_resolve_save_file`, 404 sem save; sem `Cache-Control` público; rate limit padrão). Modelos Pydantic de resposta com `extra="forbid"` na saída para que campo novo não vaze por acidente.
- **Alterado** `web/src/types.ts`, `web/src/api.ts` (`getDossiers`), `web/src/components/CodexTab.tsx` (vira container: Pessoas, Locais, Facções, Crônica, Segredos revelados), **novo** `web/src/components/tabs/BestiaryTab.tsx`, **novo** `web/src/components/tabs/DossierList.tsx`/`DossierDetail.tsx`/`CertaintyBadge.tsx`; `Hud.tsx` perde `PeopleTab`/`FactionsTab`/`ChronicleTab` (extraídos; shell da SPEC-204 monta). CSS novo em arquivo próprio (ex.: `web/src/components/tabs/tabs.css`, padrão SPEC-204 R14 — `styles.css` não recebe regras novas, para reduzir conflito com SPEC-197), consumindo os tokens da SPEC-208.
- **Testes** `tests/test_dossiers.py`, `tests/test_dossiers_api.py`, `tests/test_dossier_leak.py` (fixtures de vazamento; os datasets do eval protegido ficam para a tarefa de autoria); frontend: teste de unidade do `last_seen_version` e Playwright (jornada, autoria separada).

### 3.2 Contratos de dados (esboço)
```
Dossier {
  id: str               # entity_id canônico (npc_*/loc_*/fac_*/enemy_*)
  kind: "npc"|"location"|"faction"|"creature"
  title: str
  last_updated_turn: int  # turno do último dado visível alterado (nome alinhado à SPEC-206)
  version: int            # = last_updated_turn (monotônico por save); sem relógio real
  art: {asset_id, alt, variants} | null     # só se público/gerado e permitido
  ...campos por kind (allowlist)
}
NpcDossier(Dossier) { role, location, relationship, disposition_label,
  knowledge_source, revealed_traits[], claims[Claim], appears_to_know[Claim],
  encounters[{turn, location_id, outcome, encounter_id?}], last_seen_turn }
Claim { text, knowledge: KnowledgeStamp /* SPEC-206 §3.2b: knowledge_kind ≠ certainty; turnos em first_seen_turn/last_updated_turn */ }
CreatureDossier(Dossier) { tier, tier_name, regions[], rarity_note?,
  description? (tier>=2), type? (tier>=2), max_hp?/defense?/attacks? (tier>=3),
  behavior?/loot? (tier>=4), revealed_cards[]?, revealed_resistances[]?,
  first_seen_turn }
```
[R] `version` = `last_updated_turn` evita relógio real e é estável em replay/restore; [H] verificar se NPCs têm turno de mudança suficiente (`last_seen_turn`, `created_turn`, entradas de `memory`); onde não houver, usar o turno do último `event_log` que cita a entidade e, na falta, `0`.

`disposition_label`: tabela fixa em Python por faixa de `relationship` (0–10, default 5; mapeamento exato definido na Etapa 1 e travado por teste), sem LLM.

### 3.3 State ownership
- **Canônico (servidor):** `state["npcs"]`, `bestiary_knowledge`, overlay de bestiário, `faction_intel`, `world.visited`, `world_projection.revealed_facts`, `chronicle`, `event_log`. Esta spec **não escreve** nenhum deles: dossiê é projeção somente leitura calculada sob demanda (nada persistido ⇒ sem migração de save).
- **Cliente (conveniência por viewer):** categoria/dossiê aberto/busca e `last_seen_version` por `game_id` em `localStorage` com try/catch (render correto sem ele). Nunca fonte de verdade; perder o dado só faz tudo parecer "novo".
- **Derivado e eventualmente consistente (futuro SPEC-213):** `appears_to_know` e `encounters` podem passar a vir de projeção assíncrona; contrato já carrega `generated_at_turn`.

### 3.4 Degradação / fallback
- Sem save → 404 (igual a `/game/codex`). Endpoint novo falha → cliente cai para `GET /game/codex` (formato antigo) e esconde rótulos/novo-atualizado, sem erro bloqueante.
- Sem asset de arte → placeholder; asset expirado → refetch único → placeholder.
- Sem rótulo derivável → afirmação omitida. Sem `known_by_player` → NPC ausente.
- MockLLM/FallbackLLM: nenhum LLM nesta feature; comportamento idêntico.

## 4. Plano passo a passo (TDD)

### Etapa 1 — Dossiê de NPC e lista de allowlist
1. **Testes** (`tests/test_dossiers.py`, `tests/test_dossier_leak.py`): `test_npc_dossier_exclui_hidden_traits`; `test_npc_nao_conhecido_nao_aparece`; `test_appears_to_know_so_de_fatos_publicos` (NPC com `memory` privada e secret hidden ⇒ lista vazia); `test_disposition_label_por_faixa`; `test_encounters_teto_20`; `test_payload_so_campos_allowlist` (`extra="forbid"`); `test_dossie_nao_copia_last_memory`; `test_npc_sem_known_by_player_segue_spec206`; `test_assert_no_player_leak_spec206_verde`.
2. **Implementação:** `services/dossiers.py` (NPC) + `services/dossier_visibility.py`.
3. **Verificação:** `uv run pytest tests/test_dossiers.py tests/test_dossier_leak.py -q`.

### Etapa 2 — Locais, facções, crônica
1. **Testes:** `test_local_nao_visitado_ausente`; `test_faccao_goal_so_com_knows_goal`; `test_faccao_intel_stale_rotulada`; `test_cronica_busca_export_inalterados` (contratos de `/game/chronicle/search|export` byte a byte em fixture).
2. **Implementação:** blocos de local/facção/índice de crônica.
3. **Verificação:** pytest focado + `tests/test_polish_sessao.py`.

### Etapa 3 — Bestiário
1. **Testes:** `test_criatura_chaves_acima_do_tier_ausentes` (tiers 1–4); `test_cartas_resistencias_so_reveladas`; `test_variante_exclusiva_oculta`; `test_last_updated_turn_vem_de_last_update_turn`; `test_criatura_adhoc_fora`.
2. **Implementação:** `creature_dossier` reusando `bestiary_view` sem alterar limiares.
3. **Verificação:** pytest focado + `tests/test_fase32.py` (regressão do codex antigo).

### Etapa 4 — Endpoint e arte
1. **Testes** (`tests/test_dossiers_api.py`): `test_get_dossiers_404_sem_save`; `test_get_dossiers_save_arquivado`; `test_codex_antigo_inalterado`; `test_arte_so_se_publica` (`visibility != public` ⇒ `art` nulo); `test_404_e_vazio_indistinguiveis_para_oculto`; `test_sem_cache_publico`.
2. **Implementação:** rota + modelos de resposta; `visual_for`/`entity_identity`.
3. **Verificação:** pytest focado.

### Etapa 5 — Frontend
1. **Testes** (Vitest/Node + Playwright, jornadas em tarefa de eval separada): `last_seen_version` marca novo/atualizado; sem `localStorage` ⇒ renderiza; categoria bloqueada não mostra total; DOM sem `title`/`data-*` com texto de dossiê oculto (inspeção do payload mockado); reload mantém dossiê aberto; expirar URL ⇒ refetch único.
2. **Implementação:** `CodexTab`/`BestiaryTab`/`DossierList`/`DossierDetail`/`CertaintyBadge`; extração de People/Factions/Chronicle do `Hud`.
3. **Verificação:** `cd web && npm run build`, testes Node, Ruff.

### Etapa 6 — Handoff de eval e revisão
Registrar `handoffs/SPEC-211-eval-authoring.md` (casos de leak) para tarefa separada; abrir revisão Sol (`REVIEW_REQUIRED: true`), sem autoaprovação.

## 5. Critérios de aceite
- [x] `GET /game/codex/dossiers` implementado; `GET /game/codex` e rotas de crônica **inalterados** (testes de regressão verdes).
- [x] Todo dossiê traz `id`, `last_updated_turn`, `version` do backend; cliente não calcula versão.
- [x] `appears_to_know` derivado só de fatos públicos; teste com NPC de memória privada retorna vazio.
- [x] Nenhum payload contém `hidden_traits`, docs hidden/secret, cartas/resistências não reveladas, campos acima do tier; `assert_no_private_fields` verde nas fixtures.
- [x] Bestiário respeita os 4 tiers existentes; chaves acima do tier ausentes do JSON.
- [x] Crônica: busca e export preservados; navegação por capítulo no Codex.
- [x] "Novo/atualizado" por dossiê visível; nenhuma contagem/tooltip/prefetch de conteúdo oculto.
- [x] Arte só por ID canônico existente/permitido; fallback honesto; refetch após expirar.
- [x] Abas utilizáveis em tela cheia e 50%, teclado e reduced-motion; estado preservado entre abas.
- [x] `uv run pytest` verde (suíte completa offline); `npm run build` verde; Ruff verde; `uv run python scripts/validate_content.py` sem novos erros.
- [x] Saves antigos carregam (sem migração, projeção calculada); round-trip save→load→dossiê idêntico.
- [ ] `EVAL_AUTHORING_REQUIRED` cumprido por tarefa separada antes de `done` (pendente). Revisão Sol independente registrada em `handoffs/SPEC-211-SOL-independent-review.md` (17/10) — corrigiu chaves acima do tier saindo como `null` no JSON da API e leitura do overlay legado de bestiário em perfil com banco.

## 6. Smoke
1. Offline (MockLLM, padrão): `uv run pytest tests/test_dossiers.py tests/test_dossiers_api.py tests/test_dossier_leak.py -q`; subir `uv run uvicorn api:app --port 8000`, criar jogo, 3 turnos com NPC e combate (`bash scripts/smoke_api.sh`), consultar `/game/codex/dossiers` e conferir ausência de campos privados.
2. Navegador (Chromium 1440 e split 50%): abrir Codex → Pessoas → dossiê; Bestiário tier 1→3 após derrotar criatura; reload; trocar save.
3. Provider real: **não requerido** (feature sem LLM). Se o verificador optar por um turno real, teto explícito de 5 requests e autorização do dono.

## 7. Riscos & compatibilidade
- **Vazamento (alto):** qualquer campo novo no dossiê pode expor estado privado. Mitigação: allowlist + `extra="forbid"` + teste de leak + eval separado + revisão Sol obrigatória. `npc.memory` livre pode conter conteúdo privado do NPC; por isso `appears_to_know` não lê memória bruta (só o que a SPEC-206/provenance já classificou como observado pelo jogador).
- **`mdLite`/XSS [F]:** `web/src/lib.ts::mdLite` escapa `&`, `<`, `>` antes de aplicar negrito/itálico (seguro em conteúdo de elemento); não escapa aspas, logo **nunca** usá-lo em atributo. Etapa 5 adiciona teste com `<img onerror>`/`<script>` no corpo.
- **Dependência da SPEC-206:** sem a taxonomia, R7 não fecha; não inventar rótulos locais. Se 206 atrasar, entregar com apenas `knowledge_source` existente e sem R3.
- **Conflito de arquivos:** `Hud.tsx`/`styles.css` também mudam em SPEC-204/209/210 e na SPEC-197 (em curso, não editada aqui); rebasear a cada etapa.
- **Projeção atrasada:** SPEC-213 pode tornar dossiês eventualmente consistentes; contrato já preparado (R11).
- **Saves:** nenhum campo persistido novo; sem migração. Se a decisão §8.3 adicionar `last_visit` no servidor, exige migração + teste round-trip.
- **Custo/latência:** cálculo sob demanda O(entidades conhecidas); sem LLM; [H] medir em save longo (200 turnos) antes de declarar aceitável.

## 8. Pontos de decisão do dono
1. **Fusão de abas (D1):** Facções e Crônica como seções do Codex (default recomendado, alinhado ao pedido de 5 abas). Alternativa: manter 7 abas.
2. **Quanto o NPC "parece saber" (default recomendado):** só o que o jogador já contou/viu em cena, sempre como suspeita/percepção. Alternativa mais ousada (fora desta spec): usar o modelo por-NPC da SPEC-215 depois de aprovada.
3. **Onde guardar "visto pela última vez" (default recomendado):** `localStorage` por viewer (sem persistência servidor, sem migração). Alternativa: campo no save para sincronizar entre dispositivos (custa migração e mistura estado de UI com estado de jogo).
4. **Arte de criatura:** exibir só asset curado/gerado já permitido (default). Gerar arte nova para criaturas descobertas é custo permanente e fica para decisão separada (SPEC-125/188).

## 9. Evidência requerida
- Saída de `uv run pytest` (completa) e dos testes focados; build web; Ruff.
- Dump do JSON de `/game/codex/dossiers` em save de fixture com segredo/trait oculto/carta não revelada, mostrando ausência dos campos.
- Capturas/Playwright em 1440 e split 50% (Codex, dossiê de NPC, Bestiário nos 4 tiers) e após reload.
- Handoff `handoffs/SPEC-211-eval-authoring.md` + parecer de revisão Sol independente; atualização de `specs/index.yaml`, `ESTADO_ATUAL.md` e `ROADMAP.md` pelo executor ao concluir.
