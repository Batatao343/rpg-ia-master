# SPEC-373 — revisão sol (review)

> Nome do arquivo: `handoffs/SPEC-373-sol-review.md`.
> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Sol (Opus, revisão técnica independente) · **Data:** 2026-11-04 · **Commit revisado:** `cbd899b4`

## Escopo

Branch `spec/373` (`efb58938..cbd899b4`), diff de produto `git diff main...HEAD`. Revisados:
- motor: `services/enemy_decks.py` (R9/R10/R12) e a linha nova de `services/conflict_orchestrator.py`;
- `scripts/bestiario/calibrar.py` (D4) e `docs/spec373/work/dial.py`;
- `_ajustes.yaml`, `bestiary.json` e `data/cards/criaturas/*.json` (só a coerência com `recalibradas.json`);
- os testes `tests/test_spec373_*.py` e as mudanças em `tests/test_enemy_decks.py` e `tests/test_spec349_mecanica.py`;
- a integridade de eval (`evals/protected-paths.txt`, R1, exceção D-373 em `fb739425`);
- o impacto mecânico da Parte C. A voz das Cartas ficou com o revisor Opus.

Fora do escopo: as 28 Cartas de família (`SPEC-373-astra-review.md`), a voz de `cor1_tro_mao_adiantada` (`SPEC-373-astra-independent-review.md`) e o smoke §6.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/enemy_intent.py:176-189` (`forecast_round`) | **O R12 é contornado com `RPG_ENEMY_INTENT=on`**, que é o modo do staging (`scripts/staging/staging_flags.json:27`). O Presságio da ação extra (`idx >= 1`) chama `enemy_declaration` no `sandbox[aid]` com o baralho cheio. Depois, `_enemy_decl_inner` (`conflict_orchestrator.py:2773-2800`) cumpre a intenção congelada se `still_possible`. O `declare_extra` só age no caminho tardio (`late()`). Sondagem local: 24 criaturas com mais de uma ação, sementes 0-7 e 0-3 rodadas antes; das 192 intenções extras, 38 telegrafam Carta de família ou facção, inclusive no slot `enemy_aranha_de_cristal`. A arena mede com o intent `off` (default), então os números dos chefes não valem para o staging. Os testes de `test_spec373_acao_extra.py` só cobrem o intent `off`. | Em `forecast_round`, para `idx >= 1`, envolver a chamada em `with edk.extra_action_deck(sandbox[aid]):` (o sandbox é cópia rasa, então a troca não vaza para a ficha real). Adicionar teste com `RPG_ENEMY_INTENT=on`: a intenção `idx>=1` e a jogada efetiva da extra só usam Carta própria. Com `RPG_ENEMY_DECKS=off`, `extra_action_cards` devolve `None`, então nada muda. Não precisa remedir a arena, porque ela roda com o intent `off`. |
| P1-2 | P1 | `data/cards/posturas/corruptor_tronco.json` (`cor1_tro_mao_adiantada`); `services/conflict_turn.py:242-258`, `:399-402`, `:712-718` | Confirmo o P1-1 do revisor Opus: a Carta é `ativa` com efeito principal `buff_iniciativa`, um kind que não está em `_ATTACK_EFFECTS` nem em `_SUPPORT_EFFECTS`. Quando jogada, ela só loga "sem resolução" (com `on`, o Fôlego já foi cobrado). A meta R22 de emboscada passa **só porque a Carta está no `full_deck`** (`docs/spec355/arena_spec355.py:58-63`, `:87`). O único efeito medido de verdade é o custo: Corruptor base `todas` 51,9 → 48,3 % (−3,6 pp, a 3,3 pp do piso), uma vaga morta no baralho. Do jeito que está, não aceito. | Ver o parecer sobre a correção abaixo. Depois dela: remedir as 0–19 (base e emboscada do Corruptor; as outras 3 Posturas devem continuar idênticas) e refazer **uma vez** a confirmação 260–339, registrada em §9 como "reconfirmação após correção de defeito, Carta sem mudança numérica". Isso não é ajuste até passar no R3: a confirmação anterior mediu uma Carta inerte. |
| P2-1 | P2 | `data/bestiario/mecanica/_ajustes.yaml:566-571`, `:686-691`; spec §9 | O D4 (`LIMITE_DANO_CHEFE=9`) foi implementado, mas nenhum chefe passou de ±7. `mon_hospede_do_estomago` está com `dano` −7 e `sig` 0, e `mon_escavador_das_camaras` com `dano` e `sig` −7. A leitura das duas fichas ainda é a da 349 ("arena final"). Pelo R11, o passo 2 (`calibrar.py` com a folga do D4) vem antes do passo 3 (R12) e do 4 (registro). Não há registro de que o `calibrar` com o D4 rodou nesses dois. A D-373 do dono cobre o resultado, mas a frase "as Cartas próprias pesam mais que o dial permite" não tem evidência. | Registrar em §9 que a folga do D4 não foi usada (ou rodar 1 rodada do `calibrar` nos dois e registrar). Sem bloqueio. |
| P2-2 | P2 | `tests/test_spec373_artefatos.py:238-249` + `docs/spec373/recalibradas.json` | A lista de exceção do portão "`off` idêntico" fica em arquivo do lado do produto. Conferi: as 12 ids têm mudança real de dial contra a `main`. `enemy_fantasma` mudou de dial (`sig` 0 → 6, passo manual), não está na lista e passa no portão, o que é mais estrito. Mesmo assim, nada impede o produto de pôr na lista uma id sem mudança. | Fica para o autor de eval: exigir `recal ⊆ ids com diff de dial contra a main`. A `enemy_fantasma` ficou de fora da confirmação 40–119 (conjunto = chefes + recalibradas); registrar isso em §9. |
| P2-3 | P2 | `docs/spec373/work/dial.py` e `*.py` | Os passos manuais pelo `dial.py` usam os mesmos dials do R8, dentro de ±7. Não afrouxam oráculo: os portões e a confirmação são independentes. Mas o script grava `arena: 'SPEC-373 passo manual'`, e as leituras finais de parte das entradas foram escritas à mão, algumas sem procedência (`enemy_vinha_estranguladora`, `mon_cisne_de_patina` …). Os 4 scripts de `work/` reprovam `ruff format` e têm 24 erros no `ruff check` (`docs/` está excluído do lint, então não reprova gate). | Anotar a procedência nas leituras (`(SPEC-373 passo manual, 0-39)`) ou apagar `docs/spec373/work/*.py` antes do pouso. |
| P2-4 | P2 | `services/enemy_decks.py:297` | Pelo R10, uma criatura autoral sem `_deck332` e com **1** Carta dos pools conta como já montada. Hoje nenhuma das 281 autorais tem `inf_*` ou facção curada no template (conferi: 0). Uma ficha futura da esteira com 1 Carta curada, porém, pularia a montagem, o que o F-1 da 332 quis evitar. | Teste de guarda: nenhuma entrada autoral do bestiário tem Carta dos pools no template. |
| P2-5 | P2 | `tests/test_spec349_mecanica.py:203`; `calibrar.py:36` | O D4 diz "até −9", mas o teste e o `calibrar` aceitam ±9. O efeito prático é nulo (os chefes só descem). | Opcional: aceitar só `-9 <= v <= 7` para chefe. |
| P2-6 | P2 | `services/conflict_resolution.py:141-146` (fora do diff) | Achado pré-existente, da SPEC-355: o `initiator` age primeiro "sem disputa" e ignora `initiative`. Nenhuma Carta `buff_iniciativa` (passiva ou ativa, de qualquer Postura) anula uma emboscada no motor. A "contrapartida" do R17 da 355 existe só no modelo da arena. O smoke §6.5 ("a emboscada é anulada") não tem como passar. | Para a SPEC-369: decidir se a contrapartida vira mecânica (ex.: `initiative` do lado emboscado disputa a 1ª rodada) ou se o critério da arena muda. Ajustar o texto do smoke §6.5. |

### Parecer sobre a correção do P1-2 (pedido do coordenador)

O que foi proposto: pôr `buff_iniciativa` em `_SUPPORT_EFFECTS` (`conflict_turn.py:242-256`) e `"buff_iniciativa": "initiative"` no mapa de `stat` do `else` de `_resolve_support_card` (`:712-718`). Hoje o `.get(kind, kind)` gravaria `stat: "buff_iniciativa"`, que o `combat_modifiers` ignora.

- **Segura no motor, sim.** Os dois pontos só valem quando o efeito **principal** de uma Carta **ativa** é `buff_iniciativa`. Inventário em `data/cards/**`: as outras 8 Cartas com `buff_iniciativa` são `passiva` (`arc_imp_remendo`, `arc_equacao_persistente`, `dev_zel_vigilia`, `san_conta_memorizada`), `reacao` (`med_dose_choque`, que resolve por `conflict_orchestrator.py:1212-1231`, outro caminho) ou Carta de criatura com `buff_iniciativa` como efeito **secundário** (`cri_pernalta_do_conselho_mao_que_rebaixa`, `cri_virado_do_avesso_dor_que_acelera`, `cri_parado_do_sopro_golpe_ja_dado`, todas com efeito principal `dano`). Os efeitos secundários passam por `fx.resolve_extras`, que a mudança não toca. A única Carta afetada é `cor1_tro_mao_adiantada`.
- **Com flag `off`, nada muda.** Com as Cartas desligadas não há jogada de Carta de jogador. `RPG_ENEMY_DECKS` (`off` ou `on`) não muda nada, porque nenhuma Carta de inimigo tem `buff_iniciativa` como efeito principal. As fichas da arena do bestiário e a população da 332 não mudam. Só o Corruptor muda nas arenas de Postura.
- **Ressalva mecânica (registrar, não bloqueia):** a condição `initiative +2` com `duracao` 1 só vale na rolagem da **rodada seguinte** (`_initiative_value`, `conflict_resolution.py:113-118`). Ela não anula a emboscada da 1ª rodada (ver P2-6). Pedir um teste: jogar a Carta na rodada N dá +2 no `_side_roll` dos heróis na N+1 e o Fôlego é cobrado uma vez. Se o teste mostrar que o tick de condição consome a duração antes da rolagem, usar `duracao` 2 ou documentar.
- Se o bot continuar sem jogá-la depois da correção, o −3,6 pp do base fica. Ainda está dentro de 45–85 %, então passa, mas a Carta não entrega nada mecânico até o P2-6 ser resolvido. Registrar em §9.

### Outros pontos conferidos (sem achado)

- **R9/R10 determinismo:** `_autoral` e `want` são função de `id` + `seed` (`_h`). `test_autoral_familia_1_ou_2` repete a montagem e compara. `_autoral` vale para as 281 da esteira. Save antigo (3–5 da família, sem marcador) não remonta. Round-trip com `fase_idx` verde.
- **`off` byte-idêntico:** `apply_deck`, `extra_action_cards` e `declare_extra` retornam cedo com `off` e com `shadow`. O snapshot R2 fica verde fora das recalibradas, e `test_off_declaracao_igual_nas_duas_acoes` também.
- **`extra_action_deck`:** troca `cartas` só durante a declaração e restaura no `finally`. Não filtra por `categoria`: vale para qualquer criatura com `acoes_por_rodada > 1` (24 hoje, todas chefe ou slot de chefe), o que é coerente com o R12.
- **`calibrar.py`:** para não-chefe, `_passos` faz exatamente o que o laço antigo fazia (`LIMITE_DANO == LIMITE == 7`). Só pula dial saturado, e o laço antigo gastava esse passo sem efeito. Não afrouxa oráculo: o `calibrar` é ferramenta de ajuste, não avaliador.
- **±9 em `test_ajustes_registrados`:** restrito a `CHEFES` × {`dano`, `sig`}, como no D4. Nenhum valor passa de 7 hoje.
- **Integridade de eval:** os únicos commits que tocam caminho de `evals/protected-paths.txt` são os 4 de eval (`1729475d`, `6f022a9d`, `f2f16083`, `fb739425`). O R1 está limpo: `git diff --stat main...HEAD` nos 16 avaliadores, fixtures e testes congelados sai vazio. As Cartas legadas não foram tocadas.
- **Exceção D-373 (`fb739425`):** é nominal e vale por célula (`hospede` `L5|off`/`L5|on`, `escavador` só `L5|on`), presa ao valor gravado + 3 pp. `test_excecoes_d373_sao_so_as_aceitas_pelo_dono` fixa exatamente as 2 ids, nenhuma de slot, e só células que estão de fato fora. `test_chefes_reprovados_known_good_e_bad` cobre outro chefe a 0,5 pp. Não abre brecha.
- **Testes não protegidos mudados pelo produto:** (a) o teto de tamanho de família 8–12 → 8–16 é estrutural, não oráculo de balanço, e o teto de uso 15 (o oráculo de verdade) segue protegido pela E2. Aceito com o registro em §9. (b) Comparar a população da 332 com os pools da `main` testa exatamente o R9 ("regra de montagem não muda a 332"). As Cartas novas mudam os pools de propósito, e o efeito disso está no R17/arena e no P2-5 do astra. Aceito.
- **Parte C, `bomba_estopim` v2:** 2 passos (`valor` em área 3 → 2, `custo_folego` 1 → 2), `versao` 2, como no R20 e no D11. `lote` sem `dominante` (−5,0 pp, uso 53 %). Arcanista `todas` 52,3 % (0–19) e 51,1 % (260–339), acima dos pisos. `test_spec341_balanco` verde, então a Carta não está nas `versoes` da 341. Aceito.
- **Tamanho e lint:** funções novas ≤ 15 linhas, `enemy_decks.py` com 677 linhas, `conflict_orchestrator.py` sem crescer (troca de 1 linha). `test_size_budget` verde, `dup_helpers` sem duplicata, `ruff check` limpo no produto. Nenhum `except` novo.

## Correções aplicadas

(o executor preenche: P1-1 e P1-2, com commit por item)

## Pendências

- P2-1, P2-3, P2-4 e P2-5: executor, nesta spec (registro ou teste pequeno).
- P2-2: autor de eval (portão de `recalibradas.json`).
- P2-6: coordenador → SPEC-369 (contrapartida de emboscada no motor) e texto do smoke §6.5.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_spec373_{montagem,acao_extra,artefatos,cartas}.py tests/test_enemy_decks.py tests/test_spec349_mecanica.py tests/test_card_lint.py tests/test_boss_phases.py tests/test_spec295_chefe_no_topo.py -n 4 → 708 passed
bash scripts/dev/pt.sh tests/test_size_budget.py tests/test_spec341_balanco.py tests/test_spec355_arena.py tests/test_spec287_encounter_scale.py tests/test_spec290_chefe_sobrevivencia.py tests/test_handoff_names.py -n 4 → 179 passed
bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova duplicada
uv run ruff check services/enemy_decks.py services/conflict_orchestrator.py scripts/bestiario/{calibrar,arena}.py tests/test_spec373_*.py → All checks passed
git log main..HEAD -- <evals/protected-paths.txt> → só 1729475d, 6f022a9d, f2f16083, fb739425 (eval)
git diff --stat main...HEAD -- <avaliadores do R1> → vazio
sondagem forecast_round com RPG_ENEMY_INTENT=on (24 criaturas multi-ação, sementes 0-7) → 38/192 intenções extras com Carta de família/facção (P1-1)
dials _ajustes.yaml × main → 13 ids mudaram; recalibradas.json = 12 (falta enemy_fantasma, cujo off é idêntico)
```
