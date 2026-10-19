// SPEC-243: mapa único código -> mensagem pt-BR. Código desconhecido nunca aparece cru.
import catalog from "./errorCodes.json";

export const GENERIC_MESSAGE = "Algo deu errado.";
export const STALE_PAGE_MESSAGE = "A proteção desta página expirou. Recarregue a página e tente de novo.";
const SERVICE_DOWN = "O serviço está indisponível no momento. Tente novamente mais tarde.";
const NOT_FOUND = "Não encontramos o que você procurava.";
const BUSY = "Outra ação deste jogo ainda está em andamento. Aguarde um instante e tente de novo.";

const CODE_RE = /^[a-z][a-z0-9_.]{1,63}$/;
export const isCodeLike = (value: unknown): value is string => typeof value === "string" && CODE_RE.test(value);

export const MESSAGES: Record<string, string> = {
  // auth / conta (absorve authErrors.ts)
  credentials_invalid: "E-mail ou senha incorretos.",
  email_not_confirmed: "Confirme seu e-mail antes de entrar: abra o link que enviamos. Não chegou? Use “Reenviar confirmação de e-mail”.",
  captcha_invalid: "A verificação anti-robô expirou ou falhou. Refaça a verificação e tente de novo.",
  captcha_required: "A verificação anti-robô expirou ou falhou. Refaça a verificação e tente de novo.",
  csrf_invalid: STALE_PAGE_MESSAGE,
  origin_denied: STALE_PAGE_MESSAGE,
  captcha_unavailable: "O serviço de contas está indisponível no momento. Tente novamente mais tarde.",
  auth_unavailable: "O serviço de contas está indisponível no momento. Tente novamente mais tarde.",
  server_misconfigured: "O serviço de contas está indisponível no momento. Tente novamente mais tarde.",
  session_missing: "Sua sessão acabou. Entre de novo.",
  session_invalid: "Sua sessão acabou. Entre de novo.",
  recent_session_required: "Por segurança, confirme sua senha para continuar.",
  account_deleted: "Esta conta foi excluída.",
  account_delete_not_requested: "Não há exclusão de conta pendente.",
  signup_failed: "Não foi possível criar a conta agora.",
  password_reset_failed: "Não foi possível redefinir a senha agora.",
  link_invalid_or_expired: "Este link expirou ou já foi usado. Peça um novo.",
  auth_rate_limit: "Muitas tentativas. Aguarde alguns minutos e tente de novo.",
  auth_disabled_legacy: "Contas não estão disponíveis neste modo.",
  lifecycle_unavailable: "Esta operação de conta não está disponível agora.",
  account_unavailable: "Esta área da conta não está disponível agora.",
  unauthorized: "Sua sessão acabou. Entre de novo.",
  // genéricos
  internal_error: "Erro interno do servidor. Tente novamente em instantes.",
  not_found: NOT_FOUND,
  validation_failed: "Alguns dados enviados não são válidos. Confira e tente de novo.",
  validation_error: "Alguns dados enviados não são válidos. Confira e tente de novo.",
  rate_limited: "Muitas ações em pouco tempo. Aguarde um instante e tente de novo.",
  payload_too_large: "O conteúdo enviado é grande demais.",
  network_error: "Não consegui falar com o servidor. Verifique sua conexão.",
  stream_error: "A narração foi interrompida. Tente de novo.",
  // jogo / turno
  game_not_found: "Não encontramos esta campanha.", no_saved_game: "Nenhum jogo salvo encontrado.",
  save_not_found: "Não encontramos este save.", game_id_invalid: "Identificador de campanha inválido.",
  id_invalid: "Identificador inválido.", turn_not_found: "Não encontramos este turno.",
  game_over_memorial: "Esta saga terminou. A crônica permanece como memorial — comece uma nova jornada.",
  simulation_finished: "O laboratório de combate terminou — reinicie a simulação.",
  simulation_no_prepare: "O laboratório de combate não guarda preparação.",
  game_archived: "Este personagem foi arquivado por uma migração — comece uma nova jornada.",
  death_pending: "Você tombou. Resolva a tela de morte antes de continuar.",
  no_pending_death: "Não há queda pendente para resolver.",
  no_restore_point: "Sem ponto de retorno válido; aceite o memorial ou inicie uma nova jornada.",
  save_schema_newer: "Este save é de uma versão mais nova do jogo. Atualize antes de continuar.",
  internal_turn_error: "Houve um erro interno ao processar o turno. Tente de novo.",
  internal_new_game_error: "Houve um erro interno ao criar o jogo. Tente de novo.",
  lab_create_failed: "Não foi possível criar o laboratório.",
  action_id_required: "A ação não pôde ser identificada. Recarregue a página.",
  action_id_invalid: "A ação não pôde ser identificada. Recarregue a página.",
  idempotency_key_required: "A requisição não pôde ser identificada. Recarregue a página.",
  operation_in_progress: BUSY, operation_conflict: BUSY, operation_request_mismatch: BUSY,
  stale_version: "O jogo mudou em outra aba ou dispositivo. Recarregue a campanha.",
  pending_operation: "Há uma ação que falhou e ainda não foi superada. Retome-a ou descarte-a.",
  history_cursor_stale: "O histórico mudou. Recarregue a lista.",
  invalid_target: "O alvo escolhido deixou de ser válido. Escolha de novo.",
  equip_request_invalid: "Informe o item ou o espaço a esvaziar.",
  equip_rejected: "Não foi possível equipar isso.", prepare_rejected: "Não foi possível preparar essas Cartas.",
  levelup_rejected: "Escolha recusada.", invalid_request: "Parâmetros inválidos.",
  chronicle_query_invalid: "Busca inválida.", onboarding_unavailable: "O conteúdo de introdução está indisponível.",
  // arte
  art_unavailable: "Retrato ou reformulação indisponível.", art_check_previous: "Confira a geração anterior antes de reformular.",
  art_budget_unavailable: "O orçamento visual desta campanha acabou.", offer_not_found: "Oferta de arte não encontrada.",
  generation_id_invalid: "Geração inválida.", generation_not_found: "Geração não encontrada.",
  art_not_rateable: "Esta arte não está disponível para avaliação.", art_rating_failed: "Não foi possível salvar a avaliação.",
  player_offer_not_required: "Esta oferta não é necessária.", reformulation_only_player: "Só o retrato do herói pode ser reformulado.",
  image_generation_disabled: "A geração de imagens está desligada.", image_pricing_unavailable: "O preço da imagem está indisponível.",
  image_quotes_unavailable: "As cotações de imagem estão indisponíveis.", image_quote_conflict: "A cotação mudou. Peça uma nova.",
  image_insufficient_shards: "Saldo de Estilhas insuficiente.",
  // voz
  speech_disabled: "Entrada de voz indisponível nesta sessão. Continue digitando.",
  speech_insufficient_balance: "Saldo insuficiente para transcrever. Continue digitando.",
  speech_rate_limit: "Muitas gravações seguidas. Aguarde um minuto ou continue digitando.",
  speech_internal_error: "Não foi possível transcrever o áudio. Continue digitando.",
  speech_operation_unavailable: "Não foi possível transcrever o áudio. Continue digitando.",
  speech_pricing_unavailable: "Não foi possível transcrever o áudio. Continue digitando.",
  speech_request_invalid: "Não foi possível transcrever o áudio. Continue digitando.",
  audio_bytes: "Áudio muito grande. Grave uma ação mais curta.",
  audio_decoder_unavailable: "Este navegador não conseguiu preparar o áudio para o servidor. Continue digitando.",
  audio_mime: "Formato de áudio não aceito. Continue digitando.",
  audio_duration: "Áudio longo demais. Grave até 60 segundos.",
  speech_failed: "Não foi possível transcrever o áudio. Continue digitando.",
  // pagamentos
  stripe_disabled: "Pagamentos estão desligados no momento.", stripe_catalog_unavailable: SERVICE_DOWN,
  stripe_checkout_unavailable: SERVICE_DOWN, stripe_unavailable_on_android: "Use a compra pela Google Play neste aparelho.",
  stripe_body_limit: SERVICE_DOWN, stripe_body_timeout: SERVICE_DOWN, stripe_event_invalid: SERVICE_DOWN,
  new_purchases_disabled: "Novas compras estão desligadas no momento.",
  payment_order_not_found: "Não encontramos este pedido.", google_play_disabled: "Compras pela Google Play estão desligadas.",
  google_play_unconfigured: SERVICE_DOWN, google_play_unavailable: SERVICE_DOWN,
  google_play_wallet_conflict: "Não foi possível creditar a compra agora. Tente restaurar mais tarde.",
  google_play_token_conflict: "Esta compra já foi usada por outra conta.",
  google_play_purchase_cancelled: "A compra foi cancelada.", google_play_already_consumed: "Esta compra já foi consumida.",
  google_play_test_purchase_rejected: "Compras de teste não são aceitas aqui.",
  too_many_open_orders: "Há compras abertas demais. Conclua ou aguarde expirar antes de iniciar outra.",
  // export / cron
  audit_export_rate_limit: "Muitas exportações seguidas. Aguarde antes de tentar de novo.",
  audit_export_redaction_failed: "Não foi possível gerar a exportação com segurança.",
  audit_export_unavailable_in_legacy: "A exportação não está disponível neste modo.",
  cron_not_configured: SERVICE_DOWN, cron_task_failed: SERVICE_DOWN,
  daily_quota_exceeded: "Cota diária de turnos atingida.",
  daily_spend_cap: "O servidor atingiu o limite de custo de hoje. Tente novamente mais tarde.",
};

/** Códigos do catálogo do backend sem mensagem (o teste Node exige lista vazia). */
export const missingCatalogCodes = (): string[] => (catalog as string[]).filter((c) => !(c in MESSAGES));

/** SPEC-219: 429 de abuso vira aviso legível. Retorna null se não for um. */
export function rateLimitNotice(code: string, retryAfterSeconds?: number, now: Date = new Date()): string | null {
  const wait = Math.max(1, Math.ceil(Number(retryAfterSeconds) || 0));
  if (code === "daily_quota_exceeded") {
    const back = new Date(now.getTime() + wait * 1000);
    const hh = String(back.getHours()).padStart(2, "0");
    const mm = String(back.getMinutes()).padStart(2, "0");
    return `Cota diária de turnos atingida; volta às ${hh}:${mm}.`;
  }
  if (code === "rate_limited") return `Muitas ações em pouco tempo. Aguarde ${wait} s e tente de novo.`;
  if (code === "daily_spend_cap") return MESSAGES.daily_spend_cap;
  if (code === "too_many_open_orders") return MESSAGES.too_many_open_orders;
  return null;
}

/** Mensagem para o usuário: prosa do servidor (já pt-BR) > mapa do código > genérica. Nunca o código cru. */
export function messageFor(code: string, prose?: string, retryAfterSeconds?: number): string {
  if (code === "rate_limited" || code === "daily_quota_exceeded") {
    const notice = rateLimitNotice(code, retryAfterSeconds);
    if (notice) return notice;
  }
  if (prose && !isCodeLike(prose)) return prose;
  return MESSAGES[code] ?? GENERIC_MESSAGE;
}

/** Código de suporte exibido ao usuário: 8 primeiros caracteres do request_id. */
export const supportCode = (requestId?: string | null): string | undefined =>
  requestId ? requestId.replace(/[^A-Za-z0-9]/g, "").slice(0, 8) || undefined : undefined;

export function errRequestId(err: unknown): string | undefined {
  const id = typeof err === "object" && err ? (err as { requestId?: unknown }).requestId : undefined;
  return typeof id === "string" && id ? id : undefined;
}

export function errMsg(err: unknown): string {
  if (err instanceof Error) return isCodeLike(err.message) ? messageFor(err.message) : err.message;
  return typeof err === "string" && !isCodeLike(err) ? err : GENERIC_MESSAGE;
}
