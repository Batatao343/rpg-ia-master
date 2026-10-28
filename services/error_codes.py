"""SPEC-242: catálogo de códigos de erro estáveis + envelope ``{detail, code, request_id}``.

``detail`` mantém o valor histórico (compatibilidade do cliente); ``code`` é SEMPRE um
snake_case estável do catálogo. Mensagens internas de exceção nunca entram na resposta.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

_CODE_RE = re.compile(r"^[a-z][a-z0-9_.]{1,63}$")

# código -> descrição curta (documentada em docs/operacao/CODIGOS_DE_ERRO.md)
CODE_DOCS: dict[str, str] = {
    # genéricos
    "internal_error": "Exceção não tratada (500). Ver `http.unhandled_exception`.",
    "not_found": "Rota ou recurso inexistente.",
    "validation_failed": "Corpo/parâmetros inválidos (422).",
    "rate_limited": "Limite de requisições por IP/owner excedido (429).",
    "payload_too_large": "Corpo acima do limite da rota (413).",
    "server_misconfigured": "Segredo de sessão ausente/curto no servidor (503).",
    "unauthorized": "Credencial interna ausente/inválida (cron).",
    # auth/sessão
    "session_missing": "Sem cookie de sessão.",
    "session_invalid": "Sessão inválida ou expirada.",
    "csrf_invalid": "Token CSRF ausente/inválido.",
    "origin_denied": "Origin fora da allowlist.",
    "captcha_required": "Captcha obrigatório.",
    "captcha_invalid": "Captcha recusado.",
    "captcha_unavailable": "Provedor de captcha indisponível.",
    "recent_session_required": "Operação sensível exige prova recente de senha.",
    "account_delete_not_requested": "Retomada de exclusão sem pedido prévio.",
    "credentials_invalid": "E-mail/senha incorretos.",
    "link_invalid_or_expired": "Link de e-mail inválido ou expirado.",
    "signup_failed": "Cadastro não concluído.",
    "password_reset_failed": "Redefinição de senha não concluída.",
    "account_deleted": "Conta em exclusão/excluída.",
    "email_not_confirmed": "E-mail ainda não confirmado.",
    "auth_unavailable": "Provedor de identidade indisponível (503).",
    "auth_rate_limit": "Limite de tentativas de auth (429).",
    "auth_disabled_legacy": "Auth desativada no perfil legacy.",
    "lifecycle_unavailable": "Ciclo de conta indisponível no perfil.",
    "account_unavailable": "Conta indisponível neste perfil.",
    # jogo / turno
    "game_not_found": "Jogo inexistente ou de outro owner.",
    "no_saved_game": "Nenhum jogo salvo.",
    "save_not_found": "Save inexistente.",
    "game_id_invalid": "game_id não é UUID.",
    "id_invalid": "Identificador inválido.",
    "turn_not_found": "Turno inexistente.",
    "game_over_memorial": "Saga terminada (memorial); mutações recusadas.",
    "simulation_finished": "Laboratório de combate encerrado.",
    "simulation_no_prepare": "Laboratório não tem preparação persistente.",
    "game_archived": "Save arquivado por migração de sistema.",
    "death_pending": "Queda pendente: resolver a tela de morte antes.",
    "no_pending_death": "Não há queda pendente para resolver.",
    "no_restore_point": "Morte sem ponto de retorno válido.",
    "save_schema_newer": "Save de schema mais novo que o servidor.",
    "internal_turn_error": "Falha interna ao processar o turno.",
    "internal_new_game_error": "Falha interna ao criar o jogo.",
    "lab_create_failed": "Falha ao criar o laboratório de combate.",
    "action_id_required": "action_id obrigatório neste perfil.",
    "action_id_invalid": "action_id não é UUID.",
    "idempotency_key_required": "Idempotency-Key UUID obrigatório.",
    "operation_in_progress": "Outra operação do mesmo jogo em andamento (409).",
    "operation_conflict": "Conflito de operação.",
    "operation_request_mismatch": "Mesma chave com corpo diferente.",
    "stale_version": "Versão do save desatualizada.",
    "pending_operation": "Há ação falha pendente a retomar/descartar.",
    "history_cursor_stale": "Cursor de histórico obsoleto.",
    "invalid_target": "Alvo de combate deixou de ser válido.",
    "preview_no_combat": "Prévia de jogada sem conflito em andamento (409).",
    "preview_invalid": "Prévia de jogada com carta/alvo inválido ou não ofensivo (409).",
    "deck_off": "Jogadas em lista sem o Baralho de Conflito ativo (409).",
    "equip_request_invalid": "Pedido de equipar/desequipar incompleto.",
    "equip_rejected": "Regra de inventário recusou o equipamento.",
    "prepare_rejected": "Regra de Cartas recusou a preparação.",
    "levelup_rejected": "Regra de progressão recusou a escolha.",
    "espolio_rejected": "Regra do espólio de Cartas recusou a escolha.",
    "forja_rejected": "Regra da Forja do baralho recusou a ação.",
    "card_rewards_off": "Espólio/Forja de Cartas desligados neste ambiente (409).",
    "invalid_request": "Parâmetros de consulta inválidos.",
    "chronicle_query_invalid": "Busca da crônica inválida.",
    "onboarding_unavailable": "Conteúdo de onboarding indisponível.",
    # arte
    "art_unavailable": "Retrato/reformulação indisponível.",
    "art_check_previous": "Conferir a geração anterior.",
    "art_budget_unavailable": "Orçamento visual esgotado.",
    "offer_not_found": "Oferta de arte inexistente.",
    "generation_id_invalid": "generation_id inválido.",
    "generation_not_found": "Geração inexistente.",
    "art_not_rateable": "Arte não disponível para avaliação.",
    "art_rating_failed": "Falha ao salvar avaliação.",
    "player_offer_not_required": "Oferta de jogador não exigida.",
    "reformulation_only_player": "Reformulação só para jogador.",
    "image_generation_disabled": "Geração de imagem desligada.",
    "image_pricing_unavailable": "Preço de imagem indisponível.",
    "image_quotes_unavailable": "Cotações de imagem indisponíveis.",
    "image_quote_conflict": "Cotação de imagem em conflito.",
    "image_insufficient_shards": "Saldo de Estilhas insuficiente.",
    "creature_art_disabled": "Retrato de criatura desligado.",
    "monster_quote_invalid": "Pedido de retrato inválido.",
    "enemy_id_only_monster": "enemy_id só vale para retrato de criatura.",
    "enemy_not_in_conflict": "Inimigo fora do conflito atual.",
    "creature_portrait_curated": "Este retrato já existe no bestiário.",
    "creature_portrait_exists": "Este retrato já existe ou está sendo gerado.",
    "creature_portrait_in_progress": "Outro jogador já está gerando este retrato.",
    "quality_not_applicable": "Retrato compartilhado não é avaliado por jogador.",
    # voz
    "speech_disabled": "STT desligado.",
    "speech_insufficient_balance": "Saldo insuficiente para STT.",
    "speech_internal_error": "Falha interna do STT.",
    "speech_operation_unavailable": "Operação de STT indisponível.",
    "speech_pricing_unavailable": "Preço de STT indisponível.",
    "speech_rate_limit": "Limite de STT (429).",
    "speech_request_invalid": "Pedido de STT inválido.",
    # pagamentos
    "stripe_disabled": "Stripe desligado.",
    "stripe_catalog_unavailable": "Catálogo Stripe indisponível.",
    "stripe_checkout_unavailable": "Checkout Stripe indisponível.",
    "stripe_unavailable_on_android": "Stripe recusado no Android.",
    "stripe_body_limit": "Webhook acima do limite.",
    "stripe_body_timeout": "Webhook com corpo lento.",
    "stripe_event_invalid": "Webhook com assinatura/corpo inválido.",
    "new_purchases_disabled": "Novas compras desligadas.",
    "payment_order_not_found": "Pedido de pagamento inexistente.",
    "google_play_disabled": "Google Play desligado.",
    "google_play_unconfigured": "Google Play sem configuração.",
    "google_play_unavailable": "Google Play indisponível.",
    "google_play_wallet_conflict": "Conflito de carteira na verificação Play.",
    "google_play_token_conflict": "Token Play já usado por outra conta.",
    "google_play_purchase_cancelled": "Compra Play cancelada.",
    "google_play_already_consumed": "Compra Play já consumida.",
    "google_play_test_purchase_rejected": "Compra de teste recusada fora de staging.",
    # export / cron
    "audit_export_rate_limit": "Limite do export de auditoria.",
    "audit_export_redaction_failed": "Redaction do export falhou.",
    "audit_export_unavailable_in_legacy": "Export de auditoria indisponível no legacy.",
    "cron_not_configured": "Segredo do cron ausente (fail closed).",
    "cron_task_failed": "Tarefa de cron falhou.",
}
CODES = frozenset(CODE_DOCS)

# Prosa histórica (mantida em ``detail`` por compatibilidade) -> código estável.
PROSE_CODES: dict[str, str] = {
    "auth desativada no perfil legacy": "auth_disabled_legacy",
    "game_id inválido (esperado UUID).": "game_id_invalid",
    "Not Found": "not_found",
    "Nenhum jogo salvo encontrado.": "no_saved_game",
    "Jogo não encontrado.": "game_not_found",
    "Conta indisponível neste perfil.": "account_unavailable",
    "ID inválido.": "id_invalid",
    "Turno não encontrado.": "turn_not_found",
    "Resolva a queda antes de encomendar arte.": "death_pending",
    "Retrato ou reformulação indisponível.": "art_unavailable",
    "Confira a geração anterior antes de reformular.": "art_check_previous",
    "Oferta não encontrada.": "offer_not_found",
    "Orçamento visual indisponível.": "art_budget_unavailable",
    "generation_id inválido.": "generation_id_invalid",
    "Geração não encontrada.": "generation_not_found",
    "Arte não disponível para avaliação.": "art_not_rateable",
    "Não foi possível salvar a avaliação.": "art_rating_failed",
    "Erro interno ao criar o jogo.": "internal_new_game_error",
    "action_id é obrigatório neste perfil.": "action_id_required",
    "action_id inválido.": "action_id_invalid",
    "Erro interno ao processar o turno.": "internal_turn_error",
    "Você tombou. Resolva a tela de morte.": "death_pending",
    "Nenhuma queda pendente para resolver.": "no_pending_death",
    "Resolva a queda antes desta alteração.": "death_pending",
    "Informe item_id ou unequip_slot.": "equip_request_invalid",
    "O laboratório de combate não tem preparação persistente.": "simulation_no_prepare",
    "Save não encontrado.": "save_not_found",
    "Idempotency-Key UUID é obrigatório.": "idempotency_key_required",
    "Não foi possível criar o laboratório.": "lab_create_failed",
    "Conteúdo de onboarding indisponível.": "onboarding_unavailable",
}
_PROSE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("Esta saga terminou", "game_over_memorial"),
    ("simulation_finished", "simulation_finished"),
    ("Personagem arquivado", "game_archived"),
    ("Este save foi criado por uma versão mais nova", "save_schema_newer"),
    ("Sem ponto de retorno", "no_restore_point"),
)


def is_code(value: Any) -> bool:
    return isinstance(value, str) and bool(_CODE_RE.match(value))


def prose_code(detail: str) -> str | None:
    if detail in PROSE_CODES:
        return PROSE_CODES[detail]
    for prefix, code in _PROSE_PREFIXES:
        if detail.startswith(prefix):
            return code
    return None


def code_for(status: int, detail: Any, explicit: str | None = None) -> str:
    """Código estável de um erro HTTP. Nunca devolve prosa."""
    if explicit and is_code(explicit):
        return explicit
    if isinstance(detail, dict):
        inner = detail.get("code")
        if is_code(inner):
            return inner
    elif isinstance(detail, str):
        if is_code(detail):
            return detail
        mapped = prose_code(detail)
        if mapped:
            return mapped
    return f"http_{int(status)}"


class ApiError(HTTPException):
    """``HTTPException`` com código explícito e campos extras aditivos."""

    def __init__(
        self,
        status_code: int,
        code: str,
        detail: Any = None,
        *,
        headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(
            status_code=status_code, detail=detail if detail is not None else code, headers=headers
        )
        self.code = code
        self.extra = extra


def api_error(status: int, code: str, detail: Any = None, **extra: Any) -> ApiError:
    """``raise api_error(409, "x", detail="texto", operation_id=...)``."""
    return ApiError(status, code, detail, **extra)


def envelope(
    status: int,
    detail: Any,
    *,
    code: str | None = None,
    request_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": detail, "code": code_for(status, detail, code)}
    body.update(extra)
    if request_id:
        body["request_id"] = request_id
    return body


def render_markdown() -> str:
    lines = [
        "# Códigos de erro da API",
        "",
        "> Gerado de `services/error_codes.py` (SPEC-242). Não edite à mão: rode "
        "`uv run python scripts/gen_error_codes_doc.py`.",
        "",
        'Toda resposta de erro traz `{"detail", "code", "request_id"}`. `code` é estável; '
        "`request_id` (também no header `X-Request-ID`) é o código de suporte: "
        "buscar o valor nos logs mostra todas as linhas da requisição.",
        "",
        "| code | significado |",
        "|---|---|",
    ]
    lines += [f"| `{c}` | {CODE_DOCS[c]} |" for c in sorted(CODE_DOCS)]
    lines += [
        "",
        "Códigos `http_<status>` são o fallback para erros sem código catalogado "
        "(o teste de catálogo impede novos).",
        "",
    ]
    return "\n".join(lines)
