# SPEC-293 — Rótulo de exibição de combatente de fação oculta

> **Status:** `done` (aprovada: o dono autorizou em 19/10 tudo que não exige ação externa dele)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-292 (`concealed_faction`/`public_hint`), SPEC-206/211 (projeção fail-closed e `assert_no_player_leak`)
> **Desbloqueia:** —
> **Origem:** follow-up P1-1 da revisão da SPEC-292 (`handoffs/SPEC-292-review.md`)

---

## 1. Contexto & Objetivo

O nome canônico de combatentes de fação carrega o nome da fação ("Iniciado da Chama Azul",
"Degolador da Mão Sombria", "Soldado da Legião de Ferro", "Cultista da Destilação"). A SPEC-292
tirou o nome da fação da **prosa** do narrador de combate e calculou um `public_hint`, mas nenhuma
superfície visível o consome: o jogador que ainda não conhece a fação (`faction_intel[fid].known`
falso) continua vendo o nome canônico no HUD (`combat.enemies[].name`), no manifesto público
(`encounter_view.participants[].species_label`), no desfecho (`combat_result`), nas linhas do log
mecânico dentro de `message`/`last_turn_log`, no Bestiário/Codex/dossiês (o spawn faz
`record_rumor(enemy_id)`), no histórico e na crônica. Isso fura a não-onisciência da Fase 2.

Objetivo: um **rótulo de exibição por observador**. Enquanto a fação não é conhecida, toda
superfície player-facing usa o **papel** ("Iniciado", "Soldado", "Degolador", "Cultista"); o nome
canônico continua interno (ids, `enemies[]` no save, manifesto canônico, prompts, audit/eval). Depois
de `apply_faction_reveal`, o nome completo aparece em todas as superfícies, inclusive
retroativamente (Bestiário/dossiê), porque o rótulo é calculado na leitura, nunca gravado.

Princípio: mesma arquitetura fail-closed da SPEC-206/211 — projeção na borda (Python), oráculo
determinístico reusado (`assert_no_player_leak`), frontend só consome o que a API manda.

## 2. Requisitos

- **R1 — Regra do rótulo (pura).** `display_label(name, faction_id, factions, intel)`:
  - fação conhecida, sem fação ou nome que não expõe a fação (`concealed_faction` da SPEC-292 vazio)
    → `name` inalterado;
  - senão, se o nome tem qualificador organizacional (`" da|de|do|das|dos "` ou `"("`) → o papel,
    texto antes do qualificador ("Iniciado da Chama Azul" → "Iniciado"; "Devorador de Sol (Zhur)"
    → "Devorador");
  - senão, se os radicais do nome cobrem todos os radicais do nome da fação (o nome **é** a fação,
    ex. "Druida-Renegado" × "Os Druidas-Renegados") → `"Combatente desconhecido"`;
  - senão (papel/povo genérico sem qualificador, ex. "Nômade Canibal", "Arpoador Osshari") → `name`.
  Sufixo numérico de instância é preservado ("Iniciado da Chama Azul 2" → "Iniciado 2").
- **R2 — Mapa por observador.** `concealed_name_map(state) -> {canônico: rótulo}` cobre o bestiário
  (curadoria ∪ overlay), `state.enemies[]` e participantes do manifesto, só para pares em que
  rótulo ≠ canônico. Fação conhecida (`intel[fid].known`) sai do mapa.
- **R3 — Projeção na borda.** `conceal_payload(obj, mapping)` substitui, em todo **valor** string
  (recursivo; chaves e campos de id — `id`, `*_id`, `*_ids` — intactos), cada nome canônico pelo
  rótulo, sem diferenciar caixa e com fronteira de palavra; mais longo primeiro; tolera espaço/
  quebra de linha, acento, hífen↔espaço e plural (revisão P1-1). Aplicada em:
  `format_response` (POST `/game/action`, `/game/state`, `/game/new`, `/game/death`, replay de
  `action_id`; o SSE fatia `resp.message` e serializa `resp` → coberto; equip/levelup/cards não
  passam por ela e não carregam nome de inimigo),
  `project_player_knowledge` (Codex `/game/codex` e base dos dossiês), `build_dossiers`
  (`/game/codex/dossiers`), `/game/history`, `/game/chronicle/search` e `/game/chronicle/export`.
- **R4 — Interno intacto.** Save, `enemies[].name`, manifesto canônico, `combat_target`, `hint`,
  ids, prompts e `bestiary_knowledge` não mudam. Nenhum bump de schema.
- **R5 — Retroatividade.** Após `apply_faction_reveal(..., fid, ...)` as mesmas leituras mostram o
  nome canônico (HUD, Bestiário, dossiê, histórico).
- **R6 — Oráculo reusado.** `assert_no_player_leak` ganha a checagem **(e)**: nome canônico de
  combatente de fação desconhecida em qualquer ponto do payload → `e:concealed_faction_name:<fid>`.
  Teste-oráculo percorre todas as superfícies de R3 com um estado de combate real.
- **R7 — Narrador.** `_concealed_species` (SPEC-292, cláusula do `_narrate`) passa a usar
  `display_label`, então o rótulo da prosa e o do HUD são o mesmo.

### Fora de escopo

- `POST /game/{id}/audit-export` e `/account/export` (trilha de auditoria/LGPD: canônico por design).
- CLI (`game_engine.py`) — terminal local de desenvolvimento.
- Nome da **fação** solto na prosa ("Chama Azul" sem a criatura): já tratado pela cláusula da
  SPEC-292; esta spec não reescreve prosa além do nome da criatura.
- Casos novos no dataset protegido de eval (`evals/datasets/**`) — exigem relock; ficam como
  follow-up (o oráculo de código já cobre via R6).
- Mudança no frontend: a UI só renderiza o que recebe.

## 3. Design técnico

- **Novo** `services/faction_display.py`:
  - `display_label(name: str, faction_id: str, factions, intel) -> str`
  - `concealed_name_map(state: Mapping) -> dict[str, str]`
  - `conceal_text(text: str, mapping: dict[str, str]) -> str`
  - `conceal_payload(obj: Any, mapping: dict[str, str]) -> Any` (cópia; não muta)
  - `conceal_for(state, obj)` = `conceal_payload(obj, concealed_name_map(state))`
  - `concealed_name_problems(payload, state) -> list[str]` (usado pela checagem (e))
- **Alterados:** `api.py` (`format_response` e endpoints de R3), `services/player_knowledge.py`
  (projeção + (e)), `services/dossiers.py` (`build_dossiers`), `agents/combat.py`
  (`_concealed_species`).
- Rótulo genérico: `GENERIC_LABEL = "Combatente desconhecido"`.

## 4. Plano passo a passo

1. **Testes** (`tests/test_spec293_rotulo_faccao.py`): regra de R1 (4 ramos + sufixo numérico +
   fação conhecida); mapa de R2; `conceal_text`/`conceal_payload` (caixa, id intacto, sem mutação);
   oráculo (e); superfícies (POST/state via `format_response`, SSE, codex, dossiês, history,
   crônica) sem nome canônico; retroatividade após `apply_faction_reveal`; save intacto;
   cláusula do narrador usa o rótulo.
2. **Implementação:** módulo novo → projeção na borda → oráculo (e) → `_concealed_species`.
3. **Verificação:** testes do escopo + suítes afetadas; suíte completa 1×.

## 5. Critérios de aceite

- [x] R1–R7 cobertos por teste
- [x] Nenhuma superfície de R3 contém nome canônico de fação desconhecida (oráculo (e))
- [x] Revelação mostra o nome completo retroativamente
- [x] Save/manifesto canônico intactos; saves antigos carregam (sem bump)
- [x] Revisão independente Opus (`handoffs/SPEC-293-review.md`)
- [x] Suíte completa offline (falhas só de índice stale, esperadas antes do pouso)

## 6. Smoke test com LLM real

Não aplicável: projeção 100% determinística na borda, sem chamada/schema de LLM novo. A cláusula
do narrador (R7) só troca a fonte do rótulo curto já validada em real na revisão da SPEC-292.

## 7. Riscos & compatibilidade

- Saves antigos: nenhum campo novo; o rótulo é derivado na leitura.
- Jogador que digita o nome canônico ("ataco o Iniciado da Chama Azul") vê a própria fala com o
  rótulo no histórico — aceitável (fail-closed). A resolução de alvo é interna e usa o canônico.
- Custo: um regex por resposta (≤ ~20 nomes), desprezível.

## 8. Follow-ups (revisão `handoffs/SPEC-293-review.md`, APPROVED_WITH_FOLLOWUPS)

- P2-1: o oráculo (e) busca substring sem fronteira de palavra (falso positivo em "…Chama Azulado");
  ajustar exige relock de eval.
- P2-2: inimigo sem `id` (só save legado) usa o nome como id → canônico em `enemies[].id`.
- P2-3: `/data/combat-simulator` lista o bestiário com nomes canônicos (anterior a esta spec;
  decisão do dono).
- P2-5: projeção custa ~3,5 ms por resposta; cache opcional.
- Caso novo de eval para o rótulo (dataset protegido) exige relock — follow-up.
