import { useState } from "react";
import { supportCode } from "../lib/errorMessages";

/** SPEC-243 R3: "Código de suporte" copiável; o id completo vai para a área de transferência. */
export function SupportCode({ requestId }: { requestId?: string | null }) {
  const [copied, setCopied] = useState(false);
  const short = supportCode(requestId);
  if (!requestId || !short) return null;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(requestId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard indisponivel: o codigo curto continua visivel */ }
  };
  return (
    <span className="support-code">
      Código de suporte: <code>{short}</code>
      <button type="button" className="support-code-copy" onClick={copy} aria-label="Copiar código de suporte">
        {copied ? "Copiado" : "Copiar"}
      </button>
      <span className="sr-only" aria-live="polite">{copied ? "Código de suporte copiado" : ""}</span>
    </span>
  );
}
