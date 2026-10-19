/** Hosted (serverless) has no ffmpeg: browsers transcode to mono 16 kHz PCM16 WAV before upload. */
export const WAV_SAMPLE_RATE = 16_000;

export function encodeWav(samples: Float32Array, sampleRate = WAV_SAMPLE_RATE): Uint8Array {
  const out = new Uint8Array(44 + samples.length * 2);
  const view = new DataView(out.buffer);
  const text = (offset: number, value: string) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
  text(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); text(8, "WAVE");
  text(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, "data"); view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff), true);
  }
  return out;
}

/** Decodes with Web Audio and resamples to mono 16 kHz. Any failure returns the original blob. */
export async function transcodeToWav(blob: Blob): Promise<Blob> {
  if (blob.type.split(";")[0].trim().toLowerCase() === "audio/wav") return blob;
  const g = globalThis as unknown as Record<string, typeof AudioContext | typeof OfflineAudioContext | undefined>;
  const Ctx = (g.AudioContext || g.webkitAudioContext) as typeof AudioContext | undefined;
  const Offline = (g.OfflineAudioContext || g.webkitOfflineAudioContext) as typeof OfflineAudioContext | undefined;
  if (!Ctx || !Offline) return blob;
  let ctx: AudioContext | undefined;
  try {
    ctx = new Ctx();
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    const length = Math.max(1, Math.ceil(decoded.duration * WAV_SAMPLE_RATE));
    const offline = new Offline(1, length, WAV_SAMPLE_RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return new Blob([encodeWav(rendered.getChannelData(0)) as BlobPart], { type: "audio/wav" });
  } catch { return blob; }
  finally { try { await ctx?.close?.(); } catch { /* ignore */ } }
}
