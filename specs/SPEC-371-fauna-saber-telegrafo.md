# SPEC-371 — Fauna, saber do jogador: sinais lidos, telegrafos vistos e contra-jogo revelado (filha 360-C)

> **Status:** `in-review` (aprovada pelo dono em 03/11; Etapas 0–6 executadas, faltam revisões e smoke; arena E2–E4 reprovadas, ver §9)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Depende de:** SPEC-360 (`done`: `sinais_vistos` gravado no save, `fauna.json` de Nova Arcádia, `aproximacao` no `combat_encounter_hint`); SPEC-329 (`done`: Presságio, `pressagios_publicos`); SPEC-332 (`done`: baralho de inimigo, padrão, assinatura e `prenuncio`); SPEC-355 R3 (promessa do presságio na cena, `record_promise`/`note_declaration`); SPEC-349 (`done`: 281 fichas com `telegrafo` e `contra_jogo`, Cartas autorais das 12 regiões). SPEC-361 é opcional (criatura gerada em jogo traz `contra_jogo` na `ficha` do template).
> **Desbloqueia:** 360-D (`fauna-tramas`) pode usar o saber como estágio "investigada"; o guarda-chuva SPEC-360 fecha quando 360-B/C/D estiverem `done`.
> **EXECUTOR_MODEL:** `Terra` (Sonnet) no motor, no frontend e nos testes. Fable nunca (dono, 28/10). **REVIEW_MODEL:** `spec-reviewer` Opus independente (nunca o executor) + `Sol` técnico (writer único, estado, determinismo, flag `off`, integridade da métrica). **REVIEW_REQUIRED:** `true`.
> **EVAL_AUTHORING_REQUIRED:** `false`. A métrica "a luta ensina" mora em `scripts/fauna/arena_saber.py` + `tests/test_spec371_eval.py`, fora de `evals/` protegido; os limiares ficam congelados num commit próprio **antes** do produto (Etapa 1; D7).

Rótulos: **[F]** fato no HEAD `86cb7bb8` · **[D?]** decisão aberta (§8, com default) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

O pilar 4 da SPEC-360 ("telegrafo e contra-jogo visíveis; a luta ensina") ficou fora da Fase 1. A 360 já **grava** o que o jogador leu antes da luta, mas nada disso volta para ele: o Codex não mostra, o presságio não usa, a preparação da cena não recebe. Referências (só ideia, §3.7): *The Witcher 3* (o bestiário ensina a fraqueza depois da investigação ou da luta), *Monster Hunter: World* (rastros juntados sobem o nível de pesquisa), *Slay the Spire* (a intenção do inimigo é legível e quem a conhece se defende).

**Problemas, com evidência:**

| # | Problema | Evidência |
|---|---|---|
| P1 | `sinais_vistos` é gravado e nunca lido: `bestiary_view` não tem sinais, telegrafos nem contra-jogo | [F] `services/discovery.py:106-120` (`record_sinais`) vs `:133-170` (`bestiary_view`); `agents/storyteller.py:1723-1737` |
| P2 | O dossiê de criatura (BestiaryTab) e a lista do Codex não têm campo para o saber | [F] `services/dossiers.py:323-356`; `web/src/types.ts:1140-1157` (`CreatureDossier`), `:1009-1022` (`CodexCreature`); `web/src/components/tabs/DossierDetail.tsx:139-162`; `web/src/components/CodexTab.tsx:150-174` |
| P3 | O `knowledge_level` do presságio só lê Cartas reveladas e `_revelado` do ator; o que o jogador viveu antes (sobreviveu à assinatura, estudou a criatura) não conta | [F] `services/enemy_intent.py:207-218` |
| P4 | O `prenuncio` sai em `pressagios_publicos`, mas o tipo do cliente não o declara e o chip do inimigo não o mostra; com `RPG_ENEMY_INTENT=on` ele também não vai ao log (só vai com intenção `off`) | [F] `services/enemy_intent.py:301-307`; `services/conflict_orchestrator.py:2980-2986`; `web/src/types.ts:530-538` (`PressagioView` sem `prenuncio`); `web/src/combat/deck.ts:140-148` (`omenView` ignora); Grep `prenuncio` em `web/src` = 0 ocorrência |
| P5 | Não fica registro de telegrafo visto nem de assinatura sobrevivida: a promessa sai da cena quando é cumprida | [F] `services/enemy_decks.py:404-416` (`record_promise`), `:475-485` (`note_declaration` apaga a promessa) |
| P6 | O `contra_jogo` não existe em runtime fora de Nova Arcádia: está nas 281 fichas YAML (que o runtime não carrega, exceto o gerador com ~5 s a frio) e no `fauna.json` (38 entradas de Nova Arcádia) | [F] Grep `contra_jogo` em `data/`: 12 `fichas/*.yaml` (281) + `fauna/nova_arcadia.yaml` (38) + `world/fauna.json` (38); `services/creature_gen.py:399-407` (leitura lenta); `:1081`, `:1133` (runtime guarda a ficha no template) |
| P7 | X-02 (follow-up da 360): o `contra_jogo` dos 11 legados de Nova Arcádia promete efeitos sem Carta que os sustente | [F] `specs/SPEC-360-criaturas-vivas-no-mundo.md:529` |
| P8 | A preparação da cena (`prepare_encounter`) não recebe a aproximação nem os sinais lidos; só a abertura narrada recebe a aproximação | [F] `agents/combat.py:1042-1049` (ctx), `services/encounter_preparation.py:553-573` (`_prep_prompt`); `agents/combat.py:3305-3310` (`_approach_context`) |
| P9 | A arena mede só vitória por criatura; não há medida de que conhecer a criatura muda o resultado | [F] `scripts/bestiario/arena.py:46-59`; bot `cartas` ignora o presságio, `docs/spec285/arena_lethality.py:158-189` |

**Objetivo.** Fechar o ciclo "ler, lutar, aprender": o que o jogador viu (sinais, telegrafos) e viveu (sobreviveu à assinatura, venceu várias vezes) vira **saber** registrado no save, mostrado no Codex/BestiaryTab e no presságio, e o contra-jogo da criatura é revelado por uma regra **determinística**. Princípios:

- **Mecânica é Python.** Registro, regra de revelação e nível de conhecimento são funções puras do save e da cena. A LLM só recebe linhas prontas, na mesma chamada que já existe.
- **Zero chamada LLM nova.** O custo é de prompt (≤ 1 linha curta na preparação da cena, só com a flag `on`).
- **Writer único.** `services/fauna_saber.py` é o único que escreve os campos novos do saber.
- **Flag `RPG_FAUNA_SABER` `off`**: comportamento do backend byte-idêntico ao de hoje.

## 2. Requisitos

### A. Registro do saber (writer único `services/fauna_saber.py`)

- **R1 — Campos novos no contador do save.** O saber estende `state["bestiary_knowledge"][cid]` (o contador do save, `discovery.py`; mesmo dono escolhido pela 360 no P9), nunca o catálogo runtime de `services/bestiary_knowledge.py`. Campos opcionais:
  - `telegrafos_vistos: list[str]` — textos do `prenuncio` já formatados, na ordem da primeira vez, sem repetição, ≤ 4 itens, cada um ≤ 160 chars;
  - `assinaturas_sobrevividas: int` — quantas assinaturas telegrafadas o jogador viu cumprir e terminou a rodada de pé;
  - `saber_revelado: {"motivo": str, "turn": int}` — gravado **uma vez** quando a regra de R4 dispara; nunca é removido (revelação pegajosa).
  `sinais_vistos` continua com a 360 (`record_sinais`); esta spec só o lê.
- **R2 — Observação na cena.** Com `RPG_FAUNA_SABER=on`:
  - `enemy_decks.record_promise` anexa `{"actor_id", "carta", "texto"}` a `scene["saber_obs"]["telegrafos"]` quando a promessa se torna pública (vale para os dois caminhos que chamam `record_promise`: `agents/combat.py:2936-2941` e `conflict_orchestrator.py:2980-2986`);
  - `enemy_decks.note_declaration`, no ramo em que a promessa é cumprida, anexa `{"actor_id", "carta", "rnd"}` a `scene["saber_obs"]["cumpridas"]`.
  Com a flag `off`, nenhuma chave nova aparece na cena.
- **R3 — Absorção por rodada.** Depois de cada `run_round` do combate real, `agents/combat.py` chama `fauna_saber.absorb(bk, scene, actors_by_id, player_alive, turn) -> tuple[dict, list[str]]`, que:
  - mapeia `actor_id → cid` por `discovery.normalize_bestiary_id` (ator sem id no bestiário é ignorado);
  - acrescenta os textos a `telegrafos_vistos` (R1);
  - soma `+1` em `assinaturas_sobrevividas` por assinatura cumprida **se** `player_alive` (jogador não morto, nem em estado terminal, ao fim da rodada);
  - remove `scene["saber_obs"]` e devolve as linhas de log de R14.
  Simulação (`combat_simulation.enabled`, `agents/combat.py:2223`) e prévia (`combat_preview`) **não** absorvem.
- **R4 — Regra de revelação do contra-jogo (determinística).** `fauna_saber.reveal_reason(rec: dict) -> str | None`, avaliada em `absorb` e no fim do combate (depois de `record_kills`), na ordem:
  1. `"sobreviveu"` — `assinaturas_sobrevividas ≥ 1` (viu o telegrafo e aguentou a assinatura);
  2. `"estudada"` — `discovery.knowledge_tier(rec) ≥ 3` (venceu ≥ 3 instâncias; tier "Estudada" de `discovery.py:31-36`);
  3. `"rastreada"` — `len(sinais_vistos) ≥ 2` e `fought ≥ 1` (leu ≥ 2 sinais e enfrentou a dona deles; o mesmo limiar do bônus de detecção da 360 R18). [D?] D1.
  Só revela se `contra_jogo_of(cid)` (R5) devolve texto. Ao disparar, grava `saber_revelado` (R1) e `log_event("fauna_saber", "revelado", cid=…, motivo=…)`. Testemunha NPC fica fora (D2).
- **R5 — Fonte do contra-jogo em runtime.** `fauna_saber.contra_jogo_of(cid) -> str` (`""` quando não há), nesta ordem:
  1. `data/world/bestiario_saber.json` (gerado, R6) — fichas `nova`/`reinventada`/`adotada` das 12 regiões;
  2. `template["ficha"]["contra_jogo"]` da criatura gerada em jogo (overlay de `agents.bestiary.load_bestiary`, `creature_gen.py:1133`), quando houver;
  3. nada mais: legado sem ficha **não** revela (R7).
- **R6 — Compilação.** `scripts/fauna/build_saber.py` lê `data/bestiario/fichas/*.yaml` (com libyaml, como `creature_gen.py:399-407`) e grava `data/world/bestiario_saber.json` = `{"version": 1, "criaturas": {"<id>": {"contra_jogo": str, "regiao": str}}}`, ordenado por id, `ensure_ascii=False`, LF. Teste de frescor (build em memória = arquivo versionado). O runtime nunca lê os YAMLs. O `bestiary.json` e o `fauna.json` não mudam (nenhum byte; o `fauna.json` muda pesos de encontro e não pode ganhar entradas).
- **R7 — X-02, legado.** Criatura com `fonte: legado` (11 de Nova Arcádia; 88 no total) não tem `contra_jogo` revelável nesta spec: o dossiê mostra sinais e telegrafos, mas não a linha "Como se luta". Teste: nenhuma entrada de `bestiario_saber.json` tem id do legado (`curadoria_legado.yaml` com `classe: valoria` e sem ficha). [D?] D3.

### B. Presságio e preparação do combate

- **R8 — Saber no ator ao entrar no combate.** Com a flag `on`, no spawn (o mesmo ponto de `_sync_enemy_knowledge`, `agents/combat.py:754`, chamado em `:2310`), cada inimigo com `cid` ganha `enemy["saber_jogador"] = {"contra_jogo": str | None, "assinaturas": list[str]}`: `contra_jogo` só quando `saber_revelado` existe; `assinaturas` = Cartas de assinatura (`enemy_decks.assinatura_of(enemy)["carta"]`) quando `assinaturas_sobrevividas ≥ 1`. Campo fora de `bestiary_knowledge._PUBLIC_FIELDS` (`services/bestiary_knowledge.py:22-33`): nunca vai ao painel público.
- **R9 — `knowledge_level` considera o saber.** Em `enemy_intent.knowledge_level(enemy, carta_id)` (`:207-218`), com a flag `on`: `carta_id ∈ saber_jogador.assinaturas` → `"estudada"`; `saber_jogador.contra_jogo` não vazio → no mínimo `"conhecida"`. As regras atuais continuam valendo antes destas. Com a flag `off`, nenhuma mudança.
- **R10 — Linha de contra-jogo no presságio.** Em `enemy_intent.public_round` (`:290-309`), com a flag `on`, a linha que recebe `prenuncio` ganha também `contra_jogo` (texto de `saber_jogador.contra_jogo`) quando revelado. Só nessa linha (a rodada em que a assinatura vem; D4). Sem `prenuncio`, nenhuma linha recebe `contra_jogo`.
- **R11 — Preparação da cena na mesma chamada.** Com a flag `on`, `agents/combat.py::_prepare_scene` põe no `ctx` `saber_linha` (≤ 200 chars) montada em Python: aproximação (de `state["combat_encounter_hint"]["aproximacao"]`) e tipos de `sinais_vistos` dos inimigos da cena, sem nome nem texto de sinal (ex.: `"O herói leu antes: rastro, som. Aproximação: …"`). `_prep_prompt` (`encounter_preparation.py:553-573`) acrescenta `"Saber do herói: {saber_linha}"` só quando a chave existe. A preparação continua rodando só quando `_wants_prepared_scene` manda (`agents/combat.py:1054`); nenhum invoke novo.
- **R12 — Zero chamada LLM nova; custo de prompt limitado.** Contagem de `invoke` (via `set_llm_telemetry_hook`) num combate MockLLM de 6 rodadas contra `mon_arame_vivo`, flag `on` × `off`, na mesma seed: igual. Linha de R11 ≤ 200 chars (≈ 50 tokens).

### C. Exibição (Codex, BestiaryTab, combate)

- **R13 — `bestiary_view` com o saber.** Com a flag `on`, em `discovery.bestiary_view` (`:133-170`), a entrada com tier ≥ 2 ganha:
  - `sinais_vistos: [{"tipo": str, "texto": str}]` — texto de `fauna.entry(cid)["sinais"][tipo]` (só tipos ainda presentes; tipo sem texto é omitido). O sinal já foi associado à criatura no encontro (360 R23), então mostrar o texto não vaza nada;
  - `telegrafos_vistos: list[str]` (R1);
  - `contra_jogo: str` e `contra_jogo_motivo: str` (rótulo fixo: `sobreviveu` → "Aprendido ao aguentar o golpe preparado", `estudada` → "Aprendido de tanto enfrentá-la", `rastreada` → "Aprendido seguindo os rastros") só quando `saber_revelado` existe e R5 devolve texto.
  Com a flag `off`, a lista é byte-idêntica à de hoje (golden). A projeção da SPEC-206 (`services/player_knowledge.py:374-377`) e o dossiê (`services/dossiers.py:323-356`) repassam os campos sem filtro novo.
- **R14 — Aviso no combate.** Quando `absorb` (R3) ou o fim do combate grava `saber_revelado`, o `out["logs"]` do turno ganha 1 linha fixa: `"Você aprendeu como enfrentar {nome}: veja o Bestiário."` (nome da instância). Uma vez por criatura por save.
- **R15 — Frontend (React, tom Witcher).** Com os campos presentes:
  - `CreatureDossier` e `CodexCreature` (`web/src/types.ts`) ganham `sinais_vistos?`, `telegrafos_vistos?`, `contra_jogo?`, `contra_jogo_motivo?`;
  - `DossierDetail.CreatureView` e `CodexTab.CreatureList` mostram três blocos, nesta ordem e só quando há conteúdo: **"Rastros lidos"** (tipo em rótulo PT: Rastro, Restos, Som, Cheiro, Marca + o texto em itálico), **"Presságios testemunhados"** (os textos), **"Como se luta"** (o contra-jogo + o motivo em `codex-entry__meta`). Reusar as classes `codex-entry__*` existentes; sem cor nova fora dos tokens;
  - `PressagioView` ganha `prenuncio?: string | null` e `contra_jogo?: string | null`; `omenView` (`web/src/combat/deck.ts:140-148`) e o `OmenView` passam a carregar os dois; o `TargetChip` mostra o `prenuncio` (sempre que vier; corrige P4, D5) e, abaixo, o `contra_jogo` com o prefixo "Você sabe:". O `spoken` (leitor de tela) inclui os dois.
- **R16 — e2e.** `web/e2e/dossiers.spec.ts` ganha um caso com save sintético (flag `on`): dossiê de `mon_arame_vivo` mostra os três blocos; um caso de combate com `pressagios_publicos` sintético mostra `prenuncio` e "Você sabe:". Rodar com `--workers=1`.

### D. Flag, métrica, compatibilidade

- **R17 — Flag.** `RPG_FAUNA_SABER` em `config/flags.yaml`: `kind: release`, `default: "off"`, `spec: SPEC-371`, `expires: 2027-03-01`, `note: "fauna viva: saber do jogador (sinais lidos, telegrafos vistos, contra-jogo revelado)"`. Valores `off|on`. Independe de `RPG_FAUNA`/`RPG_FAUNA_SINAIS` (sem fauna, só `sinais_vistos` fica vazio e a regra `rastreada` nunca dispara); telegrafos exigem `RPG_ENEMY_DECKS=on` na prática (sem assinatura não há `prenuncio`).
- **R18 — `off` byte-idêntico.** Com a flag `off`: golden de 30 turnos da 360 (`tests/fixtures/spec360_flags_off_golden.json`) inalterado; `bestiary_view`, `public_round`, `_prep_prompt` e a cena (`scene` sem `saber_obs`) byte-idênticos em fixture fixa; nenhum campo novo em `bestiary_knowledge`.
- **R19 — Métrica "a luta ensina" (arena).** `scripts/fauna/arena_saber.py` (offline, MockLLM, seeded; reusa `docs/spec332/arena_familias.py` e `docs/spec285/arena_lethality.py` como `scripts/bestiario/arena.py:32-37`), `RPG_ENEMY_DECKS=on`, `RPG_ENEMY_INTENT=on`, `RPG_FAUNA_SABER=on`:
  - **população:** criaturas não-chefe de Nova Arcádia com assinatura e `contra_jogo_of` não vazio (Etapa 0 lista; esperado ~22 das 27 fichas), 5 Posturas, `--seeds 20`, nível 3, tamanho de grupo de `A.group_size`;
  - **par por (criatura, Postura, seed):** luta 1 com `bestiary_knowledge` vazio; o `bk` resultante (pelo `absorb` real e o fim de combate real, R3/R4) entra na luta 2, **mesma seed**, com o ator carimbado por R8;
  - **bot `leitor`** (novo, em `arena_saber.py`): calcula a linha pública do alvo (`forecast_round` + `public_round`) antes de declarar; se a linha tem `prenuncio` **e** (`contra_jogo` ou `valor_estimado ≥ 30 %` da Vitalidade atual), declara a melhor opção defensiva disponível (Etapa 0 define a ordem: Carta de reação/defesa preparada → manobra defensiva → afastar-se); senão age como o bot `cartas`. Sem saber, `leitor` = `cartas` (D6);
  - **métricas (limiares congelados na Etapa 1, D7):**
    - **E1 (a regra dispara):** fração de pares com `saber_revelado` depois da luta 1 ≥ **0,30**;
    - **E2 (vitória):** nos pares revelados, vitória da luta 2 − luta 1 ≥ **+3 pp** (agregado);
    - **E3 (Vitalidade):** nos pares revelados e vencidos nas duas, Vitalidade perdida média da luta 2 ≤ **0,92 ×** a da luta 1;
    - **E4 (não trivializa):** vitória agregada da luta 2 ≤ **0,92**, e nenhuma criatura com luta 2 pior que a luta 1 em mais de **2 pp**;
    - **E5 (determinismo):** duas execuções com a mesma seed dão relatório byte-idêntico.
  Relatório em `docs/spec371/arena-saber-nova_arcadia.md` (+ JSON bruto). Se E2/E3 falharem, **não** mexer no avaliador nem nos limiares: registrar na §9 e levar ao dono (é sinal de que o contra-jogo autoral não tem mecânica que o bot consiga usar).
- **R20 — Saves antigos.** Entrada sem os campos novos carrega e é exibida como hoje; ator salvo sem `saber_jogador` funciona (`knowledge_level` trata ausência). Round-trip save/load preserva `telegrafos_vistos`, `assinaturas_sobrevividas` e `saber_revelado`. `scene["saber_obs"]` sobrevivendo num save no meio do combate é absorvido no turno seguinte (nunca perdido nem duplicado).
- **R21 — Telemetria e playtest.** `log_event("fauna_saber", …)` com `telegrafo`, `sobreviveu` e `revelado` (só ids e motivo; nunca texto). O harness ganha o invariante `saber_valido`: `sinais_vistos` ⊆ {rastro, resto, som, cheiro, marca}; `assinaturas_sobrevividas` int ≥ 0; `telegrafos_vistos` ≤ 4; `saber_revelado.motivo` ∈ {sobreviveu, estudada, rastreada}; `saber_revelado` só com `contra_jogo_of(cid)` não vazio. `playtest run --profile combate --turns 30` com a flag `on`: 0 violação `error`.

### Fora de escopo

- Backfill de fauna (sinais, ecologia) nas outras 11 regiões e no legado: **360-B** (SPEC-370 ou o ID que o coordenador reservou). Aqui só o `contra_jogo` das fichas das 12 regiões entra em runtime (R6).
- Criaturas de trama, estágio de trama: **360-D**.
- Reescrever o `contra_jogo` do legado como conselho tático (X-02): conteúdo, decisão D3.
- Testemunha NPC que conta o contra-jogo (D2); compra de saber (livro, mestre caçador).
- Bônus numérico por saber (Esquiva, dano, iniciativa): o saber só **informa** nesta spec (D6).
- Mudar números de combate, Cartas, `bestiary.json`, `fauna.json`, fichas YAML, `lore_nova/`.
- Mudar o catálogo runtime `services/bestiary_knowledge.py` (Cartas/resistências reveladas por arquétipo).
- Narrar o contra-jogo pela LLM ou pôr o contra-jogo no prompt da abertura/narração (só a preparação da cena recebe a linha de R11, e sem contra-jogo).
- Ligar a flag em staging ou produção (coordenador, depois do smoke).

## 3. Design técnico

### 3.1 Arquivos

| Arquivo | Novo/alterado | Responsabilidade |
|---|---|---|
| `services/fauna_saber.py` | novo | `mode()`, `contra_jogo_of`, `absorb`, `reveal_reason`, `finish_combat`, `stamp_actor`, `prep_line`, `view_fields`; writer único dos campos de R1 |
| `scripts/fauna/build_saber.py` | novo | R6 |
| `data/world/bestiario_saber.json` | novo (gerado) | R6 |
| `scripts/fauna/arena_saber.py` | novo | R19 (avaliador; commit da Etapa 1) |
| `docs/spec371/arena-saber-nova_arcadia.{md,json}` | novo (gerado) | relatório R19 |
| `services/enemy_decks.py` | alterado | R2 (`record_promise`, `note_declaration` anexam a `saber_obs` só com a flag `on`) |
| `services/enemy_intent.py` | alterado | R9, R10 |
| `services/discovery.py` | alterado | R13 (`bestiary_view` chama `fauna_saber.view_fields`) |
| `agents/combat.py` | alterado | R3 (após `run_round`), R4 (fim do combate, depois de `record_kills` em `:2761`), R8 (spawn, `:2310`), R11 (`_prepare_scene`, `:1042-1065`), R14 |
| `services/encounter_preparation.py` | alterado | R11 (`_prep_prompt`) |
| `services/dossiers.py` | alterado | R13 (repasse dos campos) |
| `web/src/types.ts`, `web/src/combat/deck.ts`, `web/src/combat/TargetChip.tsx`, `web/src/components/tabs/DossierDetail.tsx`, `web/src/components/CodexTab.tsx` | alterados | R15 |
| `web/e2e/dossiers.spec.ts` | alterado | R16 |
| `config/flags.yaml` | alterado | R17 |
| `playtest/invariants.py`, `playtest/telemetry.py` | alterados | R21 |

### 3.2 Assinaturas

```python
# services/fauna_saber.py
MODES = ("off", "on")  # RPG_FAUNA_SABER
MOTIVOS = ("sobreviveu", "estudada", "rastreada")
MOTIVO_LABEL = {
    "sobreviveu": "Aprendido ao aguentar o golpe preparado",
    "estudada": "Aprendido de tanto enfrentá-la",
    "rastreada": "Aprendido seguindo os rastros",
}
MAX_TELEGRAFOS = 4
MAX_TEXTO = 160
SINAL_LABEL = {"rastro": "Rastro", "resto": "Restos", "som": "Som", "cheiro": "Cheiro", "marca": "Marca"}


def mode() -> str: ...  # env RPG_FAUNA_SABER; inválido -> "off" + log_event 1x
def contra_jogo_of(creature_id: str) -> str: ...  # R5; "" quando não há
def reveal_reason(rec: dict, creature_id: str) -> str | None: ...  # R4 (None se já revelado ou sem fonte)
def observe_promise(scene: dict, actor: dict, carta: str, texto: str) -> None: ...  # R2 (chamado por enemy_decks)
def observe_fulfilled(scene: dict, actor_id: str, carta: str, rnd: int) -> None: ...  # R2
def absorb(
    bk: dict, scene: dict, actors_by_id: dict[str, dict], player_alive: bool, turn: int
) -> tuple[dict, list[str]]: ...  # R3 + R4; devolve (bk novo, linhas de log R14)
def finish_combat(
    bk: dict, enemies: list[dict], turn: int
) -> tuple[dict, list[str]]: ...  # R4 depois de record_kills
def stamp_actor(enemy: dict, bk: dict) -> None: ...  # R8 (muta o ator; no-op com a flag off)
def prep_line(state: dict, enemies: list[dict]) -> str: ...  # R11; "" quando nada a dizer
def view_fields(creature_id: str, rec: dict, tier: int) -> dict: ...  # R13
```

`enemy_decks` importa `fauna_saber` de forma preguiçosa (dentro da função) para não criar ciclo; com a flag `off` a chamada sai antes de tocar na cena.

### 3.3 Estado (exemplo real, `mon_arame_vivo`)

```json
"bestiary_knowledge": {
  "mon_arame_vivo": {
    "seen": 2, "fought": 1, "defeated": 1,
    "first_seen_turn": 14, "last_update_turn": 19,
    "sinais_vistos": ["rastro", "som"],
    "telegrafos_vistos": ["<texto do prenuncio formatado com o nome da instância>"],
    "assinaturas_sobrevividas": 1,
    "saber_revelado": {"motivo": "sobreviveu", "turn": 18}
  }
}
```

Cena, só durante o combate e só com a flag `on`:

```json
"saber_obs": {
  "telegrafos": [{"actor_id": "mon_arame_vivo_1", "carta": "<id da assinatura>", "texto": "…"}],
  "cumpridas": [{"actor_id": "mon_arame_vivo_1", "carta": "<id da assinatura>", "rnd": 3}]
}
```

O executor confirma o id da Carta de assinatura e o texto do `telegrafo` do `mon_arame_vivo` por Grep na ficha (`data/bestiario/fichas/nova_arcadia.yaml`) e em `data/cards/` na Etapa 0; o exemplo não inventa ids.

### 3.4 Fluxo de um combate com a flag `on`

1. Spawn: `record_encounter` (já existe) → `stamp_actor` em cada inimigo (R8).
2. Preparação (só quando `_wants_prepared_scene`): `ctx["saber_linha"] = prep_line(...)` (R11).
3. Fim de cada rodada: o presságio da próxima rodada é congelado; `record_promise` → `observe_promise` (R2). A linha com `prenuncio` ganha `contra_jogo` se revelado (R10). O `knowledge_level` usa o saber do ator (R9).
4. Na rodada seguinte: a assinatura é declarada → `note_declaration` → `observe_fulfilled`; depois de `run_round`, `absorb` (R3/R4) atualiza `bestiary_knowledge` (`bk_changed = True`) e devolve a linha de R14.
5. Fim do combate: `record_kills` → `finish_combat` (regra `estudada`/`rastreada`).
6. Codex/BestiaryTab: `bestiary_view` → `view_fields` (R13) → dossiê → UI (R15).

### 3.5 Regra de revelação: tabela de decisão

| `assinaturas_sobrevividas` | tier | `sinais_vistos` | `fought` | `contra_jogo_of` | Resultado |
|---|---|---|---|---|---|
| ≥ 1 | qualquer | qualquer | qualquer | texto | `sobreviveu` |
| 0 | ≥ 3 | qualquer | qualquer | texto | `estudada` |
| 0 | < 3 | ≥ 2 | ≥ 1 | texto | `rastreada` |
| qualquer | qualquer | qualquer | qualquer | `""` (legado, ad-hoc) | nada |
| já há `saber_revelado` | — | — | — | — | nada (pegajoso) |

### 3.6 Riscos de leitura da UI

O texto do sinal só aparece depois do encontro (tier ≥ 2 e associação feita pela 360 R23); o `prenuncio` já é texto público do combate; o contra-jogo só aparece revelado. Nenhum segredo (`LEAK_PHRASES`) entra: os três textos já passaram pelos lints da 349 (fichas) e da 360 (E10/E16).

### 3.7 Inspiração externa (só ideia; nada de nome, silhueta ou texto)

| Fonte | O que tomou | Distância |
|---|---|---|
| *The Witcher 3* (CD Projekt Red, 2015): bestiário que ensina a fraqueza depois da investigação ou da luta | Contra-jogo revelado por `rastreada`/`sobreviveu`/`estudada`; bloco "Como se luta" | Sem óleos, sinais de bruxo ou bônus de dano; o saber só informa |
| *Monster Hunter: World* (Capcom, 2018): pesquisa que sobe com rastros e caças | Rastros lidos ficam no dossiê; `rastreada` exige ≥ 2 sinais | Sem nível de pesquisa numérico nem medidor |
| *Slay the Spire* (MegaCrit, 2019): intenção do inimigo legível | O presságio mostra o `prenuncio` e, com saber, o que fazer e o valor estimado | Sem ícone novo; reusa o chip do inimigo |

## 4. Plano passo a passo

Testes do escopo com `bash scripts/dev/py.sh -m pytest <arquivos> -q -n 2` no máximo (RAM). A suíte completa é do coordenador no pouso.

### Etapa 0 — Sondas (sem código de produto; registrar na §9)

1. Listar as criaturas não-chefe de Nova Arcádia com assinatura (`enemy_decks.assinatura_of`) e `contra_jogo` na ficha; anotar o id da Carta de assinatura e o `telegrafo` do `mon_arame_vivo`.
2. Para cada Postura do herói da arena (`A.hero(cls, 3)`), listar as opções defensivas disponíveis (Cartas de reação/defesa preparadas, manobras de `ct.TurnStep(kind="maneuver")`, mover). Definir a ordem do bot `leitor`. Se uma Postura não tiver opção, o `leitor` age como `cartas` nela e o relatório separa essa Postura.
3. Confirmar P4 no navegador (MockLLM, `RPG_ENEMY_DECKS=on`, `RPG_ENEMY_INTENT=on`): o `prenuncio` não aparece no chip.
4. Confirmar que `combat_meta["scene"]` persiste entre turnos no save (R20) e o ponto exato pós-`run_round` em `agents/combat.py` onde o `out` do orquestrador e `bestiary_knowledge` coexistem.

### Etapa 1 — Avaliador e limiares congelados (commit próprio, antes do produto)

1. `scripts/fauna/arena_saber.py` (população, pares, bot `leitor`, E1–E5, relatório MD+JSON) e `tests/test_spec371_eval.py` com os limiares literais de R19 (E1/E2/E3/E4 vermelhos sem o produto; E5 verde).
2. Commit `test(fauna): freeze SPEC-371 teaching-arena evaluator and thresholds`. O executor de produto não altera esses dois arquivos depois (D7).

### Etapa 2 — Fonte do contra-jogo (TDD)

1. **Testes** (`tests/test_spec371_fonte.py`): `test_build_deterministico`; `test_bestiario_saber_fresco` (R6); `test_cobre_todas_as_fichas` (281 ids, todos com texto); `test_legado_fora` (R7); `test_contra_jogo_of_ordem` (json → `template["ficha"]` → `""`); `test_bestiary_e_fauna_json_intocados`.
2. **Implementação:** `build_saber.py`, `bestiario_saber.json`, `contra_jogo_of`.

### Etapa 3 — Registro e regra de revelação (TDD)

1. **Testes** (`tests/test_spec371_saber.py`):
   - `test_observe_so_com_flag_on` (cena sem `saber_obs` com `off`, R2/R18);
   - `test_record_promise_anexa_telegrafo` e `test_note_declaration_anexa_cumprida` (R2);
   - `test_absorb_soma_sobrevivida_so_com_jogador_vivo`, `test_absorb_telegrafo_dedup_e_cap_4`, `test_absorb_ignora_ator_sem_bestiario`, `test_absorb_limpa_saber_obs` (R3);
   - `test_regra_tabela_3_5` (parametrizado pelas 5 linhas da §3.5), `test_revelacao_pegajosa`, `test_ordem_dos_motivos` (R4);
   - `test_simulacao_e_previa_nao_absorvem` (R3);
   - `test_linha_de_log_uma_vez` (R14);
   - `test_saber_obs_de_save_no_meio_do_combate` e `test_round_trip_campos_novos`, `test_save_antigo_sem_campos` (R20).
2. **Implementação:** `fauna_saber.py` (registro, regra), ganchos em `enemy_decks.py`, chamadas em `agents/combat.py` (pós-`run_round` e fim de combate).

### Etapa 4 — Presságio e preparação (TDD)

1. **Testes** (`tests/test_spec371_pressagio.py`):
   - `test_stamp_actor_campos` e `test_stamp_fora_do_painel_publico` (R8);
   - `test_knowledge_level_assinatura_sobrevivida_estudada`, `test_knowledge_level_contra_jogo_conhecida`, `test_knowledge_level_off_inalterado` (R9);
   - `test_contra_jogo_so_na_linha_do_prenuncio`, `test_sem_revelacao_sem_linha`, `test_public_round_off_byte_identico` (R10);
   - `test_prep_line_sem_nome_e_curta`, `test_prep_prompt_off_byte_identico`, `test_prep_sem_invoke_novo` (R11, R12);
   - `test_invoke_count_on_igual_off` (R12).
2. **Implementação:** `enemy_intent.py`, `stamp_actor`, `prep_line`, `_prepare_scene`, `_prep_prompt`.

### Etapa 5 — Codex, dossiê e frontend (TDD)

1. **Testes** (`tests/test_spec371_view.py`): `test_view_fields_tier_2`, `test_texto_do_sinal_vem_do_fauna_json`, `test_contra_jogo_so_revelado`, `test_rotulo_do_motivo`, `test_bestiary_view_off_golden` (fixture nova `tests/fixtures/spec371_bestiary_view_off.json`, gravada **antes** da mudança), `test_dossie_repassa_campos` (R13).
2. **Frontend:** tipos, `omenView`, `TargetChip`, `CreatureView`, `CreatureList` (R15); testes unitários de `omenView` (`web/src/combat/deck.test.ts`, se existir o padrão; senão no e2e); `cd web && npm run build` e `npm run lint`.
3. **e2e** (R16): `npx playwright test e2e/dossiers.spec.ts --workers=1`.

### Etapa 6 — Flag, playtest e métrica

1. `config/flags.yaml` (R17); `tests/test_spec371_flags_off.py`: golden de 30 turnos da 360 inalterado com a flag `off`; gate de flags (`docs/guias/TESTES.md` § Flags).
2. Invariante `saber_valido` e telemetria (R21); `playtest run --profile combate --turns 30` com a flag `on` (e `RPG_ENEMY_DECKS=on`): 0 violação `error`.
3. Rodar `scripts/fauna/arena_saber.py --regiao nova_arcadia --seeds 20 --md docs/spec371/arena-saber-nova_arcadia.md --json docs/spec371/arena-saber-nova_arcadia.json`. E1–E5 verdes. Falhou → §9 + decisão do dono; nunca mexer no avaliador.

### Etapa 7 — Revisões

`spec-reviewer` Opus independente (requisitos, UI, texto) e `Sol` (writer único, estado, `off` byte-idêntico, integridade da métrica). Handoffs `handoffs/SPEC-371-independent-review.md` e `handoffs/SPEC-371-sol-review.md`.

### Etapa 8 — Smoke real (§6) e pouso (`/spec-land`, coordenador).

## 5. Critérios de aceite

- [x] `bestiario_saber.json` gerado, fresco, 281 fichas, sem legado; `bestiary.json` e `fauna.json` byte-idênticos (R5–R7)
- [x] Telegrafo visto e assinatura sobrevivida registrados pela cena e absorvidos por rodada; simulação/prévia não gravam (R1–R3)
- [x] Regra de revelação com as 5 linhas da §3.5 em teste; revelação pegajosa; linha de log 1× (R4, R14)
- [x] `knowledge_level` com saber; `contra_jogo` só na linha do `prenuncio`; ator carimbado fora do painel público (R8–R10)
- [x] Linha de saber na preparação da cena, ≤ 200 chars, sem nome; contagem de `invoke` igual `on`×`off` (R11, R12)
- [x] `bestiary_view`/dossiê com sinais lidos, telegrafos e contra-jogo; golden `off` byte-idêntico (R13, R18)
- [x] Frontend mostra os três blocos e o `prenuncio` + "Você sabe:" no chip; `npm run build` e lint verdes; e2e `--workers=1` verde (R15, R16)
- [x] Flag `RPG_FAUNA_SABER` registrada `off`; golden de 30 turnos da 360 inalterado (R17, R18)
- [ ] Arena "a luta ensina" E1–E5 verdes com o avaliador do commit da Etapa 1 intocado; relatório publicado (R19)
- [x] Playtest `combate` 30 turnos com a flag `on`: 0 violação `error`; invariante `saber_valido` (R21)
- [x] Saves antigos carregam; round-trip dos campos novos (R20)
- [x] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo); se surgir, com guard
- [ ] Revisões independente e Sol aprovadas
- [ ] `uv run pytest` verde (suíte completa, no pouso, pelo coordenador)
- [ ] Smoke real da §6 executado e registrado na §9

## 6. Smoke test com LLM real

Coordenador, com chave (`ROUTES` de hoje), API local, `RPG_FAUNA_SABER=on`, `RPG_FAUNA=on`, `RPG_FAUNA_SINAIS=on`, `RPG_ENEMY_DECKS=on`, `RPG_ENEMY_INTENT=on`. ≤ 8 turnos (~3 chamadas por turno).

1. Save scratch (não versionado) em Nova Arcádia, Noite, sem `mon_arame_vivo` no `bestiary_knowledge`, com presença ativa dele em `na_anel_lama` e **1** sinal já mostrado (`rastro`), adaptando o setup da 360 §6. Com 1 sinal só, a regra `rastreada` não dispara e o smoke exercita `sobreviveu`.
2. "sigo o rastro": combate começa (360 R20). No turno seguinte, `GET` dos dossiês: o `mon_arame_vivo` mostra "Rastros lidos" com o texto do rastro e **ainda não** mostra "Como se luta".
3. Avançar rodadas até o presságio trazer `prenuncio` (a assinatura do `mon_arame_vivo` cai na rodada seguinte). Conferir no navegador: o chip mostra o `prenuncio`.
4. Aguentar a assinatura (defender). No turno seguinte: log "Você aprendeu como enfrentar …"; `GET /game/state` → `saber_revelado.motivo == "sobreviveu"`, `assinaturas_sobrevividas == 1`, `telegrafos_vistos` com o texto.
5. No próximo `prenuncio` do mesmo combate (ou num 2º encontro): o chip mostra "Você sabe: …" com o contra-jogo da ficha; o presságio da assinatura mostra `carta_nome` e valor estimado (estudada).
6. Se a cena for preparada pela LLM (elite/Abismo), o prompt capturado (log de debug) tem "Saber do herói:" sem o nome da criatura; a cena valida.
7. Custo: contagem de chamadas por turno com `RPG_FAUNA_SABER=on` igual à mesma sequência com `off` (`set_llm_telemetry_hook`); Δ p50 de latência do turno ≤ 100 ms.

## 7. Riscos & compatibilidade

- **Saves antigos.** Todos os campos novos são opcionais; ausência = comportamento de hoje. `saber_obs` só existe na cena durante o combate.
- **Flag `off`.** Backend byte-idêntico (golden da 360 + fixtures desta spec). A única mudança visível com `off` é o chip mostrar um `prenuncio` que o backend já envia (D5).
- **Bot `leitor` como modelo de jogador.** A métrica mede o valor da informação para um jogador que age sobre ela; não prova que um humano age. Os limiares são modestos (+3 pp, −8 % de Vitalidade) e o E4 impede que o saber trivialize o encontro.
- **Contra-jogo sem mecânica que o bot use.** Se E2/E3 falharem, a causa provável é conteúdo (contra-jogo autoral que não corresponde a nenhuma ação defensiva do herói). Não se ajusta limiar: vai ao dono (§9).
- **Vazamento.** Nenhum texto novo é escrito; todos vêm de fichas/fauna já linted. A linha da preparação usa só tipos de sinal e a aproximação (já lintada, sem nome).
- **Conflito com 360-B em voo.** Esta spec não toca em `data/bestiario/fauna/*.yaml`, `fauna.json` nem nas fichas; a 360-B pode correr em paralelo. `bestiario_saber.json` é regenerado se uma ficha mudar `contra_jogo` (teste de frescor pega).
- **MockLLM / FallbackLLM.** Nenhum caminho novo de LLM; a preparação já tem guard e fallback (`encounter_preparation.py:445-480`). O MockLLM ignora a linha nova: os testes conferem o prompt capturado.
- **Quota e latência.** 0 chamada nova; ≤ 50 tokens só em cenas preparadas com saber.
- **RAM.** Arena de Nova Arcádia: ~22 criaturas × 5 × 20 × 2 lutas ≈ 4,4 mil lutas MockLLM, um processo, sem xdist.

## 8. Decisões abertas (default; o coordenador decide)

- **D1 — Regra `rastreada`.** Default: **sim** (≥ 2 sinais + enfrentou). Alternativa: só `sobreviveu`/`estudada` (o contra-jogo fica mais raro; E1 pode cair abaixo de 0,30 só com `sobreviveu`).
- **D2 — Testemunha NPC revela.** Default: **não** (mesma razão da D10 da 360: exigiria escrever no ledger da 215). Fica para spec própria.
- **D3 — Legado (X-02).** Default: **não revela** contra-jogo de legado nesta spec. Alternativa: reescrever os 11 contra-jogos de Nova Arcádia como conselho tático (Opus + revisor) e incluí-los em `bestiario_saber.json` com `fonte: legado`.
- **D4 — Onde aparece o contra-jogo no presságio.** Default: **só na linha com `prenuncio`**. Alternativa: na 1ª linha do inimigo em toda rodada (mais ruído).
- **D5 — `prenuncio` no chip sem a flag.** Default: **mostrar sempre** que o backend enviar (corrige P4, lacuna da 329/355; o payload não muda). Alternativa: mostrar só com `RPG_FAUNA_SABER=on` (o chip continua sem o golpe preparado até ligar a flag).
- **D6 — Saber dá bônus mecânico.** Default: **não**; o saber só informa e o bot `leitor` mede o valor da informação. Alternativa: +1 Esquiva contra a assinatura com contra-jogo revelado (muda balanço; exigiria a arena 45–85 % de novo).
- **D7 — Proteger o avaliador.** Default: **não** pôr em `evals/protected-paths.txt` (congelado por commit, como a 361). Alternativa: proteger, como a D6 da 360 (precisa de aceite explícito do dono).
- **D8 — Limiares E1–E4.** Default: E1 ≥ 0,30; E2 ≥ +3 pp; E3 ≤ 0,92×; E4 vitória 2 ≤ 0,92 e nenhuma criatura −2 pp. Congelados na Etapa 1.

## 9. Registro de execução

**Etapa 0 (sondas).**
- População da arena: 26 criaturas de Nova Arcádia (não-chefe, ficha não-`retro`, assinatura e `contra_jogo`): as 17 `mon_*` nova/reinventada mais 9 `enemy_*` reinventadas/adotadas (a spec estimava ~22). `mon_arame_vivo`: assinatura `cri_arame_vivo_enroscar`, `a_cada_n` 3, telegrafo "{nome} recolhe o arame das costas e abre os ganchos das mãos.".
- Fichas: 368 no total (249 nova, 29 reinventada, 3 adotada, 87 `retro`); as 281 não-`retro` têm `contra_jogo` (= `bestiario_saber.json`, 281 ids, zero legado).
- Opções defensivas do herói (nível 3): Devoto/Sangromante/Corruptor têm 1 Carta de reação preparada (`dev_ombro_porta`, `san_esquiva`, `cor_membrana`), mas `cards.can_use_card` devolve `False` no setup da arena; Arcanista e Médico não têm. Ordem do `leitor` (congelada): reação usável > Guardar. Na prática só Guardar existe.
- P4 confirmado no código (Grep `prenuncio` em `web/src` = 0 antes); no e2e o chip passou a mostrar o `prenuncio` mesmo sem `contra_jogo` (D5).
- `combat_meta["scene"]` persiste entre turnos (o `saber_obs` sobrevive ao save; R20 testado); o ponto pós-`run_round` é logo depois de `logs += …` em `agents/combat.py`, onde `out`, `scene`, `actors_by_id` e `bestiary_knowledge` coexistem.

**Desvios / decisões de implementação.**
- Arena: o avaliador reproduz o fluxo de `agents/combat.py` (previsão congelada entre rodadas, `record_promise`, `absorb` por rodada, `record_kills` + `finish_combat` no fim, vitória/morte/timeout) sobre `run_round`; sem `services.fauna_saber` ele degrada para "nada se revela" (E1–E3 vermelhos).
- `view_fields` só inclui as chaves com conteúdo (listas/strings vazias não saem); `omenView` só inclui `prenuncio`/`saber` quando presentes (compatível com o teste existente de `deepEqual`).
- `absorb` também avalia a regra de revelação para todo inimigo presente na cena (não só os tocados nesta rodada), para a regra `rastreada` disparar na 1ª rodada.

**Resultados (Etapa 6).**
- Testes: `test_spec371_{eval,fonte,saber,pressagio,view,flags_off}` + 10 arquivos de regressão (enemy_decks/intent, dossiês, fase32, flags, 355, 360, perfil normal): verdes; `web` lint + `tsc -b` + `node --test` (deck-342 + fauna-saber-371) verdes; e2e `dossiers.spec.ts --workers=1`: 9/9. Golden de 30 turnos da 360 com a flag `off`: inalterado. Playtest `combate` 30 turnos com a flag `on`: 0 erro, 0 violação `error`. Contagem de `invoke` `on` = `off`.
- Arena `docs/spec371/arena-saber-nova_arcadia.{md,json}` (2600 pares, 682 s): **E1 34,4 % OK; E2 −25,59 pp FALHA; E3 0,999× FALHA; E4 vitória 55,2 % mas pior criatura −47 pp FALHA; E5 verde.** O avaliador não foi tocado. Causa: as Cartas de reação do herói nunca são usáveis na arena e a única defesa do `leitor` é Guardar, que gasta a Ação e dá Desvantagem aos próprios ataques; a luta 2 só difere da 1 por essa decisão. Diagnóstico não versionado (6 criaturas × 5 Posturas × 10 seeds): com o `leitor` impedido de defender (ou limitado à reação), E2 = 0,0 pp e E3 = 1,0 (a luta 2 fica idêntica à 1), ou seja, o produto é neutro e a regressão vem só do Guardar. **Decisão para o dono** (não resolvida aqui): (a) conteúdo/mecânica que dê ao herói uma resposta barata ao golpe preparado (Carta de reação usável, ou bônus de Esquiva contra a assinatura conhecida, D6), ou (b) nova spec de avaliador com outro bot defensivo.

**Conteúdo de Cartas — decisão do dono 03/11 "Reação p/ toda Postura" (§9 (a), D6 mantida: o saber só informa).**
- Duas Cartas de reação de tronco (nível 1, comum, onda 1, `gatilho: ao_ser_atacado`), registradas em `data/cards/_ondas.yaml` (voz coberta pela autorização geral de 27/10, sem leitura):
  - `arc1_ini_cinza_nos_olhos` "Cinza nos Olhos" (Arcanista; Entropia 2, Fôlego 1, turno): aplica Cego (Desvantagem) em quem ataca. "Sopra contra os olhos de quem ergue o golpe a cinza que o éter deixou no cajado."
  - `med1_ini_pinca_no_tendao` "Pinça no Tendão" (Médico; Entropia 0, Fôlego 1, turno): aplica Desarme (−2 de dano) em quem ataca. "Dedos de trincheira acham o tendão do pulso que desce; a mão afrouxa e o golpe chega sem peso."
  - Não são reskin de `san_esquiva`/`cor_membrana` (condição no atacante, não Esquiva/Proteção). Lint sem erro nem aviso; custos escolhidos para não repetir a assinatura de `arc1_des_garganta`/`med1_fer_garra_de_protese`.
- Preparação inicial: campo `reacao_inicial` na Carta; `character_creator.starting_reaction_id`/`keep_starting_reaction` põem a reação no Acervo e nas Preparadas automáticas (toma a vaga da última Carta não `ativa`: Arcanista sai `arc_olho`; Médico sai `med_triagem`). `playtest/runner.py` (nível > 1) aplica a mesma regra; o herói de nível 3 da arena passa a ter a reação. Devoto, Sangromante e Corruptor: preparação inalterada (teste).
- Sonda (goblin, 400 seeds, reação armada): perda média de Vitalidade na rodada Arcanista 1,55 → 1,07, Médico 1,55 → 0,36 (Sangromante com `san_esquiva`: 0,90). A condição dura até o turno seguinte do atacante (marcador `_pula_tick` da SPEC-339), como as demais reações de condição.
- Arena oficial de Posturas (`docs/spec341/arena_spec341.py posturas --seeds 180:260`; o bot não joga reações, então mede só a diluição do baralho): Arcanista `todas` 49,0 → 48,1 % (cal 61,7 → 60,1; des 47,3 → 47,3; imp 56,6 → 56,6); Médico `todas` 47,3 → 46,7 % (trincheira 48,3 → 45,9; boticário 47,1 → 45,8; ferro 51,8 → 50,9). Tudo dentro de 45–85 %. Artefatos `docs/spec371/arena-posturas-reacao-{antes,depois}.json`. A arena do saber (`scripts/fauna/arena_saber.py`) não foi rodada nem tocada (é do coordenador).
- Devoto (`dev_ombro_porta`, `ao_inimigo_engajar`): não mudou. O gatilho só casa com ataque corpo a corpo de quem ainda não está engajado (`services/reactions.py:78-79`); contra a assinatura, que chega depois do 1º engajamento, quase nunca dispara. Proposta (precisa de aprovação, mexe no motor e numa Carta legada guardada pelo golden da 341): o gatilho `ao_inimigo_engajar` também casar quando o golpe declarado é a assinatura anunciada (campo `anunciado` em `_declared_attack`, lido da intenção congelada da 329). Fica na identidade ("o ombro devolve o invasor antes do golpe") e vale também para `cor_chao_morde` e `med1_bot_frasco_aos_pes`. Alternativa sem motor: nova reação de tronco do Devoto com `ao_ser_atacado`.

**Devoto e diagnóstico da Gralha (pedido do coordenador após a arena do saber rerodada: E1 34,4 % OK, E2 +3,69 pp OK, E3 0,895× OK, E4 falha só pela pior criatura: `mon_gralha_de_crematorio` −19 pp, `mon_lencol_de_chamine` −4 pp).**
- Devoto sem mudar o motor: `dev1_ini_dor_devolvida` "Dor Devolvida" (reação de tronco, comum, nível 1, Entropia 1, Fôlego 1, turno, `ao_ser_atacado`, Virtude corpo/força): contra-ataque de 2 em quem ataca. "O Devoto deixa o ferro entrar até onde a fé aguenta e devolve a dor pelo mesmo caminho." Fica no primário do Devoto ("dano ao ser atingido"); não é Esquiva nem Proteção. Lint sem erro nem aviso. `reacao_inicial`: nível 1 sai `dev_aguentar`; nível 3 da arena sai `dev_conviccao`. `keep_starting_reaction` agora põe a reação inicial antes de outra reação já preparada (`dev_ombro_porta`): é a resposta padrão; a outra é situacional. Isso também faz o `leitor` (que pega a 1ª reação disponível) não armar o Ombro, que quase nunca casa.
- Arena de Posturas do Devoto (`posturas --seeds 180:260`): `todas` 61,0 → 61,0 %; consagrado 61,7 → 61,1; zeloso 58,8 → 58,8; enlutado 64,0 → 64,3. Dentro de 45–85 %. Artefatos `docs/spec371/arena-posturas-devoto-{antes,depois}.json`.
- Diagnóstico da Gralha (sonda não versionada sobre `arena_saber.fight`, 20 seeds, com as 3 Cartas novas, sem alterar o avaliador). Médico: luta 1 vence 11/20 (7 timeouts) e só ataca; luta 2 vence 3/20 (17 timeouts), com 199 reações, 148 Guardar e 25 ataques. Sangromante: 129 ataques → 112 reações + 84 Guardar. Devoto com a Carta nova: 16 → 17 vitórias (antes 16 → 9).
- Causa: política congelada do bot, não conteúdo. (1) `_triggers` defende sempre que a linha tem `contra_jogo`. A assinatura da Gralha é fraca (3 de dano, `a_cada_n` 2, bando de lacaios), então na luta 1 o valor estimado nunca passa de 30 % e o bot só ataca. Na luta 2 ele defende em toda rodada contra um lacaio covarde de 12 de Vitalidade que recua 3 zonas, e a luta estoura o limite de 20 rodadas. (2) `reacao_disponivel` lê `card_usage` antes de `run_round` zerar o uso `turno` (`services/conflict_orchestrator.py:2804`), então uma reação usada na rodada anterior aparece gasta e o bot cai no Guardar uma rodada sim, outra não. O conteúdo está certo: o `contra_jogo` da Gralha já manda o oposto ("Matá-la antes de ela sair do alcance ou não preparar nada enquanto ela ronda"). O Lençol (−4 pp, Médico 14 → 12) está no ruído de 20 seeds, e a 2ª parte da assinatura é dano em área condicional que nenhuma reação evita. Nada foi mudado no avaliador nem nas fichas. Correção possível só por nova spec de avaliador: defender só quando o valor estimado pede, e ler o uso depois do reset da rodada.

**2ª correção do harness e decisão do dono (coordenador, 03/11).** Autor de eval independente corrigiu a leitura do uso `turno` antes do reset da rodada (`6c32b683`; relatório `7265ed1e`; parecer `handoffs/SPEC-371-eval-authoring.md` §2). Arena com a mesma configuração: E1 34,4 % OK, E2 +10,06 pp OK, E3 0,842× OK, E4 67,5 % OK mas pior criatura −3,0 pp (`enemy_elemental_fogo_poluido`, `mon_lencol_de_chamine`, ambas puxadas pelo Médico −10) contra o limiar −2 pp. **Dono (03/11): "Aceitar o desvio"** — 3 lutas em 100 por criatura, dentro do ruído de 20 seeds; limiar e avaliador intocados; `test_arena_a_luta_ensina[E4]` fica vermelho como desvio aceito e documentado. Política `_triggers` (defender sempre que há `contra_jogo`) não foi mudada; observação registrada no parecer de eval.
