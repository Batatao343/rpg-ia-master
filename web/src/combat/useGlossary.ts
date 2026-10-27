import { useEffect, useState } from "react";
import type { Glossary } from "../types";
import * as api from "../api";

/** SPEC-342 R19.1: glossário de palavras-chave (1 fetch por sessão; o cache vive em `api.getGlossary`). */
export function useGlossary(): Glossary {
  const [glossary, setGlossary] = useState<Glossary>({});
  useEffect(() => {
    let alive = true;
    void api.getGlossary().then((g) => { if (alive) setGlossary(g); });
    return () => { alive = false; };
  }, []);
  return glossary;
}
