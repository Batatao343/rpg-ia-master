# SPEC-363 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` — re-revisão de `20053563`, sem P0/P1 aberto (1ª rodada em `ca9e8e14`: `CHANGES_REQUIRED`)
> **Revisor:** Opus / Sol · **Data:** 2026-11-02 · **Commits revisados:** `ca9e8e14` (base `ab6ae398`) e `8a9f8bf8..20053563`

## Escopo

Branch `spec-363`, commits `34452421..ca9e8e14` (10 commits, 57 arquivos). Revisados no source:
`api.py` (portão da oferta, alvos da mão, 409), `llm_setup.py` (timeout do CLASSIFY), `agents/combat.py`
(fonte do resumo, matador, fuga, condições, nome genérico), `agents/loot.py` (gramática da compra, mercado),
`services/{round_log,conflict_summary,combat_targeting,combat_preview,chase,card_rewards,card_shop,economy,creature_art,encounter_manifest}.py`,
`scripts/staging/art_preflight.py`, front (`TargetChip`, `deck.ts`, `DeckCombat`, `CombateTab`, `boardState`,
`portraitOrder`, `rejectedPlay`, `http.ts`, `api.ts`, `App.tsx`, `cardRewards.ts`, `CombatDeckTab`, `types.ts`) e os
três testes antigos alterados. Fora: Playwright (`spec363-board.spec.ts` não rodado, RAM), arena (só lida em
`docs/spec363/arena.md`), smoke §6 (coordenador).

Guardas conferidas sem achado: `git diff` vazio em `evals/`, `tests/spec330_equivalence.py`,
`tests/fixtures/spec330_legacy_golden.json`, `services/conflict_orchestrator.py` e `config/flags.yaml` (R40, R47);
nenhum `with_structured_output` novo (R43); evento novo no catálogo e no doc (R41); campos novos opcionais (R42/R44).

Pontos do foco do coordenador:

1. **Retrato pago (P1-1): ok.** `_image_effect_open` (`api.py:2862`) espelha `_guard_image_effect` (`api.py:4833`):
   mesmo `get_switches().is_enabled(IMAGE)` + `require_paid_effect("image")`, fail-closed em erro do store. A oferta
   (`_portrait_offer_price`, `api.py:2882`) só sai com o portão aberto e preço; a cotação continua passando por
   `_image_finance()` (perfil com banco + `RPG_DYNAMIC_ART_ENABLED`) + `_guard_image_effect`, que são as mesmas
   condições de `_creature_art_live`. Cotação não debita; autorização/IDOR do fluxo pago (SPEC-352,
   `_monster_quote_inputs` recalcula a chave no servidor) intocados. Resta só a corrida do cache (5 s do switch),
   coberta por R4 no front (`shouldHidePortraitOffer`/`withoutPortraitOffer`). Oferta com mira como irmã do botão
   (`TargetChip.tsx`), sem botão aninhado; a arena é `data-aim-safe`.
2. **Resumo/morte (P1-2): fallback correto; V4 com falso positivo em massa (P1-1 abaixo).** `_no_digits` protege nomes
   com dígito por placeholder PUA e restaura; `humanize_ids` só casa `[a-z]+_…_\d+` e não toca "Smoke3A"/"Bandido 2"
   (provado em script: "Goblin 2", "Smoke3A" intactos; "fallback_goblin_1" → "Goblin 1"). Herói fora das orações,
   dedupe por categoria mais forte sem mexer no `ConflictSummary`, quedas antigas no passado. V5 é estreito o bastante.
3. **valid_targets = motor: ok.** `hand_card_targeting` usa os mesmos `_enemy_targets`/`friendly_ids` do motor;
   `check_declared_target` cai nele só para Carta em `pilhas.mao` não preparada. Os portões de economia que
   `valid_targets_for_card` aplica a mais (frequência, Entropia, silêncio) não são de alvo e o edge devolve `None`
   para eles, então não há 409 divergente. 409 traz `play_index`/`card_id`; o front tira só a jogada (índice
   conferido contra `cardId`, fallback por `cardId`).
4. **Compra por texto: fechada.** O complemento é alternância de nomes escapados (mercador, local atual, NPCs do
   contexto), opcional, antes do `tail`; `fullmatch` + "?"/negação continuam barrando. Testes cobrem "?", "depois",
   nome desconhecido e negação.
5. **CLASSIFY 6,5 s: ok.** Timeout só no candidato DeepSeek do tier CLASSIFY, com chave de cache própria; timeout é
   exceção comum → próximo candidato; não abre circuito (`_permanent_provider_error` não casa timeout).
   `LLM_TIMEOUT_SECONDS`/`DEEPSEEK_TIMEOUT_SECONDS` vencem. Seams de teste com `_build_client(p, m, t)` continuam
   compatíveis (o kwarg só é passado quando há timeout de tier).
6. **Testes antigos alterados: justificados.** `test_spec346_outcome.py` (só tolera os dígitos dos nomes listados,
   R6; o resto continua sem número e sem id), `test_spec353_registry.py` ("no seu torso", R10),
   `spec347-components.test.mjs` (oferta com mira, R3, e ainda prova que nada interativo fica dentro do botão do
   alvo). Nenhum afrouxamento além do que o requisito pede.
7. **Excepts/eventos:** os `except` novos logam (`log_fallback`) e são dica de UI; `combat.outcome_narrative_rejected`
   registrado. Ver P3-3 sobre o conteúdo de `codes`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/conflict_summary.py:450,460-471` | V4 rejeita **qualquer** "seu/sua/teu/tua + parte do corpo" fora das regiões feridas do herói, sem exigir marca de dano. Prosa correta e comum de vitória cai no fallback: provei em script (auth de herói ileso) que "Você ergue seu braço e a lâmina desce sobre o Mímico", "Com o peso do seu ombro, você empurra o Goblin…", "Você firma sua perna no chão…" e "…o coração batendo forte no seu peito" dão todos `['V4']`. É o "falso positivo em massa" que o R11 proíbe ("um texto correto sobre o mesmo fato passa"); o `MIMIC_GOOD` da fixture só passa porque evita "seu". | Em `_v4`, exigir na **mesma oração** uma marca de dano junto da marca de corpo (ex.: `sangue|sangr|corte|cortad|ferid|ferimento|rasg|perfur|escorr|lateja|doi|dor|arde|atinge|acerta|fere|golpe\w* (?:no|na|em)`), ou então só a forma `pelo/pela/no/na + seu/sua + região` com um desses verbos. Acrescentar a `tests/test_spec363_outcome_text.py` um corpus negativo (as 4 frases acima e equivalentes) que **não** pode disparar V4, mantendo `MIMIC_BAD` rejeitado. |
| P2-1 | P2 | `agents/combat.py:1539`; `services/round_log.py:743` | Matador por dano contínuo usa `blow["condition"]` cru (`tick["condition"]` = `c["name"]`, que pode ser id com `_`, ex. `veneno_fraco`) e artigo fixo masculino: "Você tomba, consumido pelo veneno_fraco" / killer "o queimadura" no `death_context.killer`, no `player_downed` e na Roda. Fura o invariante de ids (R27) no texto de morte. | Passar por `card_effects.condition_label(...)` e montar sem artigo de gênero ("consumido por Veneno Fraco" / killer "Veneno Fraco"; `_diante_de` já trata o caso sem "o "). Teste com condição de id composto. |
| P2-2 | P2 | `tests/test_spec363_portrait_offer.py:78-80` | A "propriedade sobre os 2⁴ estados" amarra switch e preço numa só variável (`switch=gate, pricing=gate`) e não passa pela view: os estados switch on + preço vencido (e o inverso) não são exercitados no implicante, nem `_enemy_portrait`/`portrait_for` (o caminho que de fato monta `retrato.gerar`). | Parametrizar `switch` e `pricing` separadamente (e preço `None`) e afirmar sobre `_enemy_portrait(...)["gerar"]` com registro falso: `gerar` presente ⇒ `_guard_image_effect()` não levanta e `_image_finance` não daria `image_quotes_unavailable`. |
| P3-1 | P3 | `agents/combat.py:2040-2063` | `last_outcome_source` não é gravado quando `strip_mechanic_numbers` esvazia o texto (nem o ramo `llm` nem o `elif text` rodam), e o `not in source_sink` deixa passar um valor velho de conflito anterior se `combat_meta` for reaproveitado. | Gravar `fallback_narrative` (ou `fallback_numbers`) quando o texto zera após o filtro; `source_sink.pop("last_outcome_source", None)` no início de `_narrate_outcome`. |
| P3-2 | P3 | `tests/test_spec363_rare_scenarios.py:31-58` | R37 pede 5 rodadas com Carta de cena, fuga, Reação e Última Ação; o teste só afirma `mid_rounds >= 1` e não força Carta de cena/Reação/Última Ação. A propriedade "0 LLM por rodada" fica provada em 1 rodada no pior caso. | Fixar seed/estado que mantenha ≥ 4 rodadas ativas e afirmar `mid_rounds >= 4`; incluir uma rodada com Carta de cena e uma com Reação preparada. |
| P3-3 | P3 | `agents/combat.py:2062` | `combat.outcome_narrative_rejected` grava em `codes` as frases de `violations` ("X foi narrado vivo… apesar de morto."), não códigos (R13 pede "códigos, sem texto"). Não é segredo, mas é texto livre com nomes no log. | Mapear para códigos curtos (`dead_alive`, `captured_free`) em `validate_narrative_text` ou só emitir a contagem. |
| P3-4 | P3 | `web/src/components/combat/DeckCombat.tsx:80-85` | Assinatura do 409 com deps `[]` captura o `onAnnounce` do 1º render (closure velha). Hoje funciona se a prop for estável; quebra em silêncio se mudar. | Espelhar `onAnnounce` num ref como já se faz com a fila. |
| P3-5 | P3 | `scripts/staging/art_preflight.py:75` | `env = {**env_file, **os.environ}`: o env local do operador sobrepõe o `.env.staging`, então o preflight pode dizer `ok` por uma var que só existe na máquina (e não na Vercel). O pool também não é fechado. | Ler só o `--env-file` para as flags (os.environ só para o DSN); `pool.close()` no fim. |
| P3-6 | P3 | `tests/fixtures/spec363_smoke.py:10-13` | `DEATH_GOOD` sai "diante de Minotauro Esqueleto" (sem artigo), diferente do formato da §3.3 ("diante do Minotauro Esqueleto"). Cosmético; o teste fixa a forma sem artigo. | Aceitar como está e ajustar a §3.3, ou artigo por gênero do bestiário em spec própria. |

## Correções aplicadas

Commit `20053563` (executor), re-revisado no diff `8a9f8bf8..20053563`:

| Achado | Status | Conferência |
|---|---|---|
| P1-1 | **fechado** (resíduo vira P2-3) | `_v4` agora exige, na mesma oração (entre vírgulas), parte do corpo do herói **e** marca de dano (`_DAMAGE_MARK_RE`, `services/conflict_summary.py:463-480`). As 4 frases da 1ª rodada passam; escrevi mais 8 frases benignas novas: 5 passam ("…seu golpe atinge o Lobo…; seu ombro mal sente o peso", "Sua perna avança, firme, e a lâmina fere o Mímico", "…o peito arfando…", "Você ergue seu braço… recua ferido", "…crava a espada no torso do Orc, que sangra e cai"). Rejeitados de forma correta: `MIMIC_BAD`, "A garra do Lobo rasga seu braço…", "Seu ombro sangra…", "O Orc te atinge na perna… sua perna latejando". O falso positivo deixou de ser em massa; sobram 3 casos de borda (P2-3). |
| P2-1 | **fechado** | `_cond_name` → `condition_label` em `authorship`, `final_blow_sentence`, `deterministic_outcome_text` e `_killer_identity`. Testado com `veneno_fraco`/`sangramento_profundo`: "Você tomba, consumido por Veneno fraco.", "Sangramento profundo termina o serviço…", killer `('Veneno fraco', '')`. Nenhum id sobra. A mudança em `test_spec353_registry.py` (sem "O ") é coerente com a correção. |
| P2-2 | **fechado** | A propriedade agora varia `live × db × env × switch × fresh × preço` (64 casos) e afirma sobre `api._enemy_portrait(...)["gerar"]`: `gerar` ⇒ `_guard_image_effect()` não levanta e todas as condições estão abertas; há também o controle positivo `test_offer_present_when_everything_open`, então a propriedade não passa por vacuidade. |
| P3-1 | fechado | `pop` no início; `fallback_narrative` quando o filtro esvazia o texto. |
| P3-2 | fechado | O R37 foi reforçado (Carta de cena, Reação, fuga, ≥ 4 rodadas, Última Ação) e está verde. |
| P3-3 | fechado | `validate_narrative_text` devolve `codes` (`dead_alive`, `captured_free`); o evento grava só códigos. |
| P3-4 | fechado | `announceRef`; `eslint` do arquivo limpo. |
| P3-5 | fechado | As flags vêm só do `--env-file`; `os.environ` só entra para o DSN; o pool é fechado. |
| P3-6 | fechado | A §3.3 foi alinhada ao texto produzido. |

## Achados da re-revisão

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-3 | P2 | `services/conflict_summary.py:463-466` | Ainda há falso positivo de V4 em 3 de 8 frases benignas que escrevi: "Seu braço acerta o Goblin em cheio e ele tomba." (`acerta`/`atinge`/`fere` com o corpo do herói como **sujeito**), "O sangue do Goblin respinga no seu braço quando ele cai." e "O Lobo rasga o ar onde estava sua cabeça…, e erra.". O custo é só prosa (o fallback é correto) e o caso não é mais em massa, por isso não bloqueia. | Contar `acerta/atinge/fere/rasga` só quando o corpo do herói é **objeto** (`<verbo> (?:o |a )?(?:seu|sua) <região>` ou `te <verbo>`) e ignorar "sangue d[oa] <outro>". Somar as 3 frases ao corpus `test_v4_never_fires_on_benign_prose`. Medir a taxa de `fallback_attribution` no §6. |
| P3-7 | P3 | `services/round_log.py:687-688` | Sem `condition`, `final_blow_sentence` começa a frase em minúscula: "dano contínuo termina o serviço: Goblin tomba." | `cond[:1].upper() + cond[1:]` ao abrir a frase. |

## Pendências

- P2-3 e P3-7 ficam como follow-up desta spec ou da próxima de cartas (o coordenador decide); nenhum P0/P1 aberto.
- Continuam fora desta revisão: Playwright `spec363-board` e a suíte completa (coordenador, no pouso), e o smoke §6.

## Comandos rodados

```text
git diff ab6ae398...HEAD --stat → 57 arquivos, +2996/-107
git diff ab6ae398...HEAD -- evals/ tests/spec330_equivalence.py tests/fixtures/spec330_legacy_golden.json services/conflict_orchestrator.py config/flags.yaml → vazio
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec363_{portrait_offer,outcome_text,hand_targets,flee_verdict,ids,shop_grammar,enemy_name,rewards_shop,latency,golden_guard}.py tests/test_spec346_outcome.py tests/test_spec353_registry.py tests/test_routing.py → 260 passed, 1 skipped
node --test tests/spec363-*.test.mjs tests/spec347-components.test.mjs (web/) → 23 pass, 0 fail
bash scripts/dev/py.sh <scratchpad>/probe_v4.py → 4 frases benignas com "seu braço/ombro/perna/peito" ⇒ ['V4'] (P1-1); humanize_ids preserva "Smoke3A"/"Goblin 2"
```

Re-revisão (`8a9f8bf8..20053563`):

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec363_{portrait_offer,outcome_text,rare_scenarios,ids,golden_guard}.py tests/test_spec353_registry.py tests/test_spec346_outcome.py → 236 passed (rc 0)
node --test tests/spec363-*.test.mjs (web/) → 10 pass, 0 fail
npx eslint src/components/combat/DeckCombat.tsx → limpo
bash scripts/dev/py.sh <scratchpad>/probe_v4b.py → 8 benignas novas: 5 ok, 3 V4 (P2-3); 4 ruins todas V4; condições sem id
```
