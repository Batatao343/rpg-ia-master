# Handoff — próxima sessão (escrito em 2026-10-19, noite)

Leia isto + `ESTADO_ATUAL.md`. Main em `b67b92f` (ou mais nova), CI verde
(validate, audit-local, eval-gates). Nenhum worktree de spec aberto.

## 1. Fazer primeiro: SPEC-236 §6.2, dia 2

O agendamento das 00:17 de 20/10 vivia só na sessão antiga e **não sobrevive**.
Rodar manualmente em 20/10 a partir de 00:00 BRT (03:00 UTC):

- Roteiro com comandos prontos:
  [docs/staging-wave-2026-10-17/spec236-s62-plano.md](staging-wave-2026-10-17/spec236-s62-plano.md).
- Dia 1 já feito: trip real do teto diário em `2026-10-19T12:12:37Z`.
- Dia 2: religar à mão + gastar acima do teto. A imagem tem que desligar.
- Se verde, marque o §6.2 e a SPEC-236 como `done`, pouse e confira o CI.
- No fim, devolva o staging: teto R$ 5, Jev `primary`
  (`--jev-router-mode primary --owner-approved-primary`), `e2e_session` verde.

Pedido ao Claude: **"roda o dia 2 da 236"**.

## 2. Decisão do dono (19/10): "Chefe no topo: sim"

Criar e executar a spec com `/spec-new chefe-no-topo`. Ela nasce aprovada:
o dono decidiu em 19/10.

- **Objetivo:** em cada nível, o Chefe é o encontro mais letal.
  A ordem fica Lacaio < Padrão < Elite < Chefe.
- **Por que hoje não é assim:** ver a SPEC-287 (§ decisões, revisão e
  `docs/spec287/README.md`).
  - Hoje o Chefe fica acima do Lacaio e abaixo de Padrão/Elite, inclusive nos
    níveis 1–4.
  - Só dar Vitalidade não basta: +36 de Vitalidade chega a 0,49 e 2 ações a
    0,42, contra ~0,70 de 2 Elites.
- **Caminhos já apontados:**
  - séquito escalado pelo Nível do Encontro;
  - ações extras do Chefe por rodada;
  - fases do Chefe.
- **Restrições:**
  - mecânica 100% Python, determinística por seed;
  - dados só pelos geradores oficiais (`scripts/migrate_bestiary_v4.py`);
  - "o mundo não escala com o herói" (§5 das regras de design);
  - não piorar as metas da SPEC-285 (M1–M5) nem os níveis 1–4 de
    Lacaio/Padrão/Elite.
- **Medição:**
  - arena `docs/spec285/arena_lethality.py`, por nível × categoria;
  - `playtest run --profile combate --turns 200` em várias seeds,
    com 0 `no_progress`.
- Revisão independente Opus antes de pousar.

## 3. Bloqueios no dono (ação externa) — ver tabela no ESTADO

Cada linha tem a frase-gatilho e o que o Claude faz em seguida:

- conta no staging ("confirmei e loguei");
- Stripe teste ("colei a Stripe");
- domínio ("comprei o domínio X");
- go do beta;
- Play Console;
- Axiom;
- liberar a SPEC-104;
- desligar os plugins em claude.ai.

O dono autorizou em 19/10 **tudo que não exige ação externa dele**
(memória `autonomia-dono`): não perguntar para aprovar spec, aprovar
`eval-governance`, configurar GitHub/staging ou fazer merge na main.

## 4. Como trabalhar (lições desta sessão)

- **Pousar uma spec:** `/spec-land NNN` ou o fluxo manual abaixo, em ordem.
  1. Rebase na main.
  2. Nota no CHANGELOG § 2026-10-19 e linha curta no ESTADO
     (o ESTADO tem **teto de 8 KB**).
  3. `scripts/spec_index.py build`.
  4. `ruff format` → `project_index build` → `ruff check` + `format --check`.
  5. Conferir que a spec está `done`.
  6. Suíte completa com `-n auto`, **capturando o exit do pytest e não o
     do `tail`**.
  7. Fast-forward da main, push e acompanhar o CI.
- **Subagentes:**
  - Usar `bash scripts/dev/py.sh` (venv do checkout principal).
  - **Não** criar `.venv` no worktree: sem o extra `anthropic`, quebra
    `test_routing`.
  - **Não** rodar `uv sync`.
  - **Nunca** usar `taskkill /IM python.exe`: mata os outros agentes.
- **Testes de tempo:** sob `-n auto` intervalos de parede variam muito.
  Assertar a ordem dos eventos, não milissegundos.
- **Playwright local:** a suíte completa leva ~8–17 min nesta máquina, e
  timeouts de 30 s em specs sem relação são carga. Reexecutar só as falhas;
  o CI é o árbitro.
- **Job protegido `eval-governance`** (mudança em `evals/` ou
  `web/e2e/contracts`): depois do push, aprovar com
  `gh api -X POST repos/Batatao343/rpg-ia-master/actions/runs/<id>/pending_deployments -F 'environment_ids[]=23265439768' -f state=approved -f comment='…'`.
- **Rede do `gh`/push:** instável (TLS timeout / curl 52). Repetir.

## 5. Follow-ups conhecidos (baixa prioridade, sem dono)

- SPEC-294 P2-2/P2-3: reescrita de refs de save legado por igualdade de
  string; campo `archetype` legado.
- SPEC-276: tirar o override do `uuid` quando o `@capacitor/cli` atualizar o
  `xcode`; PR #42 (TypeScript 7) aguarda o typescript-eslint.
- Encolher o baseline do Ruff (`ruff-baseline.toml`).
- Remedir tokens do workspace com `scripts/dev/transcript_stats.py` depois
  de uma onda inteira.
