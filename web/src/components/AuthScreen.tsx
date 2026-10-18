import { useState, type FormEvent } from "react";
import * as api from "../api";
import { Frame } from "./ornaments";
import { TurnstileChallenge } from "./TurnstileChallenge";
import { authErrorMessage } from "../lib/authErrors";

type Mode = "login" | "signup" | "reset_request" | "verify_request" | "verify_link" | "reset_link";

function readEmailLink(): { mode: Mode; tokenHash: string } | null {
  // The fragment is never sent with HTTP requests or Referer headers.
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const action = params.get("auth_action");
  const tokenHash = params.get("token_hash");
  if (!tokenHash || tokenHash.length > 2048 || (action !== "verify" && action !== "recovery")) return null;
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  return { mode: action === "verify" ? "verify_link" : "reset_link", tokenHash };
}

const emailLink = typeof window === "undefined" ? null : readEmailLink();
export const hasEmailActionLink = emailLink !== null;
const genericEmailNotice = "Se o endereço puder receber mensagens, enviaremos as instruções.";

export function AuthScreen({ busy, onLogin, onAuthenticated, config, error, notice, onClearMessages }: {
  busy: boolean;
  onLogin: (email: string, password: string, create: boolean, captchaToken?: string) => Promise<void>;
  onAuthenticated: () => Promise<void>;
  config?: api.AuthConfig;
  error?: string;
  notice?: string;
  /** Limpa erro/aviso vindos do pai (ex.: falha de login) ao trocar de tela. */
  onClearMessages?: () => void;
}) {
  const [mode, setMode] = useState<Mode>(emailLink?.mode ?? "login");
  const [tokenHash, setTokenHash] = useState(emailLink?.tokenHash ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [captchaRevision, setCaptchaRevision] = useState(0);
  const [localBusy, setLocalBusy] = useState(false);
  const [localError, setLocalError] = useState("");
  const [localNotice, setLocalNotice] = useState("");
  // SPEC-222 R9 (D-D): idade mínima 18, autodeclarada e obrigatória no cadastro.
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const working = busy || localBusy;
  const lifecycle = config?.lifecycle_available ?? false;
  const captchaRequired = config?.captcha?.required ?? false;
  const needsCaptcha = (["signup", "reset_request", "verify_request"].includes(mode)
    || (mode === "login" && config?.captcha?.mode === "gotrue")) && captchaRequired;

  function switchMode(next: Mode) {
    setMode(next); setLocalError(""); setLocalNotice(""); setCaptchaToken("");
    onClearMessages?.();
    setCaptchaRevision(value => value + 1);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (working || (needsCaptcha && !captchaToken) || (mode === "signup" && !ageConfirmed)) return;
    setLocalError(""); setLocalNotice(""); onClearMessages?.();
    try {
      if (mode === "login" || mode === "signup") {
        await onLogin(email, password, mode === "signup", captchaToken || undefined);
      } else {
        setLocalBusy(true);
        if (mode === "reset_request") {
          await api.requestPasswordReset(email, captchaToken);
          setLocalNotice(genericEmailNotice);
        } else if (mode === "verify_request") {
          await api.requestEmailVerification(email, captchaToken);
          setLocalNotice(genericEmailNotice);
        } else if (mode === "verify_link") {
          await api.confirmEmailVerification(tokenHash);
          setTokenHash("");
          await onAuthenticated();
        } else if (mode === "reset_link") {
          if (password !== confirmPassword) { setLocalError("As senhas não coincidem."); return; }
          await api.confirmPasswordReset(tokenHash, password);
          setTokenHash(""); setPassword(""); setConfirmPassword("");
          switchMode("login");
          setLocalNotice("Senha atualizada. Entre novamente.");
        }
      }
    } catch (cause) {
      const linkError = mode === "verify_link" || mode === "reset_link";
      setLocalError(linkError ? "Link inválido ou expirado. Solicite um novo e-mail."
        : authErrorMessage(cause, "email"));
    } finally {
      setLocalBusy(false);
      if (needsCaptcha) { setCaptchaToken(""); setCaptchaRevision(value => value + 1); }
    }
  }

  const title = mode === "verify_link" ? "Confirmar e-mail" : mode === "reset_link" ? "Criar nova senha"
    : mode === "reset_request" ? "Recuperar acesso" : mode === "verify_request" ? "Reenviar confirmação"
      : "Retorne à fogueira";
  const requiresEmail = ["login", "signup", "reset_request", "verify_request"].includes(mode);
  const requiresPassword = ["login", "signup", "reset_link"].includes(mode);
  const captchaAction = mode === "signup" ? "signup" : mode === "verify_request" ? "verify"
    : mode === "login" ? "login" : "reset";

  return <main className="create">
    <Frame className="create__frame">
      <header className="create__head">
        <p className="kicker">Crônicas de Valoria</p>
        <h1 className="create__title">{title}</h1>
        <p className="create__sub">{mode === "reset_request" || mode === "verify_request"
          ? "Enviaremos instruções caso o endereço possa recebê-las."
          : mode === "reset_link" ? "Escolha uma senha nova para sua conta."
            : mode === "verify_link" ? "Confirme o endereço para proteger suas campanhas."
              : "A sessão protege suas campanhas, memórias e artes."}</p>
      </header>
      <form className="form" onSubmit={event => void submit(event)}>
        {requiresEmail && <div className="field">
          <label htmlFor="auth-email">E-mail</label>
          <input id="auth-email" type="email" autoComplete="email" required
            value={email} onChange={event => setEmail(event.target.value)} />
        </div>}
        {requiresPassword && <div className="field">
          <label htmlFor="auth-password">{mode === "reset_link" ? "Nova senha" : "Senha"}</label>
          <input id="auth-password" type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"} required
            minLength={mode === "login" ? 8 : 10} aria-describedby={mode === "login" ? undefined : "auth-password-hint"}
            value={password} onChange={event => setPassword(event.target.value)} />
          {mode !== "login" && <small id="auth-password-hint" className="muted">Mínimo de 10 caracteres.</small>}
        </div>}
        {mode === "reset_link" && <div className="field">
          <label htmlFor="auth-password-confirm">Repita a nova senha</label>
          <input id="auth-password-confirm" type="password" autoComplete="new-password" required
            minLength={10} value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} />
        </div>}
        {needsCaptcha && <TurnstileChallenge required siteKey={config?.captcha?.site_key ?? null}
          action={captchaAction} revision={captchaRevision} onToken={setCaptchaToken} />}
        {mode === "signup" && <div className="auth-consent" data-testid="signup-consent">
          <p className="muted">
            Ao criar conta você concorda com os <a href="/termos/" target="_blank" rel="noopener">Termos</a> e
            a <a href="/privacidade/" target="_blank" rel="noopener">Política de Privacidade</a>; texto e voz
            enviados ao jogo são processados por provedores de IA listados na política.
          </p>
          <label className="auth-consent__age">
            <input type="checkbox" required checked={ageConfirmed}
              onChange={event => setAgeConfirmed(event.target.checked)} />
            Declaro ter 18 anos ou mais.
          </label>
        </div>}
        {(localError || error) && <p role="alert" className="muted">{localError || error}</p>}
        {(localNotice || notice) && <p role="status" className="muted">{localNotice || notice}</p>}
        <button className="btn btn--primary"
          disabled={working || (needsCaptcha && !captchaToken) || (mode === "signup" && !ageConfirmed)}>
          {working ? "Aguarde…" : mode === "signup" ? "Criar conta" : mode === "reset_request"
            ? "Enviar recuperação" : mode === "verify_request" ? "Enviar confirmação"
              : mode === "verify_link" ? "Confirmar e-mail" : mode === "reset_link" ? "Atualizar senha" : "Entrar"}
        </button>
        {mode === "login" && <button type="button" className="btn btn--ghost" disabled={working}
          onClick={() => switchMode("signup")}>Criar uma conta local</button>}
        {mode === "signup" && <button type="button" className="btn btn--ghost" disabled={working}
          onClick={() => switchMode("login")}>Já tenho uma conta</button>}
        {lifecycle && mode === "login" && <>
          <button type="button" className="btn btn--ghost" disabled={working}
            onClick={() => switchMode("reset_request")}>Esqueci minha senha</button>
          <button type="button" className="btn btn--ghost" disabled={working}
            onClick={() => switchMode("verify_request")}>Reenviar confirmação de e-mail</button>
        </>}
        {mode !== "login" && mode !== "signup" && <button type="button" className="btn btn--ghost"
          disabled={working} onClick={() => switchMode("login")}>Voltar para entrar</button>}
      </form>
      <nav className="auth-legal" aria-label="Documentos legais">
        <a href="/privacidade/">Privacidade</a>
        <a href="/termos/">Termos</a>
      </nav>
    </Frame>
  </main>;
}
