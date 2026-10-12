import { MAX_AUDIO_BYTES, MAX_RECORDING_MS, type RecorderAdapter, type Recording } from "./recorder";

export type VoicePhase = "idle" | "recording" | "uploading" | "transcribing" | "error";
export interface VoiceState { phase: VoicePhase; seconds: number; requesting: boolean; message: string }
export type Transcribe = (audio: Blob, signal: AbortSignal, uploaded: () => void) => Promise<string>;
const idle = (): VoiceState => ({ phase: "idle", seconds: 0, requesting: false, message: "" });

/** Owns one ephemeral capture/request. Generation fencing discards late callbacks. */
export class VoiceController {
  state = idle();
  private generation = 0;
  private abort?: AbortController;
  private recording?: Recording;
  private deadline?: ReturnType<typeof setTimeout>;
  private counter?: ReturnType<typeof setInterval>;
  constructor(private adapter: RecorderAdapter, private transcribe: Transcribe,
    private changed: (state: VoiceState) => void, private transcript: (text: string) => void) {}

  private update(state: Partial<VoiceState>) {
    this.state = { ...this.state, ...state };
    this.changed(this.state);
  }
  private clearTimers() { clearTimeout(this.deadline); clearInterval(this.counter); }

  async start() {
    if (this.state.requesting || !["idle", "error"].includes(this.state.phase)) return;
    const generation = ++this.generation;
    const abort = this.abort = new AbortController();
    this.update({ ...idle(), requesting: true, message: "Aguardando permissão do microfone…" });
    try {
      const recording = await this.adapter.start(abort.signal, error => this.fail(error, generation));
      if (generation !== this.generation) { recording.cancel(); return; }
      this.recording = recording;
      const started = Date.now();
      this.update({ phase: "recording", requesting: false, message: "Gravando. Pare quando terminar." });
      this.counter = setInterval(() => this.update({ seconds: Math.min(60, Math.floor((Date.now() - started) / 1000)) }), 250);
      this.deadline = setTimeout(() => void this.stop(), MAX_RECORDING_MS);
    } catch (error) { this.fail(error, generation); }
  }

  async stop() {
    if (this.state.phase !== "recording" || !this.recording || !this.abort) return;
    const generation = this.generation;
    const recording = this.recording;
    const signal = this.abort.signal;
    this.recording = undefined;
    this.clearTimers();
    this.update({ phase: "uploading", message: "Enviando áudio…" });
    try {
      const audio = await recording.stop();
      if (generation !== this.generation) return;
      if (!audio.size) throw new Error("Nenhum áudio capturado. Tente novamente ou digite sua ação.");
      if (audio.size > MAX_AUDIO_BYTES) throw new Error("Áudio muito grande. Grave uma ação mais curta.");
      const text = await this.transcribe(audio, signal, () => {
        if (generation === this.generation) this.update({ phase: "transcribing", message: "Transcrevendo áudio…" });
      });
      if (generation !== this.generation) return;
      if (!text.trim()) throw new Error("Não reconheci sua fala. Tente novamente ou digite sua ação.");
      this.transcript(text.trim());
      this.update({ ...idle(), message: "Transcrição pronta. Edite o texto e pressione Agir para enviar." });
    } catch (error) { this.fail(error, generation); }
  }

  cancel(notify = true) {
    ++this.generation;
    this.clearTimers();
    this.abort?.abort();
    this.recording?.cancel();
    this.recording = undefined;
    this.abort = undefined;
    if (notify) this.update({ ...idle(), message: "Gravação cancelada. Seu texto foi preservado." });
    else this.state = idle();
  }
  private fail(error: unknown, generation: number) {
    if (generation !== this.generation) return;
    this.cancel(false);
    const denied = error instanceof DOMException && ["NotAllowedError", "SecurityError"].includes(error.name);
    this.update({ phase: "error", requesting: false, message: denied
      ? "Permissão do microfone negada. Autorize nas configurações do navegador ou continue digitando."
      : error instanceof Error ? error.message : "Falha na transcrição. Continue digitando sua ação." });
  }
}
