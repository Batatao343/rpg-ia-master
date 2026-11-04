# Smoke local (LLM real): ressalvas do épico de Cartas só provadas por teste

Feito em 04/11/2026 (agente de smoke local). Base: `2fcb2cb3` (main).

**Ambiente.** Cópia `git archive` do HEAD fora do OneDrive, `.env` copiado (nenhum valor impresso), perfil `legacy`, preset `scripts/staging/staging_flags.json` (cartas `on`, `RPG_TOKEN_STREAM=on`, `RPG_CREATURE_ART=on`), rotas default, API em `:8780` (a `:8000` de outra sessão ficou intocada). Saves de `tests/fixtures/spec368_seed.py` (`seed_save` com MockLLM); as ações foram contra o LLM real. API morta por PID (árvore), sem órfãos; cópia e pastas temporárias apagadas no fim. Evidências pequenas nesta pasta (`ev1`..`ev5`).

**LLM.** DeepSeek em todas as chamadas (54 chamadas em 37 turnos, `llm_providers: {deepseek: 54}`). Zero geração de retrato (só `creature_portrait.offer_view`).

## Tabela item → resultado

| Item | Resultado | Evidência |
|---|---|---|
| 1 Morte do herói (346) | **ok**. Médico de Campo com Vitalidade 1 contra 2 goblins: na 2ª rodada `combat.phase=ended`, `outcome=death`, `death_pending=true`, `entered_terminal=true`, `killer: "Goblin"` (nome, não id). A prosa fecha com a Roda do Abismo ("Voltar ao último respiro seguro, ou aceitar o fim aqui?"). `POST /game/death continue`: Vitalidade 16, combate encerrado, cena do início da sessão. `accept` (2º jogo): `game_over=true`, `dead=true`. 0 ids crus nas mensagens (regex de prefixos e `palavra_palavra`). Observações em Achados 1 e 2. | `ev1-morte.json` |
| 2 "Vasculho o corpo" depois de vencer (346 R20) | **ok**. Vitória com 2 Bisturis (+8 ouro, `loot_claimed=true`); "Vasculho o corpo" → `router.decision route=loot source=classify`, evento `loot.corpse_already_looted`, texto fixo "Você revira o corpo de novo; o que havia de valor já está com você.", `gold_delta 0`, `source none` (sem rerrolar a tabela). | `ev2-vasculho.json` |
| 3 `trade_prose_rejected` (367/387) | **ok, mas só provocado**. Naturalmente: 0 rejeições em 6 compras reais de Carta (seed 15) — o DeepSeek obedeceu ao contexto de ouro (R15) e citou só antes/preço/depois. Provocado em processo (`agents.loot._narrate` com o `gold_check` real, DeepSeek real, instrução de estilo contraditória ao contexto): "últimas moedas" (com sobra 30) e número inventado ("120 moedas") → ambos rejeitados, evento `loot.trade_prose_rejected` (warning), retorno = fallback "Forja dos Clãs fecha o negócio sem cerimônia."; no turno real o jogador ainda vê a linha `[SISTEMA] +1 Carta … Ouro −50 (total 30)`. `place_as_actor` (Skallgard como sujeito): o modelo não obedeceu à instrução, sem rejeição (ramo `reason=place_as_actor` não exercido por LLM real). | `ev3-trade-prose.json` |
| 4 Taxa real de `replace` (355) | **0 em 8 combates**. 5 `13 reacao` + 3 `13 leitura` jogados até o fim por `POST /game/action/stream` (token stream `on`): 0 eventos `sse.token_replace`, 0 `replace:true` nos chunks, `turn.token_replace=false`. Rodadas intermediárias: 0 chamadas LLM; cada desfecho: 2 (narrador + arquivista). Confirma que, com o Baralho `on`, a rodada não streama tokens e o desfecho usa `stream=False`; o número sintético (0/30) deixa de ser o único. | `ev4-replace.json` |
| 5 Import de imagem de criatura (347) | **ok**. `import_bestiary_art.py` sobre PNGs sintéticos: 3 importados (criatura do bestiário, família, id `bst_` do pool); reimport = "sem mudanca: 3"; criatura fora do bestiário, família inválida e troca sem `--force` falham com mensagem clara e não tocam o catálogo; `validate_content.py` 0 ERRO; `tests/test_import_bestiary_art.py` 6 passed. Sem custo, sem rede. O script não tem `--dry-run` (grava na cópia); `retire_creature_portrait.py --dry-run` não rodado (exige banco). | `ev5-import.txt` |
| 6 Chefe `unico` entre duas contas (347/352) | **só staging**. O `unico:{game}` vive em `creature_portraits` (Postgres com RLS/visibilidade por `origin_game_id`, SPEC-352 §4); o perfil `legacy` não tem contas nem essa tabela, e duas contas locais exigiriam o stack Supabase local (`start_local_api.py`, `supabase status`), fora do orçamento de RAM (1,0–1,6 GB livres na máquina durante a sessão). Não tentado. | n/a |

## Custo

54 chamadas DeepSeek em 37 turnos da API (US$ 0,0206 estimado pelo log) + 3 chamadas SMART do item 3 em processo (~US$ 0,003): **~US$ 0,024**, abaixo do teto de US$ 0,10. 0 retrato pago.

## Achados

1. **P3: depois de `accept` a mensagem continua sendo a pergunta de escolha.** Com `game_over=true` o texto devolvido ainda diz "Voltar ao último respiro seguro, ou aceitar o fim aqui?" (é a mensagem da queda, reaproveitada). Causa provável: `services/checkpoints.py:143-146` (`resolve_death_choice`, ramo `accept`) só liga `game_over` e não troca a mensagem. Se a UI mostra o memorial por `game_over`, é só texto residual na resposta/histórico.
2. **Observação (provável artefato da seed): o `continue` restaura a abertura da sessão com o pedido do jogador dentro da prosa** ("Você descreva o cenário ao meu redor. Sou um Médico de Campo de nível 1."). O save foi criado por `seed_save` com MockLLM; em jogo real a abertura vem do LLM. Conferir no staging antes de tratar como bug.
3. **P3: o texto de vitória nomeia só o primeiro golpe final.** Dois goblins morrendo na mesma rodada deram "Seu golpe termina o serviço: Goblin 1 tomba." (o último a cair foi o Goblin 2). Causa provável: `services/round_log.py:834-851` (`final_blow_sentence`) devolve no primeiro `final_blow` do laço.
4. **P3 (roteiro, não produto): a frase do roteiro 15 `vg_ouro` ("Compro a <Carta> com minhas últimas moedas", SPEC-387 ~l.475) não compra.** A gramática fechada (`agents/loot.py:~585-603`, `tail` só admite "por favor|agora|então") responde só o preço e pede confirmação ("nada foi cobrado"). Além disso a prateleira é por jogo: o nome da Carta tem que ser lido do próprio save (3 de 5 tentativas com o nome de outro jogo deram "O mercador não tem 'X' à venda"). Para provar o V-G ao vivo use "Compro a <Carta>." com o nome do jogo.
5. **Observação (LLM, baixa gravidade): a prosa de morte descreve ferimentos que não batem com o registro** (ex.: "perna grave" quando o registro diz "ferimento leve na perna"). Não há guarda de conteúdo nessa narração; é deriva do modelo no resumo do desfecho.
6. **Observação: `bst_inexistente_zz.png` foi importado sem checar o pool.** `scripts/import_bestiary_art.py:60-70` só valida o formato `bst_[a-z0-9_-]+`; um id de pool digitado errado vira entrada de catálogo órfã. Provavelmente intencional (pool é dinâmico), mas vale um aviso no script.

## Não verificado

- Item 6 inteiro (só staging, com duas contas).
- Ramo `reason=place_as_actor` do `trade_prose_rejected` com LLM real.
- `retire_creature_portrait.py --dry-run` (sem banco local).
- Morte e `Vasculho o corpo` no staging (serverless); aqui só local `legacy`.
