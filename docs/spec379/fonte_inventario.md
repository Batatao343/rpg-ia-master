# SPEC-379 R6.1 — inventário de testes que leem código-fonte

> Gerado em 03/11 por varredura de `tests/*.py` (Grep de `getsource`, `ast.parse(`, `read_text(` com alvo `.py/.tsx/.css/.html/.mjs`, `api.py`, `App.tsx`, `SRC`). A decisão por linha vem da tabela preliminar da §3.6 da spec quando existe; o resto é **(c) provisório** (guarda de padrão/segurança), a confirmar função a função na Etapa 5. **Limite honesto:** a varredura acha leituras com literal de caminho ou `getsource`; leituras via variável indireta (`src = _read(...)`) entram só quando a linha casa o filtro. Falsos positivos (arquivos escritos em repo temporário, strings) estão marcados 'não se aplica'.

Leitor fora do pytest: `web/tests/design.test.mjs:91,105-112` (permissão por nome de quem importa `motion` = (c) com aviso à 383; regex de `<MotionConfig reducedMotion="user"` em `App.tsx` = (c) reancorado em `web/src/**`, trava 383).

| arquivo:linha | função | lê (trecho) | decisão | nota |
|---|---|---|---|---|
| test_abuse_logging.py:185 | `test_every_429_records_block` | `tree = ast.parse((ROOT / "api.py").read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_abuse_policy.py:158 | `test_account_security_and_captcha_use_client_ip` | `assert "remote_ip=_client_ip(request)" in Path("api.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_abuse_policy.py:386 | `test_stream_and_post_share_the_single_per_turn_check` | `tree = ast.parse(Path("api.py").read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_abuse_policy.py:408 | `test_quota_error_reaches_sse_payload_with_retry` | `assert "retry_after_seconds=exc.retry_after_seconds" in Path("api.py").read_text(` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_api_fuzz_harness.py:41 | `test_intentional_503_allowlist_matches_source` | `source = (ROOT / "api.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_audit_local_gate_contract.py:13 | `test_gate_lists_security_files` | `source = (ROOT / "scripts" / "audit_local_gate.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_bug_api_pending_erros.py:144 | `test_backstory_null` | `src = inspect.getsource(api)` | (a) | POST /game/new backstory=None sem 'None' no resumo; trava 381 |
| test_bug_memoria_resiliencia.py:415 | `test_configured_profile_is_shared_by_every_adapter` | `src = inspect.getsource(postgres_turns)` | (a) ou (c) | depende de seam com pool fake; trava 378 |
| test_db_logging.py:144 | `_raise_sites` | `tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_db_logging.py:184 | `test_postgres_modules_do_not_log_sql` | `tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_dynamic_art_jobs.py:212 | `test_aprovado_exige_status_ready_e_sem_retrato_segue_texto` | `sql = inspect.getsource(DynamicArtRepository.approved_portrait_key)` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_error_envelope.py:27 | `_http_exception_calls` | `tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_eval_frontend.py:118 | `test_frontend_suite_has_every_hard_gate_and_no_fixed_sleep` | `source = (WEB / "e2e/fixtures.ts").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_frontend_accessibility_contracts.py:5 | `test_scene_art_nao_rotula_div_sem_role_e_imagem_tem_alt` | `source = Path("web/src/components/SceneArtwork.tsx").read_text(encoding="utf-8")` | (b) condicionado | só depois do e2e visual-cue afirmar o `alt` |
| test_frontend_auth_bootstrap.py:5 | `test_frontend_nao_chama_saves_protegidos_antes_de_confirmar_auth` | `source = Path("web/src/App.tsx").read_text(encoding="utf-8")` | (a) | e2e novo `auth-bootstrap` (zero /game/saves antes do login); trava 383 |
| test_frontend_visual_contracts.py:25 | `test_home_header_buttons_do_not_overlap` | `css = (Path(__file__).resolve().parents[1] / "web/src/styles.css").read_text(encoding="utf` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_frontend_visual_contracts.py:52 | `test_portraits_are_uncropped_and_stay_inside_cards` | `css = (Path(__file__).resolve().parents[1] / "web/src/styles.css").read_text(encoding="utf` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_no_print_in_production.py:53 | `test_production_code_has_no_print_calls` | `tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_no_print_in_production.py:61 | `test_guard_detects_print_outside_main` | `tree = ast.parse("print('x')\nif __name__ == '__main__':\n    print('ok')\n")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_postgres_claim_idempotency.py:5 | `test_claim_insert_handles_every_unique_arbiter_before_validating_existing` | `source = Path("infrastructure/postgres_turns.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_rls_runtime_config.py:213 | `_direct_connection_calls` | `tree = ast.parse(path.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_rls_runtime_config.py:243 | `test_request_side_job_queue_only_enqueues_with_the_request_role` | `source = (ROOT / "infrastructure/postgres_jobs.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_rls_runtime_config.py:250 | `test_rate_limiter_is_system_only` | `source = (ROOT / "infrastructure/postgres_turns.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_rls_runtime_config.py:257 | `test_api_request_queries_only_use_granted_tables` | `source = (ROOT / "api.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_session_hardening.py:212 | `test_auth_error_codes_closed_set` | `tree = ast.parse(path.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec192_vercel_packaging.py:79 | `test_hosted_profile_never_writes_saves_or_faiss` | `src = (ROOT / "persistence.py").read_text(encoding="utf-8")` | (b) [H] | só as contagens de RPG_RUNTIME_PROFILE; trava 378 |
| test_spec196_finops.py:669 | `test_f3_reader_sql_covers_195_and_legacy_entries` | `sql = inspect.getsource(PostgresFinopsReader.purchases)` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec198_rename_package.py:60 | `test_dry_run_changes_nothing` | `assert OLD in (repo / "web/capacitor.config.ts").read_text()` | não se aplica | não lê o fonte real |
| test_spec222_transparency.py:23 | `test_index_html_has_no_external_font_hosts` | `html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec222_transparency.py:30 | `test_fonts_are_self_hosted_and_referenced` | `css = (ROOT / "web" / "src" / "fonts.css").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec279_usage_retention.py:52 | `test_readers_keep_events_whose_operation_was_deleted` | `src = re.sub(r"\s+", " ", inspect.getsource(fn))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec297_review_fixes.py:186 | `test_player_inputs_are_last_three_human_messages` | `src = inspect.getsource(st.storyteller_node)` | (a) | storyteller com 5 HumanMessage, player_inputs = 3 últimas; trava 382 |
| test_spec299_prisoner_api.py:78 | `test_no_graph_caller` | `if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec302_tick.py:91 | `test_no_global_random_in_world_modules` | `tree = ast.parse(path.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec303_calendar.py:44 | `test_no_global_random_in_calendar_module` | `tree = ast.parse(_SRC.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec303_calendar.py:130 | `test_calendar_independent_of_player` | `tree = ast.parse(_SRC.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec303_passes.py:84 | `test_crossing_note_is_deterministic_fact` | `assert "world_calendar.CROSSING_NOTE" in inspect.getsource(storyteller)` | (a) [H] | viagem pela passagem fechada; trava 382 |
| test_spec304_roster.py:183 | `test_no_global_random_in_npc_modules` | `tree = ast.parse((root / name).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec305_perception.py:159 | `test_only_world_quests_module_builds_world_kind` | `tree = ast.parse(path.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec305_sources.py:146 | `test_no_global_random_in_world_quests` | `tree = ast.parse((ROOT / "services" / "world_quests.py").read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec307_calendar.py:80 | `test_date_at_pure_deterministic_and_no_global_random` | `tree = ast.parse(_SRC.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec307_calendar.py:208 | `test_calendar_independent_of_player` | `tree = ast.parse(_SRC.read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec312_birth.py:171 | `test_no_global_random_in_rumors` | `tree = ast.parse(Path(rumors.__file__).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec312_birth.py:183 | `test_rumor_module_never_writes_event_log_projection_memory_quests` | `tree = ast.parse(Path(rumors.__file__).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec313_catalog.py:103 | `test_no_global_random_in_lore_quests` | `tree = ast.parse((ROOT / "services" / "lore_quests.py").read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec313_catalog.py:116 | `test_lore_module_builds_no_quest_dict_and_calls_no_llm` | `src = (ROOT / "services" / "lore_quests.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec315_truth.py:143 | `test_no_global_random` | `tree = ast.parse(Path(ra.__file__).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec347_creature_art.py:176 | `test_no_image_provider_import_in_creature_art` | `tree = ast.parse(Path(ca.__file__).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec347_creature_art.py:184 | `test_family_icons_only_use_existing_web_icons` | `icons = Path("web/src/design/icons.tsx").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec350_api.py:171 | `test_no_llm_no_io_in_module` | `tree = ast.parse(f.read())` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec352_creature_portraits.py:462 | `test_s3_shared_store_copy_and_sign_path` | `runtime_src = (ROOT / "infrastructure/runtime.py").read_text(encoding="utf-8")` | (a)/(c) | linha 462: (a) [H] identidade de blob store; 409/413: (c) |
| test_spec361_integracao.py:324 | `test_drenagem_fora_do_lock_do_jogo` | `assert "creature_gen" not in inspect.getsource(api._execute_action)` | (c) | única guarda de 'nada drena sob o lock'; trava 381 |
| test_spec368_replace.py:109 | `test_deck_on_outcome_narration_never_streams` | `src = inspect.getsource(combat._narrate_outcome)` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_spec371_saber.py:214 | `test_simulacao_e_previa_nao_absorvem` | `src = inspect.getsource(combat)` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_vercel_config.py:45 | `test_codex_markdown_is_read_at_runtime` | `source = (ROOT / "services" / "discovery.py").read_text(encoding="utf-8")` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |
| test_visual_assets.py:209 | `test_frontend_contract_contains_visual_flow` | `app = (root / "App.tsx").read_text(encoding="utf-8")` | (a) | e2e novo `visual-cue`; trava 383 |
| test_world_rejection_logs.py:219 | `_rejection_messages` | `tree = ast.parse(Path(path).read_text(encoding="utf-8"))` | (c) provisório | guarda de padrão; confirmar na Etapa 5 |

## Estado de execução (R6)

- **Etapas 4 e 5 (trocas (a) e remoções (b)) NÃO executadas nesta rodada.** Exigem e2e Playwright novos (`web/e2e/auth-bootstrap.spec.ts`, `web/e2e/visual-cue.spec.ts`), prova de quebra local e coordenação com a 383; ficam como pendência (hand-back).
- Nenhum teste foi apagado: a regra R6.5 só permite apagar depois que o substituto passar e a quebra for provada.
