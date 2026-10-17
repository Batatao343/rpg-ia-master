import { useEffect, useState } from 'react';
import { getArtStatus, type ArtStatus } from '../api';
import { ArtworkDialog } from './ArtworkDialog';

const LABELS: Record<string, string> = {
  pending: 'Retrato na fila', generating: 'Retrato em criação', disabled: 'Arte dinâmica desativada',
  failed: 'Não foi possível concluir o retrato', failed_retryable: 'Retrato aguardando recuperação',
  reconcile_required: 'Retrato aguardando verificação; não será gerado novamente automaticamente',
  rejected_quality: 'Retrato reprovado', refused: 'Pedido de retrato recusado', superseded: 'Retrato de uma linha do tempo anterior',
};

export function GeneratedPortrait({ gameId, generationId }: { gameId: string; generationId?: string | null }) {
  const [result, setResult] = useState<{ key: string; art: ArtStatus } | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0); // SPEC-209 R10: URL assinada expirada → refetch UMA vez
  const [broken, setBroken] = useState(false);
  const key = `${gameId}:${generationId}`;
  useEffect(() => {
    if (!generationId) return;
    let active = true, attempts = 0;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const art = await getArtStatus(gameId, generationId, controller.signal);
        if (!active) return;
        setResult({ key, art }); setError('');
        if (art.status === 'ready') timer = setTimeout(poll, 240_000); // renew signed URLs
        else if (['pending', 'generating', 'failed_retryable'].includes(art.status) && ++attempts < 30)
          timer = setTimeout(poll, Math.min(15_000, 2000 * 1.3 ** attempts));
        else if (attempts >= 30) setError('Ainda processando. Reabra a campanha para consultar novamente.');
      } catch {
        if (active) setError('Não foi possível consultar o retrato. Nenhuma nova arte foi solicitada.');
      }
    };
    void poll();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [gameId, generationId, key, reload]);
  if (!generationId) return null;
  const art = result?.key === key ? result.art : null;
  const image = art?.status === 'ready' && !broken ? art.assets?.find(a => a.variant === 'full') : null;
  const financeMessage = art?.financial_status === 'uncertain'
    ? 'Resultado financeiro incerto: o saldo segue reservado para conferência. A geração não será repetida automaticamente.'
    : art?.credits_held ? 'Saldo reservado até a conclusão financeira da imagem.' : null;
  return <section className="generated-portrait" aria-label="Retrato do personagem">
    {financeMessage && <p role="status">{financeMessage}</p>}
    {image ? <>
      <button type="button" className="card__select" onClick={() => setExpanded(true)} aria-label="Ampliar retrato do personagem">
        <img src={image.url} width={image.width} height={image.height} alt="Retrato do personagem"
          onError={() => { if (reload === 0) setReload(1); else setBroken(true); }} />
      </button>
      {expanded && <ArtworkDialog url={image.url} alt="Retrato do personagem" onClose={() => setExpanded(false)} />}
    </> : <p role="status">{(broken && 'Retrato indisponível no momento.') || error || LABELS[art?.status || 'pending'] || 'Arte indisponível'}</p>}
  </section>;
}
