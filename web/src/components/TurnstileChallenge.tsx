import { useEffect, useRef, useState } from "react";

type TurnstileApi = {
  render: (element: HTMLElement, options: Record<string, unknown>) => string;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window { turnstile?: TurnstileApi }
}

let scriptReady: Promise<TurnstileApi> | null = null;

function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (!scriptReady) scriptReady = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.onload = () => window.turnstile ? resolve(window.turnstile) : reject(new Error("turnstile_unavailable"));
    script.onerror = () => { script.remove(); scriptReady = null; reject(new Error("turnstile_unavailable")); };
    document.head.appendChild(script);
  });
  return scriptReady;
}

export function TurnstileChallenge({ siteKey, required, action, revision, onToken }: {
  siteKey: string | null; required: boolean; action: "signup" | "reset" | "verify" | "login" | "reauth";
  revision: number; onToken: (token: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const onTokenRef = useRef(onToken);
  const [failed, setFailed] = useState(false);
  useEffect(() => { onTokenRef.current = onToken; });

  useEffect(() => {
    if (!required || !siteKey) return;
    let active = true;
    let widgetId: string | null = null;
    onTokenRef.current("");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setFailed(false);
    void loadTurnstile().then(api => {
      if (!active || !container.current) return;
      widgetId = api.render(container.current, {
        sitekey: siteKey,
        action,
        callback: (token: string) => onTokenRef.current(token),
        "expired-callback": () => onTokenRef.current(""),
        "error-callback": () => { onTokenRef.current(""); setFailed(true); },
      });
    }).catch(() => { if (active) { onTokenRef.current(""); setFailed(true); } });
    return () => {
      active = false;
      if (widgetId) window.turnstile?.remove(widgetId);
      onTokenRef.current("");
    };
  }, [required, siteKey, action, revision]);

  if (!required) return null;
  if (!siteKey) return <p role="alert">Verificação de segurança indisponível nesta configuração.</p>;
  return <div className="auth-challenge" role="group" aria-label="Verificação de segurança">
    <div ref={container} />
    {failed && <p role="alert">Não foi possível carregar a verificação. Recarregue a página para tentar novamente.</p>}
  </div>;
}
