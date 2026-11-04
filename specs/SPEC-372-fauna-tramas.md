# SPEC-372 — Criaturas de trama: o campo `tramas` passa a valer, com estágio de trama derivado (filha 360-D; Nova Arcádia)

> **Status:** `done` — aprovada pelo dono em 03/11 via pedido de execução imediata ("transforme em spec e execute agora"); os defaults da §8 valem até ele dizer o contrário.
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-04
> **Depende de:** SPEC-360 (`done`: `services/fauna.py`, campo `tramas` validado só em forma, NA com 38 entradas aprovadas). SPEC-350 (`done`: catálogo `data/world/plot_threads.json`, hoje só com as 7 tramas de Nova Arcádia; `services/plot_threads.py`). SPEC-351 (`done`, opcional: o fio de abertura conta como "tocada"). **Não** depende da SPEC-370: Nova Arcádia já tem fauna.
> **Desbloqueia:** criaturas de trama nas regiões 2–12, quando a SPEC-350 povoar outras regiões (ondas em `plot_threads.json:12-58`) e a SPEC-370 tiver coberto a região; presságio e saber ligados à trama (filha 360-C, se quiser).
> **EXECUTOR_MODEL:** `Terra` (Sonnet, `spec-executor`) no estágio derivado, motor, lint, flag e testes. **Opus** (`claude-opus-5-5`, `spec-author`) escolhe e justifica as ligações criatura → trama em NA. Nunca Fable (dono, 28/10). **REVIEW_MODEL:** revisor Opus independente (`spec-reviewer`, nunca o autor) para as ligações; `Sol` técnico (estado derivado, determinismo, flags, integridade de eval). **REVIEW_REQUIRED:** `true`.
> **EVAL_AUTHORING_REQUIRED:** `true`. Avaliador novo, escrito e congelado antes do produto por um autor de eval que não executa o produto, e protegido em `evals/protected-paths.txt` (mesmo padrão da D6 da 360).

Rótulos: **[F]** fato no HEAD `86cb7bb8` · **[D?]** decisão aberta (§8, com default) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

O terceiro pilar da fauna viva, decidido pelo dono em 01/11, é "criaturas que pertencem a uma trama aparecem quando ela avança" (SPEC-360 §1, pilar 3). A 360 deixou o campo `tramas` no bloco de fauna, mas inerte: o lint só confere que é lista de strings e o build copia (`services/fauna_lint.py:160-163`, `scripts/fauna/build.py:55`) [F]. Todas as 38 entradas de NA têm `tramas: []` (`scripts/fauna/rascunho.py:69`). A SPEC-350 criou 7 tramas em Nova Arcádia, sem estágio: deixou "escalada mecânica de trama" fora de escopo (`specs/SPEC-350-mundo-povoado-tramas.md:232-234`).

Esta spec liga as duas coisas sem estado novo. O **estágio da trama** é uma visão derivada do que o jogo já grava: NPC âncora conhecido, rumor percebido, quest de investigação, segredo revelado. A criatura ligada a uma trama **não existe** no sorteio antes do estágio dela; depois, pesa mais nos locais da trama, nasce como presença ali e puxa os rumores da trama. Tudo determinístico, atrás de uma flag nova `RPG_FAUNA_TRAMAS` (`off`).

**Problemas, com evidência [F]:**

| # | Problema | Evidência |
|---|---|---|
| P1 | `tramas` é validado e compilado, mas nenhum código lê | `services/fauna_lint.py:160-163`; `scripts/fauna/build.py:55`; `Grep tramas services/fauna.py` sem resultado |
| P2 | As tramas não têm estágio; nada diz se o jogador já tocou numa trama | SPEC-350 §Fora de escopo (`:232-234`); `services/plot_threads.py:48-64` (`PlotThread` sem estado) |
| P3 | Os sinais de progresso já existem, espalhados em 4 donos diferentes | rumor percebido: `services/rumors.py:588-603` (`perceived_day`); quest: `state["quests"]` com `world_kind == "investigar_rumor"` e âncora `rumor_id` (`services/lore_quests.py:350-356`, `:700`); segredo: `services/memory_provenance.py:156-174` (`accepted_secret_ids`); NPC conhecido: `known_by_player`/`knowledge_source` (`services/prologue.py:790`, `services/player_knowledge.py:163-164`); fio de abertura: `campaign_plan.opening_thread` (`services/prologue.py:793-800`, `services/opening_threads.py:454-462`) |
| P4 | O peso ecológico é um produto de fatores puros num `EcoCtx` congelado, sem acesso ao estado da trama | `services/fauna.py:272-364`; `world_utils.py:1130-1153` |
| P5 | Com todos os pesos ecológicos em 0, o sorteio volta aos pesos legados, o que traria de volta uma criatura "escondida" pela trama | `world_utils.py:1154-1155` (`if sum(eco_weights) > 0`) |
| P6 | O rumor de fauna só sabe dar boost à semente `avistamento` da criatura presente; não conhece os `rumor_ids` da trama | `services/rumors.py:259-278` (`_fauna_present`, `_fauna_boost`); `data/world/plot_threads.json:108-110` (`rumor_ids` por trama) |

**Escopo real.** Só Nova Arcádia tem catálogo de trama (`plot_threads.json`: 7 tramas `tr_na_*`; as ondas 2–7 estão `pending`, `:12-58`). O motor e o lint ficam genéricos; o conteúdo cobre só NA.

## 2. Requisitos

### A. Estágio derivado (sem estado novo)

- **R1 — `plot_stage(state, thread_id)`** em `services/plot_threads.py` (dono do catálogo) devolve um de `dormente < tocada < investigada < revelada`, o maior que se aplica:
  - **tocada:** (a) algum `anchor_npc_id` das `portas` é conhecido do jogador (linha do NPC resolvida por `npc_world._row_for`, como em `plot_threads.py:283-284`, com `known_by_player` verdadeiro ou `knowledge_source == "met"`); ou (b) há rumor percebido (`world_sim.rumors[].perceived_day`) cuja `seed_id` está em `thread.rumor_ids` ou nos `rumor_ids` de uma porta; ou (c) o fio de abertura (`campaign_plan.opening_thread.thread_refs`) aponta para a trama ou para uma porta dela;
  - **investigada:** existe quest em `state["quests"]` com `world_kind == "investigar_rumor"`, `status ∈ {active, completed}` e âncora cujo rumor tem `seed_id` na trama; ou quest de porta (`quest_hint`) com o mesmo critério; ou rumor da trama resolvido como `confirmado`;
  - **revelada:** algum `thread.secret_ids` (casefold) está em `memory_provenance.accepted_secret_ids(state)`.
  Função pura: não grava nada, não chama LLM. Trama inexistente → `dormente`.
- **R2 — Monotonia prática.** Como as entradas só crescem (rumor percebido não volta, segredo aceito não volta), o estágio não regride. Exceção documentada: quest `active` que falha ou é abandonada pode baixar de `investigada` para `tocada`. Teste: `test_quest_abandonada_volta_a_tocada`.
- **R3 — `plot_stages(state, region_id) -> dict[str, Stage]`** calcula todas as tramas da região de uma vez (uma passada por `quests`, `rumors` e `event_log`). É chamada no máximo uma vez por chamada de `pick_encounter_enemy` e uma vez por região no `day_hook`.

### B. Dados e lint

- **R4 — Forma de `tramas`.** Passa a ser lista de objetos `{id: <thread_id>, desde: tocada|investigada|revelada}` [D?] (D1). String solta continua aceita e vale `desde: tocada` [D?] (D2). `fauna.json` normaliza para objetos.
- **R5 — Lint (`services/fauna_lint.py`), regras novas** (numeradas depois das E17/E18 da SPEC-370 para não colidir):
  - **E19:** `id` existe em `plot_threads.json` e `thread.region_id == entry.regiao`;
  - **E20:** `desde` no enum; no máximo 2 tramas por criatura; BOSS não tem `tramas` (BOSS nunca vira presença nem é sorteado, então a ligação não teria efeito);
  - **E21:** território efetivo da criatura ∩ `thread.locations` ≠ ∅; e no máximo **25 %** das criaturas não-BOSS da região com `tramas` não vazio [D?] (D4);
  - **E22:** nenhum texto de `sinais` de criatura ligada contém token (≥ 4 letras, fold sem acento) das assinaturas dos `secret_ids` da trama (`services/secret_signatures.SECRET_SIGNATURES`) nem dos nomes dos NPCs do `core` da trama (`plot_threads.cast_names`).
- **R6 — Ligações autoradas em NA.** O autor Opus liga criaturas de `data/bestiario/fauna/nova_arcadia.yaml` às 7 tramas `tr_na_*`. Meta: ≥ 4 das 7 tramas com ≥ 1 criatura [D?] (D5), dentro do teto do E21. Cada ligação é justificada no parecer por um trecho da ficha (ou do Codex do legado) e pelo `resumo_publico` da trama, **nunca** pelo segredo. O revisor Opus independente aprova cada ligação (§3.5).

### C. Motor (flag `RPG_FAUNA_TRAMAS`)

- **R7 — Portão antes do estágio.** Com a flag `on`, uma criatura com `tramas` cujo estágio de **nenhuma** das suas tramas atingiu `desde` tem fator **0** (razão `trama_dormente`). Vale no sorteio de encontro, no nascimento de presença do `day_hook`, no tipo `track` e na semente `avistamento` do rumor (R11).
- **R8 — Sem volta pelo legado (P5).** Criatura com fator 0 por trama sai do pool também quando a soma dos pesos ecológicos é 0 e o sorteio cai nos pesos legados (`world_utils.py:1154-1155`). Teste: `test_portao_vale_no_fallback_legado`.
- **R9 — Puxão depois do estágio.** Com o estágio atingido, a criatura pesa `TRAMA_MULT` (2,0, `[BALANCEAR]` em `fauna_config.json`) nos `locations` das tramas atingidas, e 1,0 fora delas. O fator entra no produto de `eco_multiplier`, depois dos fatores da 360, e aparece em `razoes` (`trama:<thread_id>`).
- **R10 — Presença nos locais da trama.** No `day_hook`, quando a criatura escolhida é ligada e atingida, os `locais` da presença são `território efetivo ∩ ⋃ locations das tramas atingidas` (não vazio pelo E21); a presença ganha `trama_id` opcional. Sem a flag, a presença não tem a chave (save idêntico).
- **R11 — Rumor da trama.** Com a flag `on` e `RPG_FAUNA_SINAIS=on`, quando uma criatura ligada e atingida tem presença ativa na região, as sementes em `thread.rumor_ids` (e nos `rumor_ids` das portas) ganham `RUMOR_BOOST` em `rumors.candidates`, além do boost do `avistamento` da própria criatura (`rumors.py:259-278`). O portão de segredo dos rumores (`rumors.py:180-182`) continua valendo. Antes do estágio, a semente `avistamento` da criatura ligada pesa 0 [D?] (D7).
- **R12 — Flag.** `RPG_FAUNA_TRAMAS` em `config/flags.yaml`: `kind: release`, `default: "off"`, `spec: SPEC-372`, `expires: 2027-03-01`, valores `off|on`. Exige `RPG_FAUNA=on` e `RPG_PLOT_THREADS=on`; caso contrário é tratada como `off`, com `log_event` uma vez por processo. Com a flag `off`, comportamento byte-idêntico ao de hoje (golden `tests/fixtures/spec360_flags_off_golden.json` e o relatório de NA da 360 iguais).
- **R13 — Taxa e custo.** O sorteio só escolhe **quem** (R9 da 360): o número de gatilhos de encontro com a flag `on` é igual ao do `off` nas mesmas seeds. 0 chamada LLM nova. `plot_stages` custa < 5 ms em média (teto de teste 20 ms) num estado com 50 quests, 100 rumores e 200 eventos.
- **R14 — Telemetria.** `log_event("fauna", "trama_portao" | "trama_puxao" | "trama_presenca", creature=…, thread=…, stage=…)`; só ids, nunca texto, segredo ou nome de NPC.

### D. Eval (autor de eval, antes do produto)

- **R15 — Avaliador `scripts/fauna/eval_tramas.py` + `tests/test_spec372_eval.py`**, protegidos e congelados antes do produto. NA, estados sintéticos montados pelo próprio avaliador (o estágio esperado é literal no teste, não sai do `plot_stage`):
  - **T1 (portão):** para cada criatura ligada, com o estágio abaixo de `desde`: fatia exatamente 0 em `encounter_distribution` em todo nó × período; 0 presença nascida em 20 seeds × 30 dias; 0 escolha no tipo `track`;
  - **T2 (puxão):** com o estágio atingido, a fatia da criatura nos `locations` da trama ≥ **1,5×** a fatia com a flag `off`;
  - **T3 (locais):** 100 % das presenças de criatura ligada e atingida nascem com `locais ⊆ locations` da trama;
  - **T4 (quantidade):** gatilhos iguais `on`×`off`; combates de fauna por 100 ações com a flag `on` (todas as tramas `dormente`, e depois todas `revelada`) entre **−10 % e +5 %** do `off` (com `RPG_FAUNA`/`RPG_FAUNA_SINAIS` `on` nos dois);
  - **T5 (vazamento):** 0 token de assinatura de segredo da trama ou de nome do `core` em qualquer texto emitido na simulação (sinal, conversão, rastro, aproximação);
  - **T6 (determinismo):** duas execuções com a mesma seed dão relatório byte-idêntico;
  - **T7 (off):** com a flag `off`, o relatório da 360 para NA (`scripts/fauna/eval.py`) é byte-idêntico ao baseline da Etapa 0;
  - **T8 (estágio):** 10 estados sintéticos (um por regra de R1, mais combinações e o caso de R2) dão o estágio literal esperado.
  Relatório em `docs/spec372/eval-tramas-nova_arcadia.md`.

### E. Playtest

- **R16 — Invariante.** `fauna_presenca_valida` (`playtest/invariants.py`) passa a conferir também: presença com `trama_id` tem a criatura ligada a essa trama, e `locais ⊆ locations`. `playtest run --profile explorador --turns 50` com `RPG_FAUNA`, `RPG_FAUNA_SINAIS`, `RPG_PLOT_THREADS` e `RPG_FAUNA_TRAMAS` `on` termina com 0 violação `error`.

### Fora de escopo

- Tramas fora de Nova Arcádia: só quando a SPEC-350 (ondas 2–7) publicar o catálogo da região **e** a SPEC-370 tiver a fauna dela. O motor e o lint já servem; falta só conteúdo (uma spec curta por onda, ou um item no plano da onda).
- Avançar a trama por causa da criatura (matar a criatura de trama não muda o estágio), relógio de trama, presságio de trama, fim de trama.
- Sinal ou `aproximacao` específicos de trama (texto novo por estágio); variantes de trama da SPEC-361 (`data/bestiario/modificadores_trama.yaml`).
- Mostrar o estágio na UI, no diário ou na API.
- Criatura de trama BOSS (E20 proíbe).
- Supressão entre humanos (F-16), caps em escala, Víbora R2-02: SPEC-370.
- Ligar a flag em staging ou produção (coordenador, depois do smoke).

## 3. Design técnico

### 3.1 Arquivos

**Novos**

| Arquivo | Responsabilidade |
|---|---|
| `scripts/fauna/eval_tramas.py` | Avaliador T1–T8 (**autor de eval**) |
| `tests/test_spec372_eval.py` | Asserts com limiares literais (**autor de eval**, protegido) |
| `docs/spec372/eval-tramas-nova_arcadia.md` | Relatório |
| `handoffs/SPEC-372-eval-authoring.md`, `handoffs/SPEC-372-independent-review.md`, `handoffs/SPEC-372-sol-review.md` | Registros de eval, ligações e revisão técnica |
| `tests/test_spec372_{stage,lint,motor,rumor,flags_off}.py` | §4 |
| `tests/fixtures/spec372/` | YAML de fauna e estados sintéticos |

**Alterados**

| Arquivo | O que muda |
|---|---|
| `services/plot_threads.py` | `Stage`, `STAGES`, `plot_stage`, `plot_stages` (R1–R3), só leitura |
| `services/fauna.py` | `EcoCtx.trama_stages`; fator de trama em `eco_multiplier` (R7, R9); `day_hook` com `locais` da trama e `trama_id` (R10); `tramas_mode()` (R12) |
| `world_utils.py` | `pick_encounter_enemy`: passa `trama_stages` ao `eco_ctx`; remove do pool quem tem fator 0 por trama antes do fallback legado (R8) |
| `services/rumors.py` | Boost dos `rumor_ids` da trama e portão do `avistamento` (R11) |
| `services/fauna_lint.py` | E1 aceita a forma nova; E19–E22 (R5) |
| `scripts/fauna/build.py` | Normaliza `tramas` para objetos |
| `data/bestiario/fauna/nova_arcadia.yaml` | Ligações autoradas (R6) |
| `data/world/fauna.json` | Regenerado |
| `data/world/fauna_config.json` | `TRAMA_MULT` |
| `config/flags.yaml` | `RPG_FAUNA_TRAMAS` (R12) |
| `playtest/invariants.py` | R16 |
| `evals/protected-paths.txt` | `+ scripts/fauna/eval_tramas.py`, `+ tests/test_spec372_eval.py` (autor de eval) |

### 3.2 Formato

```yaml
  mon_<criatura_de_na>:
    ...
    tramas:
      - {id: tr_na_corpos_marcados, desde: tocada}
```

O id da criatura é escolhido pelo autor na Etapa 4; o exemplo usa só um id real de trama (`plot_threads.json:199`). `fauna.json`: `"tramas": [{"id": "tr_na_corpos_marcados", "desde": "tocada"}]`.

### 3.3 Assinaturas

```python
# services/plot_threads.py
Stage = Literal["dormente", "tocada", "investigada", "revelada"]
STAGES: tuple[Stage, ...] = ("dormente", "tocada", "investigada", "revelada")

def plot_stage(state: dict, thread_id: str) -> Stage: ...
def plot_stages(state: dict, region_id: str) -> dict[str, Stage]: ...

# services/fauna.py
TRAMAS_MODES = ("off", "on")
def tramas_mode() -> str: ...  # "off" se RPG_FAUNA != on ou RPG_PLOT_THREADS != on
def trama_factor(entry: dict, ctx: EcoCtx) -> tuple[float, str | None]: ...
# EcoCtx ganha: trama_stages: Mapping[str, str] (default vazio => sem efeito)
# Presenca ganha: trama_id: NotRequired[str]
```

`trama_factor`: sem `tramas` ou flag `off` → `(1.0, None)`. Nenhuma ligação atingida → `(0.0, "trama_dormente")`. Alguma atingida e `ctx.location_id` em `locations` de uma atingida → `(TRAMA_MULT, "trama:<id>")`. Atingida fora dos locais, ou `location_id == ""` (contexto regional do `day_hook`) → `(1.0, "trama:<id>")`.

### 3.4 Fluxo com a flag `on`

1. `day_hook` (por região): `plot_stages(state, region)` → `EcoCtx.trama_stages` → candidatas com fator 0 saem; a escolhida ligada nasce nos locais da trama, com `trama_id`.
2. `rumors.day_hook`: sementes da trama com boost se há presença ligada e atingida; `avistamento` da criatura dormente pesa 0.
3. `check_encounter` → `pick_encounter_enemy`: `plot_stages` uma vez; portão e puxão no peso; quem tem fator 0 por trama não volta pelo fallback.
4. Sinais, conversão, caça e aproximação seguem a 360 sem mudança.

### 3.5 Checklist do revisor de ligações (por ligação)

1. A criatura cabe na trama pelo `resumo_publico` e pela ficha (citar o trecho de cada um), não pelo segredo.
2. O `desde` faz sentido: criatura que é consequência do que a trama esconde → `investigada` ou `revelada`; criatura que é o sintoma visível → `tocada`.
3. Os sinais da criatura não apontam para o segredo nem para o `core` (além do E22, leitura humana).
4. Esconder a criatura até o estágio não tira de NA uma ameaça básica do hub (o miúdo comum da Lama, por exemplo, não deve virar criatura de trama).
5. Não há duas tramas disputando a mesma criatura sem motivo.

## 4. Plano passo a passo

### Etapa 0 — Sondas (executor; sem código)

1. Confirmar e registrar na §9: o campo que marca NPC conhecido (`known_by_player` × `knowledge_source`); o formato de `opening_thread.thread_refs` (id de trama ou de porta); como a âncora `rumor_id` da quest liga à `seed_id` (`world_sim.rumors`); o desfecho `confirmado` de rumor (`rumors.py:838-905`); a cadeia de chamada até `pick_encounter_enemy` (onde o `state` está disponível para `plot_stages`).
2. Baseline: hash de `scripts/fauna/eval.py` (relatório de NA) com a `main`; `tests/test_spec360_*.py`, `tests/test_spec350_*.py` e `tests/test_spec351_*.py` com `-n 2`.

### Etapa 1 — Avaliador (autor de eval; commit próprio, antes do produto)

1. `scripts/fauna/eval_tramas.py` e `tests/test_spec372_eval.py` com T1–T8 e limiares literais (R15). As ligações ainda não existem: o avaliador lê as criaturas ligadas de `fauna.json`; com zero ligações, T1–T3 ficam `xfail(strict=True)` com motivo "sem ligação autorada", e T4–T8 já rodam.
2. `evals/protected-paths.txt`, `handoffs/SPEC-372-eval-authoring.md`. Commit `test(fauna): freeze SPEC-372 plot-creature evaluator`.

### Etapa 2 — Estágio derivado (TDD)

1. **Testes** (`tests/test_spec372_stage.py`): `test_dormente_sem_sinal`, `test_tocada_por_npc_conhecido`, `test_tocada_por_rumor_percebido`, `test_tocada_por_fio_de_abertura`, `test_investigada_por_quest`, `test_investigada_por_rumor_confirmado`, `test_revelada_por_segredo_aceito`, `test_maior_estagio_vence`, `test_quest_abandonada_volta_a_tocada`, `test_trama_inexistente_dormente`, `test_plot_stages_uma_passada`, `test_plot_stage_nao_muta_estado`.
2. **Implementação:** `plot_threads.py`.

### Etapa 3 — Forma, lint e build (TDD)

1. **Testes** (`tests/test_spec372_lint.py`): `test_string_vira_tocada`, `test_e19_trama_inexistente`, `test_e19_regiao_errada`, `test_e20_boss_com_trama`, `test_e20_tres_tramas`, `test_e21_territorio_sem_locais`, `test_e21_teto_25`, `test_e22_assinatura_de_segredo`, `test_e22_nome_do_core`; `test_fauna_json_fresco` continua verde.
2. **Implementação:** `fauna_lint.py`, `build.py`.

### Etapa 4 — Ligações em NA (Opus + revisor)

1. Autor Opus lê as 7 tramas (só campos públicos: `title`, `pergunta`, `resumo_publico`, `locations`, `portas[].hook_public`) e as fichas de NA por Grep; propõe as ligações com justificativa. Lint com 0 erro.
2. Revisor Opus independente, checklist §3.5; parecer em `handoffs/SPEC-372-independent-review.md`.
3. `build.py`; `validate_content.py` com 0 ERRO.

### Etapa 5 — Motor, rumor e flag (TDD)

1. **Testes:**
   - `tests/test_spec372_motor.py`: `test_portao_zera_antes_do_estagio`, `test_portao_vale_no_fallback_legado` (R8), `test_puxao_nos_locais`, `test_fora_dos_locais_neutro`, `test_presenca_nasce_nos_locais_da_trama`, `test_presenca_sem_trama_id_com_flag_off`, `test_track_respeita_portao`, `test_taxa_de_gatilho_inalterada`, `test_plot_stages_latencia`;
   - `tests/test_spec372_rumor.py`: `test_boost_dos_rumores_da_trama`, `test_avistamento_dormente_pesa_zero`, `test_portao_de_segredo_continua`;
   - `tests/test_spec372_flags_off.py`: golden `off` byte-idêntico; `tramas_mode()` é `off` sem `RPG_PLOT_THREADS=on` ou sem `RPG_FAUNA=on`; contagem de `invoke` igual `on`×`off` numa campanha MockLLM em `na_anel_lama` (reusar o padrão de `test_campanha_na_lama_exercita_fauna_sem_chamada_extra` da 360).
2. **Implementação:** `fauna.py`, `world_utils.py`, `rumors.py`, `fauna_config.json`, `config/flags.yaml`, `playtest/invariants.py`.
3. **Verificação:** testes da etapa + `tests/test_spec360_*.py` + `tests/test_spec312_seeds.py` com `-n 2`.

### Etapa 6 — Eval e playtest

1. `scripts/fauna/eval_tramas.py` → relatório. Se T2 ou T4 falhar: ajustar `TRAMA_MULT` (constante `[BALANCEAR]`) ou o conteúdo (`desde`, quais criaturas), com o revisor; registrar na §9. Nunca o avaliador.
2. `scripts/fauna/eval.py` (360) com a flag `off`: byte-idêntico ao baseline (T7).
3. Playtest `explorador` 50 turnos com as quatro flags `on` (R16).

### Etapa 7 — Revisão Sol

Estado derivado sem writer novo; determinismo; flag `off`; R8; integridade de eval (diff dos protegidos vazio depois da Etapa 1). Handoff `handoffs/SPEC-372-sol-review.md`.

### Etapa 8 — Smoke real (§6) e pouso

## 5. Critérios de aceite

- [x] `plot_stage`/`plot_stages` puros, com os 12 testes da Etapa 2 (R1–R3)
- [x] Forma nova de `tramas`, string legada aceita; E19–E22 com fixtures boas e ruins; `lint.py --regiao nova_arcadia` com 0 erro (R4, R5)
- [x] ≥ 4 das 7 tramas de NA com ≥ 1 criatura, ≤ 25 % das não-BOSS ligadas, todas as ligações aprovadas por revisor ≠ autor (R6)
- [x] Portão, puxão, presença nos locais e `track` com teste; portão vale no fallback legado (R7–R10)
- [x] Boost dos rumores da trama e portão do `avistamento` com teste; portão de segredo intacto (R11)
- [x] `RPG_FAUNA_TRAMAS` registrada `off`; golden `off` e relatório de NA da 360 byte-idênticos (R12, T7)
- [x] Gatilhos iguais `on`×`off`; 0 chamada LLM nova; latência no teto (R13)
- [x] Avaliador commitado antes do produto, protegido, intocado depois; T1–T8 verdes; relatório publicado (R15)
- [x] Playtest com as quatro flags `on`: 0 violação `error` (R16)
- [x] Revisão Sol `APPROVED` ou `APPROVED_WITH_FOLLOWUPS`
- [x] `uv run pytest` verde (suíte completa, no pouso, pelo coordenador)
- [x] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo)
- [x] Saves antigos continuam carregando (`trama_id` é opcional; presença sem ele vale como hoje)
- [x] Smoke real da §6 executado e registrado na §9

## 6. Smoke test com LLM real

Coordenador, API local, rotas `ROUTES` de hoje (DeepSeek primário), com `RPG_WORLD_ENGINE`, `RPG_FAUNA`, `RPG_FAUNA_SINAIS`, `RPG_PLOT_THREADS` e `RPG_FAUNA_TRAMAS` `on`. ≤ 6 turnos (~18 chamadas).

1. Save scratch (não versionado) em NA, num nó de `locations` de uma trama com criatura ligada (`desde: tocada`), trama `dormente`.
2. Dois turnos de descanso (virada de dia): no estado, nenhuma presença da criatura ligada; log `trama_portao` com ids.
3. Falar com o NPC âncora de uma porta da trama (ou ouvir o rumor dela): `plot_stage` vira `tocada` (conferido por script de leitura do save, sem LLM).
4. Virar o dia: se nascer presença da criatura ligada, ela tem `trama_id` e `locais ⊆ locations`.
5. Chegar ao nó: `<SINAIS_NA_CENA>` no prompt; a narração **não** traz o nome da criatura, nenhum nome do `core` da trama nem frase de segredo (`LEAK_PHRASES`).
6. Custo: chamadas por turno iguais às do mesmo roteiro com `RPG_FAUNA_TRAMAS=off`.

## 7. Riscos & compatibilidade

- **Criatura que some.** Quem nunca toca uma trama nunca vê a criatura dela. Por isso o teto do E21 (25 %), o item 4 do checklist (§3.5) e o T4 (a quantidade de combate não cai mais de 10 %).
- **Vazamento pela ligação.** A ligação em si é pública (o jogador não a vê). O risco é o sinal sugerir o segredo: E22 + T5 + revisor + smoke.
- **Estado derivado caro.** `plot_stages` varre `quests`, `rumors` e `event_log`. O teto de R13 e a chamada única por turno limitam; se passar, cache por `turn_count` dentro do turno [R].
- **Integridade de eval.** Avaliador novo, protegido, antes do produto; o T8 usa estágio literal, não o `plot_stage`, para não ter o produto como oráculo (lição do P2-8 da 360).
- **Conflito com a SPEC-370.** As duas mexem em `services/fauna.py`, `services/fauna_lint.py`, `nova_arcadia.yaml` e `fauna.json`. As regras de lint daqui começam em E19 para não colidir. Quem pousa depois faz rebase e roda `build.py`; `fauna.json` nunca se resolve à mão.
- **Saves antigos.** Sem estado novo; `trama_id` opcional na presença; o estágio é recalculado a cada leitura.
- **MockLLM / FallbackLLM.** Nenhum caminho novo de LLM; os testes conferem pesos, estado e prompt capturado.
- **Quota e latência.** 0 chamada nova; nenhum bloco novo de prompt.
- **RAM.** Um agente Opus por vez (autor, depois revisor); testes com `-n 2`.

## 8. Decisões abertas (default; o coordenador decide)

- **D1 — Forma de `tramas`.** Default: objetos `{id, desde}`. Alternativa: lista de ids com `desde` global por região (menos expressivo).
- **D2 — String solta.** Default: aceita, vale `desde: tocada`. Alternativa: erro no lint (NA hoje só tem listas vazias, então nada quebra).
- **D3 — `TRAMA_MULT`.** Default: 2,0 nos locais da trama (como a 360 §3.10 sugeriu). Alternativa: 1,5.
- **D4 — Teto de criaturas ligadas.** Default: ≤ 25 % das não-BOSS da região (em NA, 33 não-BOSS → até 8). Alternativa: ≤ 15 %.
- **D5 — Cobertura das tramas.** Default: ≥ 4 das 7 tramas de NA com criatura. Algumas tramas (o documento, o Código) podem não ter criatura plausível. Alternativa: todas as 7.
- **D6 — Portão total.** Default: fator 0 antes do estágio (360 §3.10). Alternativa: 0,1 (a criatura é rara, mas existe).
- **D7 — `avistamento` antes do estágio.** Default: pesa 0 (coerente com a criatura ausente). Alternativa: manter o rumor antigo como pista antecipada.
- **D8 — Fio de abertura conta como `tocada`.** Default: sim (a 351 já apresentou a trama ao jogador). Alternativa: só NPC ou rumor.
- **D9 — Exigir `RPG_PLOT_THREADS=on`.** Default: sim; sem tramas ligadas no jogo, o portão esconderia criaturas sem caminho para aparecer. Alternativa: só `RPG_FAUNA=on`.
- **D10 — Proteger o avaliador.** Default: sim, como a D6 da 360 (o dono aprovou o padrão em 02/11).

## 9. Registro de execução

**Etapa 0 (sondas, executor Terra, 03/11).**
- NPC conhecido: `known_by_player is True` ou `knowledge_source == "met"` na linha de `state["npcs"]` resolvida por `npc_world._row_for`; sem linha = nao conhecido (o default `True` de `npc_layers` so vale para linha existente).
- `opening_thread.thread_refs`: ids de **porta** (`<thread>__pN`, `prologue.py:180`); `plot_stage` aceita tambem o id da trama.
- Quest -> semente: `quest.lore_anchor.id` e o `rumor_id`; a `seed_id` vem da linha em `world_sim.rumors`. Rumor `confirmado` fica com `perceived_day > 0` e `resolution == "confirmado"`.
- `state` ate `pick_encounter_enemy`: `agents/storyteller.py` -> `check_encounter(..., trama_stages=)`; os outros chamadores (`rumor_adoption`, `encounter_budget`, `world_utils:1889`) nao passam `world` e ficam sem portao (fora de escopo).
- Desvio: `tramas_mode`/portao/puxao/nascimento/rumor ficaram em `services/fauna_tramas.py` e a forma + E19-E22 em `services/fauna_lint_tramas.py` (modulos novos), para `fauna.py`/`fauna_lint.py` crescerem pouco e o rebase da SPEC-370 ficar localizado. `fauna.tramas_mode()` delega. Sem `trama_puxao` em telemetria (so `trama_portao`/`trama_presenca`).
- Ligacoes em NA (Etapa 4) ainda nao feitas: T1-T3 do avaliador seguem `xfail(strict)` ate `fauna.json` ter `tramas`.

**Etapa 4 (ligações em NA, autor Opus, 03/11).** 8 de 33 não-BOSS (24 %), 5 de 7 tramas cobertas. Justificativa só por `resumo_publico`/`hook_public` e pela ficha; nenhuma pelo segredo. Lint NA 0 erro; `validate_content.py` 0 ERRO; T1–T5, T7 e T8 verdes (T2 razão mínima 1,63; T3 n = 15; T4 Δ máximo −1,0 %); M1 de NA 0,7542, relatório da 360 byte-idêntico (sha `8005b253…`).

| Criatura | Trama · `desde` | Justificativa (ficha × trama pública) |
|---|---|---|
| `mon_rosario_de_vertebras` | `tr_na_corpos_marcados` · tocada | Ficha: vértebras "de vários mortos", vive "onde os corpos sem Corvo acabam"; trama: "certos corpos nunca chegam ao forno". É o sintoma visível; no Lama sobram outros padrão (Roda de Mandíbulas, Rato da Peste). |
| `mon_sangrado_da_clinica` | `tr_na_corpos_marcados` · investigada | Ficha: doente da Praga que "uma clínica" sangrou até esvaziar; trama: Praga que marca e não mata, "o médico que os estuda" e a porta da enfermeira da clínica. É consequência do tratamento, não o primeiro sinal, por isso `investigada`. |
| `mon_sorvedouro_do_codigo` | `tr_na_lista_de_fornalha` · tocada | Ficha: Inquisidor que "patrulha os anéis de baixo atrás de magia não registrada"; trama: no Lama e no Ferro "quem tem o Éter escolhe entre se esconder e se inscrever". Território = locais da trama. |
| `mon_pavio_da_lista` | `tr_na_lista_de_fornalha` · investigada | Ficha: "mago da Lista de Fornalha" rebitado na gaiola e levado "até onde a máquina do Anel de Ferro precisa de Éter"; trama: "nos livros da Legião, o nome é outro". Mostra o que o registro faz; trama sem `secret_ids`, teto `investigada`. |
| `mon_enxerto_da_fornalha` | `tr_na_aco_que_lembra` · investigada | Ficha: lâmina de Aço de Sangue que "tem vontade", guarda "os segredos da forja"; trama: "o aço chia com vozes" e "sacramento da seita". Consequência da forja, não o chiado; por isso `investigada`. |
| `mon_quebrado_de_vitrine` | `tr_na_a_colecao` · tocada | Ficha: Elfo "de estimação" exibido numa "cadeira de exposição" com coleira da casa; trama: "raridades vivas são exibidas em saraus" no Anel Dourado. Sintoma público. |
| `mon_quebrado_de_vitrine` | `tr_na_po_de_sonho` · tocada | Ficha: pele "tratada com Pó de Fada até não sobrar remédio"; trama: "o Pó de Fada tem selo e licença… os dois aliviam, os dois cobram". Duas tramas com motivo (a peça exibida é também cliente do Pó); no Dourado a Rã de Lótus segue de suporte. |
| `mon_escritura_rastejante` | `tr_na_a_colecao` · investigada | Ficha: contrato vivo do Mercado de Carne com "as assinaturas dos devedores" na espinha; trama: "contratos que nunca vencem decidem quem vira raridade". É o mecanismo por trás da vitrine, por isso `investigada`. |
| `mon_porca_da_queda` | `tr_na_po_de_sonho` · tocada | Ficha: "comeu o que os viciados do Beco dos Desdentados vomitam"; trama: "No Beco dos Desdentados vendem Pó de Sonho". Sintoma visível do Beco; não é o miúdo comum do Lama (o Rato da Peste segue livre). |

Sem criatura: `tr_na_documento_da_legiao` (nenhuma ficha de papel/adega no Lama ou na Taverna) e `tr_na_o_que_o_lorde_trocou` (a Traça do Sino Mudo só se ligaria pela porta do sétimo sino, fraco demais; o Sorvedouro serve melhor à Lista). Desvio de conteúdo: o E22 acusou o token `conta` (do núcleo `npc_lorde_oswin_conta_de_ouro`) em dois sinais por coincidência verbal; troquei "conta que" → "jura que" (rumor do Quebrado) e "livro de contas" → "livro de dívidas" (marca da Escritura), sem mudar o sentido, e regenerei `rumor_seeds.json`.

**Correções pós-revisão (03/11, executor Terra).**
- P1-1: `resolve_track(trama_stages=)` repassa o portão; `_fauna_presence` ignora presença de criatura atrás do portão (ptheme e `_presence_entry` herdam). `test_track_respeita_portao` chama `resolve_track` de verdade.
- P2: portão também em `encounter_budget.fill_encounter` (combat.py passa os estágios) e em `rumor_adoption.encounter_hint`; `_weighted_pool` aplica o portão mesmo sem `fauna_on`. NPC conhecido = `known_by_player is True`, ou `knowledge_source == "met"` com `known_by_player` não-`False` (o lojista de `reputation.py:1044` fica de fora; o T8 congelado exige o `met` sozinho). `day_hook` nunca cai numa candidata de peso 0. Telemetria `trama_puxao` adicionada.
- Avistamentos falsos: com o `avistamento` dormente em 0, `own_avist` cai e a massa dos falsos (alvo = p/(1-p) × own_avist; `len(adj)` se own_avist = 0) cai junto. Mantido de propósito (D7): a criatura escondida não pode gerar boato próprio nem boato falso proporcional a ele. Sem teste de massa.
- E22 também confere as frases de `leak_phrases()[secret_id]` (por frase, fold); tokens de nome do núcleo ignoram `COMMON_NAME_WORDS` (`conta`, `senhor`, `senhora`, `mestre`, `velho`, `velha`, `sangue`), regra registrada em `fauna_lint_tramas.py`. NA segue com 0 erro.
- `revelada` é inalcançável para 6 das 7 tramas (`accepted_secret_ids` só mapeia 4 ids via `SECRET_ENTITY_IDS`): fora de escopo, follow-up para mapear `corpos`, `praga`, `aco_lembra`, `barril`, `elaryin`.
- Evidências: `docs/spec372/eval-tramas-nova_arcadia.md` (T1–T5, T7, T8 verdes; T2 mín 1,63; T3 n = 15; T4 Δ máx −1,0 %); playtest `explorador` 50 turnos com as 4 flags `on`: 0 erro, 0 violação; `test_campanha_na_lama_mesma_contagem_de_invoke_on_off`; `test_save_load_preserva_trama_id`.

- Smoke real §6 (04/11, `docs/spec372/smoke-real.md`): 60 dias dormente = 0 presença da criatura; conhecendo o NPC âncora, nasce no dia 24 em `na_anel_lama` com `trama_id`; 6 turnos DeepSeek: sinal `rastro` na narração, 0 frase de segredo, nome da criatura só no combate; "Corva" (núcleo) citada no cenário, não nos sinais.
