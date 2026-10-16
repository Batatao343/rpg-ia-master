import { transcodeToWav } from "./wav";

export const MAX_RECORDING_MS = 60_000;
export const MAX_AUDIO_BYTES = 8 * 1024 * 1024;
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm", "audio/ogg"];

/** Native implementations can replace this adapter without changing the composer. */
export interface Recording {
  stop(): Promise<Blob>;
  cancel(): void;
}
export interface RecorderAdapter {
  start(signal: AbortSignal, failed?: (error: Error) => void): Promise<Recording>;
}

export const webRecorder: RecorderAdapter = {
  async start(signal, failed) {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") {
      throw new Error("Gravação indisponível neste navegador. Continue digitando sua ação.");
    }
    const mimeType = MIME_TYPES.find(type => MediaRecorder.isTypeSupported(type));
    if (!mimeType) throw new Error("Formato de áudio não suportado. Continue digitando sua ação.");
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const release = () => stream.getTracks().forEach(track => track.stop());
    if (signal.aborted) { release(); throw new DOMException("Cancelado", "AbortError"); }
    let recorder: MediaRecorder;
    try { recorder = new MediaRecorder(stream, { mimeType }); }
    catch (error) { release(); throw error; }
    let chunks: Blob[] = [];
    let cancelled = false;
    let stopping = false;
    let size = 0;
    let failure: Error | undefined;
    let resolve!: (audio: Blob) => void;
    let reject!: (error: Error) => void;
    const result = new Promise<Blob>((yes, no) => { resolve = yes; reject = no; });
    // Cancellation may occur before any caller requests the result.
    void result.catch(() => {});
    const stop = () => {
      if (!stopping) {
        stopping = true;
        try { if (recorder.state !== "inactive") recorder.stop(); }
        catch (error) {
          signal.removeEventListener("abort", cancel);
          reject(error instanceof Error ? error : new Error("Falha ao parar gravação."));
        }
        finally { release(); }
      }
      return result;
    };
    const cancel = () => {
      cancelled = true;
      chunks = [];
      void stop();
    };
    recorder.ondataavailable = event => {
      if (cancelled || failure) return;
      size += event.data.size;
      if (size > MAX_AUDIO_BYTES) {
        failure = new Error("Áudio muito grande. Grave uma ação mais curta.");
        chunks = [];
        void stop();
        failed?.(failure);
      } else if (event.data.size) chunks.push(event.data);
    };
    recorder.onerror = () => {
      failure = new Error("Não foi possível gravar. Continue digitando sua ação.");
      chunks = [];
      void stop();
      reject(failure);
      failed?.(failure);
    };
    recorder.onstop = () => {
      release();
      signal.removeEventListener("abort", cancel);
      if (cancelled) reject(new DOMException("Cancelado", "AbortError"));
      else if (failure) reject(failure);
      else {
        const raw = new Blob(chunks, { type: recorder.mimeType || mimeType });
        void transcodeToWav(raw).then(resolve, () => resolve(raw));
      }
      chunks = [];
    };
    signal.addEventListener("abort", cancel, { once: true });
    try { recorder.start(250); }
    catch (error) { signal.removeEventListener("abort", cancel); release(); throw error; }
    return { stop, cancel };
  },
};
