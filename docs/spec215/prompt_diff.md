### Testemunha (observed_by) — `off`

```text
<ESTADO_ATUAL_DO_MUNDO>
Quem controla Nova Arcádia agora: Lorde Protetor Valerius.
[turno 4] npc_halveth_fixture foi morto (por: player).
npc_halveth_fixture: morto.
</ESTADO_ATUAL_DO_MUNDO>
--- memory_block ---
[RESUMO NARRATIVO | speculative] O herói matou Valerius no porto e fugiu ferido.
[CONFIRMADO | player_observation] sessão do jogador
[RELATADO | npc_claim] memória do guarda
[RELATO | player_observation | fonte turn:4 | turno 4] O herói viu Valerius cair.
```

### Testemunha (observed_by) — `on`

```text
<ESTADO_ATUAL_DO_MUNDO>
[VIU] [turno 4] npc_halveth_fixture foi morto (por: player).
Quem controla Nova Arcádia agora: Lorde Protetor Valerius.
npc_halveth_fixture: morto.
</ESTADO_ATUAL_DO_MUNDO>
--- memory_block ---
[RELATADO | npc_claim] memória do guarda
```

### NPC sem relação (distante) — `off`

```text
<ESTADO_ATUAL_DO_MUNDO>
Quem controla Nova Arcádia agora: Lorde Protetor Valerius.
[turno 4] npc_halveth_fixture foi morto (por: player).
npc_halveth_fixture: morto.
</ESTADO_ATUAL_DO_MUNDO>
--- memory_block ---
[RESUMO NARRATIVO | speculative] O herói matou Valerius no porto e fugiu ferido.
[CONFIRMADO | player_observation] sessão do jogador
[RELATADO | npc_claim] memória do guarda
[RELATO | player_observation | fonte turn:4 | turno 4] O herói viu Valerius cair.
```

### NPC sem relação (distante) — `on`

```text
<ESTADO_ATUAL_DO_MUNDO>
Quem controla Nova Arcádia agora: Lorde Protetor Valerius.
</ESTADO_ATUAL_DO_MUNDO>
--- memory_block ---
[RELATADO | npc_claim] memória do guarda
```
