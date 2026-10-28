# SPEC-347 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão 28/10 sobre `ef94d286`, rebaseada na `main` com a SPEC-346 pousada; 1ª rodada `CHANGES_REQUIRED` em `dcb4505a`)
> **Revisor:** Sol (Claude Opus, spec-reviewer) · **Data:** 2026-10-28 · **Commits revisados:** `dcb4505a` (1ª) e `ef94d286` (re-revisão)

## Escopo

Branch `spec-347` (`git diff main...spec-347`, 10 commits de `494ad1db` a `dcb4505a`, 67 arquivos).
Revisados: backend (`services/conflict_orchestrator.py`, `services/combat_preview.py`,
`services/creature_art.py`, `services/card_rewards.py`, `api.py`, `agents/combat.py`,
`config/flags.yaml`, `scripts/import_bestiary_art.py`), front (`DeckCombat`, `PlayQueue`,
`CombateTab`, `ChatSurface`/`Workspace`, `Arena`, `TargetChip`, `Hud`), os e2e/`node --test` da 347
e os prints de `docs/spec347/depois/` contra `docs/spec347/smoke/`.
Fora do escopo, por decisão do coordenador: a geração paga do retrato (R13.4/R13.6, que foram para a SPEC-352).
Aqui só confirmei que o botão fica oculto e que nada pago é chamado: `CombateTab` não passa
`onGenerate` à `Arena`, e `_enemy_portrait` nunca passa `quote_price`, então `gerar` é sempre `null`.
Nenhuma mudança em `evals/`.

### Respostas ao foco do coordenador

1. **Sobreposição sem rolar (390/1440): mede de verdade.** O `web/e2e/spec347-helpers.ts::measure` usa
   `elementFromPoint(centro)`, caixa dentro do viewport e do `.ws-panel`, e linhas por `Range.getClientRects`.
   Os testes armam a carta por `dispatchEvent("click")` (390) ou pela tecla `1` (1440), sem `click`, `hover` ou
   `scrollIntoView` no elemento medido. A prévia vem com 150 ms de atraso, e os testes rodam com 1 e com 2 inimigos.
   Nos prints, `depois/390-previa.png` mostra "Jogar em Saqueador" e "Cancelar" lado a lado acima da barra,
   contra `smoke/1874135`, onde "Cancelar" ficava coberto. Já `depois/390-fila.png` mostra a barra numa linha
   (Sem matar · Fugir · Encerrar + selo "2"), com "Desfazer fila" na fila. Um detalhe: `depois/1440-registro.png`
   e `depois/1440-retratos.png` são **o mesmo arquivo** (sha1 `c97ff370…`), ver P2-6.
2. **Sem texto livre / Fugir.** Com `pilhas`, o `Composer` troca a área de texto pela nota. O botão "Fugir"
   envia `action_kind:"flee"` + "Tento fugir." sem `jogadas`, usando o contrato que já existe em `api.py:1896,5827`.
   A spec-346 **não** cria outro contrato de fuga: conferi `git diff main...spec-346 -- api.py agents/router.py`.
   Com fila, o botão pede confirmação inline, e Esc ou "Ficar" devolvem o foco (e2e verde). O alvo tem
   ≥ 43,5 px (e2e `fugir_alvo_44_390`). Lacunas: P2-2 (resultado falso depois de um envio que falhou),
   P2-3 (R18.3 e o teste `rascunho_volta_apos_conflito`).
3. **Iniciativa / golden 330.** `fora_de_turno` só é gravado com `resolved_turns` em `out`
   (`conflict_orchestrator.py:1216`). Todos os chamadores de `_basic_attack` (`:956`, `:1068`, `:1811`, `:1974`)
   são de fato fora de turno. `test_card_effects_grammar.py` (golden) está verde, junto com os testes que fazem
   monkeypatch de `_resolve_actor_turn` (339/341). O wrapper `_resolve_actor_turn` → `_inner` preserva
   o monkeypatch. **Reconciliação com a 346** em P1-2.
4. **Caminho off.** `deck-342-baseline.spec.ts` (win32) está verde e nenhum snapshot foi alterado na branch.
   A prova é parcial, porque a fixture da baseline não tem `order` e por isso não exercita R5.3/R5.4 em pixel.
   O `off` de R5.3/R5.4 está coberto por `spec347-desktop.spec.ts::off_iniciativa_honesta` (verde) e pelo SSR.
   Aceito, com o follow-up F-3.
5. **Retrato.** Chave e `is_important` determinísticos e testados. A flag `RPG_CREATURE_ART` está registrada
   (`config/flags.yaml:876`, `release`, `off`) e não tem efeito no `off` enquanto o catálogo não tem arte
   `creature`. Ponto de atenção: com arte curada, `retrato` aparece **mesmo com a flag off**, o que é por
   design de R13.7. Os achados P1-1 (importador) e P2-1 (o achado do autor da 352, confirmado) estão abaixo.
6. **R11 sem e2e: aceitável.** Não existe rota web "play → saves" na mesma aba, então o vermelho não é
   reproduzível pela UI. A correção de 1 linha (`App.tsx:756`) é defensiva e inócua. O follow-up F-2 pede um teste unitário.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `scripts/import_bestiary_art.py:88,95,108-116` × `services/content_validator.py:1168,1182,1215` × `tests/test_visual_assets.py:41-43` | A **1ª importação real quebra o lint de conteúdo e a suíte**. O validador de catálogo só aceita `subject_type` em `{race,class,location,npc}`, exige URL com prefixo `/art/v1/` e aplica o teto de 300 KB ao `display`. O teste exige `display.url` começando com `/art/v1/`. O script grava `creature`/`creature_family` em `/art/bestiario/...` com `full` de 1536 px, sem checar o teto. Isso contradiz a promessa da spec ("o dono só solta as imagens e roda o script, sem outra mudança"). O teste do importador usa um catálogo em `tmp_path` e não pega o problema. | (a) Escolher um prefixo único: gravar em `web/public/art/v1/bestiario/...`, ou estender o validador e `test_visual_assets` para aceitar `/art/bestiario/`. (b) Acrescentar `creature` (ids de `data/bestiary.json`; `bst:*` aceito por padrão) e `creature_family` (`enemy_decks.FAMILIAS`) a `canonical` em `validate_visual_assets`. (c) No script, falhar com mensagem clara se uma variante passar do teto do validador. (d) Teste: importar num catálogo temporário e rodar `validate_visual_assets(catalog_path=…, public_root=…)` sem findings. |
| P1-2 | P1 | `services/combat_preview.py:194-195,207-217`; `agents/combat.py:2342-2347`; `services/conflict_orchestrator.py:1216` | **Conflito com a spec-346, que precisa ser reconciliado no pouso.** (i) A 346 reescreve a mesma linha `what =` de `mech_log` (lê `atk["label"] == "Última Ação"`, que a 346 grava em `orchestrator` depois de `_resolve_last_stands`) e passa a usar `ticks`. A 347 lê `atk["fora_de_turno"]`. São dois campos para a mesma ideia. (ii) As duas mudam a assinatura de `store_mech_log` (a 346 passa `ticks` por dentro; a 347 acrescenta `enemy_ids`) e a mesma chamada em `agents/combat.py`. (iii) A 346 cria `services/round_log.py` (o registro em frases do turno), e a 347 cria `combat_preview.round_log` (o registro estruturado): dois "round_log" com papéis diferentes e o mesmo nome. (iv) O `round_log` da 347 ignora os `ticks` de DoT da 346. | Quem pousar por último: manter **um** rótulo, com `fora_de_turno` como fonte e a 346 derivando "Última Ação" dele (ou o contrário), e fazer o merge de `mech_log` cobrindo os dois comportamentos (rótulo + dupla do crítico + alvo declarado + ticks). Renomear o da 347 para `round_entries` (ou fazer a 346 consumir `turn_spans`, como pede a D-347-9). Acrescentar os `ticks` como entrada `efeito` no registro. Rodar `test_spec347_mech_log`, `test_spec347_round_log`, os testes de mech_log da 346 e o golden 330 juntos depois do rebase. |
| P2-1 | P2 | `services/creature_art.py:150-151` (e o teste `tests/test_spec347_creature_art.py:32`) | **Confirmado (achado do autor da 352).** `_registry_src` lê `variants["thumbnail"]["url"]` (ou `variants["url"]`). Mas o pipeline usa os nomes `full`/`thumb` (`asset_pipeline.py:15`), e o job grava `variants` como **lista** de `{variant, mime_type, width, height, …}` sem URL (`workers/dynamic_art_jobs.py:~226-236`). Uma linha real de registro nunca resolveria a imagem, e o teste valida um formato que não existe. Hoje não há impacto, porque só existe `EmptyRegistry`. É P2 porque o caminho está morto até a 352, mas o contrato errado vira armadilha. | Corrigir na 347: normalizar o formato aceito (`dict` com chave `thumb` → `thumbnail` → `full`, ou lista com `variant == "thumb"`) **ou** remover a leitura de registro (`_registry_src` devolve `(None, False)`) e deixar o formato para a 352 definir. Ajustar o teste para usar o formato real que o pipeline produz. |
| P2-2 | P2 | `web/src/workspace/tabs/CombateTab.tsx:246-258` | O resultado da fuga é inferido no cliente: `fleeRound` fica setado assim que o envio sai. Se o POST falhar ou for recusado (rede/429/`action_refused`), na próxima rodada normal (`round == fleeRound+1`) a faixa diz "Não escapou…". Se o jogador vencer essa rodada, diz "Você escapou.". A spec (R19.4) pedia usar `chase.escaped` ou o fim do combate por fuga. | Limpar `fleeRound` quando a ação termina sem mudança de estado (erro/recusa), ou ancorar no `turn_outcome`/`combat_result` da resposta (motivo `fuga`) ou no `combat.chase`. Teste: fuga com o backend respondendo erro → a próxima rodada não mostra a faixa. |
| P2-3 | P2 | `web/src/workspace/ChatSurface.tsx:190,193`; `web/e2e/spec347-board-only.spec.ts` | R18.3: com `deckLocked`, `onFocusInput` foca uma `textarea` inexistente (no-op). A spec pede que o atalho leve ao painel de Combate. Falta o teste `rascunho_volta_apos_conflito` (R20) e, a 390, o caso "sem pilhas" não asserta nada. | Com `deckLocked`, desviar o foco para o painel de Combate. Escrever o e2e do rascunho: digitar → entrar no conflito com `pilhas` → sair → o texto volta. |
| P2-4 | P2 | `services/combat_preview.py:319-321` | `round_log` coloca **toda** entrada `fora_de_turno` antes das ações do turno. Isso está certo para a janela de reação, que abre antes do golpe, mas a ordem fica invertida no "Contra-ataque" passivo (`conflict_orchestrator.py:1811`, depois de levar o golpe) e na "Última Ação" dentro do turno: o revide aparece antes do golpe que o causou. | Emitir as entradas do span pela ordem de índice em `out["attacks"]` (que já é cronológica), encaixando os usos de carta sem ataque no ponto do seu índice. Teste: passiva de contra-ataque → o golpe do inimigo vem antes do revide. |
| P2-5 | P2 | `scripts/import_bestiary_art.py:83-117` | (a) Reimportar o mesmo id com **outro** arquivo substitui sem aviso a entrada do catálogo, inclusive uma curada à mão (sem `bundle: BESTIARY_ART`), e deixa os WebP antigos órfãos. (b) `bst_*` não é validado (o id do pool vira diretório e URL do jeito que veio, com espaços ou acentos). (c) Se o 2º arquivo for inválido, os WebP do 1º já foram escritos, mas o catálogo não, e ficam órfãos. Os caminhos são seguros: o stem não tem separador e o diretório leva prefixo. | Exigir `--force` para trocar um sha existente e recusar a troca de entrada que não seja `BESTIARY_ART`. Validar `bst_` com `[a-z0-9_-]+`. Validar todos os arquivos antes de escrever qualquer coisa. |
| P2-6 | P2 | `docs/spec347/depois/1440-retratos.png` | Arquivo idêntico a `1440-registro.png`. O print de retratos não tem cenário próprio (só o marcador e um `<img>` vazio no Bandoleiro). | Gerar o print com a fixture de retrato (`pronto` com imagem real + `marcador`), ou remover o duplicado e anotar na §9. |
| P2-7 | P2 | `specs/SPEC-347-cartas-smoke-layout.md` §5 | Critérios abertos que o executor não marcou nem registrou como desvio: smoke real (§6) não executado; R15.2/R15.3 (regeração e diffs) dispensados porque a fixture não tem `order`. | Registrar na §9 como desvio aceito (F-3), ou executar. O smoke real fica para o coordenador antes de `done`. |

## Correções aplicadas

Re-revisão sobre `ef94d286` (commits `3e3a4460`..`ef94d286`, já rebaseados sobre a 346):

| Achado | Commit | Conferido |
|---|---|---|
| P1-1 | `3e3a4460` | O importador grava em `web/public/art/v1/bestiario/` com `thumbnail` ≤ 120 KB e `display` ≤ 768 px ≤ 300 KB (a qualidade desce até caber). `validate_visual_assets` aceita `creature` (ids de `data/bestiary.json` + `bst:[a-z0-9_-]+`) e `creature_family` (`FAMILIAS`). O teste roda o validador numa **cópia do catálogo real** depois da importação e dá zero findings. `test_visual_assets` está verde. **Resolvido.** |
| P1-2 | `4c7198dc` | `mech_log` mostra a "Última Ação" da 346 (`label`) e o rótulo `fora_de_turno` da 347 no ramo `else`, sem conflito. `store_mech_log` passa `ticks`/`heals`. O registro da 347 foi renomeado para `round_board` (`meta["last_round_board"]` → `registro_rodada`, separado do `services/round_log.py` da 346) e inclui ticks de DoT (rótulo "Dano contínuo") e curas. Testes da 346 (10 arquivos) e da 347 verdes juntos. **Resolvido.** |
| P2-1 | `9cfd7e7b` | `creature_art.variant_url` aceita a lista real do job (`variant` = `thumb` ou `full`) e o dict. Sem `url`, cai no marcador e nunca inventa caminho. O teste usa o formato do job. A conversão `key`→URL é da 352. **Resolvido.** |
| P2-2 | `0da60fde` | O resultado só vale depois que `data` muda. Envio que falha mostra "A fuga não chegou ao mestre. Tente de novo." (`role=alert`), sem resultado inferido. E2e `fugir_falha_no_envio_…` verde. **Resolvido.** |
| P2-3 | `9765f4dc` | `focusComposerTarget` + `onFocusCombat={() => openTab("combate")}` (`Workspace.tsx:361`). E2e `rascunho_volta_apos_conflito` verde. O R18.3 só tem teste node da função; a fiação é 1 linha e o e2e do rascunho cobre o travamento. **Aceitável.** |
| P2-4 | `a9efdc08` | Entradas na ordem de índice de `out["attacks"]`. Testes verdes para contra-ataque passivo depois do golpe e janela de reação antes dele. **Resolvido.** |
| P2-5 | `3e3a4460` | `--force` para trocar sha; entrada curada à mão recusada sem ele; `bst_` validado; tudo codificado antes de escrever, com rollback dos WebP escritos se algo falhar. **Resolvido.** |
| P2-6 | `fd31e916` | `1440-retratos.png` agora é próprio: marcador da família (Saqueador) + imagem (Bandoleiro). **Resolvido.** |
| P2-7 | `fd31e916` | Desvios R15.2/R15.3 registrados na §9; smoke real com o coordenador. **Registrado.** A §9 ainda diz que o P1-2 "fica para quando a 346 pousar", mas já foi feito em `4c7198dc`: nota defasada, o coordenador ajusta no pouso. |
| Alvos | `9765f4dc` | Os e2e da 347 agora exigem ≥ 44 px (antes 43,5) e passam. |
| R11 | `9765f4dc` | `resetBookScroll` extraído e testado (`spec347-logic`), preservando o rascunho. Sem e2e (aceito). |

Golden 330: `test_card_effects_grammar.py` verde, sem diff contra a `main` em `tests/test_card_effects_grammar.py`, `tests/data/`, `evals/` e nos snapshots da baseline 342. Caminho `off`: `deck-342-baseline.spec.ts` (win32) verde sem regerar.

## Pendências

- F-1: FEITO em `4c7198dc`. Pendente só a nota defasada na §9 da spec.
- F-2: FEITO (`resetBookScroll` testado).
- F-3 (coordenador): se quiser a prova pixel do `off` de R5.3/R5.4, colocar `order` na fixture da baseline 342 e regerar em commit próprio.
- F-4 (SPEC-352): converter `key`→URL na linha do registro e ligar `onGenerate`.
- F-5 (coordenador): smoke real (§6) da 347 antes de `done`.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -n 2 tests/test_card_effects_grammar.py tests/test_flag_registry.py tests/test_import_bestiary_art.py tests/test_spec347_*.py(5) tests/test_spec342_nonlethal_jogadas.py tests/test_spec342_scene_view.py tests/test_spec309_golden_rule.py tests/test_card_rewards.py tests/test_forge.py tests/test_spec345_mech_log.py → 168 passed (exit 0)
bash scripts/dev/py.sh -m pytest -q -n 2 tests/test_spec339_duracao_condicoes.py tests/test_spec341_balanco.py tests/test_spec295_chefe_no_topo.py tests/test_spec283_enemy_support_cards.py tests/test_round_multi_play.py tests/test_combat_preview.py tests/test_bug_combate_modificadores.py tests/test_bug_combate_morte_aliados.py tests/test_spec297_flag_off.py → 276 passed, 4 skipped (exit 0)
node --test tests/spec347-components.test.mjs tests/spec347-logic.test.mjs tests/deck-queue.test.mjs tests/deck-tokens-342.test.mjs → 23/23 pass
RPG_E2E_PORT=5041 npx playwright test e2e/deck-342-baseline.spec.ts e2e/spec347-mobile.spec.ts --workers=1 → 16 passed
RPG_E2E_PORT=5041 npx playwright test e2e/spec347-board-only.spec.ts e2e/spec347-desktop.spec.ts e2e/spec347-retrato.spec.ts --workers=1 → 17 passed
```

Re-revisão (`ef94d286`):

```text
bash scripts/dev/py.sh -m pytest -q -n 2 (golden 330, flags, import_bestiary_art, visual_assets, 5× spec347, 342, card_rewards, forge, 345 mech_log, 339, 341, round_multi_play, combat_preview, morte_aliados, 10× spec346) → 588 passed, 4 skipped (exit 0)
node --test spec347-components, spec347-logic, deck-queue, deck-tokens-342 → 25/25 pass
RPG_E2E_PORT=5041 npx playwright test deck-342-baseline, spec347-{mobile,board-only,desktop,retrato}, deck-combat-342 --workers=1 → 72 passed
```

Observação: o coordenador pediu `-n auto`, mas mantive `-n 2` por regra do CLAUDE.md (subagente nunca usa `-n auto`).
