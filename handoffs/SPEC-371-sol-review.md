# SPEC-371 — revisão sol (review)

> **Veredito:** `APPROVED` (rodada 2; rodada 1: `APPROVED_WITH_FOLLOWUPS`)
> **Revisor:** Sol (Opus 5.5, revisão técnica independente; não escreveu produto nem avaliador) · **Data:** 2026-11-03 · **Commit revisado:** `04f8acb5` (rodada 1), `c8177a02` (rodada 2)

## Escopo

Branch `spec-371`, `main...HEAD` (16 commits). Produto: `44323672` (motor: `services/fauna_saber.py`,
`scripts/fauna/build_saber.py`, `data/world/bestiario_saber.json`, ganchos em `enemy_decks`,
`enemy_intent`, `discovery`, `dossiers`, `agents/combat.py`, `encounter_preparation`, flag),
`99b9c19e` (web), `572d5daf` (playtest), `87ec4837` + `8d11c4a9` (3 Cartas de reação inicial,
`character_creator.py`, `playtest/runner.py`). Avaliador (outro autor): `f75f88d2`, `bff04051`,
`6c32b683`, `04f8acb5`. Foco pedido: flag `off`, writer único e save/load, regra determinística,
zero LLM novo, Cartas novas × saves existentes, Acervo/Preparadas, XSS, e2e, texto das Cartas.
Fora: o e2e Playwright não foi rodado por mim (RAM livre entre 1,0 e 1,6 GB); conferi o diff do
spec e rodei os testes unitários de `omenView`.

## Conferência dos pontos pedidos

- **Flag `off` no backend.** Todo gancho sai antes de tocar estado/cena/prompt: `observe_promise`/
  `observe_fulfilled`/`absorb`/`finish_combat`/`stamp_actor`/`prep_line`/`view_fields` checam
  `active()`; `enemy_intent._saber` devolve `None` com `off`; `dossiers` só repassa chave presente;
  `_prep_prompt` só acrescenta a linha com `ctx["saber_linha"]`. A refatoração de
  `enemy_decks.record_promise` (`services/enemy_decks.py:407`) mantém a semântica (mesmo retorno,
  uma chamada a `prenuncio`). `test_spec371_flags_off` e o golden de 30 turnos da 360 verdes.
- **D5 (`prenuncio` no chip com a flag `off`).** Só UI: `omenView` lê um campo que o backend já
  mandava em `pressagios_publicos` (`services/enemy_intent.py:320-321` existia antes); nenhuma regra
  ou payload muda. Confirmado.
- **Writer único / round-trip.** Só `fauna_saber` escreve `telegrafos_vistos`,
  `assinaturas_sobrevividas`, `saber_revelado` (Grep). `persistence.py:741/1092` repassa
  `bestiary_knowledge` sem filtro, e `combat_meta["scene"]` persiste o `saber_obs` (pop no
  `absorb`, sem duplicar: `test_saber_obs_de_save_no_meio_do_combate`). O teste de round-trip é
  `json.dumps/loads`, não `save_game_state`/`load_game_state` (P2-4).
- **Regra determinística.** `reveal_reason` (`services/fauna_saber.py:103-116`) segue a §3.5, na
  ordem, pegajosa, sem RNG nem LLM. Simulação e prévia não absorvem (`agents/combat.py:2698`,
  `:2785`; `combat_preview` trabalha em `deepcopy`).
- **Zero LLM novo / guard.** Nenhum `with_structured_output` novo; a linha de R11 entra na chamada
  de preparação existente (guard interno de `prepare_encounter`). `test_invoke_count_on_igual_off`
  verde. Telemetria só com `cid`/`motivo` (sem texto, sem segredo).
- **Integridade da métrica.** Limiares e `verdict` intocados desde `f75f88d2`; as mudanças em
  `scripts/fauna/arena_saber.py` são do autor de eval (`bff04051`, `6c32b683`: leitura da reação
  preparada e do uso `turno` antes do reset), e o E4 virou `xfail(strict=True)` por decisão
  registrada do dono (§9). Nenhum arquivo de `evals/` no diff.
- **XSS.** `FaunaSaber.tsx` e `TargetChip.tsx` renderizam texto como nó React (sem `mdLite` nem
  `dangerouslySetInnerHTML`). OK.
- **Saves existentes × Cartas novas.** Herói já criado não ganha a reação (não há migração) e nada
  quebra: `reacao_inicial` só é lido na criação automática e no runner do playtest; Acervo e
  Preparadas salvos seguem válidos. Herói novo (wizard web não manda `known_cards`, então vale a
  auto-seleção): Arcanista perde a 6ª do Acervo e `arc_olho` das Preparadas; Médico perde a 6ª e
  `med_triagem`; Devoto perde a 6ª e `dev_aguentar` (sonda abaixo).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `specs/SPEC-371-fauna-saber-telegrafo.md` §7 ("Flag `off`. Backend byte-idêntico") e R18; `character_creator.py:298-312` | As 3 Cartas e a nova Preparação inicial **não** ficam atrás de nenhuma flag: no deploy, todo herói novo de Arcanista/Médico/Devoto nasce com outro Acervo e outras Preparadas, com `RPG_FAUNA_SABER=off`. É decisão do dono (§9), mas a spec ainda afirma "off byte-idêntico" sem a exceção, e "Fora de escopo" ainda lista "Mudar … Cartas". | Registrar na §7/R18 e em Fora de escopo a exceção (Cartas e criação mudam sem flag, decisão de 03/11) para o coordenador e o smoke saberem que o staging muda já no deploy. |
| P2-2 | P2 | `character_creator.py:298-312` × `tests/test_spec371_reacao_inicial.py:26` | "Reação p/ toda Postura" não vale no nível 1 para o Corruptor: `cor_membrana` está no Acervo, mas fora das 4 Preparadas (sonda: `cor_toque, cor_esporos, cor_carne_docil, cor_farejar`). O teste congela esse comportamento. Só no nível 3 (arena) as 5 Posturas têm reação preparada. | Levar ao dono: ou marcar `cor_membrana` como `reacao_inicial` (aplicando `keep_starting_reaction` também ao Corruptor), ou registrar que a regra é "no nível da arena". |
| P2-3 | P2 | `docs/spec371/arena-posturas-reacao-depois.json`, `arena-posturas-devoto-depois.json` | A arena de Posturas não joga reações, então mede só a diluição do baralho. O ganho real das reações não foi medido. A sonda da própria §9 mostra que `Pinça no Tendão` (0 Entropia, 1 Fôlego, por turno) corta a perda de Vitalidade por rodada do Médico de 1,55 para 0,36 (−77 %); o Médico está em 46,7 %, perto do piso, então a direção é boa, mas a magnitude é desconhecida. | Follow-up de balanço: arena de Posturas com bot que arma a reação (ou o `leitor` da 371 sem saber), verificar a faixa 45–85 % por Postura e subclasse antes de ligar cartas `on` em staging. |
| P2-4 | P2 | `tests/test_spec371_saber.py:229-231` | O round-trip é só `json.dumps/loads` do `bk`; não passa por `save_game_state`/`load_game_state` nem pela serialização hosted. Hoje o caminho repassa o dict sem filtro (`persistence.py:741`, `:1092`), então não há bug, mas um filtro futuro quebraria sem teste. | Um teste que salve e recarregue um estado com os três campos e com `combat.scene.saber_obs` (padrão de `tests/test_spec360_saves.py`). |
| P2-5 | P2 | `agents/combat.py:2317-2318`; `services/fauna_saber.py:231-247` | `stamp_actor` só roda no spawn. Se o contra-jogo é revelado no meio do combate (`absorb`), o ator não é recarimbado: o "Você sabe:" e o `knowledge_level` `estudada` só aparecem no **próximo** encontro. Bate com R8 ("ao entrar no combate") e com o "(ou num 2º encontro)" do passo 5 do smoke, mas o log de R14 aparece antes do chip mudar. Reforços que entram depois do spawn também ficam sem carimbo. | Aceitável como está. Se o dono quiser o chip mudando na mesma luta: recarimbar os inimigos vivos logo depois de `absorb` quando ele devolver linha de revelação. |
| P2-6 | P2 | `character_creator.py:221-223` | Docstring de `starting_reaction_id` diz que o Devoto não tem reação inicial ("Devoto, Sangromante e Corruptor já nascem com reação"), mas `8d11c4a9` deu `dev1_ini_dor_devolvida` ao Devoto. | Corrigir o texto (só Sangromante e Corruptor ficam sem `reacao_inicial`). |
| P2-7 | P2 | `services/fauna_saber.py:126-141` | Em modo simulação, `note_declaration`/`record_promise` (caminho do orquestrador) ainda anexam `saber_obs` à cena simulada. Nada absorve, então não vai ao save do jogador, mas a cena da simulação carrega lixo. | Opcional: limpar `scene.pop("saber_obs", None)` quando `is_simulation`. |

Nenhum P0 ou P1.

## Texto das 3 Cartas (voz de Valoria)

- **Cinza nos Olhos** (Arcanista): "Sopra contra os olhos de quem ergue o golpe a cinza que o éter
  deixou no cajado." Na voz do Arcanista: cinza e éter, o resíduo da magia vira arma, e "cajado"
  aparece em `data/classes.json`. Cego no atacante não repete Esquiva/Proteção. A ordem da frase
  ("quem ergue o golpe a cinza") pede uma releitura; não é erro.
- **Pinça no Tendão** (Médico): "Dedos de trincheira acham o tendão do pulso que desce; a mão
  afrouxa e o golpe chega sem peso." Concreta, anatômica e coerente com o Médico. "Trincheira" é
  também o nome de uma subclasse (`medico_cirurgiao_trincheira`) numa Carta de tronco, o que não
  chega a ser problema, e a palavra já aparece uma vez em `medico_tronco.json`. O efeito
  (`desarmado_risco`, −2 de dano) bate com o texto.
- **Dor Devolvida** (Devoto): "O Devoto deixa o ferro entrar até onde a fé aguenta e devolve a dor
  pelo mesmo caminho." É a melhor das três: aguentar e devolver, fé como limite, no primário do
  Devoto. Contra-ataque 2 não é reskin de `dev_ombro_porta` (gatilho e efeito diferentes).
- Nenhuma das três é reskin de `san_esquiva`/`cor_membrana`. Os `momento` são claros e não citam
  mecânica de outro sistema. `_ondas.yaml` registra com honestidade que a voz foi coberta pela
  autorização geral, sem leitura do dono.

## Correções aplicadas

Nenhuma até agora (revisão só de leitura).

## Pendências

- P2-1 e P2-6: o executor ajusta o texto da spec e a docstring antes do pouso (custo baixo).
- P2-2: decisão do dono (Corruptor no nível 1).
- P2-3: follow-up de balanço das reações antes de ligar cartas `on` (spec de balanço ou 362/355).
- P2-4, P2-5, P2-7: follow-ups opcionais.
- Smoke real da §6 e o e2e `dossiers.spec.ts --workers=1` ficam com o coordenador (eu não rodei o e2e por falta de RAM).

## Comandos rodados

```text
git diff main...HEAD --stat → 43 arquivos; nenhum em evals/
git diff f75f88d2 HEAD -- scripts/fauna/arena_saber.py → só reacao_disponivel/round_state (autor de eval); limiares intactos
py.sh -m pytest -q -p no:cacheprovider tests/test_spec371_{fonte,saber,pressagio,view,reacao_inicial,eval,flags_off}.py → verde, 1 xfail (E4 strict, desvio aceito)
py.sh -m pytest -q -p no:cacheprovider 23 arquivos de cartas/criação/golden (api_jogadas, cards_prepare_api, conflito_cartas, card_lint, spec341_balanco, spec339, golden_guard 353/363/364, spec360_flags_off/saves, …) → verde (alguns skip)
py.sh -m pytest -q -p no:cacheprovider tests/test_{dossier_leak,dossiers,dossiers_api,enemy_decks,enemy_intent,enemy_intent_node,flag_registry,playtest_harness,playtest_start_levels,perfil_normal_invariantes}.py → exit 0
node --test web/tests/fauna-saber-371.test.mjs + deck*.test.mjs → 20/20
sonda _resolve_starting_cards por Postura (scratchpad) → Acervo/Preparadas acima; Corruptor sem reação preparada no nível 1
e2e dossiers.spec.ts → não rodado (RAM livre 1,0–1,6 GB)
```

## Rodada 2 (HEAD `c8177a02`)

Commits `ce338047` e `c8177a02` aplicam os 7 P2. Conferido:

- **P2-5, recarimbo** (`agents/combat.py:2710-2713`): está dentro do bloco
  `not is_simulation and _fauna_saber.active()` e só roda quando `absorb` devolve linha de
  revelação. Com a flag `off`, o caminho não é alcançado, e `stamp_actor` também faz no-op com
  `off`, então não há efeito colateral. O recarimbo é determinístico: `stamp_actor` é uma função
  pura do `bk` e do ator, sem RNG. `actors_by_id[e["id"]] = e` (`:2454`) é o mesmo objeto de
  `enemies`, então o presságio congelado no fim deste turno (`:2944+`) já lê o `saber_jogador`
  novo. Teste: `test_revelacao_no_meio_da_luta_recarimba_os_inimigos`. Resíduo sem impacto: o
  filtro olha só `dead`, não `status == "morto"`; carimbar um morto é inofensivo.
- **P2-7:** o ramo `elif is_simulation` faz `pop` de `saber_obs`. Com `off` a chave nunca existe,
  então é no-op.
- **P2-2:** `cor_membrana` (`data/cards/corruptor.json:714`) ganhou só `reacao_inicial: true`, sem
  mudança de número. O Corruptor de nível 1 prepara `cor_membrana` no lugar de `cor_farejar`, e o
  teste foi trocado de forma explícita. Os golden guards 353/363/364, o lint e `spec341_balanco`
  estão verdes. O gatilho `ao_ser_alvo_distancia` faz dela a reação mais situacional das cinco; a
  sonda mostra que armar quase não muda o resultado do Corruptor (48,9 → 48,7 %).
- **P2-1:** a exceção sem flag foi registrada em R18, §7 e Fora de escopo, incluindo `cor_membrana`.
- **P2-4:** há round-trip real por `save_game_state`/`load_game_state`, com `combat.scene.saber_obs`.
- **P2-6:** docstring corrigida.
- **P2-3:** a sonda informativa (`docs/spec371/arena_posturas_reacao_armada.py`, fora de `evals/` e
  sem mexer no avaliador) mostra as cinco Posturas entre 45 e 85 % com a reação armada. Fica um
  resíduo aceito: o Médico com a reação no baralho e nunca armada fica em 44,0 %, 1 pp abaixo do
  piso. Isso só vale para um jogador que não arma a reação, e armar dá +3,5 pp. Fica como
  observação para a recalibração de balanço (follow-up da 362/358), não bloqueia.

Resultado: nenhum P0, P1 ou P2 aberto da rodada 1. Veredito: **APPROVED**.

```text
py.sh -m pytest -q -p no:cacheprovider test_spec371_{fonte,saber,pressagio,view,reacao_inicial,eval,flags_off} + card_lint, spec341_balanco, golden_guard 353/363/364, conflito_cartas, cards_prepare_api, classes_refactor, spec360_flags_off, playtest_start_levels → exit 0 (E4 xfail strict)
```
