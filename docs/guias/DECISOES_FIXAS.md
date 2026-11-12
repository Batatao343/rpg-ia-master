# Decisões fixas

Itens que auditorias e dono já decidiram. Antes de reportar achado sobre um deles, leia a linha:
só reabre com fato novo (arquivo:linha ou commit posterior à fonte) ou quando o gatilho disparou.
Achado que contradiz uma linha cita o `D-NN`. `ID` nunca é reaproveitado; teto de 60 linhas e 12 KB
(o excedente vai para `docs/historico/DECISOES_FIXAS-ate-AAAA-MM-DD.md`, nunca é apagado). Gate: `tests/test_decisoes_fixas.py`.

| ID | Item | Decisão | Fonte | Gatilho de revisão |
|---|---|---|---|---|
| D-01 | `persistence._MIGRATIONS` | manter | docs/auditorias/ponytail-poda-2026-10-18.md:69 | dono decide não carregar saves anteriores a uma versão |
| D-02 | `wallet_spend_scope` (`infrastructure/wallet.py`) | manter: gancho reserve→settle | docs/auditorias/ponytail-poda-2026-10-18.md:70-71; specs/SPEC-405-poda-simbolos-sem-chamador.md:63 | SPEC-185 fecha reserve→settle sem usar o gancho |
| D-03 | adapters `portable`/OIDC/S3 | manter (perfil da SPEC-181) | docs/auditorias/ponytail-poda-2026-10-18.md:72-73 | decisão de produto de abandonar o perfil portable |
| D-04 | `services/gameplay_oracles.py` | manter: contrato da SPEC-212 | docs/auditorias/ponytail-poda-2026-10-18.md:74; docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:258; specs/SPEC-405-poda-simbolos-sem-chamador.md:64 | SPEC-212 aposenta o contrato |
| D-05 | fakes e seams em módulo de produto (`FakeFinopsReader`, `MemorySwitchStore`, `MemoryDailyQuota`, `reload_cards`, `reset_text_cap_cache`, `set_switches`) | manter | docs/auditorias/ponytail-poda-2026-10-18.md:75-76; specs/SPEC-405-poda-simbolos-sem-chamador.md:65 | nenhum uso em `tests/` |
| D-06 | símbolos usados só no próprio arquivo (`_native_tracer`, `image_defer_max_age`, `PurchaseStore`, `accept_test_purchases`, `_legacy_shape`, `ProjectionRetry`, `ImageGenerationRefused`) | manter | docs/auditorias/ponytail-poda-2026-10-18.md:77-79 | o uso interno some |
| D-07 | `tests/test_mvp.py`, `test_fase0.py`, `test_fase25.py` | manter: única cobertura | docs/auditorias/ponytail-poda-2026-10-18.md:80-81 | cobertura equivalente provada em outro arquivo |
| D-08 | `tests/test_cutover_audit.py` | manter até a SPEC-272 apagar tudo | docs/auditorias/ponytail-poda-2026-10-18.md:82 | SPEC-272 `done` com a lista vazia |
| D-09 | régua `evals/` e `evals/experiments/*` | protegida; arquivar só por proposta do papel de autoria | docs/auditorias/ponytail-poda-2026-10-18.md:83-85 | proposta do papel de autoria de eval |
| D-10 | índices FAISS versionados | manter: lidos em runtime na Vercel | docs/auditorias/ponytail-poda-2026-10-18.md:86 | runtime deixa de ler do repo |
| D-11 | `handoffs/` | manter: evidência de revisão linkada | docs/auditorias/ponytail-poda-2026-10-18.md:89 | nenhum link restante (`scripts/check_md_links.py`) |
| D-12 | binários: evidências `docs/spec*/evidence` e mídia de `docs/` | manter: linkados ou insumo do Remotion; o histórico guarda | docs/auditorias/ponytail-poda-2026-10-18.md:90; docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:261 | o README que linka sai; decisão do dono |
| D-13 | `langchain-community` | trocar só por spec com teste de leitura dos índices | docs/auditorias/ponytail-poda-2026-10-18.md:91-92 | spec de migração do FAISS aprovada |
| D-14 | `scripts/staging/*` | manter: runbooks da SPEC-197 | docs/auditorias/ponytail-poda-2026-10-18.md:93 | runbook aposentado na SPEC-197 |
| D-15 | `CLASS_THEMES`/`class_themes.json` | manter: usado pelo prólogo | docs/auditorias/ponytail-poda-2026-10-18.md:94 | `services/prologue.py` deixa de usar |
| D-16 | rotas FastAPI (inclui `/auth/logout`, canônica da SPEC-220) | manter: todas com chamador | docs/auditorias/ponytail-poda-2026-10-18.md:95; docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:277-278 | rota sem chamador em `web/src`, `scripts`, CI e bundle Android |
| D-17 | `set_postura`, `consume_postura_on_attack`, `clear_sustained_postura`, `alert_party`, `suggested_virtue_cards` | manter (SPEC-272 "(c) manter") | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:257 | dono reverte na SPEC-272 |
| D-18 | `services/creature_gen_eval.py` | não mover: código de eval | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:259 | proposta do papel de autoria de eval |
| D-19 | `currentPurchaseAdapter`/`WebStripeAdapter` | manter: gancho da SPEC-198 | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:260 | SPEC-198 encerrada sem billing |
| D-20 | leitores de `.env` duplicados | não unificar (`python-dotenv` já) | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:262 | ganho medido > 5 linhas |
| D-21 | imports locais de `api.py` | não subir: cold start e ciclos | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:263 | medição de cold start mostra que não importa |
| D-22 | migrar tudo para `services/file_cache.py` | não: 19 seams, semântica mtime ≠ `lru_cache` | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:264 | decisão do dono |
| D-23 | tabela única de campos em `persistence.py` | não: mexe no round-trip de save | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:265 | spec de save com teste de round-trip |
| D-24 | `motion` → CSS | não trocar | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:266 | dep abandonada ou com CVE |
| D-25 | renomear `tests/test_specNNN_*` | não: só regra para arquivo novo | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:267 | decisão do dono |
| D-26 | fundir `npm ci/build` entre workflows | não fundir | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:268 | decisão do dono |
| D-27 | reforços, duas políticas de facção, `_side_of` "hero"/"heroes" | não é duplicação nem bug | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:279-283 | SPEC-384 D3 / SPEC-377 D4 revistas |
| D-28 | `_fold` restantes | contrato da SPEC-378: só migra equivalência provada | specs/SPEC-405-poda-simbolos-sem-chamador.md:70; docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:285 | linha nova verde em `tests/test_spec378_text_fold.py` |
| D-29 | TypedDicts de forma persistida em `state.py` (`NpcFavors`, `CalendarParams`) | manter: documentam a forma do save | specs/SPEC-405-poda-simbolos-sem-chamador.md:66 | a forma persistida muda |
| D-30 | flags do D1 da SPEC-384 | 7 aposentadorias só após smoke real por flag no staging; 3 reclassificadas; `WORLD_ENGINE` e `OPENING_THREAD` adiadas | specs/SPEC-384-poda-decisoes-dono-flags-perfis.md:3; specs/SPEC-384-poda-decisoes-dono-flags-perfis.md:29 | smoke real por flag registrado na SPEC-384 |
| D-31 | contrato front↔back (SPEC-385) | adiado: sem bug de contrato real até hoje | docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md:318; specs/SPEC-385-contrato-api-tipos.md:3 | 1º bug de contrato front↔back visto em staging (gatilho da SPEC-385) |
| D-32 | mod guard do Claude Code | não: hooks clássicos cobrem e valem em `claude -p` | docs/auditorias/auditoria-workspace-2026-11-03.md:215 | decisão do dono |
| D-33 | skills `taste`/`impeccable` | manter (escolha do dono) | docs/auditorias/auditoria-workspace-2026-11-03.md:214 | decisão do dono |
| D-34 | lock entre sessões | não: o preflight da SPEC-415 resolve | docs/auditorias/auditoria-workspace-2026-11-11.md:47 | preflight deixa passar uma colisão |
| D-35 | web no executor | não: injeção de prompt | docs/auditorias/auditoria-workspace-2026-11-11.md:47 | decisão do dono |
| D-36 | Postgres/Docker local nesta máquina | não instalar (auditoria 11/11, "Não fazer") | docs/auditorias/auditoria-workspace-2026-11-11.md:47 | troca de máquina ou decisão do dono |
| D-37 | `DTZ` global no ruff | não: catraca AST de teste (SPEC-416) | docs/auditorias/auditoria-workspace-2026-11-11.md:47 | decisão do dono |
| D-38 | hook que bloqueie todo `\| tail` | não | docs/auditorias/auditoria-workspace-2026-11-11.md:47 | decisão do dono |
