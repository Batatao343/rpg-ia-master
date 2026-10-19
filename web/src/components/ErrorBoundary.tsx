import { Component, type ReactNode } from "react";
import { newRequestId } from "../http";
import { reportClientError } from "../lib/clientErrors";
import { SupportCode } from "./SupportCode";

interface State { failed: boolean; supportId: string | null }

/** SPEC-244 R1: erro de render nao derruba a arvore sem rastro — tela de recuperacao + beacon. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false, supportId: null };

  static getDerivedStateFromError(): Partial<State> {
    return { failed: true };
  }

  componentDidCatch(error: Error): void {
    const supportId = newRequestId();
    this.setState({ supportId });
    reportClientError({ kind: "render", error, code: "render_failed", requestId: supportId });
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="error-boundary" role="alert">
        <h1>Algo se partiu no caminho.</h1>
        <p>A tela encontrou um erro inesperado. Seu progresso salvo continua seguro.</p>
        <button type="button" className="btn" onClick={() => window.location.reload()}>Recarregar</button>
        <p><SupportCode requestId={this.state.supportId} /></p>
      </main>
    );
  }
}
