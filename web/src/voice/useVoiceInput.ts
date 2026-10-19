import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../api";
import { VoiceController, idle } from "./controller";
import { webRecorder } from "./recorder";

export function useVoiceInput(onTranscript: (text: string) => void, sessionKey: string | undefined) {
  const callback = useRef(onTranscript);
  useEffect(() => { callback.current = onTranscript; });
  const [state, setState] = useState(idle);
  // eslint-disable-next-line react-hooks/refs -- callbacks do controller leem o ref apenas em eventos, nunca no render
  const [controller] = useState(() => new VoiceController(webRecorder, transcribeAudio,
    state => setState(state), text => callback.current(text)));
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setState(controller.state);
    const leave = () => {
      if (controller.state.requesting || ["recording", "uploading", "transcribing"].includes(controller.state.phase)) controller.cancel();
    };
    const hidden = () => { if (document.visibilityState !== "visible") leave(); };
    document.addEventListener("visibilitychange", hidden);
    window.addEventListener("pagehide", leave);
    return () => {
      document.removeEventListener("visibilitychange", hidden);
      window.removeEventListener("pagehide", leave);
      controller.cancel(false);
    };
  }, [controller, sessionKey]);
  return { ...state, start: () => void controller.start(), stop: () => void controller.stop(),
    cancel: () => controller.cancel() };
}
