import { useState } from "react";
import { Frame } from "./ornaments";

export function AuthScreen({ busy, onLogin, error }: {
  busy: boolean;
  onLogin: (email: string, password: string, create: boolean) => Promise<void>;
  error?: string;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [create, setCreate] = useState(false);
  return (
    <main className="create">
      <Frame className="create__frame">
        <header className="create__head">
          <p className="kicker">Crônicas de Valoria</p>
          <h1 className="create__title">Retorne à fogueira</h1>
          <p className="create__sub">A sessão protege suas campanhas, memórias e artes.</p>
        </header>
        <form onSubmit={(event) => {
          event.preventDefault();
          void onLogin(email, password, create);
        }}>
          <div className="field">
            <label htmlFor="auth-email">E-mail</label>
            <input id="auth-email" type="email" autoComplete="email" required
              value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="auth-password">Senha</label>
            <input id="auth-password" type="password" autoComplete="current-password" required
              minLength={8} value={password}
              onChange={(event) => setPassword(event.target.value)} />
          </div>
          {error && <p role="alert" className="muted">{error}</p>}
          <button className="btn btn--primary" disabled={busy}>
            {busy ? "Abrindo o tomo…" : create ? "Criar conta" : "Entrar"}
          </button>
          <button type="button" className="btn btn--ghost" disabled={busy}
            onClick={() => setCreate((value) => !value)}>
            {create ? "Já tenho uma conta" : "Criar uma conta local"}
          </button>
        </form>
      </Frame>
    </main>
  );
}
