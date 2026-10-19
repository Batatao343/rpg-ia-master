# SPEC-294 — Rótulo de fação oculta: follow-ups da revisão + caso de eval

> **Status:** `approved` (o dono autorizou em 19/10 tudo que não exige ação externa dele)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-293 (`services/faction_display.py`), SPEC-206 (`player_knowledge`)
> **Desbloqueia:** —
> **Origem:** pendências P2-1, P2-2 e P2-3 de `handoffs/SPEC-293-review.md`

---

## 1. Contexto & Objetivo

A revisão da SPEC-293 aprovou o rótulo de exibição ("Iniciado" no lugar de "Iniciado
da Chama Azul" enquanto a fação é desconhecida) com três follow-ups P2:

- **P2-1** — o oráculo (e) de `assert_no_player_leak`
  (`faction_display.concealed_name_problems`) casa *substring* normalizada sem fronteira
  de palavra: "Iniciado da Chama Azulado" acusa vazamento que a projeção (corretamente)
  não troca. O oráculo deve ter a MESMA noção de "ocorrência do nome" que a projeção
  (fronteira de palavra, caixa, acento, espaço/quebra/hífen, plural `s`/`es`), sem
  perder nenhuma variante que a projeção trocaria.
- Não havia caso de eval para o rótulo; o oráculo (e) não era exercitado pela régua.
- **P2-2** — inimigo sem `id` (save legado) usa o nome como id: `enemies[].id`,
  `participant_id` e `valid_targets` saem com o nome canônico. O motor ainda faz
  `e["id"]` (KeyError) nesse caso.
- **P2-3** — `/data/combat-simulator` lista o bestiário com nomes canônicos.

## 2. Requisitos

- **R1 (P2-1)** — `concealed_name_problems` reporta `e:concealed_faction_name:<fid>` se,
  e só se, o texto contém o nome canônico como ocorrência de palavra inteira, tolerando
  caixa, acento, `[\s-]+` entre palavras e plural `s`/`es` nas palavras de conteúdo.
  "Iniciado da Chama Azulado", "Iniciado da Chama Azul_x" e "XIniciado da Chama Azul" NÃO
  disparam; "iniciado da chama  azul", "Iniciado da\nChama-Azul", "Iniciados da Chama
  Azul", "INICIADO DA CHAMA AZUL 2" disparam.
- **R2** — Propriedade: para todo texto do corpus de teste, se a projeção
  (`conceal_text`) mudaria o texto, o oráculo acusa o texto original; e o texto
  projetado nunca é acusado.
- **R3 (eval)** — `evals/datasets/regression/player_knowledge.jsonl` ganha casos do
  rótulo: projeção do Codex com criatura de fação oculta (rótulo, sem nome canônico em
  `forbidden_fragments`); mutações do oráculo que provam a detecção (nome canônico,
  plural, variação de espaço/hífen) → `["e:concealed_faction_name"]`; e casos limpos
  (fronteira "Azulado" e fação já revelada) → `[]`. Lock regenerado pelo comando
  oficial (`python -m evals.core.governance lock`), `governance check` verde.
- **R4 (P2-2)** — No load (`persistence._raw_to_state`), inimigo sem `id` recebe id
  estável e opaco `enemy_legacy_<n>` (`n` = posição 1-based, pulando colisões), sem o
  nome. Determinístico (mesmo save → mesmos ids), idempotente, não toca inimigos que já
  têm `id`, não muta o dict de entrada.
- **R5** — Combate em curso continua consistente: na subárvore `combat`, chaves de dict
  e itens de lista iguais ao nome antigo, e valores string de chaves de id
  (`(?:^|_)ids?$`), passam ao novo id (ex.: `scene.positions`, `engaged_with`,
  `hidden_from`, `encounter.participants[].participant_id`, perseguidores). Campos de
  exibição (`name`, `species_label`) ficam. `archetype_id` ausente é preenchido pela
  chave do bestiário de mesmo nome (sem sufixo numérico) ou, sem casamento, pelo nome
  (o fallback anterior de `bestiary_knowledge._archetype_id`), para o overlay não virar
  `enemy_legacy`.
- **R6** — Após o load, `format_response` e `valid_targets` de um save legado não têm o
  nome canônico em `enemies[].id`/`valid_targets`, e os ids batem com os do motor.
- **R7 (P2-3)** — Decisão do coordenador: **manter**. `/data/combat-simulator` é o
  laboratório (ferramenta), não estado de observador, e mostra o bestiário canônico por
  design. Sem mudança de código.

### Fora de escopo

P2-4 (texto da SPEC-293 §R3, corrigido no pouso pelo coordenador) e P2-5 (cache de
`concealed_name_map`). Frontend, CLI.

## 3. Design técnico

- `services/faction_display.py`:
  - `_oracle_regex(name)` — sobre texto normalizado (sem acento, casefold,
    `[\s-]+` → um espaço): palavras normalizadas, conteúdo com `(?:e?s)?`, unidas por
    `" "`, delimitadas por `(?<!\w)`/`(?!\w)`. Mesma tolerância de `_name_regex`.
  - `concealed_name_problems(payload, state)` usa esse regex (fronteira) em vez de `in`.
- `persistence.py`:
  - `backfill_enemy_ids(raw: dict) -> dict` (pura; devolve `raw` se nada a fazer, senão
    cópia com `enemies`/`combat` reescritos).
  - Chamada em `_raw_to_state` logo após `migrate_state` (antes de
    `_normalize_combat_on_load`, que constrói o manifesto a partir de `id or name`).
  - Sem bump de `SCHEMA_VERSION` (aditivo, idempotente).
- Eval: só dataset + lock; evaluator e adapter inalterados (o adapter já chama
  `assert_no_player_leak`, que inclui o ramo (e)).

## 4. Plano passo a passo

1. **Testes** (`tests/test_spec294_followups.py`): R1 (parametrizado positivo/negativo),
   R2 (corpus de variações), R4/R5 (save legado com combate ativo: ids opacos,
   determinismo, idempotência, input intacto, positions/engaged/manifesto reescritos,
   save com id inalterado, archetype), R6 (format_response + valid_targets).
2. Implementação de R1/R2 e R4/R5.
3. Casos de eval (R3) + `governance lock` + `governance check` + `python -m evals run`.
4. Revisão independente Opus → `handoffs/SPEC-294-review.md`; correções.

## 5. Critérios de aceite

- [ ] R1/R2 com testes
- [ ] R3 casos de eval + lock + governance check verde + mutação detectada
- [ ] R4/R5/R6 com testes
- [ ] R7 registrado
- [ ] Suíte completa + `python -m evals run` determinístico verdes
- [ ] Saves antigos continuam carregando

## 6. Smoke test com LLM real

Não se aplica: zero chamada de LLM (oráculo, normalização no load e dataset
determinístico).

## 7. Riscos & compatibilidade

- Saves com `id` em todos os inimigos: estado carregado idêntico ao de antes.
- Save legado com nomes repetidos: o primeiro herda as referências do nome antigo (a
  chave de `positions` só podia apontar um deles).
- Publicar exige aprovação do environment `eval-governance` (dataset/lock protegidos).
