// Auth debug 2026-10-18: a tela de conta nunca mostra códigos crus (ex.: "credentials_invalid").
// Mensagens não enumeram contas: "e-mail não confirmado" só chega depois de a senha conferir.

export type AuthFlow = "login" | "signup" | "email";

import { MESSAGES } from "./errorMessages";

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
  if (code in MESSAGES && code !== "validation_error" && code !== "rate_limited") return MESSAGES[code];   // SPEC-243: mapa unico
  switch (code) {
    case "validation_error":
      return flow === "login" ? "Verifique o e-mail e a senha informados."
        : flow === "signup" ? "Verifique os dados: e-mail válido e senha com no mínimo 10 caracteres."
          : "Verifique o e-mail informado.";
    default:
      return GENERIC;
  }
}
