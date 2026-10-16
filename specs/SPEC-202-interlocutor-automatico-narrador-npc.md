# SPEC-202 — Interlocutor automático narrador × NPC

> **Status:** `done` (implementação + smoke real + revisão Astra independente; mudança de save ADITIVA, sem bump de schema — ver §10)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-228 `done` (R9 recusa save mais novo antes do 1º bump de schema), SPEC-229 `done` (mesmo `agents/router.py`; parsers de intenção primeiro), SPEC-230 `done` (NPC vivo/em cena confiável) · SPEC-041, SPEC-149, SPEC-169, SPEC-186, SPEC-187 `done` (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-212, SPEC-215 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 07
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver `docs/planos/equivalencia-modelos-claude.md`)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — corpus `routing.interlocutor.*` (casos de interlocutor + `speaker_kind`/`speaker_id` esperados), autoria em tarefa separada ligada à SPEC-169; quem implementa esta spec não edita `evals/datasets/regression/routing_actions.jsonl` nem `evals/evaluators/routing.py`.
> **Nota de schema (cadeia final 2026-10-15):** ordem dos bumps de `SCHEMA_VERSION` (hoje 8): SPEC-228 primeiro (R9 recusa save de versão mais nova; sem bump) → [SPEC-227 só se D-C = migração; default sem bump] → SPEC-202 → SPEC-203 → SPEC-207 → SPEC-213 → SPEC-215. Nenhuma outra spec 199–236 altera o schema de save (SPEC-228 R7 `needs_replan` e SPEC-231 `scene_allies` usam default/campo existente, sem bump). Cada spec usa o próximo `SCHEMA_VERSION` livre no HEAD ao implementar e encadeia sua migração após a anterior; onde o texto disser "v8→v9", leia "vN→vN+1". **Atualização 2026-10-16 (revisão Astra): a SPEC-202 SAIU da cadeia de bump** — `last_speaker`/`speaker_*` são aditivos (default no load, rótulo legado derivado na leitura); `SCHEMA_VERSION` segue 8 e o próximo bump da cadeia é o da SPEC-203.

Rótulos: **[F]** fato observado no HEAD `6b94f66` · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[D]** O jogo é chat-first e o interlocutor é inferido da linguagem natural e do contexto. **Não existe** botão/seletor obrigatório "Narrador/NPC" (`DECISOES_PRODUTO.md` § Narrador/NPC). A proposta histórica `historico-nao-executar/HISTORICO_SPEC-178-*` (seletor explícito) e o seletor do `design-html/rpg-design-system-chat-first-v01.html` contradizem essa decisão e **não são adotados**.

**[F]** Hoje `agents/router.py::dm_router_node` decide nesta ordem: (1) `_combat_gate` se `combat.active`; (2) `services.actor_lifecycle.is_recovery_turn` → STORY; (3) `_EXPLICIT_STORY_RE` (descanso/viagem) → STORY; (4) `services.jev_rollout.decide_route` (default `off`, SPEC-180) → STORY apenas se Jev decidir STORY; (5) uma chamada CLASSIFY com `RouterDecision{route, loot_context, target, reasoning, confidence}` sobre `messages[-3:]`. O prompt CLASSIFY só diz "NPC: Conversa social, diplomacia" — **não há regra** para "pergunta ao narrador sobre um NPC", nem lista de quem está em cena.

**[F]** Resolução de `active_npc_name` (rota NPC, `router.py` ~L199–221): substring entre `decision.target` e `npc_layers.npcs_in_scene(state)`; senão, se há exatamente 1 NPC em cena, ele; senão **`decision.target` cru** ("deixa o ator tentar carregar do DB"). **[F]** Em `agents/npc.py::npc_actor_node`, um nome que não está no estado é buscado em `load_npc_db()` e, se ausente, **gerado na hora** por `generate_new_npc(npc_name, ...)` e marcado `in_scene=True`. Consequência: um alvo alucinado ou um NPC ausente vira **identidade nova em cena** falando com voz própria — viola SPEC-149 (identidade canônica) e a regra de produto "NPC ausente → narrador explica". **[F]** NPC conhecido no estado com `in_scene=False` já recebe resposta determinística `"🗣️ X não está aqui."` (camada 3, SPEC npcs-3-camadas), e rota NPC sem candidato delega ao storyteller via `npc_fallback_hint` (SPEC-041) — esses dois caminhos ficam.

**[F]** O resultado do turno não carrega quem falou: `services/presentation_history.py::record_history` grava linhas `role ∈ {player, narrator}` com `type` derivado da rota (`message_kind`); `GameResponse` (`api.py` L1028) expõe só `message_type`; o cliente (`web/src/lib.ts::roleLabel`) rotula NPC como "Diálogo" genérico. A identidade do falante só existe no texto (`**Nome:**` em `npc.py`).

**[F]** Voz: SPEC-186 (STT servidor) e SPEC-187 (`web/src/voice/useVoiceInput.ts`, usado por `PlayScreen.tsx`) já transcrevem para o composer editável, sem autoenvio. Esta spec **não toca** voz; transcrições chegam como texto comum e entram no corpus de casos.

**Objetivo:** política de interlocutor **determinística em Python + o CLASSIFY já existente (zero chamada LLM extra)**, que nunca cria identidade NPC a partir de alvo não resolvido, que encaminha meta-perguntas ao narrador, e que publica um `speaker` canônico no resultado do turno e na projeção de apresentação, consumido pela UI como indicador **passivo** de "quem respondeu".

## 2. Requisitos

- **R1 — Zero chamada extra.** Para qualquer entrada, o número de invocações LLM do router é ≤ o atual (0 ou 1 CLASSIFY). A política nova é Python puro antes e depois do CLASSIFY existente; nenhum structured output novo.
- **R2 — Meta-pergunta ao narrador.** Entrada que se dirige ao narrador (ex.: "Pergunto ao narrador o que a Velha Magda sente", "Narrador, a Brunna parece mentir?", marcador OOC `(( ))`/"fora do jogo") roteia **STORY** com `speaker.kind="narrator"` e `mediated_subject_id` = id canônico do NPC citado; o `npc_actor` **não roda** e não há fala em primeira pessoa do NPC. Decidido em Python **sem** chamar CLASSIFY.
- **R3 — Descrição de cena.** "Descreva a taverna", "o que vejo/ouço", "quem está aqui?" nunca resultam em `speaker.kind="npc"`, mesmo se o CLASSIFY devolver NPC (override pós-CLASSIFY por regra de descrição).
- **R4 — Fala direta a NPC presente.** Vocativo ("Brunna, ..."), "pergunto/digo/falo a/com <nome>", ou fala entre aspas com NPC resolvido em cena roteia **NPC** com `active_npc_name` = chave de estado resolvida por `entity_identity.find_runtime_npc_key` + aliases (SPEC-149), e `speaker.id` = id canônico desse NPC.
- **R5 — Sem identidade a partir de alvo cru.** O router **nunca** propaga `decision.target` não resolvido para `active_npc_name`. Alvo com nome próprio que não resolve para NPC em cena: (a) NPC conhecido fora de cena → mantém resposta determinística "não está aqui" do `npc_actor` (`speaker.kind="narrator"`); (b) nome desconhecido/alucinado → STORY com `npc_fallback_hint` e cláusula de ausência (SPEC-041 R2). `generate_new_npc` só é alcançável pela exceção de R6.
- **R6 — Papel genérico (exceção controlada).** Alvo que é papel genérico (lista fechada em Python: taverneiro, guarda, mercador, ferreiro, sacerdote, barqueiro…) sem NPC em cena com esse papel pode gerar NPC como hoje, **somente** se o local atual for assentamento (não-ermo) — ver decisão §8 P2. Proper names nunca entram aqui.
- **R7 — Múltiplos NPCs.** Com ≥2 NPCs em cena: nome/alias/vocativo explícito decide; sem nome, continua com o `last_speaker` NPC se ele ainda estiver em cena e o último turno NPC foi ≤ 2 ações atrás; senão **narrador media** (STORY, cláusula que apresenta quem está presente e reage) — sem pergunta de esclarecimento por default (§8 P1).
- **R8 — Pronome/ambiguidade.** "Pergunto a ela/ele", "e você?" resolvem para `last_speaker` em cena (mesmas condições de R7); sem candidato único → narrador media. Nunca há troca silenciosa de falante entre NPCs sem nome/vocativo.
- **R9 — `speaker` canônico.** Todo turno finalizado tem `speaker = {kind: "narrator"|"npc"|"system", id: str, name: str, reason: <código fechado>}`: `narrator` → `id="narrator"`; `npc` → id canônico (`entity_identity.resolve_npc_entity_id`, senão chave de estado normalizada); `system` → recusas determinísticas de ação (`last_action_outcome.allowed=False`). Persistido em `state["last_speaker"]`, em cada linha `narrator` de `presentation_history` e exposto em `GameResponse.speaker` (POST, SSE final, `/game/state`, `/game/history`).
- **R10 — Identidade estável.** Para o mesmo NPC, `speaker.id` é idêntico entre turnos, entre alias usados pelo jogador e após save→load; nunca é um id que não existe em `state.npcs`/party/catálogo canônico.
- **R11 — Segredo na mediação.** Quando o narrador responde sobre um NPC (R2/R7/R8), o contexto do sujeito vem só da camada pública (`npc_layers.visible_npc_view`: nome, papel, relação, `revealed_traits`, última memória) — nunca `hidden_traits`, memória privada não revelada nem docs `hidden/secret`. A narração final passa por `secret_signatures.find_unrevealed`; havendo assinatura não revelada, o parágrafo é substituído por descrição observável neutra determinística e o caso é registrado em `narrative_rejections` (padrão SPEC-091).
- **R12 — Precedência preservada.** `_combat_gate`, recovery, `_EXPLICIT_STORY_RE`, `jev_rollout` e comandos de party (`party.detect_party_command` dentro do `npc_actor`) mantêm precedência e comportamento atuais; testes existentes de router/npc/fallback seguem verdes sem edição de expected.
- **R13 — UI passiva.** O cliente mostra o rótulo de quem respondeu (nome do NPC ou "Narrador") a partir de `speaker`, sem botão/seletor, sem alterar composer nem voz.
- **R15 — Nome e referência consistentes (prompt 07: "pronomes inconsistentes").** [F] Os NPCs não têm
  campo de gênero/pronome em `state.npcs` nem em `services/entity_identity.py`/`npc_layers.py`. Nesta spec:
  (a) a linha `**Nome:**` do `npc_actor` e o `speaker.name` usam o nome canônico do NPC (nunca o alias digitado
  pelo jogador nem o `decision.target` do CLASSIFY); (b) a cláusula de mediação e o prompt do NPC recebem o nome
  canônico e, **se** o registro do NPC já tiver campo de pronome/gênero, esse valor; (c) teste
  `test_speaker_name_canonico_com_alias` asserta (a). Concordância de pronome na prosa livre não é gate
  determinístico aqui (exigiria campo novo de dado): vira caso candidato do eval narrativo (Etapa 6) e decisão P4.
- **R14 — Degradação.** CLASSIFY falho/`FallbackLLM`/`AIMessage` → STORY com `speaker.kind="narrator"` (comportamento atual, agora rotulado). MockLLM continua jogável.

### Fora de escopo

- Seletor explícito de interlocutor (rejeitado, [D]). Mudanças em STT/voz (SPEC-186/187).
- Conversa com NPC durante combate ativo (SPEC-038 R2 continua bloqueando).
- Conhecimento por NPC/propagação de rumores (SPEC-215) e taxonomia fato/suspeita/rumor (SPEC-206).
- Dossiês/retrato do falante na UI (SPEC-211); split/abas (SPEC-204).
- Alterar `RouterDecision` (schema usado pelo adapter da SPEC-169) — [R] manter intacto.
- Editar datasets/evaluators protegidos (`evals/protected-paths.txt`).

## 3. Design técnico

### Arquivos novos

- `services/interlocutor.py` — política pura, sem LLM, sem I/O:

```python
SpeakerKind = Literal["narrator", "npc", "system"]
ReasonCode = Literal[
    "meta_to_narrator", "scene_description", "direct_address", "quoted_vocative",
    "single_in_scene", "continuity_last_speaker", "ambiguous_multi_mediated",
    "npc_absent_known", "npc_unknown_absent", "generic_role_spawn",
    "classify_story", "classify_fallback", "action_refused",
]

@dataclass(frozen=True)
class InterlocutorResolution:
    route: str                       # RouteType.value
    speaker_kind: SpeakerKind
    npc_state_key: str | None        # chave em state["npcs"]/party; só se speaker_kind=="npc" ou absent_known
    mediated_subject_id: str | None  # NPC de quem o narrador fala (R2/R7/R8)
    reason: ReasonCode
    fallback_hint: str | None        # vira npc_fallback_hint quando npc_unknown_absent

def pre_classify(state: dict, text: str) -> InterlocutorResolution | None: ...
    # R2/R3 deterministas; None = seguir para CLASSIFY
def post_classify(state: dict, text: str, route: str, target: str | None) -> InterlocutorResolution: ...
    # R3–R8 sobre a decisão do CLASSIFY
def speaker_for_turn(state: dict) -> dict: ...  # R9: {kind,id,name,reason}
```

Regras (ordem fixa): marcadores de meta (`narrador`, `mestre`, `(( ))`, `fora do jogo`, `ooc`) → `meta_to_narrator`; padrões de descrição (`descrev\w*`, `o que (vejo|ouço|sinto)`, `quem está aqui`) → `scene_description`; vocativo inicial `^<alias>[,:]` ou `(pergunto|digo|falo|respondo|peço)\s+(a|à|ao|para|com)\s+<alias>` → `direct_address`; texto entre aspas + alias citado → `quoted_vocative`. "Sobre <nome>" sem verbo de fala direta é **meta** (narrador), não fala ao NPC. Matching de alias usa `entity_identity.runtime_npc_aliases`/`normalize_runtime_npc_ref` sobre `npcs_in_scene(state)` (nunca substring livre de 1–2 letras: mínimo 3 caracteres e fronteira de palavra).

### Arquivos alterados

- `agents/router.py` — chamar `pre_classify` logo após o gate `jev_rollout` e antes do CLASSIFY (se resolver, retorna sem LLM); acrescentar ao prompt CLASSIFY a lista de NPCs em cena e a regra "pergunta ao narrador sobre alguém = STORY" (mesma chamada, sem campo novo); substituir o bloco L199–221 por `post_classify`; remover o fallback `chosen = decision.target`. Gravar `interlocutor_reason` e `mediated_subject_id` no payload (transitórios, zerados em `_base_route_payload`).
- `agents/npc.py` — `generate_new_npc` só quando o payload do router marcar `generic_role_spawn` (R6); demais nomes não resolvidos delegam ao storyteller (`npc_fallback_hint`). Caminho "não está aqui" inalterado.
- `agents/storyteller.py` — nova cláusula pura `_mediation_clause(state)` (análoga a `_npc_fallback_clause`) com o recorte público do sujeito via `visible_npc_view`; pós-checagem `secret_signatures.find_unrevealed` na narração mediada (R11).
- `services/presentation_history.py` — `record_history` grava `speaker_kind`, `speaker_id`, `speaker_name` na linha `narrator` (linhas antigas sem campo leem como narrador, ou `npc` sem id quando `type=="NPC"`).
- `services/turn_outcome.py` — `finalize_outcome` inclui `speaker` (via `speaker_for_turn`).
- `state.py` — `last_speaker: Optional[Dict[str, str]]`; `interlocutor_reason`, `mediated_subject_id` transitórios.
- `api.py` — `GameResponse.speaker: Dict[str, str] = {}` preenchido por `format_response`; `/game/history` devolve os campos novos.
- `web/src/types.ts` (`speaker?` em `GameResponse`/entrada de log), `web/src/lib.ts::roleLabel` (usa `speaker.name` quando `kind=="npc"`), componente da linha do StoryLog — só rótulo; sem controle novo.

### Contratos de dados

```json
// GameResponse.speaker / last_turn_outcome.speaker / presentation_history[].speaker_*
{"kind": "npc", "id": "npc_brunna_ponte_alta", "name": "Brunna Ponte-Alta", "reason": "direct_address"}
{"kind": "narrator", "id": "narrator", "name": "Narrador", "reason": "meta_to_narrator"}
```

[H] o id canônico do exemplo segue o formato de `resolve_npc_entity_id`; verificar o id real no catálogo antes de fixar fixtures.

### State ownership

- `last_speaker`: escrito **só** por `turn_outcome.finalize_outcome` (fim do turno), lido por `interlocutor.post_classify` (continuidade R7/R8). Persistido no save.
- `interlocutor_reason`/`mediated_subject_id`: escritos pelo router, consumidos no mesmo turno por npc/storyteller/`speaker_for_turn`; zerados a cada rota (mesmo padrão de `active_npc_name`).
- `presentation_history[].speaker_*`: append-only por `record_history`.

### Degradação

CLASSIFY falho → `classify_fallback` (narrador). Alias não resolvido → narrador (nunca NPC inventado). Linha de histórico legada sem `speaker_*` → rótulo derivado de `type` (comportamento atual). `secret_signatures` sem hit → texto intacto.

## 4. Plano passo a passo (TDD)

### Etapa 1 — Política pura
1. **Testes** `tests/test_interlocutor.py`: `test_meta_narrador_sobre_npc_vai_story` (sem CLASSIFY: LLM fake conta 0 invokes); `test_sobre_nome_sem_verbo_de_fala_e_meta`; `test_descricao_de_cena_nunca_npc` (CLASSIFY fake devolve NPC → STORY); `test_vocativo_npc_presente`; `test_aspas_com_alias`; `test_alias_curto_nao_casa`; `test_nome_alucinado_nao_vira_active_npc`; `test_npc_conhecido_fora_de_cena_reason_absent_known`; `test_multiplos_sem_nome_continuidade`; `test_multiplos_sem_nome_sem_continuidade_media`; `test_pronome_resolve_last_speaker`; `test_pronome_sem_candidato_media`; `test_papel_generico_em_assentamento_spawn`; `test_papel_generico_em_ermo_nao_spawn`; `test_texto_transcrito_com_pausas` ("é... Brunna... você viu o barco?"); `test_pergunto_a_nome_presente_vai_npc` ("Pergunto a <nome> ..." = fala direta, contraste com "sobre <nome>"); `test_npc_ausente_nunca_fala_em_primeira_pessoa`; `test_speaker_name_canonico_com_alias` (R15).
2. **Implementação:** `services/interlocutor.py`.

### Etapa 2 — Fiação no router e no ator
1. **Testes** `tests/test_router_interlocutor.py`: `test_ordem_precedencia_preservada` (combat/recovery/viagem/jev antes da política); `test_zero_invoke_extra` (contador ≤ 1 em todos os casos de Etapa 1); `test_prompt_classify_lista_npcs_em_cena`; `test_npc_actor_nao_gera_npc_sem_generic_role`; `test_party_command_preservado`.
2. **Implementação:** `agents/router.py`, `agents/npc.py`.
3. Rodar `tests/test_npc_fallback.py`, `tests/test_encontros_dedupe.py`, `tests/test_aliados_combate.py` e testes de router existentes **sem alterar expected**.

### Etapa 3 — Mediação segura
1. **Testes** `tests/test_mediation_secret.py`: `test_mediacao_usa_visible_npc_view` (hidden_traits ausentes do prompt montado); `test_mediacao_com_assinatura_nao_revelada_substitui_paragrafo`; `test_mediacao_segredo_ja_revelado_passa` (`known_secrets`).
2. **Implementação:** `_mediation_clause` + pós-checagem no storyteller.

### Etapa 4 — `speaker` no resultado, histórico, API
1. **Testes** `tests/test_speaker_contract.py`: `test_speaker_em_post_e_sse_identicos`; `test_speaker_id_estavel_entre_aliases`; `test_speaker_round_trip_save_load`; `test_history_legado_sem_speaker_carrega` (fixture de save antigo real em `tests/fixtures/`); `test_recusa_de_acao_speaker_system`.
2. **Implementação:** `turn_outcome`, `presentation_history`, `state.py`, `api.py`.

### Etapa 5 — UI passiva
1. **Testes**: teste Node/TS de `roleLabel` com `speaker`; E2E Chromium existente do StoryLog estendido para checar rótulo "Brunna Ponte-Alta" (API determinística da SPEC-172) — sem seletor no DOM (`getByRole('radio'|'tab', {name:/narrador/i})` ausente).
2. **Implementação:** `web/src/types.ts`, `web/src/lib.ts`, linha do log.

### Etapa 6 — Handoff de eval
Preparar `handoffs/SPEC-202-eval-authoring.md` listando os casos da Etapa 1 como candidatos `routing.interlocutor.*` com `expected.route`, `expected.speaker_kind`, `expected.target` (chave canônica ou null). Não editar `evals/`.

## 5. Critérios de aceite

- [x] R1: teste de contagem prova ≤ 1 invoke CLASSIFY por turno de router em todos os casos; meta/descrição com 0.
- [x] R2/R3: meta-pergunta e descrição de cena nunca produzem `speaker.kind="npc"` nem linha `**Nome:**`.
- [x] R5: nenhum caminho do router entrega `decision.target` não resolvido ao `npc_actor`; `generate_new_npc` só chamado com `generic_role_spawn`.
- [x] R7/R8: casos de múltiplos NPCs e pronomes resolvem por regra documentada; ambiguidade → narrador.
- [x] R9/R10: `speaker` presente e idêntico em POST, SSE final, `/game/state` e `/game/history`; estável entre aliases e save→load.
- [x] R11: nenhum `hidden_traits`/assinatura não revelada em narração mediada (teste com fixture de segredo de `secret_signatures`).
- [x] R12: suítes existentes de router, npc_fallback, encontros_dedupe, aliados e SPEC-169 (`uv run python -m evals run --suite routing`) verdes sem mudança de expected.
- [x] R15: `speaker.name` e o prefixo `**Nome:**` usam o nome canônico mesmo quando o jogador usa alias.
- [x] R13: UI sem seletor; rótulo do falante visível em 390/1440 px.
- [x] Saves antigos carregam; `presentation_history` legado exibe rótulo derivado.
- [x] `uv run pytest` verde (suíte completa offline); Ruff verde; `npm run build` verde. — após a conversão aditiva (sem bump) a suíte completa fecha exit 0, inclusive `test_eval_state_rules` (schema v8 intacto).
- [x] Handoff de eval escrito (`handoffs/SPEC-202-eval-authoring.md` ✔); revisão Astra independente concluída (2026-10-16, ver §10).

## 6. Smoke

**Offline (obrigatório, MockLLM):** `uv run pytest tests/test_interlocutor.py tests/test_router_interlocutor.py tests/test_mediation_secret.py tests/test_speaker_contract.py -q`; depois `uv run python -m playtest run --profile npc_only --turns 10` e `--profile diplomatico --turns 10` com zero erro/violação e nenhum NPC criado com nome não presente no estado inicial (checar `npcs` do save final).

**Real (opt-in, só com autorização explícita):** DeepSeek, teto **15 requests / US$ 0,05**. Sequência em cena com Brunna + Velha Magda: (1) "Brunna, você viu o barco?" → NPC Brunna; (2) "Pergunto ao narrador o que a Velha Magda sente" → narrador, 0 invoke de router; (3) "E você?" → continuidade Brunna; (4) "Falo com Halveth" (inexistente) → narrador explica ausência, nenhum NPC novo em `npcs`; (5) "Descreva quem está aqui" → narrador. Registrar `speaker` de cada turno.

## 7. Riscos & compatibilidade

- **Saves:** campos novos opcionais com default na leitura; sem bump de `schema_version` se `_MIGRATIONS` não exigir — [R] confirmar e, se o loader validar chaves, adicionar migração idempotente + teste round-trip com save legado. Se houver bump, ele entra na cadeia coordenada de `SCHEMA_VERSION` da onda (nota de schema das SPEC-203/207/213/215: usar o próximo número livre no HEAD e encadear após a migração anterior; nunca fixar "v9").
- **Regressão de roteamento:** regras léxicas podem capturar falsos positivos ("o narrador da taverna" como personagem). Mitigação: meta exige marcador no início ou verbo dirigido ("pergunto ao narrador"); casos negativos no corpus.
- **Menos NPCs emergentes:** R5 reduz geração espontânea por nome próprio; R6 mantém papéis genéricos. [H] pode reduzir variedade em playtests `npc_only`; medir criação de NPC antes/depois.
- **MockLLM esconde mapeamento:** `RouterDecision` não muda, risco baixo; ainda assim smoke real recomendado antes de `done`.
- **Latência:** pre_classify economiza 1 CLASSIFY em meta/descrição; sem custo extra.
- **Jev:** `jev_rollout` permanece antes da política; em `off` (default) sem efeito.

## 8. Pontos de decisão do dono

- **P1 — Esclarecimento em ambiguidade.** Default recomendado: **narrador media** (descreve quem está presente e reage), sem pergunta de esclarecimento. Alternativa: narrador termina com pergunta curta "A quem você se dirige?" só quando ≥2 NPCs e texto tem verbo de fala direta sem alvo.
- **P2 — Papel genérico gera NPC?** Default recomendado: sim, só em assentamento (local com mercado/serviço no `world_map.json`) e só para lista fechada de papéis; em ermo, narrador explica ausência.
- **P4 — Campo de pronome do NPC.** Default recomendado: **não** adicionar campo de dado nesta spec; se o
  export beta (SPEC-207) mostrar deriva de pronome recorrente, abrir spec de dados para `pronouns` opcional
  em NPC curado/gerado (migration-safe). Alternativa: adicionar já `pronouns` opcional gerado por
  `generate_new_npc` (+1 campo no structured output existente, com guard).
- **P3 — Janela de continuidade** (R7/R8). Default: último turno NPC ≤ 2 ações atrás e NPC ainda `in_scene`.

## 9. Evidência requerida

- Saída `uv run pytest` completa (contagem passed/skipped/deselected) e dos 4 arquivos novos.
- Tabela caso→rota→`speaker`→nº invokes dos casos da Etapa 1.
- Diff mostrando remoção de `chosen = decision.target` em `agents/router.py`.
- Playtest offline `npc_only`/`diplomatico` com run_id, zero violação e contagem de NPCs criados.
- Captura do StoryLog com rótulo do falante (desktop e 390 px) e asserção de ausência de seletor.
- Handoff de eval (`handoffs/SPEC-202-eval-authoring.md`) e parecer Astra.
- Se o smoke real for autorizado: run_id, requests/custo dentro do teto e `speaker` por turno.

## 10. Execução (2026-10-16)

Evidência: [docs/spec202/README.md](../docs/spec202/README.md).

**Defaults de decisão usados (§8):** P1 narrador media (sem pergunta de
esclarecimento); P2 papel genérico só gera NPC em assentamento (tag de local
cidade/favela/porto/docas/taverna/salão/urbano/comércio ou economia comércio/porto)
e só para a lista fechada `GENERIC_ROLES`; P3 janela de continuidade ≤ 2 ações com
o NPC ainda em cena; P4 sem campo novo de pronome (usa `pronouns/gender` só se a
ficha já tiver).

**Schema (aditivo, SEM bump — revisão Astra):** `SCHEMA_VERSION` permanece **8**; não há
`_migrate_v8_to_v9`. `_raw_to_state` defaulta `last_speaker` para `{}` (save antigo ou
valor não-dict), que `response_speaker` lê como narrador; linhas `narrator` legadas do
`presentation_history` recebem `speaker_*` derivado do `type` NA LEITURA (`history_page`;
NPC legado sem id). Round-trip save→load com a fixture v8 e idempotência de
`migrate_state` (no-op) testados. A SPEC-202 saiu da cadeia de bumps; o caso protegido
`state.persistence.migration-idempotent` (v8) segue válido sem edição em `evals/`.

**Desvios/refinamentos:**
- R3: descrição de cena é ignorada quando há vocativo/verbo de fala explícito a NPC
  em cena ("Brunna, descreva o barco" segue para a Brunna).
- R4: vocativo/verbo de fala a NPC presente também promove um STORY do CLASSIFY a NPC;
  pronome + verbo de fala ("pergunto a ela", "e você?") segue a regra da rota NPC
  sem alvo (R8).
- R5: o alvo do CLASSIFY só conta se algum token significativo dele estiver no
  texto do jogador (MockLLM e LLM real alucinam alvos); nome de NPC em cena citado
  pelo jogador decide antes do alvo. Sem NPC algum em cena, o caso "desconhecido"
  mantém a rota NPC sem alvo (caminho SPEC-041 → narrador, mesmo efeito final) para
  preservar os testes de precedência existentes sem mudar expected; com NPCs em
  cena vai direto a STORY.
- R9: `action_guard` também grava `last_speaker` (`system`) na recusa, porque o grafo
  encerra antes do `turn_finalizer`; preserva `last_npc` p/ continuidade. Campos
  internos no save: `turn`, `state_key`, `last_npc` (a resposta pública expõe só
  kind/id/name/reason).
- R11: a cláusula de mediação informa `presente na cena=sim/não` (o smoke real
  mostrou o narrador afirmando ausência de NPC presente sem esse dado).
- Companheiro de party sem ficha em `npcs` mantém o caminho antigo (persona gerada
  para um membro que já existe — não é identidade nova).

**Revisão Astra independente (2026-10-16):** APPROVED após correções no WT:
(1) bump 8→9 convertido em mudança aditiva (acima); (2) falso positivo de meta —
"pergunto ao mestre Orlan…"/"falo com o mestre ferreiro" iam ao narrador como
`meta_to_narrator`; agora "mestre" só é meta no fim da frase ou antes de palavra
funcional (o que/se/sobre/quem/ela…), "narrador" segue sempre meta (teste
`test_mestre_com_nome_ou_papel_e_personagem_nao_meta`). Ataques sem defeito: segredo
via mediação (prompt só com `visible_npc_view`; saída por `find_unrevealed`), NPC
alucinado não criado, continuidade P3 exige NPC em cena + janela ≤2, zero invoke
extra no router (meta/descrição = 0, demais = 1), speaker idêntico POST/SSE/state/history.
Pendente (não bloqueante): autoria do corpus `routing.interlocutor.*` (handoff).
