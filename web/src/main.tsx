import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./fonts.css";
import "./styles.css";
import "./workspace.css";
import { App } from "./App";
import { initEffects } from "./design/motion";

initEffects();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
