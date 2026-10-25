# SPEC-317 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus / Sol (revisão técnica independente) · **Data:** 2026-10-25 · **Commit revisado:** `2477a998`

## Escopo

Branch `spec-317`, `git diff main...spec-317` (33 arquivos, 1 commit `2477a998`): router (R2/R4),
interlocutor, loot (R3), rag (R6), file_cache (R7), context_prefetch/context_sources/turn_pipeline (R5),
context_builder + combat (R8), prompt_layout + storyteller/npc/router (R9), api/rag lazy imports (R11),
vercel.json + skill (R12), `RPG_ROUTES` inline + `vercel_env.py` + `classify_ab.py` (R1), os testes novos
e a spec com o §7.1. Ficaram de fora: as medições de staging (R1/R2/R10/§6), que não aconteceram ainda.
Nenhum arquivo em `evals/` foi alterado (o `classify_ab` só lê `routing_actions.jsonl`).

Conferido e OK:
- **R9 com a flag off:** comparei os prompts da branch com os de `main` (carreguei as fontes de `main` via
  `git show` e capturei com o `tests/prompt_capture.py`). Saem **idênticos byte a byte** para story (9261),
  npc (9234) e router (1020). Os trechos que viraram strings sem `f` não têm `{{`/`}}`.
  Atenção: `test_flag_off_byte_identical` é tautológico (compara env ausente com `off` no MESMO código),
  então não prova nada sobre `main` (ver P2-7).
- **R6 sem vazamento entre sessões:** a chave é o `abspath` do diretório do índice, que inclui o game_id
  (`_get_session_path`). O carimbo é tirado ANTES do `load_local`, então numa corrida com um writer o pior
  caso é recarregar à toa, nunca servir dado velho. Os 2 sites que fazem `add_texts` (rag.py:1404, :1564)
  continuam lendo do disco, e nenhum site somente-leitura muta o objeto do cache. `_save_index` invalida.
  Fora do rag.py nenhum writer toca `index.faiss`. Entre instâncias serverless, mtime_ns + tamanho decidem.
- **R7:** o cache guarda o texto e cada chamada recebe um objeto novo (`json.loads`), então mutação não
  vaza entre chamadas.
- **R8:** no combate só se usa `world_state_block`. O `fallback_safe_scene` não lê `ctx["narrative"]`.
  O pack agora fica dentro do `try` (antes, uma exceção ali derrubava o `_prepare_scene`).
- **R12:** nada do runtime lê `lore_nova/`, `handoffs/` ou `project_index/` (`content_validator.LORE_DIR`
  só é usado no lint; `shared_pool_validators` importa só a constante `NPC_SECRET_LABELS`). `evals/**` e
  `data/codex/**` continuam no bundle. `web/public/**` já era excluído antes desta spec (não é regressão;
  fica o aviso para a SPEC-326).
- **R1:** `RPG_ROUTES` inline é lido com `json.loads` dentro de um try. Um tier inválido cai no `ROUTES`
  default e o log não mostra o JSON. `scripts/staging/**` não vai ao bundle, então o `classify_ab` não
  roda em produção.
- **Shadow do R2 não muda nada:** o payload devolvido é o do CLASSIFY (ou do Jev), e
  `addressed_in_scene` não tem efeito colateral.
- **R3:** quando o modo vem do regex, ele é o mesmo de antes (o código antigo já sobrescrevia o modo do
  LLM com `explicit_mode`). Dois ou mais itens batendo levam ao CLASSIFY. Os ids que voltam são resolvidos
  por `_resolve_ref_in` e `find_recipe`.
- Guards: nenhum `with_structured_output` novo. Não há segredo em log.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | agents/router.py:381-389, :48-53, :416 | **O gate de promoção do R2 não mede o que importa.** (a) `agree` compara só a rota e o `active_npc_name`, sem a `social_approach`. Quando o CLASSIFY diz NPC+`intimidar`/`sondar`/`pedir_favor`, o shadow conta "concorda", mas o caminho `on` devolve sempre `conversar` sem `social_intent`. Com isso a mecânica da SPEC-298 R20 some nos turnos com vocativo e os 97 % não acusam. (b) O `_NON_PLAIN_TALK_RE` roda sobre o texto cru (sem tirar acentos), então `ameac\w*` não pega "ameaço" (testado: `'Mira, ameaço contar tudo ao conde'` → nonplain=False; `'ameaco'` → True). Além disso faltam verbos de combate comuns: "esfaqueio", "corto", "soco", "mata", "desafio" passam (testado). O caso combate o shadow pega (CLASSIFY=COMBAT ⇒ agree=False). O de coerção ele não pega. Como o staging começa a juntar as 200 decisões assim que o deploy sair, a métrica precisa estar certa antes. | Em `agree`, exigir também `payload.get("social_intent") is None`, ou logar `approach_agree` separado e usar os dois no gate. Casar o léxico contra o texto dobrado (`_norm`/NFD sem combining) e acrescentar raízes de combate (`esfaque\w*`, `cort\w*`, `soc[oa]\w*`, `mat[ae]\b`, `desafi\w*`, `chut\w*`) e de sondagem (`ment\w*`). Teste: vocativo + "ameaço" ⇒ CLASSIFY; shadow com CLASSIFY NPC+intimidar ⇒ `agree=False`. |
| P2-1 | P2 | agents/router.py:351-357 | Em `on`, o atalho roda ANTES do Jev `primary`, que é o modo do staging. Os turnos com vocativo passam a ignorar o Jev. Em `shadow`, os turnos que o Jev cobre retornam antes do `_classify` e não geram log nenhum, então as 200 decisões só vêm dos turnos que o Jev não cobre. | Registrar isso na spec (D2) ou pôr o atalho depois do `pending.primary_routing()`. Na hora da promoção, contar só as decisões que de fato chegam ao CLASSIFY. |
| P2-2 | P2 | agents/router.py:428-447 (R4) | A janela enxuta entra em produção **sem flag**, e o `evals compare` do router que a spec exige (§4 Etapa 1.3, §5) não está anexado. Guardar só os 400 últimos chars da narração pode cortar uma ameaça narrada no começo (regra "reage a uma ameaça narrada" → COMBAT). | Rodar o `evals compare` do `routing_actions` antes do pouso e anexar o resultado. Se piorar, pôr R4 atrás de uma flag. |
| P2-3 | P2 | agents/loot.py:76-79 | `merchant_stock({**state, "world": dict(world)})` é uma cópia rasa. Se o `world["merchant_stocks"]` já existe, `_ensure_stock` grava a chave do mercador **dentro do estado do grafo** (e também em `merchant_restock_day`). O `market_snapshot` faz `deepcopy` justamente para não mutar. Hoje os valores gravados são os mesmos que o `execute_trade` gravaria, então o risco é baixo. | `copy.deepcopy` do `world` (ou só de `merchant_stocks`/`merchant_restock_day`) antes de chamar, igual ao `services/economy.py:608`. |
| P2-4 | P2 | agents/loot.py:61-64 | `_QTY_HINT_RE` não cobre "onze/doze/…/vinte/cem/mil/par/punhado". Em "compro doze flechas" o CLASSIFY é pulado e sai `qty=1`. Comprar menos que o pedido é falha segura (paga menos), mas é a quantidade errada. | Acrescentar os numerais por extenso ≥ 11, `par`, `punhado`, `dezena`, `centena`, ou pular o atalho em qualquer palavra numérica. |
| P2-5 | P2 | services/turn_pipeline.py:65-69, services/context_prefetch.py:117 | (a) O prefetch roda em todo turno fora de combate, mas só o STORY consome o vetor. Nos turnos NPC/LOOT é 1 embedding (Jina) desperdiçado por turno. (b) Há um único worker por processo: com uvicorn multiusuário, prefetches de sessões diferentes entram numa fila, e o `take` espera até 2 s por um future que nem começou, depois embeda inline. Isso acrescenta até 2 s ao STORY. Na Vercel (1 request por instância) não acontece. (c) `prefetch_hit/miss` saem em `debug`, então o staging não consegue medir a taxa de acerto. | Pular o prefetch quando o pré-roteamento já indica que o turno não é STORY, ou aceitar o custo e registrar isso na spec. No `take`, se o future ainda não começou (`future.running()` falso), não esperar. Subir hit/miss para `info`, com amostragem. |
| P2-6 | P2 | rag.py:754-757 | A expulsão é FIFO e não LRU. Com 64 índices de sessão ou NPC carregados depois do lore (9,9 MB), o índice global sai do cache e é recarregado do disco. | LRU (`OrderedDict.move_to_end` no hit) ou deixar `faiss_lore_index`/`faiss_rules_index` fixos fora do teto. |
| P2-7 | P2 | tests/test_prompt_order.py:43-48 | `test_flag_off_byte_identical` não compara com o prompt antigo. A identidade com `main` só foi verificada nesta revisão, por fora. | Gravar um golden (hash sha256 dos 3 prompts com flag off na fixture `_story_state`) gerado a partir de `main`, ou documentar que a garantia é a verificação manual registrada aqui. |
| P2-8 | P2 | agents/storyteller.py (compose em `on`), agents/npc.py:1270-1283 | Com a flag `on`, as cláusulas dinâmicas (`npc_fallback_clause`/`varie_clause`/`opcoes_clause`, `openings_clause`, ganchos) ficam fora do bloco `<INSTRUÇÕES>` e depois da regra 6 numerada. O conteúdo é o mesmo, mas a estrutura muda. Está coberto pelo default `off` e pelo gate do R10. | Levar isso em conta no `evals compare` do R10. Se possível, o bloco dinâmico pode abrir com um rótulo curto e fixo. |
| P2-9 | P2 | scripts/staging/vercel_env.py:84-86 | `RPG_ROUTES` entrou em `OPTIONAL_FLAGS`: qualquer `vercel_env.py` sem `--classify-routes groq_first` **apaga** um `RPG_ROUTES` posto à mão no staging (para outros tiers). | Documentar no help/skill, ou só apagar quando o valor atual for o `CLASSIFY_GROQ_FIRST_ROUTES`. |

## Correções aplicadas

(nenhuma ainda — revisão inicial)

## Pendências

- P1-1 bloqueia o deploy no staging com `shadow` ligado: sem a correção, as 200 decisões juntadas não
  servem para promover. Pode ser corrigido no próprio executor da 317; a revisão do follow-up pode ser leve
  (diff de 2 pontos + 2 testes).
- P2-2 (o `evals compare` do router) precisa estar anexado antes do `done`; é critério de aceite do §5.
- Os demais P2 podem ir como follow-up na própria spec (§7.1) ou numa spec de ajuste de latência.

## Comandos rodados

```text
git diff main...spec-317 --stat → 33 arquivos, +1377/-66
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_router_interlocutor.py tests/test_loot_trade_intent.py tests/test_rag_index_cache.py tests/test_context_prefetch.py tests/test_combat_context.py tests/test_prompt_order.py tests/test_lazy_imports.py tests/test_vercel_config.py tests/test_classify_ab.py tests/test_jev_router_port.py tests/test_spec192_vercel_packaging.py tests/test_spec192_vercel_env.py tests/test_context_sources_concurrency.py tests/test_loot_exploracao.py tests/test_spec238_loot.py tests/test_loot_voice.py → exit 0, 168 passed
script (scratchpad) prompts main × branch com flag off → story/npc/router IDENTICAL
script (scratchpad) léxico R2 em 13 frases → "ameaço", "esfaqueio", "corto", "soco", "mata", "desafio", "mentindo" passam pelo atalho
```
