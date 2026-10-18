// Auth debug 2026-10-18: a tela de conta nunca mostra códigos crus (ex.: "credentials_invalid").
// Mensagens não enumeram contas: "e-mail não confirmado" só chega depois de a senha conferir.

export type AuthFlow = "login" | "signup" | "email";

const STALE_PAGE = "A proteção desta página expirou. Recarregue a página e tente de novo.";
const GENERIC = "Não foi possível concluir agora. Tente novamente mais tarde.";

export function authErrorMessage(error: unknown, flow: AuthFlow): string {
  const status = typeof error === "object" && error && "status" in error ? Number((error as { status: unknown }).status) : 0;
  const code = typeof error === "object" && error && "code" in error ? String((error as { code: unknown }).code) : "";
  if (status === 429) {
    const retry = Number((error as { retryAfterSeconds?: unknown }).retryAfterSeconds);
    return Number.isFinite(retry) && retry > 0
      ? `Muitas tentativas. Aguarde ${Math.ceil(retry / 60)} min e tente de novo.`
      : "Muitas tentativas. Aguarde alguns minutos e tente de novo.";
  }
  switch (code) {
    case "credentials_invalid":
      return "E-mail ou senha incorretos.";
    case "email_not_confirmed":
      return "Confirme seu e-mail antes de entrar: abra o link que enviamos. Não chegou? Use “Reenviar confirmação de e-mail”.";
    case "captcha_invalid":
    case "captcha_required":
      return "A verificação anti-robô expirou ou falhou. Refaça a verificação e tente de novo.";
    case "csrf_invalid":
    case "origin_denied":
      return STALE_PAGE;
    case "captcha_unavailable":
    case "server_misconfigured":
      return "O serviço de contas está indisponível no momento. Tente novamente mais tarde.";
    case "validation_error":
      return flow === "login" ? "Verifique o e-mail e a senha informados."
        : flow === "signup" ? "Verifique os dados: e-mail válido e senha com no mínimo 10 caracteres."
          : "Verifique o e-mail informado.";
    default:
      return GENERIC;
  }
}
