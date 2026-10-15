"""Gera narração (TTS) e a timeline do vídeo a partir de ../roteiro.json.

Uso (de dentro de docs/descricao_projeto/video):
    python scripts/build_timeline.py          # só sintetiza cenas novas/alteradas
    python scripts/build_timeline.py --force  # re-sintetiza tudo
Saídas: public/audio/<cena>.wav, public/audio/_hashes.json e src/data/timeline.json
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

FPS = 30
AUDIO_LEAD = 12  # igual a SceneFrame.AUDIO_LEAD
TAIL = 24  # respiro depois da fala
TITLE_MIN = 5 * FPS

ROOT = Path(__file__).resolve().parent.parent
ROTEIRO = ROOT.parent / "roteiro.json"
AUDIO = ROOT / "public" / "audio"
OUT = ROOT / "src" / "data" / "timeline.json"

# Ajustes de pronúncia só para a fala (a legenda mostra o texto original).
SPOKEN = [
    (r"\bLangGraph\b", "Lang Graph"),
    (r"\bLangChain\b", "Lang Chain"),
    (r"\bFastAPI\b", "Fast A P I"),
    (r"\bAPI\b", "A P I"),
    (r"\bAPIs\b", "A P Is"),
    (r"\bLLMs?\b", "L L M"),
    (r"\bRAG\b", "rég"),
    (r"\bSSE\b", "S S E"),
    (r"\bJSON\b", "jêison"),
    (r"\bUUID\b", "U U I D"),
    (r"\bHP\b", "agá pê"),
    (r"\bXP\b", "xis pê"),
    (r"\bNPCs\b", "N P Cs"),
    (r"\bNPC\b", "N P C"),
    (r"\bCI\b", "C I"),
    (r"\bRLS\b", "R L S"),
    (r"\bCLI\b", "C L I"),
    (r"\bHTTP\b", "agá tê tê pê"),
    (r"\bpgvector\b", "pê gê vector"),
    (r"\bPostgres\b", "Póstgres"),
    (r"\bDeepSeek\b", "Dip Sík"),
    (r"\bGroq\b", "Gróc"),
    (r"\bGemini\b", "Gêmini"),
    (r"\bFAISS\b|\bFaiss\b", "Fais"),
    (r"\bReact\b", "Ri-ékt"),
    (r"\bVite\b", "Vit"),
    (r"\bPydantic\b", "Paidêntic"),
    (r"\bMockLLM\b", "Mók L L M"),
    (r"\bpytest\b", "pai test"),
    (r"\bplaytest\b", "plei test"),
    (r"\bplaytests\b", "plei tests"),
    (r"\bspecs?\b", "spéc"),
    (r"\bstoryteller\b", "stóri téler"),
    (r"\barchivist\b", "árquivist"),
    (r"\brouter\b", "râuter"),
]


def spoken(text: str) -> str:
    for pat, rep in SPOKEN:
        text = re.sub(pat, rep, text)
    return text


READ_CPS = 11  # caracteres por segundo: leitura confortável com visual animado ao lado


def reading_frames(text: str) -> int:
    """Duração de leitura da legenda quando não há narração (mínimo 3,5 s)."""
    return max(round(3.5 * FPS), round(len(text) / READ_CPS * FPS))


def wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        secs = w.getnframes() / w.getframerate()
    return max(1, round(secs * FPS))


def main() -> None:
    force = "--force" in sys.argv
    silent = "--silent" in sys.argv
    music = sys.argv[sys.argv.index("--music") + 1] if "--music" in sys.argv else None
    roteiro = Path(sys.argv[sys.argv.index("--roteiro") + 1]) if "--roteiro" in sys.argv else ROTEIRO
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else OUT
    data = json.loads(roteiro.read_text(encoding="utf-8"))
    AUDIO.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    hashes_file = AUDIO / "_hashes.json"
    hashes = json.loads(hashes_file.read_text(encoding="utf-8")) if hashes_file.exists() else {}

    jobs = []
    for ch in data["chapters"]:
        for sc in ch["scenes"]:
            text = spoken(sc["narration"])
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            out = AUDIO / f"{sc['id']}.wav"
            if silent:
                continue
            if force or hashes.get(sc["id"]) != h or not out.exists():
                jobs.append({"id": sc["id"], "text": text, "out": str(out)})
            hashes[sc["id"]] = h

    if jobs:
        jobs_file = ROOT / "public" / "_tts_jobs.json"
        jobs_file.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8-sig")
        print(f"Sintetizando {len(jobs)} cenas...")
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(ROOT / "scripts" / "tts.ps1"), "-JobsFile", str(jobs_file)],
            check=True,
        )
        jobs_file.unlink()
    hashes_file.write_text(json.dumps(hashes, indent=1), encoding="utf-8")

    scenes, chapters, frame = [], [], 0
    for ci, ch in enumerate(data["chapters"]):
        ch_start = frame
        for sc in ch["scenes"]:
            af = reading_frames(sc["narration"]) if silent else wav_frames(AUDIO / f"{sc['id']}.wav")
            dur = AUDIO_LEAD + af + TAIL
            if sc["visual"]["type"] == "title":
                dur = max(dur, TITLE_MIN)
            scenes.append({**sc, "audioFrames": af, "durationInFrames": dur,
                           "chapterIndex": ci, "chapterTitle": ch["title"], "color": ch["color"]})
            frame += dur
        chapters.append({"id": ch["id"], "title": ch["title"], "color": ch["color"],
                         "startFrame": ch_start, "frames": frame - ch_start})

    out_path.write_text(json.dumps({"title": data["title"], "fps": FPS, "chapters": chapters, "silent": silent, "music": music,
                               "scenes": scenes, "totalFrames": frame}, ensure_ascii=False),
                   encoding="utf-8")
    m, s = divmod(frame // FPS, 60)
    print(f"{len(scenes)} cenas, {len(chapters)} capítulos, duração {m}min{s:02d}s -> {out_path}")


if __name__ == "__main__":
    main()
