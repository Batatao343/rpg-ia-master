# SPEC-372 — smoke real §6 (04/11/2026)

Em processo (sem uvicorn), `app.invoke` real, DeepSeek primário (`deepseek-v4-flash`; houve timeouts de transporte e queda para `groq/openai/gpt-oss-120b` em alguns nós), as cinco flags `on` (`RPG_FAUNA`, `RPG_FAUNA_SINAIS`, `RPG_PLOT_THREADS`, `RPG_FAUNA_TRAMAS`, `RPG_WORLD_ENGINE`). Save descartável (`smoke372-…`, nível 3, `na_anel_lama`, período Noite, perigo forçado 2). Script fora do repo; o `.env` foi copiado só durante a rodada e apagado. Criatura ligada: `mon_rosario_de_vertebras` (`tr_na_corpos_marcados`, `desde: tocada`).

## 1. Trama dormente: a criatura não existe (motor real, sem LLM)

60 dias de `day_hook` com `plot_stage = dormente`: **0** presença de `mon_rosario_de_vertebras` (12 presenças de outras criaturas na região, o teto). Turnos 1–2 do jogo real (LLM): estágio `dormente`, 0 presença da criatura, nenhuma pista dela.

## 2. O jogador toca a trama: a criatura passa a nascer nos locais da trama

Com o NPC âncora (`npc_tr_pio_ferrugem`) conhecido (`known_by_player`), `plot_stage = tocada`. O mesmo `day_hook` fez a criatura nascer no dia 24: `origem: dia`, `trama_id = tr_na_corpos_marcados`, `locais = [na_anel_lama]` (⊆ `locations` da trama). Verificado: `locais_dentro_da_trama = true`, `trama_id_ok = true`.

Limite: a virada de dia exige muitos descansos, então a presença achada offline foi **transplantada** para o save ao vivo (nascimento real do motor, não injeção inventada) antes dos turnos 3–6. Nos turnos 3–6 (LLM): estágio `tocada`; turno 4 a narração traz o sinal `rastro` da ficha ("faixa de lodo … em ondas regulares"); turno 5 traz um chiado/ranger de som sem nome; turno 6 ("sigo o rastro") abre o combate e a presença vira `cacada`.

## 3. Vazamento

- Frases de segredo (`leak_phrases` de `corpos`/`praga` e assinaturas): **0** em todos os turnos.
- Nome da criatura: só no turno 6, depois de o jogador escolher caçar e o combate abrir (mesmo comportamento do smoke da 370). Turnos 1–5: 0.
- Token de núcleo: o turno 5 contém "Corva" (Mãe Corva, `core` da trama), que não vem dos sinais da criatura (E22 garante 0 token de núcleo neles); é o morador do Anel de Lama que o narrador já citava pelo cenário (SPEC-350), não segredo.
- Observação: o wrapper de captura do prompt não interceptou a chamada do narrador (0 prompts capturados), então `<SINAIS_NA_CENA>` foi confirmado só pela narração (sinal `rastro` no turno 4), não pelo texto do prompt.

## Custo

Uma chamada de narração por turno (mais as do roteador/combate no turno 6); nenhuma chamada originada em `services/fauna*.py` (a 372 não tem chamada LLM).
