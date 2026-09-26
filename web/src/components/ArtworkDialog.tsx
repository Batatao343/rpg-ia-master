import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export function ArtworkDialog({ url, alt, onClose }: { url: string; alt: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = dialog.current;
    node?.showModal();
    return () => { node?.close(); previous?.focus(); };
  }, []);
  return createPortal(<dialog ref={dialog} className="art-dialog" aria-label={alt}
    onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
    <button type="button" className="btn art-dialog__close" onClick={onClose} autoFocus>Fechar imagem</button>
    <img src={url} alt={alt} />
  </dialog>, document.body);
}
