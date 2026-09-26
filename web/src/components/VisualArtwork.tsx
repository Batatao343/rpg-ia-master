import { useState } from "react";
import type { VisualAsset } from "../types";
import { ArtworkDialog } from './ArtworkDialog';

export function VisualArtwork({ asset, name, caption, className = "", variant = "portrait", expandable = true }: {
  asset: VisualAsset | null;
  name: string;
  caption?: string;
  className?: string;
  variant?: 'card' | 'portrait';
  expandable?: boolean;
}) {
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const assetKey = asset ? `${asset.asset_id}:${asset.variants.display.url}` : '';
  if (!asset || failedKey === assetKey) {
    return (
      <figure className={`visual-art visual-art--fallback ${className}`}>
        <div className="visual-art__monogram" aria-hidden>{name.trim().charAt(0) || "?"}</div>
        <figcaption><strong>{name}</strong>{caption && <span>{caption}</span>}</figcaption>
      </figure>
    );
  }
  const { thumbnail, display } = asset.variants;
  return (
    <figure className={`visual-art ${className}`} style={{ backgroundColor: asset.placeholder_color }}>
      <img
        src={display.url}
        srcSet={`${thumbnail.url} ${thumbnail.width}w, ${display.url} ${display.width}w`}
        sizes={variant === 'card' ? '(max-width: 600px) 90vw, (max-width: 1000px) 42vw, 280px' : '(max-width: 600px) 92vw, 720px'}
        width={display.width}
        height={display.height}
        alt={asset.alt}
        loading="lazy"
        onError={() => setFailedKey(assetKey)}
      />
      {expandable && <button type="button" className="art-expand" aria-label={`Ampliar imagem de ${name}`}
        onClick={() => setExpandedKey(assetKey)}>Ampliar</button>}
      {expandedKey === assetKey && <ArtworkDialog url={display.url} alt={asset.alt} onClose={() => setExpandedKey(null)} />}
      {(name || caption) && <figcaption><strong>{name}</strong>{caption && <span>{caption}</span>}</figcaption>}
    </figure>
  );
}
