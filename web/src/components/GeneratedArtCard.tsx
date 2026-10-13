import { useEffect, useState } from "react";
import { getArtStatus, type ArtStatus } from "../api";
import { ArtworkDialog } from "./ArtworkDialog";

type Kind = "npc" | "scene";

export function GeneratedArtCard({ gameId, generationId, type }: {
  gameId: string; generationId: string; type: Kind;
}) {
  const label = type === "npc" ? "Retrato de NPC" : "Cena épica";
  const [result, setResult] = useState<ArtStatus | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let active = true;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const abort = new AbortController();
    const poll = async () => {
      try {
        const art = await getArtStatus(gameId, generationId, abort.signal);
        if (!active) return;
        setResult(art);
        setError("");
        if (["pending", "generating", "failed_retryable"].includes(art.status) && ++attempts < 30)
          timer = setTimeout(poll, Math.min(15_000, 2000 * 1.3 ** attempts));
        else if (art.status === "ready") timer = setTimeout(poll, 240_000); // refresh signed image URL
      } catch {
        if (active) setError("Não foi possível consultar a imagem. Nenhuma nova geração foi solicitada.");
      }
    };
    void poll();
    return () => { active = false; abort.abort(); clearTimeout(timer); };
  }, [gameId, generationId, refresh]);

  const asset = result?.status === "ready"
    ? result.assets?.find(item => item.variant === "full" || item.variant === "display") ?? result.assets?.[0]
    : undefined;
  const uncertain = result?.financial_status === "uncertain" || result?.status === "reconcile_required";
  const status = error || ({
    pending: "Na fila", generating: "Em criação", ready: "Pronta", failed: "Falhou",
    failed_retryable: "Aguardando recuperação", reconcile_required: "Aguardando verificação financeira",
    rejected_quality: "Reprovada", refused: "Recusada", superseded: "Linha temporal anterior",
  } as Record<string, string>)[result?.status ?? "pending"] || "Status indisponível";

  return <section className="generated-art-card" aria-label={label}>
    <h3>{label}</h3>
    <p role="status">{status}</p>
    {uncertain && <p role="status">Saldo retido para conferência; esta imagem não será gerada novamente automaticamente.</p>}
    {!uncertain && result?.credits_held && <p role="status">Saldo reservado até a conclusão financeira.</p>}
    {asset && <>
      <button type="button" className="card__select" onClick={() => setExpanded(true)} aria-label={`Ampliar ${label.toLowerCase()}`}>
        <img src={asset.url} width={asset.width} height={asset.height} alt={label} />
      </button>
      {expanded && <ArtworkDialog url={asset.url} alt={label} onClose={() => setExpanded(false)} />}
    </>}
    {(uncertain || !asset) && <button type="button" className="btn btn--ghost" onClick={() => setRefresh(value => value + 1)}>
      Atualizar status
    </button>}
  </section>;
}
