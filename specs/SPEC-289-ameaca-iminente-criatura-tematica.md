# SPEC-289 — ameaca-iminente-criatura-tematica

> **Status:** `approved` — dono autorizou em 19/10/2026 tudo que não exige ação externa dele (onda 19/10).
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-288 (`done` — criatura canônica no encontro `looming_threat`), SPEC-287 (escala de encontro)
> **Desbloqueia:** —
> **REVIEW_REQUIRED:** true (subagente Opus independente → `handoffs/SPEC-289-review.md`)

---

## 1. Contexto & Objetivo

Follow-up P2-3 da revisão da SPEC-288 (`handoffs/SPEC-288-review.md`). Desde a SPEC-288 o
encontro `looming_threat` de `world_utils.check_encounter` usa uma criatura canônica do
bestiário (`pick_encounter_enemy`), mas o sorteio é só regional: a ameaça "Corvane reativou
uma câmara de Destilação parcial: os Afogados patrulham…" pode virar uma Aranha Lobo, e o
narrador recebe `COMBAT START. <texto da ameaça>` ao lado de uma criatura que nada tem a ver
com ela.

Hoje só duas fações do jogo invocam ameaça (`ascension.type == "invocar_entidade"` em
`data/factions.json`): `filhos_chama_azul` (Malagor, alvo `na_anel_dourado`) e
`cultistas_destilacao` (Corvane, alvo `ae_ruinas_submersas`). O mundo guarda só o TEXTO da
ameaça (`world.looming_threat`), sem a fação de origem.

Objetivo: ligar a criatura ao tema da ameaça de forma **determinística** (Python, zero LLM),
usando só dados existentes — campo `faction` do bestiário, alvo/região da ascensão e o
próprio texto curado da ameaça — sem quebrar escala/porte (SPEC-287), manifesto (`systemic`)
nem saves antigos. Princípio: mecânica é Python; a IA só narra.

## 2. Requisitos

- **R1 — Fação de origem.** Ao aplicar `invocar_entidade`, o mundo grava
  `world.looming_threat_faction = <faction_id>` junto de `looming_threat`. Para saves antigos
  (sem o campo), a fação é resolvida casando o texto de `looming_threat` com o
  `ascension.threat` das fações vivas e, se não achar, dos seeds (`gamedata.seed_factions`).
  Sem casamento → sem tema (comportamento atual).
- **R2 — Esfera da ameaça.** Esfera = região (`region_id`) do local-alvo da ascensão ∪ região
  de origem da fação (`faction.region`, nome de exibição → `region_id` pelos locais do mapa).
- **R3 — Afinidade temática (dentro da esfera).** Uma criatura é temática se
  (a) `entry.faction == faction_id`, ou (b) algum radical do nome dela casa um radical do
  texto da ameaça (normalizado sem acento/caixa; palavra ≥ 5 letras; `s` final removido;
  radical = 6 primeiras letras; texto = `looming_threat` atual ∪ `ascension.threat` autorado da fação). Pontuação: fação (a) = 2, nome (b) = 1.
- **R4 — Preferência regional + porte.** Com o jogador DENTRO da esfera, `pick_encounter_enemy`
  restringe o sorteio às criaturas temáticas (pontuação > 0) da região do local — round-robin
  por turno no caminho legado; no ponderado (Fase 6.3) a pontuação multiplica o peso —, respeitando o porte ESTRITO do
  perigo efetivo (`forced_encounter_danger`): ≤2 só Minion; 3 qualquer; ≥4 só Elite. BOSS
  nunca (mesmo filtro por categoria da SPEC-287). Sem criatura temática compatível → sorteio
  atual (fallback). A camada temática não abre vaga a migrantes.
- **R5 — Fora da esfera.** Criatura regional (comportamento atual) e o `flavor` deixa claro que a
  ameaça está longe (o texto da ameaça continua presente, emoldurado como eco distante), para o
  narrador não colar o tema na fauna local.
- **R6 — Determinismo e manifesto.** Mesma entrada → mesmo encontro (caminho sem
  `bestiary_knowledge`/`projection`). O retorno mantém `reason="looming_threat"`,
  `hint == entry.name`, `enemy_id` do bestiário (fonte canônica `systemic` da SPEC-203/288).
- **R7 — Compatibilidade.** Sem `looming_threat_faction` e sem casamento de texto, o resultado é
  idêntico ao de hoje. `pick_encounter_enemy` sem o novo parâmetro é idêntico ao de hoje.

### Fora de escopo

- LLM escolhendo criatura; criar criaturas/tags novas no bestiário.
- Mudar o gatilho (`threat and danger >= 3`), cooldown, budget/contagem (SPEC-287) ou o ramo
  `controlled`/`high_danger`/`reinforcements`.
- Sobrevivência de Chefe/laboratório (`agents/bestiary.py` — SPEC-290, em paralelo).

## 3. Design técnico

- **`world_utils.py`**
  - `resolve_faction_completions` (ramo `invocar_entidade`): grava `world["looming_threat_faction"] = fid`.
  - `_theme_stems(text) -> set[str]`: radicais (R3b).
  - `threat_faction(world, factions) -> dict | None`: R1 (campo → texto nas vivas → seeds).
  - `threat_sphere(faction) -> set[str]`: R2.
  - `threat_theme_match(faction, threat_text) -> Callable[[dict], int]`: 2 = fação, 1 = nome, 0 = não.
  - `pick_encounter_enemy(..., theme=None)`: novo kw-only `theme` (o callable). Após filtro
    BOSS, aplica o porte estrito; se houver temáticas, sorteia só entre elas (ordenadas por id),
    sem migrantes; peso ponderado × pontuação; o resto do sorteio segue igual.
  - `check_encounter` (ramo `looming_threat`): resolve fação/esfera; dentro → passa `theme`;
    fora → `flavor` emoldurado como eco distante.
- **`state.py`** — `WorldState.looming_threat_faction: str` documentado.
- Sem schema de save novo (campo aditivo; ausência = R1 por texto).

## 4. Plano passo a passo

### Etapa 1 — Testes (`tests/test_spec289_ameaca_tematica.py`)

- `test_invocar_entidade_stamps_faction` — ascensão de `cultistas_destilacao` grava a fação.
- `test_threat_faction_legacy_text_match` — save sem o campo resolve a fação pelo texto.
- `test_corvane_in_sphere_picks_themed_creature` — `ae_ruinas_submersas`, porte Minion e Elite:
  criatura temática da região, não BOSS.
- `test_chama_azul_in_sphere_prefers_faction_creature` — Nova Arcádia com perigo ≥3 → Iniciado da Chama Azul.
- `test_porte_strict_falls_back_when_no_themed_elite` — Chama Azul em porte Elite (só Minion temática) → fallback regional.
- `test_out_of_sphere_keeps_regional_and_frames_flavor` — Corvane em `floresta_sussurros`: criatura igual à de antes; flavor como eco distante.
- `test_unknown_threat_text_is_legacy_behavior` — texto sem fação → idêntico ao sorteio antigo.
- `test_themed_pick_deterministic_and_systemic_manifest` — chamadas iguais → mesmo resultado; fonte `systemic`.
- `test_pick_encounter_enemy_without_theme_unchanged` — paridade com chamada sem `theme`.

### Etapa 2 — Implementação (§3) e testes do escopo verdes (spec 288, fase2, fase63, 287).

### Etapa 3 — Evidência: tabela ameaça → criatura antes/depois (§6) e `playtest run --profile combate --turns 200` em 3 seeds.

## 5. Critérios de aceite

- [ ] R1–R7 cobertos por testes (`tests/test_spec289_ameaca_tematica.py`)
- [ ] Tabela ameaça → criatura antes/depois com ameaças reais (§6)
- [ ] `playtest run --profile combate --turns 200` em 3 seeds: 0 erro / 0 `combat.no_progress`
- [ ] Revisão independente Opus (`handoffs/SPEC-289-review.md`) com correções aplicadas
- [ ] Suíte completa 1x (só falhas de índice stale esperadas)
- [ ] Sem `with_structured_output` novo; saves antigos carregam (campo aditivo)

## 6. Evidência (sem LLM — mudança 100% determinística)

Preenchida na execução.

## 7. Riscos & compatibilidade

- Saves antigos: sem `looming_threat_faction` → R1 por texto; texto editado/desconhecido → legado.
- Falso positivo de radical: o texto da ameaça é curado (2 ameaças); a afinidade só vale DENTRO da
  esfera, então "Afogado da Batalha" (pântano) não é puxado pela ameaça de Corvane.
- Mock/Fallback LLM: não afetados (zero LLM). Quota/latência: zero.
- Ponderação 6.3 dentro do subconjunto temático segue a mesma (pressão de caça/fação).
