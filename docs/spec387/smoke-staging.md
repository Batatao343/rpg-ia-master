# Smoke staging: SPEC-387 §6 itens 1–4 (LLM real)

Feito em 04/11/2026, das 04:25 às 04:52 UTC, pelo coordenador.

**Staging.** `hosted-supabase`, `/health` com `git_sha` `bed84ac1` (387 na `main`), preset `staging_flags.json` com
cartas `on`. Migrations 34/34 em sincronia. `post_deploy_smoke` e `e2e_session` passaram. O `vercel_smoke` deu `health` falso
só no 1º request, por erro de transporte da rede local: as 10 requisições seguintes e o `curl` responderam 200.

**Execução.** 3 execuções. Na 1ª o navegador abriu o jogo errado (3 partidas com o mesmo herói). Na 2ª houve um reset de
conexão da rede local. A 3ª foi completa.
- 9 aberturas de combate com LLM real.
- 1 retrato pago.
- Contas e jogos apagados ao fim de cada execução (`users_exist_after: [false]`).
- `image_generation` desligado no fim, conferido com `list`.

**Evidência.** Fica no scratchpad da sessão do coordenador, `smoke6stg/`:
- `s7/run.log`
- `s7/done-loads.txt`
- `s7/done-gen.txt`
- `out7/*.png`
- `s7run1/` e `s7run2/`
- `vlogs/all.json` (logs da Vercel, 30 min)

| Item | Resultado | Evidência |
|---|---|---|
| 1 S6-1 (R1–R3) | **ok**. A Carta de cena "Profanar (Altar de Lodo)" saiu com nome e custo 1 nas 6 leituras da API (clientes novos) e nos 6 carregamentos do navegador (1440, 390, 1440, 1280, 1440, 390), com 0 id `CENA_` visível. A jogada com alvo deu 200 e gerou a linha `jogada` no registro, sem 409. Na execução 1, "Derrubar (Totem de Junco Trançado)" teve o mesmo resultado | `item1_2_api_samples`, `item1_play`, `done-loads.txt` |
| 2 S6-2 (R5–R7) | **achado (não corrigido ao vivo)**. A oferta do Necromante Renegado apareceu em 4 de 6 carregamentos do navegador e em 0 de 6 leituras da API. Na execução 1, a oferta da Onça Vazada apareceu em 5 de 6 carregamentos no navegador e em 6 de 6 na API. Os logs da Vercel da janela da execução 3 não têm `creature_portrait.offer_omitted` nem `kill_switch_load_failed`: a oferta some por um caminho silencioso. Ver S7-1 | `done-loads.txt`, `item1_2_api_samples`, `vlogs/all.json` |
| 3 S6-3 (R8, R9) | **ok**. 100 ms depois de "Gerar" a 1440, o retrato já estava `gerando` com o selo "Gerando retrato…" e o botão tinha saído da tela. Houve 1 `/art/quote` e 1 `/art/confirm`. O débito foi de 8 milli, para uma cotação de 15 (pico reservado 15, 0 no fim) | `done-gen.txt`, `portrait_ready`, `out7/gen-1440-100ms.png` |
| 4 S6-4 (R10) | **ok**. 9 aberturas (6 no Pântano da Melancolia, 3 na Floresta dos Sussurros) com 0 `fallback_criatura_hostil`. Os inimigos vieram do bestiário da região: Podador do Ciclo, Tritão de Sobra, Cervo Afogado, Olhos em Volta + Necromante Renegado, Onça Vazada, Ent Dormindo e Afogado de Aethelgard | `item4` nos 3 `run.log` |
| 16 (staging) | **ok**. Varredura do `/game/history`: 0 nome do herói, 0 id, 0 ": … terminou" | `history` |

## Achados

- **S7-1 (P2): a oferta de retrato ainda some sem log.** Nenhum dos 4 caminhos que a 387 instrumentou disparou
  (`switches_unreadable`, `image_gate_failed`, `price_peek_failed`, `registry_read_failed`). Restam os caminhos silenciosos
  de `api._image_effect_open` e `_enemy_portrait`:
  - `switches.is_enabled(IMAGE)` falso com snapshot carregado. `KillSwitches.snapshot` mantém o último snapshot bom quando a
    releitura falha (`services/kill_switches.py`), então uma instância que leu `off` antes do `on` pode ficar presa.
  - `PricingUnavailable`, que retorna `False` sem log.
  - O cache de 60 s de um `value` válido calculado com o kill switch ainda desligado.
  - `_creature_art_live()` ou `_art.mode()` diferente entre instâncias.

  Pedido: logar `offer_omitted` em TODO caminho que zera a oferta (com a causa), medir de novo e corrigir a causa real. A
  diferença entre o navegador (4 de 6) e o cliente da API (0 de 6) também precisa de explicação.
