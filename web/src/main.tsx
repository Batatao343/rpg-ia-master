import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./fonts.css";
import "./styles.css";
import "./workspace.css";
import { App } from "./App";
import { initEffects } from "./design/motion";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { installGlobalErrorHandlers } from "./lib/clientErrors";

initEffects();
installGlobalErrorHandlers();   // SPEC-244 R2

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
