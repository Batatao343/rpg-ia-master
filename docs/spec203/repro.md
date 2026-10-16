# SPEC-203 — Etapa 0: reprodução do bug de identidade do encontro

Executado no HEAD `50d4620` (pré-mudança), offline (LLM stubado no módulo
`agents.combat`; bestiário curado `data/bestiary.json`). Teste:
`tests/test_encounter_identity_repro.py`. Resultado no HEAD: **7 falhas**
(H1, H2, H2b, H3, H4, H4b, H5b); H5 (estado), H6 e H7 verdes.

| Hipótese | Seed | Reproduziu? | Traço observado no HEAD |
|---|---|---|---|
| H1 scanner lê fauna da prosa | 11 | **sim** | dica `Bandido`, prosa com corvos → elenco `{mon_corvo_gelo}`; o bandido some. O scanner é chamado mesmo com dica que casa exatamente com `enemy_bandido`. |
| H2 orçamento corta bandido por variedade | — | **sim** | 3× `enemy_bandido` + 1 corvo, nível 1, perigo 2 (budget 5) → mantém `[enemy_bandido, mon_corvo_gelo]`; a regra de variedade troca o 2º bandido (alvo) por fauna. |
| H2b reforço regional sem evento | 5 | **sim** | `fill_encounter` adiciona criatura regional (`Cervo Afogado`) com só uma linha de flavor; não há evento de composição (não existia manifesto). |
| H3 librarian mapeia outra espécie | — | **sim** | `find_existing_entity("Bandido") → mon_corvo_gelo` → elenco `['Corvo de Gelo Negro', ...]`; nada valida o nome devolvido contra o pedido. |
| H4 `enemy_id` sistêmico descartado | 3 | **sim** | encontro sistêmico com `enemy_id=enemy_bandido`; scanner nomeia `Lobo Sombrio` → elenco `{enemy_lobo_sombrio, mon_cervo_afogado}`. `storyteller` só repassava `combat_target=enc["hint"]`. Com o MockLLM padrão o scanner lê só a última fala humana, então o encontro sistêmico vira uma criatura aleatória. |
| H5 prosa renomeia sem mudar estado | 7 | **só narrativo** | narração "O corvo mergulha…" com elenco de bandidos: estado intacto (ids/nomes coerentes). H5b (guard que detecta a troca) não existia. |
| H6 reload preserva elenco | — | não | ids/nomes `enemy_bandido_N` estáveis no round-trip `_state_to_save_data → _raw_to_state`. |
| H7 inimigo ativo não causa dano | 1234 | não | bandido ativo declara ação em toda rodada (`initiative` inclui `enemy`) e causa dano (Vitalidade 16→6→0). Sem bug de ação descartada; nada encaminhado à spec de pressão tática a partir deste caso. |

**Conclusão:** H1–H4 reproduzem bugs de **estado** (spawn/orçamento/dedupe); H5 é deriva
só narrativa. Como houve reprodução, D-A não se aplica: R3/R4 foram implementados.
Após a correção, os 10 testes do arquivo passam sem `xfail`.
