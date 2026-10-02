# HANDOFF — sessão 20 (2026-07-19) → próxima sessão limpa

> Leia junto de `ESTADO_ATUAL.md` (já atualizado com tudo desta sessão).
> Este doc foca no **estado VIVO** e nos **próximos passos** — o que uma sessão
> limpa precisa saber para retomar sem quebrar nada.

---

## ⚠️ 1. TEM UM PLAYTEST LONGO RODANDO EM BACKGROUND

**Um teste real de balanceamento de classes pode ainda estar rodando** quando
você retomar. NÃO rode nada que use o Jina (embeddings/RAG: `rag.py`, um turno
de API/CLI real, outro playtest `--real`) enquanto ele roda — **os dois colidem
no rate limit do Jina (100k tokens/min) e degradam um ao outro** (aconteceu
nesta sessão). A suíte `uv run pytest` é offline (Jina desligado no conftest) →
segura de rodar concorrente.

- **run_id:** `20260719-160014`
- **Config:** 5 classes × 3 perfis (combate/explorador/quester) × 70t × seed 42,
  DeepSeek real, teto $0.20/campanha. 15 campanhas.
- **Progresso ao entregar o handoff:** 5/15 concluídas (rodava
  `quester_sangromante_42`).

**Como checar se terminou / pegar os dados:**
```bash
# concluídas (procure "DONE run_id" no fim):
grep -c "### FIM" playtest_runs/console_balance_longrun.log
tail -30 playtest_runs/console_balance_longrun.log
# quando terminar, gere o relatório agregado (tem a seção "## Classes"):
uv run python -m playtest report 20260719-160014
# transcrito qualitativo por turno (ação→narração), p/ julgar prosa:
uv run python -m playtest transcript 20260719-160014
```
- **Dados brutos (durável, gitignored):** `playtest_runs/console_balance_longrun.log`
  (TODAS as mensagens: router/eventos/combate/RAG/erros) +
  `playtest_runs/20260719-160014/*.jsonl` (por turno: ação, narração, Entropia,
  Carga, rota, violações) + `*.summary.json` + `index.json`.

**O que analisar (a TAREFA que sobra):**
1. **Balanceamento das 5 classes** — a instrumentação existe (telemetria de
   Entropia/Carga por turno + seção Classes no report). Cruze starvation/
   flooding/Carga por classe × perfil. Alimenta o tuning dos **8 knobs
   `[BALANCEAR]`** em `data/classes.json` (que seguem marcados — spec
   [balanceamento-classes-pos-playtest](../specs/SPEC-049-balanceamento-classes-pos-playtest.md)).
   **Tuning = editar `scripts/gen_classes_v2.py` e regenerar**, NUNCA o JSON.
2. **Caça-bug** — no console já apareceu um `❌ [RAG ERROR] ... faiss::FileIOReader`
   (memória de sessão; archivist resiliente, não derrubou turno). Investigar se
   é corrupção de índice de sessão (resíduo do rate-limit do Jina) ou concorrência.
   Ver também os warnings por campanha (ex.: combate_devoto teve 10) no summary.
3. Sinais precoces: Devoto morre em todos os perfis (t22-67); custo ~$0.06-0.17/
   campanha; 0 erros de turno nas 5 primeiras.

---

## 2. GIT — 2 commits locais NÃO pushados

`origin/main` = `727b755` (pushado nesta sessão). Local está **2 commits à frente**:
- `9944950` feat(weather): clima global vivo + aposenta gating de classe morto
- `d0f240e` feat(items): itens vivos (passivas+ativas) + sistema de Luz

O usuário decide o push (`git push origin main`). Working tree limpo.

---

## 3. O QUE ESTA SESSÃO ENTREGOU (918 → 970 offline verdes)

Detalhe em `ESTADO_ATUAL.md` (TL;DR sessão 20). Resumo:

- **3 bugs de fiação de classe** (taunt/Transformação/Purga estavam mortos) +
  `HANDLED_KINDS` (teste anti-órfão dado↔motor) — commit `727b755`.
- **isolar-cache-runtime** `done` — cache runtime sai de `data/` p/ overlay
  gitignored `data/runtime/` (fim do `git checkout` manual).
- **balanceamento-classes-pos-playtest** `in-progress` — instrumentação `done`;
  tuning aguarda ESTE playtest.
- **Backlog:** traits 40→80; curadoria Rede Carmesim (over-share suavizado +
  reindex).
- **Auditoria de mecânica-morta** → gating de classe **aposentado** (decisão do
  usuário) — commit `9944950`.
- **weather-global-vivo** `in-progress` — trigger determinístico
  (`maybe_start_global_weather`).
- **itens-vivos-e-luz** `in-progress` — passiva de item fiada, item ativo
  ofensivo (com alvo/save), **sistema de LUZ** (`light_level`), **+22 itens** de
  lore, `<AMBIENTE_DE_LUZ>` + chip HUD — commit `d0f240e`.

---

## 4. SMOKES REAIS ADIADOS (fazer quando o playtest terminar)

3 specs estão `in-progress` só porque o smoke real §6 foi adiado (Jina em uso
pelo playtest). Quando o playtest acabar, rodar 1 turno real cada e promover a
`done`:
- **itens-vivos-e-luz:** entrar numa masmorra/noite SEM tocha → narrador diz que
  está escuro + encontro mais fácil; equipar tocha → muda; usar bomba de
  atordoamento num inimigo em combate real → inimigo atordoado.
- **weather-global-vivo:** viajar/descansar até um evento global iniciar (ou
  baixar `GLOBAL_WEATHER_BASE_CHANCE` temporariamente p/ forçar) → narração/HUD
  refletem + combate/percepção sentem o modificador.
- **fiacao-regras-orfas-classes:** já `done` (o baseline real exercitou o
  caminho de combate); só reconfirmar se quiser.

Depois de cada smoke: marcar a spec `done` (§8) + atualizar ESTADO_ATUAL/ROADMAP.

---

## 5. PRÓXIMOS PASSOS (ordem sugerida)

1. **Analisar o playtest** (balanceamento + o `faiss::FileIOReader` + warnings).
2. **Smokes reais** das 3 specs `in-progress` (§4) → promover a `done`.
3. **Tuning dos 8 knobs `[BALANCEAR]`** das classes com os dados do playtest
   (via `scripts/gen_classes_v2.py`).
4. Decidir push do `origin/main`.
5. Fast-follows do épico de classes: tiers 5+ (nível 9-20).

## 6. Ambiente (lembrete)

`uv` fora do PATH: `$env:Path="$env:APPDATA\Python\Python314\Scripts;$env:Path"`.
Python global é 3.14 (errado) — sempre `uv run`. Detalhes em `ESTADO_ATUAL.md`.
`.env` tem todas as chaves (DeepSeek/Groq/Jina/Anthropic/...).
