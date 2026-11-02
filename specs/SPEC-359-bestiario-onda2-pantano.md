# SPEC-359 — Bestiário de Valoria, onda 2: Pântano da Melancolia

> **Status:** `approved`
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Depende de:** SPEC-349 (processo, gate `services/bestiary_lint.py`, formatos, onda 1; branch base `spec-349`), SPEC-348 (lore, `main` be7212f3)
> **Desbloqueia:** Etapas 5–9 da onda 2 (mecânica, Cartas, arena, pouso); onda 3 (`pradaria_ruinas`)
> **EXECUTOR_MODEL:** Opus (prosa, Etapas 3–4); Terra (Etapas 5–7). Fable nunca. **REVIEW_MODEL:** `spec-reviewer` Opus (unicidade) + Sol (técnico). **REVIEW_REQUIRED:** `true`.
> **EVAL_AUTHORING_REQUIRED:** `false`

## 1. Contexto & Objetivo

Spec-filha da SPEC-349 (D8). Repete o processo da 349 §3 (eixos → 2× conceitos → corte → prosa →
gate U1–U13 → revisão → mecânica → arena → pouso) para o **Pântano da Melancolia**. Só o que é
variável fica aqui; o resto (formatos, regras U, checklist §3.9, Respostas do coordenador) vale
como na 349. Aprovada pelo coordenador, autorizado pelo dono.

**Âncoras de lore** (main be7212f3): bioma e crescimento de ~5 m/ano (`creatures.txt:586`,
`rumors.txt:72-73`, `daily_life.txt:117`); concentração de Éter que dissolve o que existe
(`timeline_completa.txt:402-408`); chá do Ciclo e Praga de Ferro (`timeline_completa.txt:400`,
`locations.txt:114`); turnos de duas semanas e rituais (`locations.txt:109`, `daily_life.txt:119`);
espólio da coalizão (`locations.txt:116`); Renegados de Saelwen e os Tumores (`factions.txt:484`,
`creatures.txt:654`); Cripta dos Afogados (C-13: o segredo mora em
`npc_saelwen_a_que_afundou_segredo`, hidden; o público só insinua); sangue de Malagor
(`timeline_completa.txt:390`).

## 2. Requisitos (especializam a 349)

- **R1 — Volume:** 20–25 `status: nova` com habitat em `pantano_melancolia`, `pm_profundezas`,
  `pm_cripta_afogada`; mínimo de habitat 8 / 8 / 3 (a Cripta é um interior).
- **R2 — Cotas:** as da 349 R22 (`COTAS_PADRAO`), em `COTAS_ONDA["pantano_melancolia"]`.
- **R3 — Demônios:** ≥ 4 distintos; **Solvhara obrigatória** (lugar fixo do Pântano,
  `npcs.txt:241`), sem repetir a anatomia do Velório de Sal (R29); preferência pelos que a onda 1
  não usou (Skarath, Veleth, Urath, Lyss, Morvath, Thessavar).
- **R4 — Slot genérico:** `enemy_zumbi_blindado` (único `generico` com `regiao_onda` = Pântano na
  curadoria) reinventado no slot (349 R3). Não conta no total.
- **R5 — Retro:** fichas `retro` só para as `classe: valoria` com `regiao_onda: pantano_melancolia`
  (8). Necromante Renegado e Espectro do Lamento ficam para a onda da Pradaria (o `regiao_onda`
  deles), para não duplicar ficha entre regiões (R29).
- **R6 — Segredo da Cripta:** nenhum texto público diz quem afundou os afogados nem que eram
  druidas; só insinua, no tom de `pm_cripta_afogada.md`.
- **R7 — Arquivos próprios:** fichas, conceitos e docs novos do Pântano; nos compartilhados
  (`bestiary.json`, `entities_extra.json`), só as entradas do Pântano.

### Fora de escopo
O mesmo da 349; e as Etapas 5–9 desta onda (ficam para o executor técnico).

## 3. Design técnico

Arquivos novos: `data/bestiario/fichas/pantano_melancolia.yaml`, `docs/spec349/conceitos-pantano_melancolia.md`,
`data/codex/monsters/<id>.md` (22, gerados), `docs/arte/bestiario-349/pantano_melancolia.md` (gerado),
`handoffs/SPEC-359-independent-review.md`.
Alterados: `services/bestiary_lint.py` (só a entrada `COTAS_ONDA["pantano_melancolia"]`);
`scripts/bestiario/gerar_docs.py` (lê `nome_regiao`, `paleta`, `habitat_nome` e `spec` da ficha,
com fallback para a onda 1); `data/bestiary.json` e `data/graph/entities_extra.json` (só Pântano).

## 4. Plano

- **Etapa 3:** tabuleiro (22 vagas) → `lint.py --regiao pantano_melancolia --vagas` verde → 2×
  conceitos → corte. **Etapa 4:** prosa → `gerar_docs.py --regiao pantano_melancolia` → lint da
  região → revisão de unicidade (Opus) → cortes.
- **Etapas 5–9:** como na 349 (Cartas em `data/cards/criaturas/pantano_melancolia.json`, fases do
  chefe Borda que Anda em `_decks.json`, arena, rumores, smoke, pouso), mais
  `tests/test_spec359_onda_pantano.py` no molde de `test_spec349_onda_nova_arcadia.py`.

## 5. Critérios de aceite

- [x] Tabuleiro e fichas sem erro no gate (`lint.py --regiao pantano_melancolia`)
- [x] Todas as fichas novas `revisao: aprovada` por revisor ≠ autor (2 rodadas, APPROVED_WITH_FOLLOWUPS)
- [ ] Etapas 5–9: mecânica, arena (20/22 do Pântano nos dois modos), `validate_content` 0 ERRO e rumores cobertos pela SPEC-349 §9; faltam o smoke real e o `uv run pytest` no pouso

## 6. Smoke test com LLM real

O da 349 §6, trocando a região: "ataco o `<criatura nova>`" no Pântano resolve no id novo; o
brief de arte do chefe Borda que Anda traz a `appearance`.

## 7. Riscos & compatibilidade

Os da 349 §7. Específico: o id `enemy_zumbi_blindado` não muda (saves); o nome antigo só aparece
num teste de harness como string livre (`tests/test_playtest_harness.py`), sem ligação ao bestiário.

## 9. Registro de execução

**Etapas 3–4 (28/10, autor Opus).**
- Tabuleiro de 22 vagas (21 novas + slot), verde em U2/U3/U12 e contra as 8 retro; 48 conceitos,
  26 cortes do autor com motivo (`docs/spec349/conceitos-pantano_melancolia.md`).
- Gate: região 0 erro; global 0 erro (10 avisos antigos, retro × retro de Nova Arcádia). Ajuste de
  eixo antes da prosa: Musaranho `percepcao` calor → sangue_cheiro (U3 com a Sanguessuga-Braço).
- `gerar_docs.py` tocou arquivos compartilhados só nas entradas do Pântano: `bestiary.json` (só o
  slot `enemy_zumbi_blindado`: name, description, appearance, attacks[0].name, action_hint,
  substitui_generico) e `entities_extra.json` (21 entidades novas + nome do slot).
- Refs de lore apontam para a lore da 348 (main be7212f3), convenção da onda 1.
- **Revisão de unicidade (Opus `spec-reviewer`, 2 rodadas; `handoffs/SPEC-359-independent-review.md`):**
  rodada 1 `CHANGES_REQUIRED` (20 de 22 aprovadas). Aplicado: C-1 Estaqueiro Afogado vazava o
  segredo da Cripta (cordão de medir, hábito, "borda que cresce" → tira de couro, roupa neutra,
  fileira de estacas; carta `cri_estaqueiro_afogado_fileira_de_estacas`); C-2 Banhado do Centro era
  reskin do Caído do Cadinho (placas sobre músculo → suor de ferrugem negra que enferruja a arma de
  quem o fere; carta `cri_banhado_do_centro_suor_de_ferrugem`); P2-5 corda no pescoço do Curtido →
  cordão de amuleto. Rodada 2: `APPROVED_WITH_FOLLOWUPS`; as 22 com `revisao: aprovada`.
- **Pendências:** P2-1 (âmbar do Romeiro prende como o sal do Velório), P2-2 (contra-jogo "fogo
  fecha a ferida" do Tritão lembra a hidra), P2-3 (Borda "afunda e perde movimento" = Porca da
  Queda), P2-6 (contra-jogos "pancada, não lâmina" repetidos); Etapas 5–9 (Cartas, números, fases do
  chefe, arena, rumores, `tests/test_spec359_onda_pantano.py`, smoke, pouso); o gate global segue com
  os 2 erros U11 pré-existentes da onda 1 (`enemy_elemental_fogo_poluido`, `enemy_polvo_esgoto`).
- Doc de arte (para o criador de imagens): `docs/arte/bestiario-349/pantano_melancolia.md`.
