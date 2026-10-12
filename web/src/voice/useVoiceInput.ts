import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../api";
import { VoiceController } from "./controller";
import { webRecorder } from "./recorder";

export function useVoiceInput(onTranscript: (text: string) => void, sessionKey: string | undefined) {
  const callback = useRef(onTranscript);
  callback.current = onTranscript;
  const [controller] = useState(() => new VoiceController(webRecorder, transcribeAudio,
    state => setState(state), text => callback.current(text)));
  const [state, setState] = useState(controller.state);
  useEffect(() => {
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
