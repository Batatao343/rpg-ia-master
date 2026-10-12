import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { useVoiceInput } from "../src/voice/useVoiceInput";

function Capture({ session }: { session: string }) {
  const [text, setText] = useState("");
  const voice = useVoiceInput(setText, session);
  return <div>
    <p data-testid="phase">{voice.phase}</p><p data-testid="message">{voice.message}</p>
    <input aria-label="Transcript" value={text} onChange={e => setText(e.target.value)} />
    <button onClick={voice.start}>Record fixture</button><button onClick={voice.stop}>Stop fixture</button>
  </div>;
}
function Fixture() {
  const [session, setSession] = useState("a");
  const [mounted, setMounted] = useState(true);
  return <main>
    {mounted && <Capture session={session} />}
    <button onClick={() => setSession("b")}>Switch session</button>
    <button onClick={() => setMounted(v => !v)}>Toggle mount</button>
  </main>;
}
createRoot(document.getElementById("fixture")!).render(<StrictMode><Fixture /></StrictMode>);
