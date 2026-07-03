#!/usr/bin/env node
// PostToolUse hook: Edit/Write em fontes do RAG (lore_nova/, data/codex/, data/rules.txt)
// -> lembra de rodar `uv run python rag.py`. Lembra 1x por sessão (flag em tmpdir).
// NÃO usar process.exit() após write: no Windows trunca o stdout antes do flush.
const fs = require("fs");
const path = require("path");
const os = require("os");

let raw = "";
process.stdin.on("data", (d) => (raw += d));
process.stdin.on("end", () => {
  try {
    const input = JSON.parse(raw);
    const fp = String((input.tool_input || {}).file_path || "").replace(/\\/g, "/");
    const isRagSource =
      /\/lore_nova\//i.test(fp) ||
      /\/data\/codex\//i.test(fp) ||
      /\/data\/rules\.txt$/i.test(fp);
    if (!isRagSource) return;

    const flag = path.join(os.tmpdir(), `reindex-reminder-${input.session_id || "x"}`);
    if (fs.existsSync(flag)) return; // já lembrou nesta sessão
    fs.writeFileSync(flag, "1");

    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "PostToolUse",
          additionalContext:
            "Fonte do RAG modificada (" + fp.split("/").slice(-2).join("/") +
            "). Antes de finalizar: rodar `uv run python rag.py` para reindexar os FAISS " +
            "(e, se mexeu em lore_nova/, avaliar `uv run python scripts/migrate_lore_nova.py` " +
            "— CUIDADO: sobrescreve curadoria manual do codex/entities).",
        },
      }) + "\n"
    );
  } catch (_) {
    /* hook nunca deve quebrar o fluxo */
  }
});
