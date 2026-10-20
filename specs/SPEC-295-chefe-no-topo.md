# SPEC-295 — Chefe no topo

> **Status:** `done` (decisão do dono em 2026-10-19: "Chefe no topo: sim"; ratifica o P2-4 da SPEC-287; revisão Opus APPROVED_WITH_FOLLOWUPS em 2026-10-19)
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

> **Implementado (2026-10-19, §8):** K2 + Proteção natural do Chefe pelo Nível do
> Encontro. K1 (séquito) e K3 (fases) foram sondados e descartados; nada em
> `encounter_budget.py`, `agents/combat.py` nem na arena mudou. **Desvio:** a
> Proteção natural não estava entre os knobs da R1. A sonda mostrou que K2 sozinho
> deixa 3 células abaixo da barra, que Vitalidade extra no Nível 1 quebra os testes
> da SPEC-287 (Vitalidade do Chefe = bestiário nos Níveis 1–2) e que a recalibração
> da sobrevivência (12 → 14) quebra os da SPEC-290 (valor canônico 12). A Proteção é
> "sobrevivência específica" (regras §27.3) e não toca nenhum dos dois.
>
> - `scripts/migrate_bestiary_v4.py`: `ACOES_POR_RODADA = {"chefe": 2, "nomeado": 2}`,
>   gravado como `acoes_por_rodada` só em Chefe/Nomeado (13 criaturas).
> - `services/conflict_orchestrator.py`: `extra_actions(actor)`; em `run_round` a
>   2ª ação de cada inimigo com o campo entra no **fim da rodada**, depois de todos.
>   Tick de condição, stun e expiração de buff valem só na 1ª ação; stun nega as
>   duas. Log "X age de novo." (R8). Aliado/herói com o campo não ganham ação.
> - `agents/bestiary.py`: `DEFAULT_ACTIONS_PER_ROUND` (Chefe do LLM e overlay
>   antigo, espelha o gerador) e `CHEFE_PROTECAO_POR_NIVEL_ENCONTRO = {1: 2, 3: 1}`,
>   aplicados em `apply_encounter_survival` (todas as vias de ficha: `template_by_id`,
>   cache-hit e geração). `materialize_enemy_concept` grava `acoes_por_rodada`.
> - `combat_mechanics.passive_modifiers`: `protecao_natural` de inimigo soma à
>   `protection` (absorve por golpe como Carta `protecao`; DoT/auto-dano passam).
>   Herói ignora o campo. O log do dano já mostra "Proteção (efeito) −N" (R8).
> - Sem schema novo: ficha salva sem os campos = 1 ação e Proteção 0 (R9).

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

- [x] C1: `Chefe > Elite` (≥ 3 pp) em todo nível 1–8, nos dois bots (mín. +5,5 pp, `cartas` L6)
- [x] C2: Chefe ≤ Elite + 20 pp em todo nível/bot (máx. +17,2 pp, `cartas` L2)
- [x] C3: Lacaio/Padrão/Elite idênticos ao `main` célula a célula, níveis 1–8
- [x] C4/M1: playtest `combate` (seeds 21–32) ≤ 0,564 (0,497, igual ao `main`)
- [x] C4/M2: mediana da 1ª queda ≥ 20 (seeds 21–32: 35; matriz SPEC-056: 22)
- [x] C4/M3: `tests/test_letalidade_early.py` verde
- [x] C4/M4: Lacaio ≤ 0,40 nos níveis 1–3 (0,207/0,131/0,366 `cartas`); nenhuma célula não-Chefe muda
- [x] C4/M5: 0 `combat.no_progress` em 12 × 200 turnos; parity de Cartas e lint de
  conteúdo verdes
- [x] C5: E1–E3 da SPEC-287 seguem valendo (células não-Chefe idênticas; Chefe só subiu)
- [x] R1/R2: tabela de sondas e justificativa da escolha mínima na §8
- [x] R9: saves antigos carregam (ficha sem os campos = 1 ação, Proteção 0; teste)
- [x] Revisão independente Opus ([handoff](../handoffs/SPEC-295-review.md)):
  APPROVED_WITH_FOLLOWUPS, sem P0/P1.
  - Corrigidos: P2-2 (teste de Chefe terminal entre a 1ª e a 2ª ação) e P3-3
    (campo de sobrevivência inválido não tira mais as 2 ações nem a Proteção).
  - Documentados no código: P3-1 (stun no meio da rodada vale na próxima) e P3-2
    (as ações dividem o limite por turno das Cartas de inimigo).
  - Para o dono/SPEC-049: P2-1 (Proteção `{1: 2, 3: 1}` não é monotônica: Nível
    do Encontro 2 e 4+ ficam com 0) e P3-4 (Chefe mata 0,86–0,89 no `basico`
    níveis 5–8; monitorar antes do beta).
  - Instrumento: P3-5 (comparação com `main` só em árvore limpa; o overlay runtime
    do checkout no OneDrive põe 2 criaturas a mais nos pools).
  - Follow-up: cenário de playtest que force combate de Chefe (o loop real não
    encontra Chefe nas seeds medidas).
- [x] `uv run pytest` verde (suíte completa `-n auto`: 4.397 passed, 238 skipped; só as 3 falhas de índice stale — `specs/index.yaml` e Project Index — regenerados no pouso)

## 7. Smoke real

Não se aplica: mecânica determinística, sem prompt nem structured output novo
(mesmo critério das SPEC-285/287). Se o log/flavor novo (R8) passar pelo
narrador, conferir em 1 combate de Chefe no staging depois do pouso.

## 8. Evidência

Medição de 2026-10-19, MockLLM, offline. Baseline = `main` 36cda92 (worktree
separado, mesmo instrumento). Barra de cada célula: Elite + 3 pp ≤ Chefe ≤ Elite + 20 pp.

**Sondas** (script descartável sobre a função `fight` da arena; a célula Chefe com o
mesmo `random.seed` por luta, então "1 ação, sem extras" reproduz a arena). Taxa de
morte do herói, Chefe:

| sonda | seeds | cartas L1 / L3 / L5 / L8 | basico L1 / L3 / L5 / L8 | veredito |
|---|---|---|---|---|
| nenhuma (baseline) | 5 | 0,52 / 0,19 / 0,42 / 0,40 | 0,35 / 0,35 / 0,61 / 0,62 | abaixo do Elite |
| K1 séquito 1 Lacaio regional | 5 | 0,97 / 0,94 / 0,96 / 0,95 | 0,98 / 0,97 / 0,98 / 0,99 | estoura C2 |
| K1 séquito 1 Padrão regional | 5 | 0,93 / 0,90 / 0,93 / 0,93 | 0,95 / 0,98 / 0,99 / 0,99 | estoura C2 |
| K1 1–2 Lacaio/Padrão por Nível | 5 | 0,97 / 0,90–0,94 / 0,99 / 0,99 | 0,98 / 0,97 / 1,00 / 1,00 | estoura C2 |
| K2 2 ações | 10 | 0,67 / 0,55 / 0,82 / 0,79 | 0,58 / 0,61 / 0,86 / 0,87 | 3 células abaixo |
| K2 3 ações | 5 | 0,80 / 0,67 / 0,91 / 0,90 | 0,74 / 0,68 / 0,93 / 0,95 | estoura C2 (L1–2 cartas) |
| K3 fase < 50 %: +2 dano | 5 | 0,54 / 0,24 / 0,44 / 0,43 | 0,37 / 0,38 / 0,63 / 0,66 | quase inerte |
| K3 fase < 50 %: 2 ações | 5 | 0,51 / 0,24 / 0,47 / 0,44 | 0,36 / 0,38 / 0,65 / 0,67 | quase inerte |
| K2 + K3 (+2 dano / cura 4 / 3 ações / cura 6 + 2 dano) | 5 | +0 a +4 pp sobre K2 | +0 a +6 pp sobre K2 | não fecha L1–2 `basico` sem estourar L4 `cartas` |

- **K1 descartado.** O bot ataca o primeiro inimigo vivo (o Chefe); o séquito age
  a luta inteira. Um único Lacaio leva o Chefe a 0,94–0,99, acima do teto C2 em
  toda célula. Não há tamanho menor que 1.
- **K3 descartado.** A fase dispara tarde (o Chefe cruza 50 % e morre na mesma
  rodada ou na seguinte) e soma ≤ 4 pp; o `behavior.phases` segue inerte.
- **K2 com 2 ações** fica abaixo da barra em 3 células (10 seeds): `basico` L1
  0,575 (barra 0,618) e L2 0,535 (0,590); `cartas` L6 0,740 (0,746). Com 3 ações,
  `cartas` L1/L2 estouram o teto.
- **Ajuste fino nas 3 células** (10 seeds, sobre K2): Vitalidade +1/+2/+3 no Nível
  do Encontro 1 → `basico` L2 0,558/0,574/0,629; Vitalidade +1/+2 no Nível 3 →
  `cartas` L6 0,746/0,760. Funciona, mas a Vitalidade do Chefe nos Níveis 1–2 é
  travada pelos testes da SPEC-287 (= bestiário) e o valor 12 pelos da SPEC-290,
  que esta spec não altera. Proteção natural, sem tocar Vitalidade: Nível 1 =
  1 → `basico` L1/L2 0,628/0,591 (folga 0,1 pp); Nível 1 = 2 → 0,694/0,651;
  Nível 3 = 1 → `cartas` L6 0,771. Proteção 1 em todos os Níveis estoura o teto
  no nível 4 `cartas` (0,629 > 0,597); no Nível 2 nenhuma Proteção cabe.
- Posição da 2ª ação: no fim do bloco inimigo (logo depois da 1ª) dá menos que
  no fim da rodada (`cartas` L6 0,717, `basico` L2 0,497) — fica no fim da rodada.

**Escolha mínima (R2):** K2 = 2 ações para Chefe/Nomeado + Proteção natural
`{Nível 1: 2, Nível 3: 1}`. Os valores são os menores com folga ≥ 1 pp sobre a barra
de 3 pp em toda célula. **Nomeado** entra junto (R4): é parte da célula "chefe" da
arena e já recebe a sobrevivência da SPEC-287 como Chefe. A sobrevivência
(R4 da SPEC-287) fica como está. Chefe do LLM recebe `acoes_por_rodada` e a
Proteção pelo mesmo caminho (`materialize_enemy_concept`/`apply_encounter_survival`).

**Arena final** (10 seeds, 650 lutas por célula de Chefe). Tabela completa em
[docs/spec295/README.md](../docs/spec295/README.md). C3: as 48 células
Lacaio/Padrão/Elite são idênticas ao `main` (dicionário inteiro da célula).

| bot | nível | Padrão | Elite | Chefe antes | Chefe depois | Chefe − Elite |
|---|---|---|---|---|---|---|
| cartas | 1 | 0,458 | 0,565 | 0,454 | 0,729 | +16,4 |
| cartas | 2 | 0,327 | 0,477 | 0,311 | 0,649 | +17,2 |
| cartas | 3 | 0,293 | 0,418 | 0,242 | 0,551 | +13,3 |
| cartas | 4 | 0,633 | 0,397 | 0,255 | 0,563 | +16,6 |
| cartas | 5 | 0,633 | 0,739 | 0,432 | 0,845 | +10,6 |
| cartas | 6 | 0,598 | 0,716 | 0,423 | 0,771 | +5,5 |
| cartas | 7 | 0,563 | 0,705 | 0,440 | 0,772 | +6,7 |
| cartas | 8 | 0,555 | 0,674 | 0,423 | 0,791 | +11,7 |
| basico | 1 | 0,438 | 0,588 | 0,340 | 0,694 | +10,6 |
| basico | 2 | 0,405 | 0,560 | 0,278 | 0,651 | +9,1 |
| basico | 3 | 0,425 | 0,542 | 0,377 | 0,614 | +7,2 |
| basico | 4 | 0,722 | 0,524 | 0,382 | 0,631 | +10,7 |
| basico | 5 | 0,720 | 0,783 | 0,568 | 0,889 | +10,6 |
| basico | 6 | 0,703 | 0,753 | 0,517 | 0,863 | +11,0 |
| basico | 7 | 0,697 | 0,751 | 0,665 | 0,880 | +12,9 |
| basico | 8 | 0,642 | 0,726 | 0,606 | 0,874 | +14,8 |

**Achado (fora de escopo, C3):** no nível 4 o Padrão (2 corpos) mata mais que o
Elite (1 corpo) — 0,633 contra 0,397 no `cartas`. A cadeia completa vale nos níveis
1–3 e 5–8; no nível 4 vale `Elite < Chefe` (C1), mas `Chefe > Padrão` exigiria
Chefe > 0,633, acima do teto C2 (0,597). Mexer no Padrão é fora de escopo.

**Playtest** — idêntico ao `main` em todas as medições (o perfil `combate` não
enfrenta Chefe nesse horizonte; Chefe nunca sai como reforço aleatório):

| medição | `main` | `spec-295` |
|---|---|---|
| `combate` seeds 21–32, 200 turnos: mortes/combates | 98/197 = 0,497 | 98/197 = **0,497** |
| idem: mediana da 1ª queda / `combat.no_progress` | 35 / 0 | **35 / 0** |
| matriz SPEC-056 (5 classes × 42/43 × 50): mediana 1ª queda | 22 (14/32) | **22** (14/32) |
| `--start-level 5`, seeds 21–26: mortes/combates, mediana | 45/62, 29 | 45/62, 29 |
| `--start-level 8`, seeds 21–26: mortes/combates, mediana | 23/43, 49 | 23/43, 49 |

- `--start-level 5` seed 24: 2 `combat.no_progress`, iguais em `main` (o mesmo
  achado preexistente da SPEC-287 §3). `summary.lifecycle` em 2 turnos das seeds
  21–32, também igual em `main`.
- Lint de conteúdo (`scripts/validate_content.py`): 0 erro, 0 aviso.

**Follow-up:** o playtest não exercita Chefe; um cenário dirigido de Chefe
(`playtest --scenario`) mediria o efeito no loop real. `behavior.phases` segue
inerte (K3 descartado).
