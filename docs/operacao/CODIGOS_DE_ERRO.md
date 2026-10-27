# Códigos de erro da API

> Gerado de `services/error_codes.py` (SPEC-242). Não edite à mão: rode `uv run python scripts/gen_error_codes_doc.py`.

Toda resposta de erro traz `{"detail", "code", "request_id"}`. `code` é estável; `request_id` (também no header `X-Request-ID`) é o código de suporte: buscar o valor nos logs mostra todas as linhas da requisição.

| code | significado |
|---|---|
| `account_delete_not_requested` | Retomada de exclusão sem pedido prévio. |
| `account_deleted` | Conta em exclusão/excluída. |
| `account_unavailable` | Conta indisponível neste perfil. |
| `action_id_invalid` | action_id não é UUID. |
| `action_id_required` | action_id obrigatório neste perfil. |
| `art_budget_unavailable` | Orçamento visual esgotado. |
| `art_check_previous` | Conferir a geração anterior. |
| `art_not_rateable` | Arte não disponível para avaliação. |
| `art_rating_failed` | Falha ao salvar avaliação. |
| `art_unavailable` | Retrato/reformulação indisponível. |
| `audit_export_rate_limit` | Limite do export de auditoria. |
| `audit_export_redaction_failed` | Redaction do export falhou. |
| `audit_export_unavailable_in_legacy` | Export de auditoria indisponível no legacy. |
| `auth_disabled_legacy` | Auth desativada no perfil legacy. |
| `auth_rate_limit` | Limite de tentativas de auth (429). |
| `auth_unavailable` | Provedor de identidade indisponível (503). |
| `captcha_invalid` | Captcha recusado. |
| `captcha_required` | Captcha obrigatório. |
| `captcha_unavailable` | Provedor de captcha indisponível. |
| `chronicle_query_invalid` | Busca da crônica inválida. |
| `credentials_invalid` | E-mail/senha incorretos. |
| `cron_not_configured` | Segredo do cron ausente (fail closed). |
| `cron_task_failed` | Tarefa de cron falhou. |
| `csrf_invalid` | Token CSRF ausente/inválido. |
| `death_pending` | Queda pendente: resolver a tela de morte antes. |
| `deck_off` | Jogadas em lista sem o Baralho de Conflito ativo (409). |
| `email_not_confirmed` | E-mail ainda não confirmado. |
| `equip_rejected` | Regra de inventário recusou o equipamento. |
| `equip_request_invalid` | Pedido de equipar/desequipar incompleto. |
| `game_archived` | Save arquivado por migração de sistema. |
| `game_id_invalid` | game_id não é UUID. |
| `game_not_found` | Jogo inexistente ou de outro owner. |
| `game_over_memorial` | Saga terminada (memorial); mutações recusadas. |
| `generation_id_invalid` | generation_id inválido. |
| `generation_not_found` | Geração inexistente. |
| `google_play_already_consumed` | Compra Play já consumida. |
| `google_play_disabled` | Google Play desligado. |
| `google_play_purchase_cancelled` | Compra Play cancelada. |
| `google_play_test_purchase_rejected` | Compra de teste recusada fora de staging. |
| `google_play_token_conflict` | Token Play já usado por outra conta. |
| `google_play_unavailable` | Google Play indisponível. |
| `google_play_unconfigured` | Google Play sem configuração. |
| `google_play_wallet_conflict` | Conflito de carteira na verificação Play. |
| `history_cursor_stale` | Cursor de histórico obsoleto. |
| `id_invalid` | Identificador inválido. |
| `idempotency_key_required` | Idempotency-Key UUID obrigatório. |
| `image_generation_disabled` | Geração de imagem desligada. |
| `image_insufficient_shards` | Saldo de Estilhas insuficiente. |
| `image_pricing_unavailable` | Preço de imagem indisponível. |
| `image_quote_conflict` | Cotação de imagem em conflito. |
| `image_quotes_unavailable` | Cotações de imagem indisponíveis. |
| `internal_error` | Exceção não tratada (500). Ver `http.unhandled_exception`. |
| `internal_new_game_error` | Falha interna ao criar o jogo. |
| `internal_turn_error` | Falha interna ao processar o turno. |
| `invalid_request` | Parâmetros de consulta inválidos. |
| `invalid_target` | Alvo de combate deixou de ser válido. |
| `lab_create_failed` | Falha ao criar o laboratório de combate. |
| `levelup_rejected` | Regra de progressão recusou a escolha. |
| `lifecycle_unavailable` | Ciclo de conta indisponível no perfil. |
| `link_invalid_or_expired` | Link de e-mail inválido ou expirado. |
| `new_purchases_disabled` | Novas compras desligadas. |
| `no_pending_death` | Não há queda pendente para resolver. |
| `no_restore_point` | Morte sem ponto de retorno válido. |
| `no_saved_game` | Nenhum jogo salvo. |
| `not_found` | Rota ou recurso inexistente. |
| `offer_not_found` | Oferta de arte inexistente. |
| `onboarding_unavailable` | Conteúdo de onboarding indisponível. |
| `operation_conflict` | Conflito de operação. |
| `operation_in_progress` | Outra operação do mesmo jogo em andamento (409). |
| `operation_request_mismatch` | Mesma chave com corpo diferente. |
| `origin_denied` | Origin fora da allowlist. |
| `password_reset_failed` | Redefinição de senha não concluída. |
| `payload_too_large` | Corpo acima do limite da rota (413). |
| `payment_order_not_found` | Pedido de pagamento inexistente. |
| `pending_operation` | Há ação falha pendente a retomar/descartar. |
| `player_offer_not_required` | Oferta de jogador não exigida. |
| `prepare_rejected` | Regra de Cartas recusou a preparação. |
| `preview_invalid` | Prévia de jogada com carta/alvo inválido ou não ofensivo (409). |
| `preview_no_combat` | Prévia de jogada sem conflito em andamento (409). |
| `rate_limited` | Limite de requisições por IP/owner excedido (429). |
| `recent_session_required` | Operação sensível exige prova recente de senha. |
| `reformulation_only_player` | Reformulação só para jogador. |
| `save_not_found` | Save inexistente. |
| `save_schema_newer` | Save de schema mais novo que o servidor. |
| `server_misconfigured` | Segredo de sessão ausente/curto no servidor (503). |
| `session_invalid` | Sessão inválida ou expirada. |
| `session_missing` | Sem cookie de sessão. |
| `signup_failed` | Cadastro não concluído. |
| `simulation_finished` | Laboratório de combate encerrado. |
| `simulation_no_prepare` | Laboratório não tem preparação persistente. |
| `speech_disabled` | STT desligado. |
| `speech_insufficient_balance` | Saldo insuficiente para STT. |
| `speech_internal_error` | Falha interna do STT. |
| `speech_operation_unavailable` | Operação de STT indisponível. |
| `speech_pricing_unavailable` | Preço de STT indisponível. |
| `speech_rate_limit` | Limite de STT (429). |
| `speech_request_invalid` | Pedido de STT inválido. |
| `stale_version` | Versão do save desatualizada. |
| `stripe_body_limit` | Webhook acima do limite. |
| `stripe_body_timeout` | Webhook com corpo lento. |
| `stripe_catalog_unavailable` | Catálogo Stripe indisponível. |
| `stripe_checkout_unavailable` | Checkout Stripe indisponível. |
| `stripe_disabled` | Stripe desligado. |
| `stripe_event_invalid` | Webhook com assinatura/corpo inválido. |
| `stripe_unavailable_on_android` | Stripe recusado no Android. |
| `turn_not_found` | Turno inexistente. |
| `unauthorized` | Credencial interna ausente/inválida (cron). |
| `validation_failed` | Corpo/parâmetros inválidos (422). |

Códigos `http_<status>` são o fallback para erros sem código catalogado (o teste de catálogo impede novos).
