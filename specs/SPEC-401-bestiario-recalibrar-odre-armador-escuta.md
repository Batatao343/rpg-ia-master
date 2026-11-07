# SPEC-401 — Bestiário: recalibrar odre, armador e escuta

> **Status:** `approved` — dono, 07/11: "aprovo 401"; mesmo dia, ao saber da SPEC-400, decidiu "400 motor, 401 recalibra": esta spec ficou só com a recalibração e espera a 400 pousar. D1–D2 nos defaults.
> **Criada:** 2026-11-07 · **Atualizada:** 2026-11-07
> **Épico:** SPEC-349 (bestiário) · SPEC-327 (Cartas)
> **Depende de:** **SPEC-400 `done`** (os P2-1 e P2-5 da 395 mudam a decisão de turno do inimigo, e calibrar antes deixaria o número velho), SPEC-394 `done` (exceções nominais de armador e escuta), SPEC-395 `done` (exceção nominal do odre), SPEC-373 `done` (`arena.py` congelado)
> **Desbloqueia:** veredito cheio do bestiário sem as 3 exceções nominais; `RPG_ENEMY_DECKS=on` com menos ressalvas
> **Risco:** `médio`. Só mexe nos números de 3 criaturas, pelos dials que já existem. Avaliador congelado, motor intocado (o motor é da 400).
> **Evidência:** `tests/test_spec401_calibragem.py` (novo) falha antes, porque os 3 ids estão sem `ok` na medição da Etapa 0. Equivalência: os hashes de `ensure_combat_sheet` (`off`/`on`) das demais criaturas curadas ficam iguais aos da base pós-400.
> **EXECUTOR_MODEL:** `Terra` (Sonnet) · **REVIEW_MODEL:** revisor Sonnet, outro agente · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. O oráculo é o `veredito` de `scripts/bestiario/arena.py` (faixa 45–85 %), que segue congelado. Os limiares estão fixados aqui, não pelo executor.

---

## 1. Contexto & Objetivo

Três criaturas curadas seguem fora da faixa 45–85 % do `arena.py`, como exceção nominal registrada pelo dono:

| id | leitura registrada | origem |
|---|---|---|
| `mon_odre_de_oleo` | 0–39: 56,5/53 · 40–119: 37,2/45,8 · soma 120: `off` ≈ 43,6 % | SPEC-395 §9 (decisão do dono 04/11). A R1 tirou a fuga que dava margem a ele (P2-2 da revisão Sol). |
| `mon_armador_de_fosso` | 49,5/86 · conf. 41,7/79,5 | SPEC-394 §9 (D2). Dials parciais, `off` sobreajustado. |
| `mon_escuta_do_sinal` | 41,5/87,5 · conf. 42,7/82 | SPEC-394 §9 (D2). O `on` fica 36–46 pp acima do `off`. |

A 394 parou nelas porque os dials (`corpo`, `dano`, `forca`, `sig` em `data/bestiario/mecanica/_ajustes.yaml`) movem os dois modos juntos. Ela deixou a recalibração para depois da 395. A SPEC-400 fecha os resíduos de motor da 395 (save antigo, caminho legado, guarda de eval, leituras `arena:` antigas).

**Objetivo:** com a 400 pousada, recalibrar só esses 3 ids, sobre o motor final.

## 2. Requisitos

- **R1 — Base.** Etapa 0: `arena.py` dos 3 ids na `main` pós-400 (sementes 0–39), gravado em `docs/spec401/base.json`, mais os hashes `off`/`on` de todas as curadas (`docs/spec394/snapshot.py`).
- **R2 — Recalibração.** Ajustar os dials dos 3 ids pelo `scripts/bestiario/calibrar.py`, com no máximo 2 execuções por id. Meta: as duas células L3 em 45–85 % nas sementes 0–39 (`ok` do `arena.py`, em `docs/spec401/arena-final.json`) e também na confirmação 40–119, rodada uma vez e sem reajuste (`docs/spec401/confirmacao-40-119.json`). Se um id não fechar, fica o melhor ajuste visto, ele segue como exceção nominal com a leitura nova e a §9 registra o motivo (D1).
- **R3 — Só os 3 ids.** `ids_com_dial_mudado` (`tests/test_spec373_artefatos.py:277`) entre a base e o final dá exatamente o subconjunto dos 3 ids que mudou. Os hashes das outras curadas ficam iguais aos de R1.
- **R4 — Teste.** `tests/test_spec401_calibragem.py` lê o `ok` gravado pelo `arena.py` para os ids fechados e confere R3, no padrão de `tests/test_bestiario_calibragem.py`.
- **R5 — Registro.** `docs/spec401/RELATORIO.md`: tabela base → final → confirmação por id, dials antes e depois, e exceções remanescentes. O campo `arena:` dos ids recalibrados fica com o texto que o `calibrar.py` grava.

### Fora de escopo

- Motor, `tactical_profile.py`, `conflict_orchestrator.py`, P2-1/P2-4/P2-5/P2-7 da 395: tudo isso é da SPEC-400.
- Avaliador, faixa, sementes, `arena.py`, `calibrar.py`, `evals/`, `tests/test_spec373_montagem.py`.
- Dials novos ou mudança de Carta/mecânica da criatura. Se a D1 apontar que precisa, abre-se outra spec.
- Outras exceções nominais, como o chefe hospede/escavador (D-373).

## 3. Design técnico

- **Alterado:** `data/bestiario/mecanica/_ajustes.yaml`, só os blocos `mon_odre_de_oleo` (`:889`), `mon_armador_de_fosso` (`:196`) e `mon_escuta_do_sinal` (`:581`). As linhas são as de 07/11 e podem andar com a 400.
- **Novos:** `tests/test_spec401_calibragem.py`, `docs/spec401/{base.json, arena-final.json, confirmacao-40-119.json, RELATORIO.md}`.
- O `bestiary.json` é regenerado pela esteira (`gerar_mecanica.py`), se for o caso. Não se edita à mão.

## 4. Plano passo a passo

### Etapa 0 — Base (R1)

Confirmar que a 400 está `done` na `main` e gravar a base.

### Etapa 1 — Teste vermelho (R4)

`test_spec401_calibragem.py` falha na base: os 3 ids estão sem `ok`.

### Etapa 2 — Calibrar (R2, R3)

`calibrar.py` id a id, depois `arena.py` 0–39 e a confirmação 40–119 uma vez. Em seguida, `test_spec401_calibragem`, `test_spec373_artefatos`, `test_bestiario_calibragem` e `scripts/validate_content.py`, com `-n 2` no máximo.

### Etapa 3 — Registro (R5)

Escrever o `RELATORIO.md` e a §9.

## 5. Critérios de aceite

- [ ] R1: base gravada sobre a `main` pós-400.
- [ ] R2: os 3 ids `ok` em 0–39 e na confirmação, ou exceção nominal com leitura nova e motivo (D1).
- [ ] R3: só os dials dos 3 ids mudaram; hashes das outras curadas iguais.
- [ ] R4: teste novo vermelho na base, verde no final.
- [ ] R5: `RELATORIO.md` e §9.
- [ ] `uv run pytest` verde (suíte completa offline, no pouso).
- [ ] Revisão Sonnet APPROVED.

## 6. Smoke test

As rodadas do baralho não usam LLM (decisão do dono), então o smoke é local, com MockLLM: um combate contra cada um dos 3 ids pela API local (`/game/new` → `/game/action` até o fecho), sem 500 e com desfecho coerente.

## 7. Riscos & compatibilidade

- **Saves:** só os números da ficha mudam, e o formato fica igual. Atores já montados em save antigo mantêm a ficha montada até a próxima montagem.
- **Escuta:** com um `on` 36–46 pp acima do `off`, talvez nenhum ajuste de dial feche as duas células (D1).
- **Quota/latência:** nenhuma; não há LLM.

## 8. Decisões do dono

Defaults em negrito. O executor segue o default se o dono não responder.

- **D1 — Id que não fecha.** (**Melhor ajuste visto + exceção nominal com a leitura nova**, como a 394.) Alternativa: abrir spec de Carta/mecânica para a criatura.
- **D2 — Revisor.** (**Sonnet**, por ser Risco `médio`.) Alternativa: `spec-reviewer` Opus, por ser combate.

## 9. Resultado

(preencher no fechamento)
