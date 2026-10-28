# Eventos de log

> Gerado por `scripts/gen_event_catalog.py` a partir do codigo. Nao edite: rode `uv run python scripts/gen_event_catalog.py`.

Toda linha e JSON em stdout com `event` (`area.evento`), `level`, `logger`, `ts`, `instance_ref` e, quando houver, `request_id`/`game_ref`/`action_ref`/`owner_ref`. Campos abaixo sao os conhecidos por evento (podem variar por chamada).

| evento | campos |
|---|---|
| `abuse.blocked` | `cls`, `ip_ref`, `limit`, `owner_ref`, `retry_after_s`, `scope` |
| `abuse.limiter_unavailable` | `error_type`, `site` |
| `account.delete.finish_failed` | `error_type`, `owner_ref`, `request_id` |
| `ambient.fallback` | — |
| `api.audit_trace_not_written` | `error` |
| `api.character_create` | — |
| `api.checkpoint_deferred` | — |
| `api.new_game_failed` | `error` |
| `api.turn_failed` | `error`, `stack` |
| `archivist.both_paths_failed` | — |
| `archivist.facts_extracted` | `count` |
| `archivist.fallback` | — |
| `archivist.fallback_text_failed` | `error` |
| `archivist.lean_shadow` | `would_skip` |
| `archivist.node_failed` | `error` |
| `archivist.npc_memory_retry_failed` | `error` |
| `archivist.rag_persist_failed` | `error` |
| `archivist.structured_output_unexpected` | `result_type` |
| `archivist.summary_saved_text_fallback` | — |
| `archivist.vector_index_unavailable` | — |
| `art.canon_similarity` | `min_hamming`, `threshold` |
| `art.canon_similarity_failed` | `error_type` |
| `art.race_unresolved` | `subject_kind` |
| `art.reference_missing` | `reason`, `ref_kind` |
| `auth.captcha_rejected` | `op`, `reason` |
| `auth.csrf_rejected` | `method`, `origin_host`, `reason`, `route` |
| `auth.email_delivery_failed` | `flow`, `reason`, `request_id`, `status_class` |
| `auth.logout.revoke_failed` | `error_type`, `reason`, `request_id`, `stage` |
| `auth.rate_limited` | `bucket`, `key_ref`, `op`, `retry_after_s` |
| `auth.session_rejected` | `public_code`, `reason`, `route`, `source` |
| `auth.upstream` | `duration_ms`, `error_type`, `op`, `public_code`, `reason`, `upstream_status` |
| `bestiary.cache_hit` | `entity_id` |
| `bestiary.creating` | — |
| `bestiary.generation_failed` | `error` |
| `bestiary.legacy_monster_without_id` | — |
| `bestiary.pool_submit_failed` | `error` |
| `bestiary.pool_view_failed` | `error` |
| `bestiary.read_failed` | `error` |
| `blob_purge.fallback` | — |
| `campaign.beats_english_after_retry` | — |
| `campaign.fallback` | — |
| `campaign.generating_plot` | — |
| `campaign.planner_failed` | `error` |
| `campaign.replan` | `deferred`, `outcome`, `reason` |
| `campaign.world_replan_trigger` | `cause` |
| `campaign_manager.fallback` | — |
| `card_draft.fallback` | — |
| `cards.card_exhausted` | `card_id` |
| `cards.card_offered` | `card_id`, `picked`, `source` |
| `cards.card_picked` | `card_id`, `source` |
| `cards.card_played` | `card_id`, `pile` |
| `character.ai_failed` | `error` |
| `client.error` | `beacon_request_id`, `build`, `client`, `code`, `error_name`, `kind`, `request_id`, `route`, `stack`, `ts` |
| `client_latency` | `ack_ms`, `action_ref`, `first_phase_ms`, `outcome`, `state_ms`, `transport`, `ttfmc_ms`, `ttlt_ms` |
| `codex.doc_skipped` | `error` |
| `codex.indexed` | — |
| `codex.ingest_started` | `chunks` |
| `codex.no_documents` | — |
| `codex.no_embeddings` | — |
| `combat.abyss_clock_shadow` | `rnd` |
| `combat.budget_failed` | `error` |
| `combat.chase_abandon` | — |
| `combat.chase_abandon_shadow` | — |
| `combat.chase_approach` | `approach` |
| `combat.chase_approach_shadow` | `approach` |
| `combat.chase_attack_reengage` | — |
| `combat.chase_attack_refused` | — |
| `combat.chase_attack_shadow` | `allowed`, `mode` |
| `combat.chase_sacrifice` | — |
| `combat.chase_sacrifice_offered` | — |
| `combat.chase_sacrifice_shadow` | — |
| `combat.companion_order` | `verb` |
| `combat.companion_order_ignored` | — |
| `combat.companion_order_refused` | `verb` |
| `combat.companion_orders_shadow` | `verb` |
| `combat.enemy_knowledge_failed` | — |
| `combat.entrance_count_reconciled` | `species` |
| `combat.fast_text_failed` | `error`, `where` |
| `combat.freetext_refused` | — |
| `combat.mechanics` | `step_count`, `steps`, `truncated` |
| `combat.narrate_failed` | `error` |
| `combat.narration_numbers_stripped` | `count` |
| `combat.nonlethal` | `target` |
| `combat.nonlethal_shadow` | `target` |
| `combat.object_invalid_fallback` | — |
| `combat.object_refused` | — |
| `combat.object_used` | — |
| `combat.objects_shadow` | `action` |
| `combat.outcome_attribution_rejected` | `codes` |
| `combat.outcome_narration_budget_exceeded` | `elapsed_ms` |
| `combat.outcome_narration_failed` | `error`, `outcome` |
| `combat.parse_failed` | `error` |
| `combat.prep_failed` | `error` |
| `combat.prep_timeout` | `timeout_s` |
| `combat.preparing_encounter` | — |
| `combat.pressagio_forecast_failed` | — |
| `combat.reinforcements_cancelled` | `cause` |
| `combat.reinforcements_fired` | — |
| `combat.reinforcements_shadow` | `leaders`, `phase` |
| `combat.reinforcements_warned` | — |
| `combat.reveal_resist` | `effect` |
| `combat.reveal_resist_shadow` | `effect` |
| `combat.revelar_knowledge_failed` | — |
| `combat.scene_card_dropped` | `reason` |
| `combat.scene_card_shadow` | `card_id`, `rnd` |
| `combat.scene_cards_catalog_unavailable` | — |
| `combat.scene_cards_regions_unavailable` | — |
| `combat.scene_cards_shadow` | `cards`, `objective` |
| `combat.scene_objective_dropped` | `reason` |
| `combat.scene_objective_resolved` | `ok`, `tipo` |
| `combat.spawn_failed` | `error` |
| `combat.spawn_fallback` | — |
| `combat.spawn_from_narration` | — |
| `combat.spawn_identity_mismatch` | — |
| `combat.spawn_scanner_discarded` | — |
| `combat.started` | `enemies` |
| `combat.summary` | `death_stage_reached`, `enemy_damage_dealt`, `player_damage_taken`, `reactions`, `rounds`, `target_redirects` |
| `combat_agent.fallback` | — |
| `companion.abandon_fate_applied` | `fate` |
| `companion.abandon_fate_none` | — |
| `companion.abandon_rescued` | — |
| `companion.personal_quest_completed` | — |
| `companion.personal_quest_revealed` | — |
| `companion_soul.fallback` | — |
| `context.prefetch_failed` | `error` |
| `context.prefetch_hit` | — |
| `context.prefetch_miss` | `reason` |
| `context_builder.fallback` | — |
| `cron.auth_rejected` | `reason` |
| `cron.failed` | `duration_s`, `error_type`, `stack`, `task` |
| `cron.item_failed` | `error_type`, `item_kind`, `item_ref`, `task` |
| `cron.started` | `task` |
| `cron.state_unavailable` | `error_type`, `task` |
| `db.connect_failed` | `attempt`, `error_type`, `pool`, `wait_ms` |
| `db.idempotency_conflict` | `game_ref`, `op_kind`, `op_ref`, `reason` |
| `db.lease_conflict` | `game_ref`, `op_kind`, `op_ref`, `reason` |
| `db.lease_renewal_failed` | `error_type` |
| `db.lock_timeout` | `error_type`, `query_name` |
| `db.pool_timeout` | `in_use`, `pool`, `pool_size`, `requests_waiting`, `wait_ms` |
| `db.slow_query` | `duration_ms`, `query_name` |
| `db.stale_version` | `game_ref`, `op_kind`, `op_ref`, `reason` |
| `db.statement_timeout` | `error_type`, `query_name` |
| `death_flow.fallback` | — |
| `economy.fallback` | — |
| `economy.negative_gold_prevented` | `attempted_gold`, `player` |
| `economy.trade` | `gold_delta`, `item_id`, `mode`, `outcome`, `reason_code` |
| `economy.unique_claim_conflict` | `item_id`, `source` |
| `enrich.fallback` | — |
| `enrich.npc_sheet_completed` | — |
| `enrich.npc_sheet_failed` | — |
| `event.applied` | `event_id`, `type` |
| `event.proposal_rejected` | `reason_code`, `source`, `target_ref`, `type` |
| `faction_gate.fallback` | — |
| `gamedata.artifact_save_failed` | `error` |
| `gamedata.artifact_saved` | — |
| `gamedata.file_missing` | `file` |
| `gamedata.read_failed` | `error`, `file` |
| `graph.component_ignored` | `entity_id` |
| `graph.extra_entity_ignored` | `entity_id` |
| `graph.read_failed` | `error` |
| `http.body_too_large` | `declared_bytes`, `limit_bytes`, `route` |
| `http.request` | `app_version`, `build_skew`, `client`, `client_build`, `duration_ms`, `error_code`, `method`, `owner_ref`, `request_id`, `route`, `status` |
| `http.unhandled_exception` | `error_type`, `method`, `request_id`, `route`, `stack` |
| `http.validation_failed` | `error_count`, `locs`, `method` |
| `image.generation_failed` | `error_type`, `http_status`, `job_id`, `outcome` |
| `image.processing_failed` | `error_type` |
| `image_job.fallback` | — |
| `jev.primary` | Decisao do Jev no router (modo primary). |
| `jev.shadow` | Observacao do Jev no router (modo shadow). |
| `job.completed` | `attempt`, `duration_ms`, `kind` |
| `job.dead` | `attempt`, `error_code`, `job_ref`, `kind`, `reason` |
| `job.deferred` | `attempt`, `delay_s`, `kind`, `reason` |
| `job.failed` | `attempt`, `error_code`, `error_type`, `kind`, `next_run_in_s`, `will_retry` |
| `job.lease_lost` | `attempt`, `kind` |
| `job.started` | `attempt`, `kind` |
| `law.claims_failed` | `error` |
| `law.claims_rejected` | `count` |
| `law.crime_registered` | `crime_type`, `jurisdiction`, `reports`, `status`, `witnesses` |
| `law.gate_failed` | `error` |
| `law.hunters` | `jurisdiction` |
| `law.reports` | `delivered`, `dropped`, `wanted` |
| `law.resolved` | `crimes`, `mode` |
| `librarian.checking_duplicates` | `entity_type` |
| `librarian.failed` | `error` |
| `librarian.match_found` | `existing_id` |
| `librarian.no_candidate` | — |
| `librarian.no_match` | — |
| `llm.attempt` | `attempt_index`, `cost_basis`, `error_type`, `fell_back`, `http_status`, `latency_ms`, `model`, `node`, `outcome`, `provider`, `provider_error_code`, `structured_failure_code`, `tier` |
| `llm.exhausted` | `attempts`, `node`, `tier` |
| `llm.fallback_llm_selected` | `profile`, `reason` |
| `llm.hedge` | `hedge_ms`, `hedge_won`, `hedged`, `node`, `tier` |
| `llm.mock_selected` | `profile`, `reason` |
| `llm.routes_invalid` | `error_type` |
| `logging.config_invalid_level` | `fallback` |
| `loot.corpse_already_looted` | — |
| `loot.fallback` | — |
| `loot.narrate_failed` | `error` |
| `loot.price_reasons_failed` | `error` |
| `loot.resolve_item_ref_failed` | `error` |
| `loot.trade_intent_skipped_classify` | `mode` |
| `loot.trade_parse_failed` | `error` |
| `lore_query.fallback` | — |
| `lore_quests.fallback` | — |
| `narrative.rejected` | `count`, `kind`, `reason_code` |
| `npc.actor_failed` | `error` |
| `npc.cache_hit` | — |
| `npc.creating` | — |
| `npc.db_persist_failed` | `error` |
| `npc.db_read_failed` | `error` |
| `npc.faction_block` | — |
| `npc.faction_id_not_visible` | — |
| `npc.fallback` | — |
| `npc.generation_failed` | `error` |
| `npc.knowledge_failed` | `error` |
| `npc.pool_own_read_failed` | `error` |
| `npc.pool_submit_failed` | `error` |
| `npc.reintroduction_blocked` | `reason` |
| `npc.self_block` | `chars`, `sections`, `truncated` |
| `npc.social_failed` | `error` |
| `npc_world.fallback` | — |
| `npc_world.tick` | `day`, `defections`, `mode`, `moved`, `perils_open`, `perils_resolved`, `roster`, `travelling` |
| `operation.rejected` | `op_kind`, `op_ref`, `reason` |
| `operation.release_failed` | `cause_type`, `error_type`, `op_ref` |
| `operation.replayed` | `op_kind`, `op_ref` |
| `payments.checkout_failed` | `error_code`, `error_type`, `stage` |
| `payments.fee_reconcile_failed` | `error_code`, `error_type`, `stage` |
| `payments.google_verify` | `duration_ms`, `order_ref`, `outcome`, `product_id`, `upstream_status` |
| `payments.immediate_reconcile_failed` | `error_type` |
| `payments.stripe_webhook` | `apply_result`, `duration_ms`, `error_code`, `event_ref`, `event_type`, `outcome` |
| `perceived_world.fallback` | — |
| `persistence.atomic_failed` | `attempts`, `error_type` |
| `persistence.atomic_retry` | `attempt`, `attempts`, `error_type` |
| `persistence.checkpoint_ahead_discarded` | `checkpoint_turn`, `turn` |
| `persistence.checkpoint_load_failed` | `duration_ms`, `error_type`, `game_ref` |
| `persistence.checkpoint_restored` | `game_ref`, `turn` |
| `persistence.checkpoint_write_failed` | `duration_ms`, `error_type`, `game_ref` |
| `persistence.checkpoint_written` | `duration_ms`, `game_ref`, `turn` |
| `persistence.combat_normalize_failed` | `error` |
| `persistence.load_failed` | `duration_ms`, `error_type`, `game_ref` |
| `persistence.migrated` | `from_version`, `game_ref`, `steps`, `to_version` |
| `persistence.save_failed` | `duration_ms`, `error_type`, `game_ref` |
| `persistence.save_schema_newer` | `found_version`, `game_ref`, `supported_version` |
| `persistence.store_checkpoint_failed` | `duration_ms`, `error_type`, `game_ref` |
| `persistence.store_checkpoint_load_failed` | `duration_ms`, `error_type`, `game_ref` |
| `persistence.store_load_failed` | `duration_ms`, `error_type`, `game_ref` |
| `persistence.store_save_failed` | `duration_ms`, `error_type`, `game_ref` |
| `planner_context.fallback` | — |
| `playtest.fallback` | — |
| `pool.admin_action` | `action`, `entry_id` |
| `pool.cast_offered` | `count` |
| `pool.cast_used` | `entry_id` |
| `pool.embed_failed` | `error` |
| `pool.embedder_unavailable` | `error` |
| `pool.eval_capped` | — |
| `pool.eval_error` | `error` |
| `pool.eval_usage` | `attempts`, `entry_id` |
| `pool.mock_eval_blocked` | — |
| `pool.promote_failed` | `entry_id`, `error` |
| `pool.promoted` | `entry_id`, `namespace` |
| `pool.region_lookup_failed` | `error` |
| `pool.region_summary_failed` | `error` |
| `pool.rejected` | `code`, `entry_id` |
| `pool.request_role_applied` | `role` |
| `pool.store_runtime_unavailable` | `error` |
| `pool.submit_capped` | `namespace` |
| `pool.submitted` | `entry_id`, `namespace`, `status` |
| `pool.usage_sink_failed` | `error` |
| `projection.await_failed` | `error` |
| `projection.derived_failed` | `error` |
| `projection.drain_failed` | `error`, `where` |
| `projection.post_response_db_failed` | `error` |
| `projection.pre_turn_failed` | `error` |
| `prologue.failed` | `error` |
| `provider.attempt` | `attempt`, `capability`, `cost_basis`, `fell_back`, `http_status`, `latency_ms`, `model`, `outcome`, `provider` |
| `quest.active_cap_reached` | `cap` |
| `quest.failed` | — |
| `quest.proposal_duplicate_ignored` | — |
| `quest.proposal_world_duplicate` | — |
| `rag.global_index_read_failed` | `error`, `index` |
| `rag.ingest_done` | `index` |
| `rag.ingest_file_missing` | — |
| `rag.ingest_started` | `index`, `provider` |
| `rag.lint_error` | `message`, `path`, `validator` |
| `rag.meta_unreadable` | `error_type`, `fallback_provider`, `index` |
| `rag.npc_memory_failed` | `error` |
| `rag.npc_memory_saved` | `facts` |
| `rag.reindex_aborted` | `lint_errors` |
| `rag.reindex_started` | — |
| `rag.rules_missing` | — |
| `rag.session_memory_failed` | `error` |
| `rag.session_memory_saved` | `facts` |
| `reputation.process_failed` | `error` |
| `router.decision` | `fallback_reason`, `jev_mode`, `route`, `source`, `target_kind` |
| `router.deterministic_npc` | `route` |
| `router.deterministic_npc_failed` | `error` |
| `router.deterministic_shadow` | `agree`, `decided_by` |
| `router.failed` | `error` |
| `router.hostility_signal_failed` | `error` |
| `router.orphan_combat_expired` | — |
| `router.travel_in_combat_flee` | — |
| `rpg.cron` | `consecutive_failures`, `duration_s`, `outcome`, `task` |
| `rule.derived` | `event_id`, `type` |
| `rule.read_failed` | `error` |
| `rule.rule_ignored` | `error`, `rule_id` |
| `rumor.born` | `family`, `region` |
| `rumor.exhausted` | `region` |
| `rumor.perceived` | `channel` |
| `rumor.proposed_accepted` | `family` |
| `rumor.proposed_rejected` | `reason` |
| `rumor.proposed_seen` | `count` |
| `rumor.shadow_born` | `family`, `truth` |
| `rumor_adopt.adopted` | `kind` |
| `rumor_adopt.expired_unmaterialized` | `kind` |
| `rumor_adopt.materialized` | `kind` |
| `rumor_adopt.proposed` | `kind` |
| `rumor_adopt.rejected` | `kind`, `reason` |
| `rumor_adopt.shadow` | `kind`, `reason`, `truth` |
| `runtime.boot` | `cold_start_ms`, `embedding_provider`, `git_sha`, `hardened`, `instance_ref`, `jev_mode`, `llm_mode`, `llm_providers_with_key`, `log_level`, `profile`, `projection_mode`, `region` |
| `runtime.build_failed` | `component`, `error_type` |
| `runtime.config_warning` | `code`, `present` |
| `runtime.embedding_profile_ensure_failed` | `error` |
| `runtime.request_rls_disabled` | `profile` |
| `sse.client_disconnected` | `elapsed_ms`, `phase` |
| `sse.early_narrative_shadow` | `gain_ms`, `identical` |
| `sse.error` | `code`, `error_type`, `stack`, `status` |
| `sse.fallback` | — |
| `sse.started` | `transport` |
| `sse.stream_risk_hold` | `chars_shown`, `rule`, `sentence_index` |
| `sse.token_replace` | `common_prefix_len`, `final_len`, `reason`, `shown_len` |
| `sse.token_stream_shadow` | `identical_to_final`, `reason`, `ttft_shadow_ms`, `would_replace` |
| `sse.worker_finished_after_disconnect` | `outcome` |
| `store.listing_row_skipped` | `error` |
| `storyteller.failed` | `error` |
| `storyteller.fallback` | — |
| `storyteller.unique_item_claimed_ignored` | `item_id` |
| `storyteller.unknown_item_ignored` | — |
| `stt.circuit_opened` | `failures`, `model`, `open_seconds`, `provider` |
| `stt.internal_error` | `code`, `error_type`, `stack` |
| `stt.switch_check_failed` | `error_type`, `model`, `provider` |
| `turn` | `error`, `events_applied`, `events_rejected`, `fallbacks`, `game_id_ref`, `latency_ms`, `narrative_rejected`, `route`, `route_fallback_reason`, `route_source`, `turn` |
| `turn_delivery` | `ack_server_ms`, `action_ref`, `early_gain_ms`, `early_narrative`, `first_token_server_ms`, `outcome`, `pseudo_streaming`, `state_server_ms`, `token_replace`, `transport`, `ttfmc_server_ms`, `ttlt_server_ms` |
| `turn_finalizer.fallback` | — |
| `vector.profile_fallback` | `error_type`, `profile` |
| `vector.semantic_degraded` | `error_type` |
| `wallet.recovery_item_failed` | `error_type`, `op_ref`, `stage` |
| `wallet.reservation_uncertain` | `error_type`, `op_ref`, `stage` |
| `wallet.settle_failed` | `error_type`, `op_ref`, `stage` |
| `world.calendar` | `changed`, `day`, `day_of_month`, `festas_cancelled`, `festas_started`, `migrated`, `mode`, `month_id`, `neutral`, `passes_closed`, `season`, `weekday_id`, `year` |
| `world.tick` | `events`, `mode`, `perceived` |
| `world.tick_capped` | `skipped` |
| `world_engine.fallback` | `hook` |
| `world_quest.relief` | `kind` |
| `world_quests.fallback` | — |
| `world_simulator.fallback` | — |
| `xp.level_up` | `new_level` |
