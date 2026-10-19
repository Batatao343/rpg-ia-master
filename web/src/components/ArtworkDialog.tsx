import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export function ArtworkDialog({ url, alt, onClose }: { url: string; alt: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; });
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = dialog.current;
    node?.showModal();
    // Clique no backdrop fecha (listener nativo: o <dialog> não é um alvo interativo para o JSX).
    const onBackdrop = (e: MouseEvent) => { if (e.target === node) onCloseRef.current(); };
    node?.addEventListener("click", onBackdrop);
    return () => { node?.removeEventListener("click", onBackdrop); node?.close(); previous?.focus(); };
  }, []);
  return createPortal(<dialog ref={dialog} className="art-dialog" aria-label={alt}
    onCancel={onClose}>
    <button type="button" className="btn art-dialog__close" onClick={onClose}>Fechar imagem</button>
    <img src={url} alt={alt} />
  </dialog>, document.body);
}
