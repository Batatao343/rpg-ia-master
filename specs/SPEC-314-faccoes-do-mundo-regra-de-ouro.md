# SPEC-314 — Fações do mundo sob a regra de ouro (o NPC não entrega o plano secreto)

> **Status:** `draft`
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** SPEC-298 (`clamp_reveal`/`reveal_ceiling` por faixa), SPEC-301 (catálogo
> `data/faction_membership.json` com `secret`, `rivals`, `recruiter_npc_ids`; `apply_intent`),
> SPEC-308 (filtro de percepção dos eventos do motor), SPEC-310 (`services/npc_self.py`:
> `self_faction`, gate de fação secreta). Todas `done` na `main`.
> **Desbloqueia:** SPEC-312 (rumores com semente) e SPEC-313 (quests ancoradas em lore) sem
> herdar o vazamento; volta a valer o passo 2 do smoke da 310 sem "spoiler".
> **Origem:** revisão da SPEC-310 + smoke real de 25/10 (Comandante Thrace).

---

## 1. Contexto & Objetivo

O `npc_actor` monta `<FACÇÕES_DO_MUNDO>` com **todas** as fações não derrotadas, cada uma
com o `goal` completo (`agents/npc.py:994-1004`), e injeta o bloco em toda fala de NPC
(`agents/npc.py:1119-1125`). A lista inclui as 4 fações `secret: true` do catálogo
(`data/faction_membership.json:44` `mao_sombria`, `:73` `filhos_chama_azul`, `:232`
`druidas_renegados`, `:294` `cultistas_destilacao`). O único freio é uma instrução em
prosa ("se — e SOMENTE se — seu personagem plausivelmente saber…", `:1121-1124`). O teto
por faixa de relação (`services/reputation.py:159-161`, `:1264-1272`) só limita o que é
**gravado** em `faction_intel` (`agents/npc.py:1287-1301`); ele não muda o que o LLM **lê**
nem o que ele **fala**.

Smoke real de 25/10: com `faction_intel.filhos_chama_azul = {known: true, knows_goal:
false}`, o Comandante Thrace (Legião, faixa neutra) respondeu "Eles querem soltar o que
dorme no Palácio de Obsidiana". É o `goal` de `data/factions.json:38` ("Libertar Malagor da
armadura selada no Palácio de Obsidiana…"). O jogador ouviu um fato que nenhum gate do
Python autorizou. Há uma **segunda via** para o mesmo texto: a página do Codex das 4 fações
secretas é `visibility: public` (`data/codex/factions/filhos_chama_azul.md:11`) e traz o
plano (`:27` "Sabem que Malagor está contido na armadura do Palácio de Obsidiana, e alguns
sonham em libertá-lo"). O filtro do RAG é só por visibilidade (`rag.py:1154-1158`), então a
pergunta "e a Chama Azul?" puxa esse trecho para `<LORE_PUBLICO_CANONICO>`
(`agents/npc.py:1109-1111`). O mesmo vale para `mao_sombria.md`, `druidas_renegados.md` e
`cultistas_destilacao.md` (todas `visibility: public`).

Os outros prompts já obedecem à regra (verificado no source): o narrador lista só fações
com `intel.known` e sem `goal` (`agents/storyteller.py:1408-1416`, `:224-242`); o
`world_simulator` idem (`agents/world_simulator.py:66-73`); a nota de ascensão só nomeia a
fação conhecida (`world_utils.py:519-522`); o planner não lista fações
(`agents/campaign_manager.py:144-146`). Resta um vazamento menor de **nome** no pack:
`faction_relation_changed` renderiza os dois nomes sem olhar `faction_intel`
(`services/context_builder.py:79`, `:340-347`; eventos gerados para qualquer par em
`services/world_engine.py:364-376`), mesmo quando o evento passa no filtro de percepção
(`services/context_builder.py:431`).

Objetivo: o bloco de fações do NPC, os ids aceitos nas propostas estruturadas e o lore
recuperado passam a ser montados em Python a partir de `faction_intel`, da fação do próprio
NPC e da faixa de relação. Sem chamada LLM nova. Save sem `faction_intel` falha fechado.
Princípio: "mecânica é Python, não LLM" + regra de ouro (`docs/mundo-vivo/VISAO.md:79-82`).

## 2. Requisitos

### Bloco `<FACÇÕES_DO_MUNDO>` (o que o LLM lê)

Notação: `intel = ensure_faction_intel(state["faction_intel"])` (`world_utils.py:540-550`);
`own = npc_self.self_faction(state, npc_key, row)` (`services/npc_self.py:114-136`);
`tier = reputation.npc_tier(row["relationship"])`; `secret(f)` = catálogo `secret` **ou**
entidade com `visibility != public` (mesma regra de `services/npc_self.py:95-102`).

- **R1 — Fação secreta desconhecida não aparece.** `secret(f)`, `f != own` e
  `intel[f].known` falso → nem id, nem nome, nem região, nem plano no prompt.
- **R2 — Plano de outra fação é gated.** Para `f != own`, a linha leva `plano:` somente se
  `intel[f].knows_goal`, **ou** `f` é pública e `reveal_ceiling(tier) ∈ {objetivo,
  progresso}` (faixa amistoso/leal), **ou** (D2) `f` é secreta, `intel[f].known`, `f` está
  em `rivals` do catálogo de `own` e a faixa é amistoso/leal. Caso contrário a linha diz
  `plano: você não sabe`.
- **R3 — Fação pública sem `known` continua listada** (nome + região; plano conforme R2).
  Existência de fação pública não é segredo.
- **R4 — Fação do próprio NPC, pública.** Sempre listada com o plano e marcada
  `(a sua)`. A gravação continua presa a `clamp_reveal` (sem mudança).
- **R5 — Fação do próprio NPC, secreta.** Se o jogador não a conhece e a faixa não é `leal`
  (D3), a linha usa o alias `id=sua_irmandade`, sem nome nem plano, com a instrução fixa
  "nunca nomeie nem descreva o plano". O nome entra quando `intel[own].known` ou faixa
  `leal`. O plano entra só quando `intel[own].knows_goal` ou o jogador é membro ativo de
  `own` (`faction_membership.is_member`).
- **R6 — Fação derrotada** continua fora (comportamento de `agents/npc.py:1001`).
- **R7 — Instrução nova.** O texto fixo do bloco diz: só fale do plano de uma fação se
  ele estiver escrito na linha; `plano: você não sabe` = admita que não sabe ou especule
  sem afirmar; fação fora da lista = você nunca ouviu falar. A frase "Se — e SOMENTE se —
  seu personagem plausivelmente saber" (`:1121`) sai.
- **R8 — Determinismo e orçamento.** Mesma entrada → mesmo bloco (ordem do
  `ensure_factions`). Nenhuma chamada LLM nova; o bloco não cresce em relação ao atual
  (linhas ocultas só reduzem).

### Saída estruturada (o que o LLM pode propor)

- **R9 — Só ids visíveis.** `faction_reveals[*].faction_id` e
  `membership_action.faction_id` são aceitos só se o id (ou o alias `sua_irmandade`)
  apareceu no bloco deste turno. Fora disso: descartado, com
  `log_event("npc", "faction_id_not_visible")`. Alias → `own` antes de `apply_faction_reveal`
  / `apply_intent`.
- **R10 — Revelação limitada ao que foi mostrado.** Para uma fação cuja linha disse
  `plano: você não sabe`, `reveal_level` é limitado a `existencia` (além do `clamp_reveal`
  atual). Para R5 com alias e faixa < `leal`, a revelação é descartada (o NPC não pode
  "revelar" uma fação que não pode nomear).
- **R11 — Recrutamento de fação secreta continua.** Com o alias, `membership_action`
  `join`/`ask_mission` de um recrutador (`recruiter_npc_ids`, ex.: `npc_pardal` da
  `mao_sombria`, `data/faction_membership.json:47`) chega a `apply_intent` com o id real;
  `can_join` segue sendo o gate; entrar grava `known`+`knows_goal`
  (`services/faction_membership.py:371-375`, `:583`).
- **R12 — Descrições do schema.** `FactionReveal.faction_id`, `MembershipAction.faction_id`
  e `NPCResponse.membership_action` (`agents/npc.py:161`, `:175`, `:213`) passam a dizer
  "id EXATO que aparece em `<FACÇÕES_DO_MUNDO>` (inclui `sua_irmandade`); fação fora da
  lista = vazio".

### Outras vias do mesmo fato

- **R13 — Lore da fação secreta.** Nos packs `purpose ∈ {"npc", "story",
  "combat_narration"}` (`agents/npc.py:987`, `agents/storyteller.py:1346`,
  `agents/combat.py:480`, `:1493`), chunks do
  Codex cujo `metadata.id` é uma fação secreta sem `intel[f].knows_goal` são descartados
  antes do corte `[:2]` (`rag.py:1154-1158` e o caminho por vetor `rag.py:976-1006`).
  Exceção: `f == own` com o jogador membro ativo. O planner (`purpose="planning"`) não muda
  (D4).
- **R14 — Nome em evento de relação/controle.** No pack, `faction_relation_changed` e
  `location_control_changed` que citam fação secreta com `intel.known` falso trocam o nome
  por "uma facção desconhecida" (vale para os dois lados e para `controller`).
- **R15 — Coerência com a 310.** `_identity_lines` (`services/npc_self.py:162-167`) com
  faixa `leal` e fação secreta: "Você serve em segredo a {nome}; só admita a quem confia de
  verdade." Nas demais faixas o texto atual fica.

### Compatibilidade e falha

- **R16 — Save antigo.** Sem `faction_intel` (ou com valor não-dict) → `{}` → nenhuma fação
  secreta listada, nenhum plano de outra fação além do gate de faixa (R2), lore secreto
  descartado (R13). Nenhum campo novo é gravado no save.
- **R17 — Falha fechada.** Exceção ao montar o bloco → bloco só com fações públicas sem
  plano + `log_fallback("npc", "faction_block_failed", exc)`; o turno segue.
- **R18 — Telemetria.** `log_event("npc", "faction_block", listed=, hidden_secret=,
  goals=, alias=bool)`, sem ids de fação secreta no payload.

### Não-vazamento (testes obrigatórios)

- **R19 — Prompt inteiro capturado (padrão SPEC-310 R21).** Com spy no LLM, para cada uma
  das 4 fações secretas × intel ∈ {ausente, `known`, `known+knows_goal`} × faixa ∈
  {neutro, leal}, o `SystemMessage` inteiro contém o `goal` de `data/factions.json` **só**
  quando R2/R5 autorizam, e o `name` só quando R1/R5 autorizam. Readers de lore stub
  devolvem o trecho real da página do Codex; o trecho também só aparece quando R13 autoriza.
- **R20 — Caso Thrace.** NPC `npc_comandante_thrace`, faixa neutra, `filhos_chama_azul =
  {known: true, knows_goal: false}`: o prompt contém "Os Filhos da Chama Azul" e
  `plano: você não sabe`, e **não** contém "Palácio de Obsidiana" nem "Libertar Malagor".

### Fora de escopo

- Reescrever as páginas do Codex ou mudar `visibility` em `data/codex_overrides.yaml`
  (D4 alternativa; exige reindex).
- O planner (`campaign_manager`) e o uso de segredos nos beats (`agents/campaign_manager.py:170`).
- Persona gerada que já contenha o plano (risco herdado da 310 §7).
- Validador pós-fala que procure o `goal` no `dialogue` (D5; possível follow-up).
- Mudar `apply_faction_reveal`, `clamp_reveal` ou as faixas da 298.
- Fações no narrador e no `world_simulator` (já obedecem; só ganham teste de regressão).

## 3. Design técnico

- **Arquivo novo — `services/faction_gate.py`** (puro, sem I/O além de catálogos em cache):

  ```python
  ALIAS_OWN = "sua_irmandade"

  @dataclass(frozen=True)
  class FactionView:
      block: str                      # texto de <FACÇÕES_DO_MUNDO> já com a instrução (R7)
      visible: Mapping[str, str]      # id no prompt -> faction_id real (inclui ALIAS_OWN)
      goal_shown: frozenset[str]      # faction_ids cuja linha trouxe plano
      counts: Mapping[str, int]       # listed / hidden_secret / goals (R18)

  def is_secret(fid: str) -> bool                       # regra de npc_self.py:95-102 (mover p/ cá; npc_self importa)
  def npc_faction_view(state: Mapping, npc_key: str, row: Mapping, tier: str) -> FactionView
  def resolve_proposed_id(view: FactionView, prompt_id: str) -> str   # "" se não visível (R9)
  def cap_reveal(view: FactionView, fid: str, level: str, tier: str) -> str  # R10, depois do clamp_reveal
  def redacted_lore_ids(state: Mapping, own: str = "") -> frozenset[str]     # R13
  def display_faction(state: Mapping, fid: str) -> str  # nome ou "uma facção desconhecida" (R14)
  ```

- **`agents/npc.py`:** `:994-1004` e `:1119-1125` passam a usar
  `faction_gate.npc_faction_view(...)` (com try/except → R17). `tier_now` já existe
  (`:1057`) — calcular a view depois dele. `:1287-1301`: `resolve_proposed_id` +
  `cap_reveal` antes de `apply_faction_reveal`. `:1360-1373`: `resolve_proposed_id` antes de
  `apply_intent`. Descrições em `:161`, `:175`, `:213` (R12).
- **`rag.py` / `services/context_sources.py` / `services/context_builder.py`:** parâmetro
  opcional `exclude_ids: frozenset[str] = frozenset()` no `query_rag` e no caminho por vetor,
  aplicado junto ao filtro de visibilidade (`rag.py:1155-1157`); `build_context_pack`
  calcula `redacted_lore_ids(state, own)` para `purpose in {"npc", "story", "combat_narration"}` e passa
  adiante (`services/context_builder.py:806-810`, `services/context_sources.py:86`).
  Default vazio = comportamento atual.
- **`services/context_builder.py:340-347`:** `render_event` ganha `state: Mapping | None =
  None`; com state, `target`/`other`/`controller` de fação passam por `display_faction`. A
  chamada em `:435` passa `state`.
- **`services/npc_self.py`:** `_faction_is_secret` vira import de `faction_gate.is_secret`;
  `_identity_lines` recebe `tier` (R15).
- **Formato do bloco (exemplo real, Thrace, faixa neutra, Chama Azul `known`):**

  ```
  <FACÇÕES_DO_MUNDO>
  - id=legiao_ferro · A Legião de Ferro (Nova Arcádia) · (a sua) · plano: Cumprir as quotas do Código de Ferro…
  - id=filhos_chama_azul · Os Filhos da Chama Azul (Nova Arcádia) · plano: você não sabe
  - id=… (demais públicas, plano conforme R2)
  Fale do plano de uma facção só se ele estiver escrito acima. "plano: você não sabe" = admita
  que não sabe ou especule sem afirmar. Facção fora desta lista: você nunca ouviu falar dela.
  Registre em 'faction_reveals' só ids desta lista.
  </FACÇÕES_DO_MUNDO>
  ```

  Alias (Pardal, `mao_sombria` desconhecida, faixa neutra):
  `- id=sua_irmandade · (a sua; secreta) · nunca nomeie nem descreva o plano`.

## 4. Plano passo a passo

### Etapa 1 — Gate puro
1. **Testes** (`tests/test_spec314_faction_gate.py`): `test_secreta_desconhecida_some` (R1);
   `test_plano_outra_faccao_por_intel_e_faixa` (R2, tabela pública × secreta × faixa);
   `test_publica_desconhecida_listada_sem_plano` (R3); `test_propria_publica_com_plano` (R4);
   `test_propria_secreta_alias_nome_plano` (R5: neutro/leal/membro); `test_derrotada_fora`
   (R6); `test_bloco_deterministico_e_nao_cresce` (R8); `test_intel_ausente_falha_fechado`
   (R16, `faction_intel` ausente/`None`/lista).
2. **Implementação:** `services/faction_gate.py`; mover `is_secret`.
3. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_spec314_faction_gate.py -q`.

### Etapa 2 — Propostas estruturadas
1. **Testes** (`tests/test_spec314_npc_proposals.py`, MockLLM com resposta fixa):
   `test_reveal_id_invisivel_descartado` (R9); `test_reveal_sem_plano_vira_existencia` (R10);
   `test_alias_sem_leal_descarta_reveal` (R10); `test_recrutador_secreto_join_via_alias`
   (R11, `npc_pardal` → `apply_intent(join, "mao_sombria")`); `test_schema_descricoes` (R12).
2. **Implementação:** `agents/npc.py` (`:994-1004`, `:1119-1125`, `:1287-1301`,
   `:1360-1373`, `:161/175/213`); telemetria R18; fallback R17.
3. **Verificação:** os dois arquivos + `tests/test_spec310_no_leak.py` +
   `tests/test_faction_membership*.py`, `-n 2`.

### Etapa 3 — Lore e eventos
1. **Testes** (`tests/test_spec314_lore_events.py`): `test_rag_exclude_ids` (doc stub com
   `metadata.id=filhos_chama_azul` cai antes do `[:2]`); `test_pack_npc_redige_lore_secreto`
   (R13, sem/com `knows_goal`); `test_planning_nao_redige` (R13/D4);
   `test_relacao_com_secreta_desconhecida_mascara_nome` (R14).
2. **Implementação:** `rag.py`, `services/context_sources.py`, `services/context_builder.py`.
3. **Verificação:** arquivos acima + `tests/test_context_builder*.py`, `-n 2`.

### Etapa 4 — Não-vazamento e coerência
1. **Testes** (`tests/test_spec314_no_leak.py`): `test_prompt_inteiro_por_faccao_secreta`
   (R19, parametrizado 4 × 3 × 2, spy do `get_llm` como em `tests/test_spec310_no_leak.py:103`);
   `test_caso_thrace` (R20); `test_identity_leal_coerente` (R15);
   `test_storyteller_world_sim_sem_goal` (regressão: prompts do narrador e do simulador não
   contêm nenhum `goal`).
2. **Implementação:** `services/npc_self.py` (R15).
3. **Verificação:** arquivos do escopo; suíte completa só no pouso (coordenador).

## 5. Critérios de aceite

- [ ] R1–R20 cobertos por testes nomeados no §4, verdes.
- [ ] `tests/test_spec310_no_leak.py` e testes de 298/301 seguem verdes sem mudar asserts.
- [ ] Nenhuma chamada LLM nova; nenhum `with_structured_output` novo (o guard existente em
      `agents/npc.py:1153` cobre).
- [ ] Saves antigos (sem `faction_intel`) carregam e conversam com NPC (R16).
- [ ] `uv run pytest` verde (suíte completa offline, no pouso).
- [ ] Smoke §6 executado e registrado na spec.

## 6. Smoke test com LLM real

Local, DeepSeek (ROUTES default), `RPG_NPC_KNOWLEDGE=on`, `RPG_WORLD_ENGINE=on`, índice de
lore real. **≤ 5 requests**, teto US$ 0,05. Cada passo: save preparado + 1 fala.

1. **Thrace (repetição do bug):** herói em `na_anel_ferro`, Thrace em faixa neutra,
   `faction_intel.filhos_chama_azul = {known: true, knows_goal: false}`. "O que você sabe
   da Chama Azul? O que eles querem?". Esperado: fala da fação (hostilidade, altares) e
   **não** afirma o plano (sem "Obsidiana", "Malagor", "libertar/soltar"); `faction_intel`
   sai sem `knows_goal`.
2. **Mesmo, com `knows_goal: true`:** pode falar do plano (o jogador já sabe).
3. **Secreta desconhecida:** intel vazio, a Thrace: "Já ouviu falar da Mão Sombria?".
   Esperado: não confirma plano nem rota de venenos; nenhuma entrada nova de
   `mao_sombria` com `knows_goal`.
4. **Recrutador secreto (alias):** `npc_pardal`, intel vazio, faixa neutra: "A quem você
   serve?". Esperado: não nomeia a Mão Sombria. Em seguida, opcional (5ª request): "Quero
   entrar para o seu grupo" → `apply_intent(join, "mao_sombria")` chamado (recusa ou rito
   pelo `can_join`, sem erro).
5. Conferir no log: `npc.faction_block` em todas as falas, 0 `faction_block_failed`.

## 7. Riscos & compatibilidade

- **Saves antigos:** só leitura de `faction_intel`; ausente = fechado (R16). Nada novo gravado.
- **MockLLM/FallbackLLM:** o mock ignora o prompt; só o spy (R19/R20) prova o gate. Caminho
  de erro do `npc_actor` inalterado.
- **Quota/latência:** zero chamada nova; bloco igual ou menor. RAG: um filtro em memória.
- **Regressão de descoberta:** com o plano fora do prompt, o jogador aprende planos
  secretos só por fação própria, perk `informacao` (`services/faction_membership.py:1024-1045`),
  rival amistoso (D2) ou descoberta. Se ficar fechado demais, D2 é o botão.
- **LLM especula certo por conta própria** (lore público geral sobre Malagor). Não é o
  plano autorizado; R7 manda não afirmar. Validador pós-fala fica para D5.
- **Eval protegido `npc_knowledge`:** o pack muda só para fação secreta (R13/R14). Se o eval
  cobrir esses casos, quem otimiza não mexe no expected; registrar `MODEL_HANDOFF_REQUIRED`.
- **Alias `sua_irmandade`:** id que não existe no catálogo; `resolve_proposed_id` é o único
  ponto de tradução. Teste R11 cobre o round-trip.

## 8. Decisões do dono (recomendação em negrito; vale até ele dizer o contrário)

- **D1 — Fação pública desconhecida aparece no bloco?** **Sim, nome e região, sem plano
  abaixo da faixa amistoso (R3).** Alternativa: só fações `known` (como o narrador).
- **D2 — Inimigo jurado conta o plano da secreta?** **Sim, se a secreta for rival da fação
  do NPC, o jogador já souber que ela existe e a faixa for amistoso ou leal.** Alternativa:
  plano de secreta só por membro/perk/descoberta.
- **D3 — Quando o NPC de fação secreta pode se nomear?** **Faixa `leal` ou o jogador já
  conhece a fação; o plano só a membro ativo ou a quem já sabe (R5).** Alternativa: nunca
  se nomeia (só a entrada via rito revela).
- **D4 — Lore secreto no Codex.** **Filtrar no momento da busca (R13), sem mexer no Codex nem
  reindexar; planner fica como está.** Alternativa: `visibility: hidden` nas 4 páginas via
  `data/codex_overrides.yaml` + reindex (mais simples, mas some até para quem já descobriu).
- **D5 — Validador pós-fala.** **Não nesta spec** (o gate do prompt resolve a causa).
  Alternativa: checar `goal`/termos-chave no `dialogue` e trocar por fala neutra.
- **D6 — Kill switch.** **Sem flag:** é correção de vazamento, vale direto. Alternativa:
  `RPG_FACTION_GATE=on|off`.
