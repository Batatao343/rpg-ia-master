# SPEC-203 — Manifesto do encontro, elenco fixo e desfecho do combate

> **Status:** `done` (implementação, revisão Astra e autoria de evals concluídas — corpus `encounter_manifest`, 2026-10-16)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-199 `done` (evento estruturado de XP), SPEC-228 `done` (guard de schema + morte/checkpoint corretos), SPEC-231 `done` (morte com aliados/`scene_allies` corretos) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-205, SPEC-209, SPEC-212 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 04 (parte b)
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver `docs/planos/equivalencia-modelos-claude.md`)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — casos novos de `state_rules` (identidade do elenco
> estável por rodada/reload, lifecycle terminal→exploração) e de `narrative_npc` (prosa de
> combate não renomeia espécie do manifesto). Autoria em tarefa separada; o executor desta
> spec NÃO edita `evals/` (evaluator, expected ou datasets protegidos).
> **Nota de schema (ATUALIZADA 2026-10-16 — fora da cadeia de bump):** por instrução do coordenador, esta spec **não** faz bump de `SCHEMA_VERSION` (permanece 8): o caso protegido `state.persistence.migration-idempotent` (evals/…/state_rules.jsonl) fixa v8 e editar `evals/` exige tarefa separada. `combat.phase/outcome/encounter/result` são campos ADITIVOS normalizados de forma idempotente no load (`persistence._normalize_combat_on_load` → `encounter_manifest.normalize_combat`). R12 lê-se "normalização aditiva v8" em vez de "migração v8→v9".
> ~~Nota de schema (cadeia final 2026-10-15):~~ ordem dos bumps de `SCHEMA_VERSION` (hoje 8): SPEC-228 primeiro (R9 recusa save de versão mais nova; sem bump) → [SPEC-227 só se D-C = migração; default sem bump] → SPEC-202 → SPEC-203 → SPEC-207 → SPEC-213 → SPEC-215. Nenhuma outra spec 199–236 altera o schema de save (SPEC-228 R7 `needs_replan` e SPEC-231 `scene_allies` usam default/campo existente, sem bump). Cada spec usa o próximo `SCHEMA_VERSION` livre no HEAD ao implementar e encadeia sua migração após a anterior; onde o texto disser "v8→v9", leia "vN→vN+1".

Contexto histórico (não executar, só referência): `historico-nao-executar/HISTORICO_SPEC-179-manifesto-encontro-fim-combate.md`
e `HISTORICO_SPEC-183-pressao-tatica-balanceamento.md` do pacote. Os IDs 179/183 daquele
material NÃO correspondem às SPEC-179/183 do repo (já `done`, outros temas).

---

## 1. Contexto & Objetivo

No playtest beta, bandidos foram "confundidos com corvos" e sumiram do encontro, o fim do
combate não devolveu o jogador ao chat com um desfecho, e a transição chat→combate pareceu
arbitrária. A decisão de produto fechada é: **inimigos e NPCs não mudam de identidade nem
desaparecem por confusão com fauna/cena; o chat recebe o desfecho narrado; a UI recebe XP e
números** [D] (`DECISOES_PRODUTO.md` § Combate).

O que o source mostra hoje [F]:

- O elenco nasce em `agents/combat.py::_spawn_v4_enemies` (l.162-218), chamado de
  `combat_node` (l.651) **só** quando não há inimigo ativo em `state["enemies"]`. Ele invoca
  LLM `ModelTier.CLASSIFY` com `with_structured_output(EncounterScanner)` sobre
  `[SystemMessage] + messages[-2:]` (l.185-186), e para cada grupo chama
  `agents.bestiary.generate_new_enemy(name, ...)` (l.193), que por sua vez usa
  `agents.librarian.find_existing_entity` — um **segundo** ponto de classificação por LLM
  (dedupe semântico, `librarian.py:15`).
- Falha/vazio do scanner → fallback fixo `{"id": "sombrio_1", "name": "Inimigo Sombrio"}` (l.211-214).
- Depois, `_apply_encounter_budget` (l.221-245) chama `encounter_budget.clamp_encounter`
  (corta excedente priorizando **variedade de template**, l.38-77) e `fill_encounter`
  (l.79-102), que **adiciona criatura regional** via `world_utils.pick_encounter_enemy`
  com log `"<nome> surge atraído pelo tumulto."` — ou seja, fauna regional pode entrar e
  um bandido pode sair por orçamento, sem evento explícito de composição.
- A fonte canônica do encontro já existe e é **descartada**: `world_utils` devolve
  `{"hint", "flavor", "reason", "enemy_id"}` (l.752-785, `enemy_id` = id do bestiário), mas
  `agents/storyteller.py:464-467` só repassa `combat_target = enc["hint"]` e a mensagem
  `COMBAT START. {flavor}`; o `enemy_id` não chega ao spawn. O router (`agents/router.py:226-237`)
  usa `decision.target` (texto livre do LLM) como `TARGET_HINT`.
- Pós-spawn, IDs `base_id_N` são estáveis em `state["enemies"]` e persistidos
  (`persistence.py:540,609,790`). `services/conflict_scene.py` `new_scene/place/freeze`
  congela **zonas/posições**, não identidade/espécie/facção.
- O fim já é determinístico no servidor: `combat_meta["active"] = not combat_over` (l.971),
  `conflict_summary` via `services/conflict_summary.build_summary` (l.946-962), `next="loot"`
  na vitória, `death_pending` na morte (l.1013-1035), fuga via `_apply_flee_travel`. Mas não
  há `phase`, `encounter_id` público nem bloco de desfecho para a UI: `web/src/types.ts`
  `CombatBlock` (l.272) só tem `active/round/...`; quando acaba, o cliente só vê `active=false`.
- A narração `_narrate` (l.561) recebe só nomes vivos; nada impede a prosa de chamar o
  bandido de corvo (deriva narrativa sem efeito no estado).

**Não há reprodução registrada do bug de identidade.** Por isso a Etapa 0 é obrigatória:
reproduzir de forma determinística qual(is) mecanismo(s) causam a troca/sumiço **antes** de
alterar qualquer regra (prompt 04: "Não alterar regras existentes sem provar bug").

Objetivo: um **manifesto de encontro** determinístico, congelado no spawn, persistido e
lido a cada rodada (nunca reclassificado por LLM); spawn a partir de fonte canônica com o
scanner apenas como fallback validado; uma state machine explícita do encontro exposta ao
cliente; e um desfecho mecânico na UI + desfecho narrado no chat, com retorno à exploração.

## 2. Requisitos

- **R0 — Reprodução antes de regra.** Existe teste determinístico (MockLLM/stubs, seed fixa)
  que reproduz no HEAD pelo menos um caminho de troca de espécie, sumiço ou confusão com
  fauna, e falha (`xfail strict` ou known-bad documentado) antes da correção. Se nenhuma
  hipótese reproduzir, a spec volta ao dono (ver §8, D-A) antes de R2–R5.
- **R1 — Manifesto congelado.** Ao iniciar um encontro, Python grava
  `combat["encounter"] = EncounterManifest` com `encounter_id`, `origin`, `source`,
  `target_ref` canônico já resolvido e um `participants[]` com, por participante:
  `participant_id` (= `enemy["id"]`), `bestiary_id`, `species_label`, `faction_id`,
  `categoria`, `role` (`hostile|ally|neutral|hazard`), `presence`
  (`present|arrived|departed`), `zone_id` inicial e `status`. Após o congelamento,
  `species_label`/`bestiary_id`/`faction_id`/`role` de um `participant_id` existente são
  imutáveis.
- **R2 — Leitura por rodada, sem reclassificação.** Toda rodada valida
  `state["enemies"]` contra o manifesto: nenhum `enemy.id` fora do manifesto entra na
  rodada sem evento de composição, e nenhuma chamada LLM (scanner, librarian ou outra) é
  feita com `combat.encounter` presente. Teste com spy de `get_llm` asserta zero invokes
  CLASSIFY nas rodadas ≥1.
- **R3 — Spawn por fonte canônica.** Ordem de resolução determinística:
  (a) `enemy_id` do encontro sistêmico (`world_utils`) propagado pelo storyteller;
  (b) NPC em cena resolvido por `npc_layers.npcs_in_scene` quando o alvo do router casa
  com ele; (c) alvo/ameaça já resolvida (`alert.enemy_id`, facção dominante);
  (d) **só então** o `EncounterScanner`, cuja saída é validada (nome casa com entrada
  existente do bestiário ou da região; total limitado por `_MAX_SCANNER_*`), com
  `source="scanner"` registrado. O fallback `"Inimigo Sombrio"` fica com
  `source="fallback"` e é visível na telemetria.
- **R4 — Composição só por evento.** `clamp_encounter`/`fill_encounter`, reforços e saídas
  (`dead|fled|surrendered|captured|departed`) geram `EncounterCompositionEvent` no
  manifesto (`kind`, `participant_id`, `cause`, `round`). Um participante só deixa a luta
  com evento. A política numérica de orçamento não muda nesta spec (ver §8, D-B).
- **R5 — State machine explícita.** "Encontro confirmado" (prompt 04) = transição
  `entering→active`, que só ocorre depois que o manifesto foi congelado (`frozen=True`) e a
  narração de entrada foi enviada ao chat; a UI de combate só abre em `active`. `combat["phase"] ∈ {entering, active, resolving,
  ended}` e `combat["outcome"] ∈ {null, victory, fled, surrendered_enemy, defeat, death,
  expired}`; transições permitidas: `entering→active→resolving→ended`,
  `entering→ended` (só `expired`/inconsciente), sem retorno de `ended`. Transição inválida
  levanta em teste e é registrada (não silenciosa) em produção.
- **R6 — Retorno à exploração.** Em `ended` com outcome ≠ `death`, o próximo turno do jogador
  é roteado como exploração (não `combat_agent`) sem exigir mensagem extra; `death` mantém o
  fluxo `death_pending` existente (SPEC-060/083) intacto.
- **R7 — Desfecho na API.** `GameResponse`/estado expõem `combat.encounter_view` (só
  campos públicos e participantes percebidos) e, no turno de término, `combat_result`:
  `{encounter_id, outcome, participants:[{participant_id, species_label, final_status}],
  xp_event_ref, loot_ref, ended_round, result_event_id}`. XP vem **exclusivamente** do
  evento estruturado da SPEC-199; nenhum número de XP é derivado de prosa.
  **Contrato compartilhado com SPEC-199:** o "evento de XP" é a projeção pública
  `GameResponse.turn_outcome` (`PublicOutcome`: `receipt_id`, `xp_delta`, `level_delta`,
  `level_after`, `gold_delta`, `items_gained`, `quests_completed`, `source`), derivada de
  `last_turn_outcome`. `combat_result.xp_event_ref` = `turn_outcome.receipt_id` do turno de
  término; o painel lê os números de `turn_outcome`, nunca duplica o valor em `combat_result`.
  `combat_result` é **derivado** de estado persistido (manifesto com `phase="ended"` +
  `conflict_summary` + `last_turn_outcome`), não de campo transitório — por isso sobrevive a
  reload antes de "Continuar" (R11).
- **R8 — Painel de desfecho + desfecho no chat.** Frontend exibe painel/tela de desfecho
  mecânico (outcome, baixas, XP/nível via evento SPEC-199, loot) com ação "Continuar"
  que fecha **apenas o painel de desfecho**, sem consumir turno (a aba Combate permanece aberta
  conforme SPEC-204 R10/P2; o shell decide layout, esta spec não); o chat recebe o desfecho narrado
  (`conflict_summary.narrative_or_fallback`), sem números de XP.
- **R9 — Prosa ancorada no manifesto.** O prompt de `_narrate` recebe a lista de
  `species_label` do manifesto como nomes canônicos; `prose_guard` (ou validador novo)
  marca/neutraliza prosa que atribui a um participante espécie diferente da do
  manifesto. Não reescreve estado.
- **R10 — Idempotência.** Replay da mesma `action_id` (ledger existente) não duplica
  evento de composição, `result_event_id`, XP, loot nem kill.
- **R11 — Save/reload causal.** Salvar e recarregar em cada fase (`entering`, `active`
  rodada 1 e 2, `resolving`, `ended` antes de "Continuar") reproduz o mesmo manifesto,
  a mesma fase e o mesmo próximo passo.
- **R12 — Migração.** `SCHEMA_VERSION` vN→vN+1 (hoje N=8, `persistence.py:59`; ver nota de schema no cabeçalho): save v8 com `combat.active=True` ganha manifesto
  derivado de `state["enemies"]` (`source="legacy_migrated"`, `phase="active"`); save sem
  combate ativo ganha `phase="ended"`/`outcome=null` sem `encounter`. Round-trip com
  fixtures v8 reais.

### Fora de escopo

- Remoção de XP da prosa e o evento estruturado de XP (SPEC-199).
- Interação gesto→alvo e `valid_targets` por carta (SPEC-205); layout de abas/split (SPEC-204);
  menu Combate/deck (SPEC-209); efeitos visuais (SPEC-208).
- Balanceamento: dano, IA tática, orçamento numérico, "spam de estratégia", inimigos sem dano
  (pressão tática do HISTORICO_SPEC-183 — fica para spec própria após medição).
- Combat simulator (`combat_simulation`) além de não quebrá-lo; ele não precisa de manifesto
  narrativo, mas recebe `phase/outcome` para paridade.
- Codex/Bestiário assíncronos: o combate **não** depende deles (prompt 04).

## 3. Design técnico

**Arquivos novos**

- `services/encounter_manifest.py` — schema + funções puras:
  - `class EncounterParticipant(BaseModel)`: `participant_id: str`, `bestiary_id: str = ""`,
    `species_label: str`, `faction_id: str = ""`, `categoria: str = "padrao"`,
    `role: Literal["hostile","ally","neutral","hazard"] = "hostile"`,
    `presence: Literal["present","arrived","departed"] = "present"`, `zone_id: str = "z0"`,
    `status: Literal["ativo","morto","fugiu","rendido","capturado","ausente"] = "ativo"`.
  - `class EncounterCompositionEvent(BaseModel)`: `kind: Literal["joined","cut","dead","fled",
    "surrendered","captured","departed"]`, `participant_id`, `cause: str`, `round: int`, `event_id: str`.
  - `class EncounterManifest(BaseModel)`: `encounter_id: str` (= `combat.instance_id` atual,
    `game_id:epoch:session_action_count`, l.663-667), `origin` (vocabulário de
    `services/combat_origin.ORIGINS`), `source: Literal["systemic","npc_in_scene","threat",
    "scanner","fallback","legacy_migrated","simulation"]`, `target_ref: str`,
    `participants: list[EncounterParticipant]`, `events: list[EncounterCompositionEvent]`,
    `frozen: bool`, `schema: int = 1`.
  - `resolve_canonical_source(state, combat_target, encounter_hint) -> CanonicalSource | None`
  - `build_manifest(enemies, *, source, origin, encounter_id, target_ref, scene) -> dict`
  - `validate_roster(manifest, enemies) -> list[str]` (violações; vazio = ok)
  - `apply_composition(manifest, kind, participant_id, cause, round) -> dict` (idempotente por `event_id`)
  - `transition(combat, to_phase, outcome=None) -> dict` (levanta `InvalidEncounterTransition`)
  - `public_view(manifest, knowledge) -> dict` e `result_view(manifest, summary, turn_outcome) -> dict`
    (`turn_outcome` = `PublicOutcome` da SPEC-199; só referencia `receipt_id`)
- `tests/test_encounter_identity_repro.py` (Etapa 0), `tests/test_encounter_manifest.py`,
  `tests/test_encounter_lifecycle_reload.py`.

**Arquivos alterados**

- `agents/storyteller.py` (~l.464): propagar `combat_encounter_hint = {"enemy_id", "reason",
  "hint"}` junto com `combat_target`.
- `agents/router.py` (~l.226): propagar `combat_target_ref` quando o alvo casa com NPC em cena.
- `agents/combat.py`: `_spawn_v4_enemies` passa a consultar `resolve_canonical_source`
  antes do scanner; `_apply_encounter_budget` emite eventos de composição; `combat_node`
  grava/valida manifesto, chama `transition`, emite `combat_result`; `_narrate` recebe
  nomes canônicos.
- `encounter_budget.py`: `clamp_encounter`/`fill_encounter` passam a retornar também a lista
  de ids cortados/adicionados (aditivo; logs atuais mantidos).
- `state.py`: documentar `combat.encounter`, `combat.phase`, `combat.outcome`,
  `combat_result`, `combat_encounter_hint`, `combat_target_ref`.
- `persistence.py`: `SCHEMA_VERSION=9`, `_migrate_v8_to_v9`.
- `api.py`: `_combat_block` (l.1408) inclui `phase`, `encounter_id`, `encounter_view`;
  resposta do turno inclui `combat_result` quando presente; rota `Continuar` = ação local
  do cliente (não chama o grafo) — ver §8, D-C.
- `web/src/types.ts`: `CombatBlock.phase`, `CombatBlock.encounter_id`, `CombatResultView`.
- `web/src/components/` — componente de desfecho (nome a definir pelo executor, ex.
  `CombatOutcomePanel.tsx`), montado onde hoje a UI de combate vive; posicionamento final
  respeita SPEC-204 quando existir (sem terceira coluna).
- `services/prose_guard.py`: verificação de espécie (R9).
- `playtest/invariants.py`: invariante `encounter.identity_drift` (`error`) e
  `encounter.phase_stuck` (`error`, fase ≠ `ended` com `active=False`).

**State ownership.** Dono canônico do manifesto: `combat_node` (escrita) +
`services/encounter_manifest` (regras). Router e storyteller só **propõem** referências
(`combat_encounter_hint`, `combat_target_ref`), one-shot, zeradas pelo combat como já ocorre
com `combat_origin_hint` (l.991). API e frontend são somente leitura. `combat_result` é
transitório por turno; o histórico durável é o `conflict_summary` + `pending_world_events`.

**Contrato de dados (exemplo).**

```json
{"combat": {"phase": "active", "outcome": null, "instance_id": "g1:0:42",
  "encounter": {"encounter_id": "g1:0:42", "origin": "travel_encounter",
    "source": "systemic", "target_ref": "<enemy_id do bestiário>", "frozen": true,
    "participants": [{"participant_id": "<enemy_id>_1", "bestiary_id": "<enemy_id>",
      "species_label": "<nome do bestiário>", "faction_id": "", "categoria": "padrao",
      "role": "hostile", "presence": "present", "zone_id": "z0", "status": "ativo"}],
    "events": []}}}
```

IDs concretos nos testes vêm de `data/bestiary.json` via grep do executor (não inventar).

**Contrato de UI.** Durante `entering|active|resolving` o cliente mostra o elenco a partir
de `encounter_view` (ordem e nomes estáveis). Em `ended`, mostra o painel de desfecho até o
jogador clicar "Continuar"; o draft do composer é preservado; nenhum valor de XP aparece
no balão de chat.

**Degradação/fallback.** Scanner falha → `source="fallback"` (comportamento atual).
Manifesto ausente/corrompido num save → reconstruído de `state["enemies"]` com
`source="legacy_migrated"` + log; nunca crasha. `validate_roster` com violação em produção
→ mantém o manifesto como verdade, descarta o participante intruso e registra evento
`cut` com `cause="roster_violation"`. Guard de FallbackLLM permanece no scanner (l.187).

## 4. Plano passo a passo (TDD)

### Etapa 0 — Reprodução do bug de identidade (obrigatória, sem mudar regra)

1. **Testes** (`tests/test_encounter_identity_repro.py`), cada um isolando uma hipótese:
   - `test_h1_scanner_le_fauna_da_prosa` [H]: `messages[-2:]` com bandidos + corvos na
     prosa, hint "bandidos" → MockLLM scanner configurado para devolver o que a prosa lista;
     asserta se o elenco perde o bandido.
   - `test_h2_budget_corta_bandido_e_injeta_fauna` [H]: 2 bandidos + budget baixo em local
     com fauna regional → `clamp` por variedade + `fill` com `pick_encounter_enemy`.
   - `test_h3_librarian_dedupe_mapeia_outra_especie` [H]: stub de `find_existing_entity`
     devolvendo id de outra criatura para "Bandido".
   - `test_h4_enemy_id_sistemico_descartado` [F→teste]: encontro sistêmico com
     `enemy_id` X → elenco final não contém X quando o scanner nomeia outra coisa.
   - `test_h5_prosa_renomeia_sem_mudar_estado` [H]: narração mock chama participante de
     outra espécie; asserta estado intacto (isola bug narrativo de bug de estado).
   - `test_h6_reload_preserva_elenco`: save/reload no meio do combate mantém ids/nomes.
   - `test_h7_inimigo_ativo_nao_causa_dano` [H] (problema "inimigos às vezes não causam
     dano" do prompt 04): N rodadas com seed fixa e inimigo `ativo` em alcance → asserta que
     cada inimigo ativo declara e resolve uma ação (`TacticalProfile.pick_action`) e que há
     dano >0 em ≥1 rodada com acerto. **Só diagnóstico:** se reproduzir bug (ação descartada,
     alvo nulo, declaração perdida), corrigir aqui com teste; se for balanceamento/rolagem,
     registrar em `repro.md` e encaminhar à spec de pressão tática (fora de escopo, §2).
2. **Registro:** marcar as que reproduzem como `xfail(strict=True)` com motivo; anexar
   relatório curto em `docs/spec203/repro.md` (qual hipótese reproduziu, seed, traço).
3. **Gate:** se nenhuma reproduzir, parar e devolver ao dono (§8, D-A).

### Etapa 1 — Schema e funções puras do manifesto

- **Testes** (`tests/test_encounter_manifest.py`): `test_build_manifest_campos`,
  `test_participante_imutavel_apos_freeze`, `test_validate_roster_intruso`,
  `test_apply_composition_idempotente`, `test_transicoes_validas_e_invalidas`,
  `test_public_view_nao_vaza_oculto` (respeita `bestiary_knowledge`/ocultação).

### Etapa 2 — Spawn por fonte canônica

- **Testes:** `test_spawn_usa_enemy_id_sistemico_sem_scanner` (spy: 0 invokes CLASSIFY),
  `test_spawn_npc_em_cena_vira_participante`, `test_scanner_so_como_fallback_validado`,
  `test_fallback_sombrio_marca_source`. Converter H1/H4 de `xfail` para verdes.
- **Implementação:** storyteller/router propagam hint/ref; `_spawn_v4_enemies` resolve.

### Etapa 3 — Composição por evento e leitura por rodada

- **Testes:** `test_budget_emite_eventos_cut_joined`, `test_rodada_sem_llm_classify`,
  `test_saida_so_com_evento` (morte/fuga/rendição/captura), converter H2/H3.

### Etapa 4 — State machine e retorno à exploração

- **Testes** (`tests/test_encounter_lifecycle_reload.py`): fluxo completo
  ameaça→`entering`→2 rodadas com reação/dano→vitória→`ended`→turno seguinte roteado
  para exploração; variantes fuga, rendição inimiga, derrota/morte (death_pending
  intacto), `expired` do router (SPEC-038). Save/reload em cada fase (R11).
  `test_replay_action_id_nao_duplica_resultado` (R10).

### Etapa 5 — API, migração e prosa

- **Testes:** `test_combat_block_expoe_phase_e_view`, `test_combat_result_xp_do_evento_spec199`,
  `test_migracao_v8_combate_ativo` e `test_migracao_v8_sem_combate` com fixtures v8,
  `test_prose_guard_especie_divergente` (converter H5).

### Etapa 6 — Frontend

- Tipos em `types.ts`; painel de desfecho; "Continuar" local. Testes Node/Playwright
  existentes do frontend estendidos com fixture de `combat_result` (sem provider).
  `npm run build` verde.

### Etapa 7 — Invariantes de playtest e suíte

- `encounter.identity_drift` e `encounter.phase_stuck` em `playtest/invariants.py`;
  smoke offline curto (§6). `uv run pytest` completo verde.

## 5. Critérios de aceite

- [x] `docs/spec203/repro.md` registra quais hipóteses reproduziram no HEAD pré-mudança.
- [x] Todas as hipóteses reproduzidas passam a verde sem `xfail`; H7 (dano de inimigo)
      classificada como bug corrigido ou como balanceamento encaminhado.
- [x] `combat_result.xp_event_ref == turn_outcome.receipt_id` (SPEC-199) e painel de
      desfecho reaparece igual após reload em `ended` antes de "Continuar".
- [x] Zero invokes CLASSIFY em rodadas ≥1 (spy) e no spawn de fonte canônica.
- [x] Elenco do manifesto == elenco da rodada, salvo eventos de composição registrados.
- [x] Fluxo completo ameaça→2 rodadas→terminal→exploração verde para vitória, fuga,
      rendição, derrota/morte e expiração, com save/reload em cada fase.
- [x] Nenhum XP em `messages`/`presentation_history` narrativos; XP do painel vem do
      evento SPEC-199 e é concedido exatamente uma vez sob replay.
- [x] Saves v8 (com e sem combate ativo) carregam e fazem round-trip (v8 aditivo, sem bump — ver nota de schema).
- [x] Guard de FallbackLLM preservado no scanner; nenhum `with_structured_output` novo sem guard.
- [x] `uv run pytest` verde (suíte offline completa); `npm run build` verde.
- [x] Revisão independente Astra aprovada; evals novos autorados em tarefa separada
      (suíte dedicada `encounter_manifest`, 31 casos, `state_transition_pass_rate` 1.0 —
      ver `docs/spec203/README.md` § Evals).

## 6. Smoke

**Offline (obrigatório, MockLLM):**
1. `uv run pytest tests/test_encounter_identity_repro.py tests/test_encounter_manifest.py tests/test_encounter_lifecycle_reload.py tests/test_combat_lifecycle.py tests/test_conflict_summary_lifecycle.py tests/test_cutover_audit.py -q`
2. `uv run python -m playtest run --profile combate --turns 30` e `--profile fujao --turns 30`:
   zero `encounter.identity_drift`/`encounter.phase_stuck`.
3. Browser local (API mock determinística): combate até vitória → painel → "Continuar"
   → composer com draft preservado, sem XP no balão.

**Provider real (opt-in, só com autorização explícita):** 1 campanha `combate` × 10 turnos
em DeepSeek, teto 60 requests / US$ 0,05; verificar que `source` ≠ `scanner` em encontros
sistêmicos e zero drift. Não executar sem pedido do dono.

## 7. Riscos & compatibilidade

- **Saves:** bump v8→v9 com migração; saves com combate ativo recebem manifesto
  `legacy_migrated` (identidade = o que já estava em `enemies`, que é estável).
- **MockLLM esconde mapeamento:** o scanner mock sempre devolve schema válido; por isso
  R2/R3 são validados por spy de invocação, não por strings do mock.
- **Encontros emergentes:** corvos chegando no meio pode ser boa ficção — permitido só via
  evento `joined` com causa, nunca por reclassificação.
- **Latência:** remove 1 invoke CLASSIFY (e possível librarian) por encontro sistêmico; não
  adiciona chamadas.
- **Simulator** (`api.py` ~l.1823) monta `combat` diretamente: recebe `source="simulation"`.
- **SPEC-117/151/038:** origem por cena, replan diferido e expiração permanecem; `expired`
  vira outcome explícito.

## 8. Pontos de decisão do dono

- **D-A — Etapa 0 sem reprodução.** Default recomendado [R]: implementar mesmo assim R1, R2,
  R5–R12 (manifesto, state machine, desfecho) e adiar R3/R4 (mudança de spawn/budget) até
  haver reprodução com transcript real do beta (export da SPEC-207).
- **D-B — Fauna "atraída pelo tumulto" (`fill_encounter`).** Default [R]: manter a regra
  numérica, mas tornar o reforço um evento `joined` visível e narrado na entrada; não
  cortar participante canônico (alvo resolvido) por variedade no `clamp`.
- **D-C — "Continuar" consome turno?** Default [R]: não; é ação local do cliente que só
  fecha o painel. O próximo turno textual é roteado como exploração.

## 9. Evidência requerida

- `docs/spec203/repro.md` (Etapa 0) com seed, hipótese e traço por caso.
- Saída de `uv run pytest` completa + lista dos testes novos.
- Summary JSON dos dois playtests offline (run_id) com contagem zero das invariantes novas.
- Screenshot/trace do painel de desfecho (desktop 1440) com "Continuar".
- Diff da migração + fixture v8 usada.
- Parecer Astra em `handoffs/SPEC-203-ASTRA-independent-review.md`.
- Handoff de autoria de evals (`handoffs/SPEC-203-eval-authoring.md`) — tarefa separada.

**Status da evidência (2026-10-16):** atendida. Autoria de evals concluída em commit
separado (`test(evals): author encounter manifest cases for SPEC-203`): dataset novo
`evals/datasets/regression/encounter_manifest.jsonl` (31 casos fixture-authored, sem LLM)
+ `EncounterManifestAdapter`; casos antigos de `state_rules`/`narrative_npc` intocados.
Relock oficial, `governance check` verde, todas as suítes do CI verdes. Publicar exige
aprovação do environment `eval-governance`.

## 10. Registro de execução (2026-10-16)

- **Etapa 0:** H1, H2, H2b, H3, H4 reproduziram bug de estado no HEAD `50d4620`; H5 só narrativo
  (H5b: guard ausente); H6/H7 não reproduziram (H7 = sem bug; nada encaminhado à pressão tática).
  Detalhe em `docs/spec203/repro.md`. Como houve reprodução, **D-A não se aplicou** (R3/R4 feitos).
- **Defaults de decisão usados:** D-B (reforço vira evento `joined`/`arrived`; alvo canônico
  protegido da variedade no clamp; regra numérica intacta); D-C ("Continuar" é ação local, não
  consome turno, preserva o draft).
- **Desvios:** (1) sem bump de schema (ver nota). (2) `clamp_encounter` ganhou kwarg opcional
  `protected`; os ids cortados/adicionados são derivados no chamador (`_apply_encounter_budget`
  report) em vez de mudar a tupla de retorno — evita quebrar chamadores. (3) "Zero CLASSIFY nas
  rodadas ≥1" vale com declaração estruturada (UI/harness); a fala livre do jogador continua
  sendo identificada por CLASSIFY (identifica ação, não elenco). (4) `{}` (jogo que nunca teve
  combate) permanece `{}` no load. (5) `combat.result` guarda o snapshot persistido do desfecho;
  `turn_finalizer` carimba `xp_event_ref` uma vez. (6) Nome canônico por token exato do bestiário
  (`resolve_bestiary_name`) é tratado como fonte (c) `threat`; `reinforcements/controlled`
  também viram `threat`.
- **Smoke real** (DeepSeek, ≤10 turnos autorizados): ver `docs/spec203/README.md`.
- **Fechamento:** revisão Astra aprovada (2 correções); autoria dos evals concluída
  (suíte `encounter_manifest`) — status `done`.
