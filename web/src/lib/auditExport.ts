// SPEC-207 R15: fluxo puro do botão "Exportar sessão para auditoria".
// idle → (403 recent_session_required) pede senha → reauth → tenta de novo → download.
// Sem prova recente nunca há download; nada aqui chama modelo nenhum.

export type AuditExportResult =
  | { status: "ok"; blob: Blob }
  | { status: "cancelled" }
  | { status: "error"; httpStatus: number; message: string };

export interface AuditExportDeps {
  exportGame: (gameId: string) => Promise<Blob>;
  reauthenticate: (password: string) => Promise<unknown>;
  askPassword: () => Promise<string | null>;
}

interface ErrorLike { status?: number; code?: string }

export function auditErrorMessage(status: number, code = ""): string {
  if (status === 403 || code === "recent_session_required") return "Confirme sua senha para exportar.";
  if (status === 404) return "Exportação indisponível para esta campanha.";
  if (status === 429) return "Muitas exportações seguidas. Aguarde alguns minutos.";
  if (status === 401) return "Sua sessão terminou. Entre novamente.";
  return "Não foi possível gerar o pacote. Tente novamente.";
}

function asError(cause: unknown): ErrorLike {
  return (cause && typeof cause === "object") ? cause as ErrorLike : {};
}

export async function exportWithReauth(gameId: string, deps: AuditExportDeps): Promise<AuditExportResult> {
  try {
    return { status: "ok", blob: await deps.exportGame(gameId) };
  } catch (cause) {
    const err = asError(cause);
    if (err.status !== 403) {
      return { status: "error", httpStatus: err.status ?? 0, message: auditErrorMessage(err.status ?? 0, err.code) };
    }
  }
  const password = await deps.askPassword();
  if (!password) return { status: "cancelled" };
  try {
    await deps.reauthenticate(password);
  } catch {
    return { status: "error", httpStatus: 401, message: "Senha não confirmada. Tente novamente." };
  }
  try {
    return { status: "ok", blob: await deps.exportGame(gameId) };
  } catch (cause) {
    const err = asError(cause);
    return { status: "error", httpStatus: err.status ?? 0, message: auditErrorMessage(err.status ?? 0, err.code) };
  }
}

export const AUDIT_EXPORT_NOTICE =
  "Gera um arquivo .zip com o transcrito, as mudanças de estado, erros e tempos de cada turno, "
  + "para você analisar com seu próprio assistente de código. Dados da conta (e-mail, ids, pagamentos) "
  + "não entram. Atenção a spoilers: segredos do mundo vêm marcados como \"privado — referência de auditoria\".";
