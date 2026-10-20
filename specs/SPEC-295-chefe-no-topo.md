# SPEC-295 — Chefe no topo

> **Status:** `approved` (decisão do dono em 2026-10-19: "Chefe no topo: sim"; ratifica o P2-4 da SPEC-287)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** SPEC-287 §2 (desvio "Chefe no topo") e revisão P2-4; `docs/HANDOFF-PROXIMA-SESSAO.md` §2
> **Depende de:** SPEC-285 (`done`), SPEC-287 (`done`)
> **Desbloqueia:** retomada do tuning de classe (SPEC-049) com a cadeia completa de ameaça
> **EXECUTOR_MODEL:** `Opus` · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (motor de conflito, montagem de encontro e dados do bestiário)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

O dono decidiu que, em cada nível, o Chefe é o encontro mais letal:
**Lacaio < Padrão < Elite < Chefe**. Hoje não é assim. Na arena da SPEC-285
(`docs/spec287/README.md`, 10 seeds), o Chefe fica acima do Lacaio e abaixo de
Padrão/Elite em todos os níveis 1–8, nos dois bots:

| bot | nível | Padrão | Elite | Chefe |
|---|---|---|---|---|
| cartas | 1 | 0,458 | 0,565 | 0,454 |
| cartas | 3 | 0,293 | 0,418 | 0,242 |
| cartas | 5 | 0,633 | 0,739 | 0,432 |
| cartas | 8 | 0,555 | 0,674 | 0,423 |
| basico | 1 | 0,438 | 0,588 | 0,340 |
| basico | 8 | 0,642 | 0,726 | 0,606 |

A causa já foi medida na SPEC-287 (§1 e §8): a ameaça no motor v4 é superlinear
no número de corpos (cada corpo age uma vez por rodada contra uma Vitalidade que
não cresce), e o Chefe é um corpo só. Durabilidade sozinha não fecha a distância:
+36 de Vitalidade dá 0,49 no nível 8, duas ações por rodada dão 0,42, contra
~0,70 de dois Elites.

As regras consolidadas preveem as ferramentas: §27.3 ("Elite e chefe … podem
possuir fases, Última Ação ou sobrevivência específica"). O bestiário já traz
`behavior.phases` em 7 criaturas, mas **nenhum código v4 lê esse campo** — é dado
inerte desde a migração. Esta spec dá ao Chefe economia de ações própria, sem
tocar Lacaio/Padrão/Elite e sem escalar com o herói (§5: o mundo não escala com o
protagonista; o Nível do Encontro é perigo absoluto).

Modelo "medir → decidir" das SPEC-056/285/287: sondas dos knobs, escolha do menor
conjunto que fecha a meta, ajuste fino, prova.

## 2. Meta (decisão do dono, números do coordenador)

Na arena (`docs/spec285/arena_lethality.py`, 10 seeds, níveis 1–8, bots `cartas` e
`basico`), a célula "chefe" passa a medir o **encontro de Chefe** como o jogo o
monta (Chefe + o que esta spec acrescentar, ex.: séquito):

- **C1** — Em todo nível 1–8 e nos dois bots: `Chefe > Elite`, com margem ≥ 3 pp.
  Junto com E1/E2 da SPEC-287, a cadeia completa `Lacaio < Padrão < Elite < Chefe`
  vale em toda célula.
- **C2** — Teto de sanidade: Chefe ≤ Elite + 20 pp em todo nível/bot. Chefe é o
  ápice, não sentença de morte.
- **C3** — Lacaio/Padrão/Elite nos níveis 1–8: idênticos célula a célula ao `main`
  (mesmo instrumento). Nada fora do Chefe muda.
- **C4** — Metas da SPEC-285 continuam valendo: M1 (playtest `combate` ≤ 0,564),
  M2 (mediana da 1ª queda ≥ 20 nas seeds 21–32 e na matriz SPEC-056), M3, M4
  (Lacaio ≤ 0,40 nos níveis 1–3; a tolerância de 1,5 pp da M4 vale para toda célula
  **exceto** as de Chefe, que sobem por decisão do dono) e M5 (0 `combat.no_progress`
  em `combate --turns 200`, várias seeds).
- **C5** — Metas E1–E3 da SPEC-287 continuam valendo.

## 3. Requisitos

- **R1 — Sondas antes de decidir.** Medir, na arena, cada knob isolado e as
  combinações candidatas (níveis 1, 3, 5, 8; os dois bots; ≥ 3 seeds), e registrar
  a tabela na §8. Knobs:
  - **K1 — Séquito pelo Nível do Encontro.** O Chefe entra acompanhado de N corpos
    não-chefe (Lacaio/Padrão) da própria região ou de uma lista curada no dado do
    Chefe; N e a categoria dependem só do Nível do Encontro.
  - **K2 — Ações extras do Chefe.** O Chefe age mais de uma vez por rodada (ex.: um
    segundo turno no fim da ordem do lado inimigo), com número de ações pelo Nível
    do Encontro ou fixo por categoria.
  - **K3 — Fases.** Ao cruzar um limiar de Vitalidade (ex.: `below: 0.5`), o Chefe
    troca de perfil/ganha Cartas/recupera algo, lendo o `behavior.phases` já
    presente no bestiário (ou um campo novo equivalente do gerador).
  - A sobrevivência da SPEC-287 (R4) fica como está, salvo se a sonda mostrar que
    precisa ser recalibrada junto (registrar o motivo).
- **R2 — Escolha mínima.** Implementar o menor conjunto de knobs que fecha C1–C5,
  com constantes `[BALANCEAR]` comentadas como na SPEC-287 (valor + por que é o
  menor que fecha). A escolha e as sondas descartadas ficam na §8.
- **R3 — Determinismo.** Toda mecânica nova é Python, sem LLM, e reproduzível por
  seed (usa o `rng` da rodada; nada de `random` global novo).
- **R4 — Só o Chefe muda.** Nenhum efeito sobre Lacaio/Padrão/Elite (C3). Nomeado
  segue o mesmo tratamento do Chefe só se a sonda justificar; senão fica de fora e
  isso é registrado.
- **R5 — Não escala com o herói.** Quantidades dependem do Nível do Encontro (§5.1
  das regras) e da categoria, nunca de `player.level` nem do tamanho da party.
- **R6 — Dados só pelo gerador oficial.** Qualquer campo novo no bestiário sai de
  `scripts/migrate_bestiary_v4.py` (idempotente); `data/bestiary.json` é
  regenerado, nunca editado à mão.
- **R7 — Jogo e arena montam igual.** Se houver séquito (K1), ele é montado por
  uma função pública única (ex.: `encounter_budget.boss_retinue(...)`) chamada pelo
  spawn de combate (`agents/combat.py`, junto de `clamp_encounter`/`fill_encounter`)
  **e** pela arena. O séquito não é cortado pelo `clamp_encounter` (faz parte do
  Chefe) e não conta para o piso do `fill_encounter` além do que já conta hoje.
- **R8 — Narração honesta.** O que a mecânica acrescentar aparece no log/flavor
  (ex.: "X chega com sua guarda", "X age de novo", "X entra em fúria"), no mesmo
  padrão dos logs de `fill_encounter`.
- **R9 — Saves antigos.** Combate salvo em andamento carrega e termina sem erro;
  ficha de inimigo salva sem os campos novos usa defaults.
- **R10 — Provar.** Arena antes/depois (níveis 1–8, dois bots, mesmo instrumento),
  playtest `combate` seeds 21–32 (200 turnos), matriz SPEC-056 e playtest com
  `--start-level 5/8`. Suíte completa verde.

### Fora de escopo

- Mudar Lacaio/Padrão/Elite, o orçamento (`encounter_budget`/`clamp_encounter`) ou
  a economia de ações do piso da SPEC-287.
- Chefe gerado pela LLM fora do bestiário (P2-2 da SPEC-287) — só se vier de graça
  pelo mesmo caminho; senão fica registrado como follow-up.
- Vitalidade do herói por nível (regra "Corpo define Vitalidade").
- Níveis 9–20 e economia de Entropia (SPEC-049).
- Prompts/structured output: nada de LLM novo.

## 4. Design técnico (ponto de partida; a §8 registra o que foi escolhido)

- `encounter_budget.py`: se K1, `boss_retinue(boss, encounter_level, loc, rng|turn,
  make_instance) -> (list[dict], list[str])` + constante de tamanho por Nível do
  Encontro.
- `services/conflict_orchestrator.py` (`run_round`): se K2, ações extras do Chefe
  na sequência da rodada (respeitando `_can_act`, stun, ticks de condição uma vez
  por rodada, Reações e `_stalemate_guard`); se K3, transição de fase avaliada após
  dano (ponto único, ex.: `_post_hit`/`_check_terminal`), idempotente por fase.
- `agents/combat.py`: chama `boss_retinue` após `clamp_encounter`/`fill_encounter`.
- `agents/bestiary.py`: se K3, `_ready_v4` normaliza `phases` para o formato v4.
- `scripts/migrate_bestiary_v4.py`: campos novos (ex.: `sequito`, `acoes_por_rodada`,
  `fases`) só em Chefe (e Nomeado, se R4 justificar).
- `docs/spec285/arena_lethality.py`: a célula "chefe" monta o encontro pela mesma
  função do jogo (R7); continua caindo na montagem antiga em commits sem a função.
- Sem bump de schema de save: campos novos opcionais com default.

## 5. Plano passo a passo

### Etapa 1 — Baseline e sondas

1. Rodar a arena no `main` (níveis 1–8, 10 seeds, dois bots) e o playtest
   `combate` (seeds 21–32) para a baseline.
2. Sondas K1/K2/K3 e combinações (R1) com patches locais descartáveis; registrar.

### Etapa 2 — Testes primeiro (`tests/test_spec295_chefe_no_topo.py`)

- Escolha mínima: testes do(s) knob(s) escolhido(s), por exemplo:
  - `test_retinue_depends_only_on_encounter_level` (R5: mesmo resultado com
    `player.level` 1 e 8);
  - `test_retinue_not_cut_by_clamp` e `test_non_boss_encounter_unchanged` (R4/R7);
  - `test_boss_extra_action_*` (K2: age N vezes, stun nega todas as ações da
    rodada, condição tica uma vez);
  - `test_boss_phase_triggers_once_below_threshold` (K3);
  - `test_generator_sets_boss_fields_only_on_chefe` (R6);
  - `test_old_save_enemy_without_new_fields_loads` (R9);
  - `test_same_seed_same_outcome` (R3).
- Os testes de SPEC-287/285 (`tests/test_spec287_encounter_scale.py`,
  `tests/test_letalidade_early.py`) seguem verdes sem alteração.

### Etapa 3 — Implementação, regeneração do bestiário, medição final

1. Implementar; regenerar `data/bestiary.json` pelo gerador.
2. Medir de novo (R10) e preencher a §8.
3. Ruff nos arquivos tocados; suíte completa (`-n auto`).

## 6. Critérios de aceite

- [ ] C1: `Chefe > Elite` (≥ 3 pp) em todo nível 1–8, nos dois bots
- [ ] C2: Chefe ≤ Elite + 20 pp em todo nível/bot
- [ ] C3: Lacaio/Padrão/Elite idênticos ao `main` célula a célula, níveis 1–8
- [ ] C4/M1: playtest `combate` (seeds 21–32) ≤ 0,564
- [ ] C4/M2: mediana da 1ª queda ≥ 20 (seeds 21–32 e matriz SPEC-056)
- [ ] C4/M3: `tests/test_letalidade_early.py` verde
- [ ] C4/M4: Lacaio ≤ 0,40 nos níveis 1–3; nenhuma célula não-Chefe piora > 1,5 pp
- [ ] C4/M5: 0 `combat.no_progress` em 12 × 200 turnos; parity de Cartas e lint de
  conteúdo verdes
- [ ] C5: E1–E3 da SPEC-287 seguem valendo
- [ ] R1/R2: tabela de sondas e justificativa da escolha mínima na §8
- [ ] R9: saves antigos carregam
- [ ] Revisão independente Opus (`handoffs/SPEC-295-review.md`) sem P0/P1
- [ ] `uv run pytest` verde (suíte completa)

## 7. Smoke real

Não se aplica: mecânica determinística, sem prompt nem structured output novo
(mesmo critério das SPEC-285/287). Se o log/flavor novo (R8) passar pelo
narrador, conferir em 1 combate de Chefe no staging depois do pouso.

## 8. Evidência

(Preenchida pelo executor: baseline, sondas K1/K2/K3, escolha, arena antes/depois,
playtest, matriz SPEC-056, `--start-level 5/8`.)
