"""Prompt-driven recorder for the Saurashtra phrase dataset.

Run with:  uv run record.py   (see README.md for setup)

Walks the recording queue in data/prompts.json, skipping prompts already
present in data/phrases.json. For each prompt: record audio, type the
transliteration, save. Writes web/audio/<id>.mp3 and appends to
data/phrases.json (mirrored to web/phrases.json).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np
import sounddevice as sd
import soundfile as sf

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
AUDIO_DIR = WEB_DIR / "audio"
PHRASES_PATH = DATA_DIR / "phrases.json"
PROMPTS_PATH = DATA_DIR / "prompts.json"
SKIPPED_PATH = DATA_DIR / "skipped.json"
WEB_PHRASES_PATH = WEB_DIR / "phrases.json"

SAMPLE_RATE = 44100
CHANNELS = 1
MP3_BITRATE = "64k"
# Broadcast-speech loudness target. Applied at encode time so takes recorded on
# different days, at different mic distances, all play back at the same volume.
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

@dataclass
class QueueItem:
    """One item still awaiting a recording.

    Normally an unrecorded English prompt. When ``phrase_id`` is set it is an
    existing phrase that has text but no audio yet, so saving updates that
    entry in place instead of appending a new one.
    """

    category: str
    label: str
    prompt: str
    phrase_id: str | None = None


def normalize(text: str) -> str:
    """Loose key for matching a prompt against an existing phrase's English."""
    return " ".join(text.lower().replace("/", " ").split()).strip(" ?.!")


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_phrases(phrases: list[dict]) -> None:
    """Write the dataset and mirror it into web/ for the app to fetch."""
    payload = json.dumps(phrases, ensure_ascii=False, indent=2) + "\n"
    PHRASES_PATH.write_text(payload, encoding="utf-8")
    WEB_DIR.mkdir(exist_ok=True)
    WEB_PHRASES_PATH.write_text(payload, encoding="utf-8")


def next_id(phrases: list[dict]) -> str:
    highest = max((int(p["id"]) for p in phrases), default=0)
    return f"{highest + 1:04d}"


def load_skipped() -> set[str]:
    """Prompts deliberately rejected — kept so they never re-enter the queue."""
    if not SKIPPED_PATH.exists():
        return set()
    return {normalize(p) for p in load_json(SKIPPED_PATH)}


def save_skipped(skipped: set[str]) -> None:
    payload = json.dumps(sorted(skipped), ensure_ascii=False, indent=2) + "\n"
    SKIPPED_PATH.write_text(payload, encoding="utf-8")


def build_queue(
    prompts: dict, phrases: list[dict], skipped: set[str] | None = None
) -> list[QueueItem]:
    """Everything still needing a recording, in category order.

    Phrases that already have text but no audio come first — they are the
    cheapest to finish, since only the microphone work is left.
    """
    labels = {c["id"]: c["label"] for c in prompts["categories"]}
    items = [
        QueueItem(p["category"], labels.get(p["category"], p["category"]),
                  p["en"], p["id"])
        for p in phrases if not p["audio"]
    ]
    done = {normalize(p["en"]) for p in phrases} | (skipped or set())
    for category in prompts["categories"]:
        for prompt in category["prompts"]:
            if normalize(prompt) not in done:
                items.append(QueueItem(category["id"], category["label"], prompt))
    return items


# --------------------------------------------------------------------------
# audio
# --------------------------------------------------------------------------

class Recorder:
    """Microphone capture into an in-memory buffer."""

    def __init__(self) -> None:
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self.audio: np.ndarray | None = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        self._chunks = []
        self.audio = None

        def callback(indata, _frames, _time, status):
            if status:
                print(f"audio status: {status}")
            self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback
        )
        self._stream.start()

    def stop(self) -> float:
        """Stop capture and return the duration in seconds."""
        if self._stream is None:
            return 0.0
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self.audio = (
            np.concatenate(self._chunks) if self._chunks else np.zeros((0, CHANNELS))
        )
        return len(self.audio) / SAMPLE_RATE

    def play(self) -> None:
        if self.audio is not None and len(self.audio):
            sd.play(self.audio, SAMPLE_RATE)

    def write_mp3(self, destination: Path) -> None:
        """Encode the buffer to mp3 — iOS Safari is picky about formats."""
        if self.audio is None or not len(self.audio):
            raise ValueError("nothing recorded")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)
        try:
            sf.write(wav_path, self.audio, SAMPLE_RATE)
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                 "-af", LOUDNORM,
                 "-ac", "1", "-ar", str(SAMPLE_RATE), "-b:a", MP3_BITRATE,
                 str(destination)],
                check=True,
            )
        finally:
            wav_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# ui
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Saurashtra recorder")
        self.geometry("720x600")
        self.configure(padx=24, pady=20)

        self.prompts = load_json(PROMPTS_PATH)
        self.phrases = load_json(PHRASES_PATH)
        self.skipped = load_skipped()
        self.queue = build_queue(self.prompts, self.phrases, self.skipped)
        self.categories = [(c["id"], c["label"]) for c in self.prompts["categories"]]
        self.position = 0
        self.mode = "queue"  # queue | custom | edit
        self.edit_id: str | None = None
        self.recorder = Recorder()

        self._build_widgets()
        self._show_current()

    # -- layout ------------------------------------------------------------

    def _build_widgets(self) -> None:
        self.counter = tk.Label(self, text="", font=("Helvetica", 13), fg="#888")
        self.counter.pack(anchor="w")

        self.en = self._field("English", font_size=24)
        self.sa = self._field("Saurashtra (transliteration)", font_size=20)
        self.lit = self._field("Word-by-word gloss")
        self.note = self._field("Note (optional)")

        category_row = tk.Frame(self)
        category_row.pack(fill="x", pady=(0, 4))
        tk.Label(
            category_row, text="Category", font=("Helvetica", 11), fg="#888"
        ).pack(side="left")
        self._label_to_id = {label: cid for cid, label in self.categories}
        self.category_var = tk.StringVar()
        ttk.Combobox(
            category_row,
            textvariable=self.category_var,
            values=[label for _, label in self.categories],
            state="readonly",
            width=22,
        ).pack(side="left", padx=8)

        controls = tk.Frame(self)
        controls.pack(fill="x", pady=(18, 8))
        self.record_btn = tk.Button(
            controls, text="● Record", width=12, command=self.toggle_record
        )
        self.record_btn.pack(side="left")
        tk.Button(controls, text="▶ Play", width=10, command=self.recorder.play).pack(
            side="left", padx=6
        )
        tk.Button(
            controls, text="Save & Next", width=14, command=self.save_and_next
        ).pack(side="left", padx=6)
        self.skip_btn = tk.Button(
            controls, text="Skip prompt", width=12, command=self.skip
        )
        self.skip_btn.pack(side="left")
        tk.Button(
            controls, text="+ Own phrase", width=13, command=self.start_custom
        ).pack(side="left", padx=6)

        self.status = tk.Label(self, text="", font=("Helvetica", 12), fg="#666")
        self.status.pack(anchor="w", pady=(4, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=16)

        redo = tk.Frame(self)
        redo.pack(fill="x")
        tk.Label(redo, text="Re-record an existing id:").pack(side="left")
        self.redo_entry = tk.Entry(redo, width=8)
        self.redo_entry.pack(side="left", padx=6)
        tk.Button(redo, text="Load", command=self.load_existing).pack(side="left")
        tk.Button(redo, text="Back to queue", command=self.exit_edit).pack(
            side="left", padx=6
        )

        self.bind("<Control-r>", lambda _e: self.toggle_record())
        self.bind("<Control-Return>", lambda _e: self.save_and_next())

    def _field(self, label: str, font_size: int = 15) -> tk.Entry:
        tk.Label(self, text=label, font=("Helvetica", 11), fg="#888").pack(anchor="w")
        entry = tk.Entry(self, font=("Helvetica", font_size))
        entry.pack(fill="x", pady=(2, 12), ipady=5)
        return entry

    # -- state -------------------------------------------------------------

    def _current(self) -> QueueItem | None:
        if self.position < len(self.queue):
            return self.queue[self.position]
        return None

    def _category_progress(self, category: str) -> tuple[int, int]:
        total = sum(
            len(c["prompts"]) for c in self.prompts["categories"] if c["id"] == category
        )
        done = sum(1 for p in self.phrases if p["category"] == category)
        return done, total

    def _set_category(self, category_id: str) -> None:
        for cid, label in self.categories:
            if cid == category_id:
                self.category_var.set(label)
                return
        self.category_var.set(self.categories[0][1])

    def _show_current(self) -> None:
        self._clear_fields()
        self.recorder.audio = None
        self.skip_btn.config(state="normal" if self.mode == "queue" else "disabled")

        if self.mode == "edit":
            entry = next(p for p in self.phrases if p["id"] == self.edit_id)
            self.counter.config(text=f"Editing {entry['id']}")
            self.en.insert(0, entry["en"])
            self.sa.insert(0, entry["sa"])
            self.lit.insert(0, entry["lit"])
            self.note.insert(0, entry["note"])
            self._set_category(entry["category"])
            self.status.config(text="Record a new take, or just fix the text.")
            self.sa.focus_set()
            return

        if self.mode == "custom":
            self.counter.config(text="Your own phrase")
            self._set_category(self.categories[0][0])
            self.status.config(text="Type the English, pick a category, record, save.")
            self.en.focus_set()
            return

        item = self._current()
        if item is None:
            self.counter.config(text="")
            self.status.config(
                text=f"Queue done — {len(self.phrases)} phrases recorded. "
                     f'Use "+ Own phrase" to keep adding.'
            )
            return

        done, total = self._category_progress(item.category)
        self.counter.config(
            text=f"{item.label} — {done + 1} / {total}      "
                 f"(queue: {self.position + 1} of {len(self.queue)})"
        )
        self.en.insert(0, item.prompt)
        self._set_category(item.category)

        if item.phrase_id:      # text already written, only audio is missing
            entry = next(p for p in self.phrases if p["id"] == item.phrase_id)
            self.sa.insert(0, entry["sa"])
            self.lit.insert(0, entry["lit"])
            self.note.insert(0, entry["note"])
            self.status.config(
                text=f"{entry['id']} has text but no audio — just record it."
            )
        else:
            self.status.config(text="Ctrl-R to record · Ctrl-Return to save")
        self.sa.focus_set()

    def _clear_fields(self) -> None:
        for entry in (self.en, self.sa, self.lit, self.note):
            entry.delete(0, tk.END)

    # -- actions -----------------------------------------------------------

    def toggle_record(self) -> None:
        if self.recorder.is_recording:
            seconds = self.recorder.stop()
            self.record_btn.config(text="● Record", fg="black")
            self.status.config(text=f"Recorded {seconds:.1f}s — play it back to check.")
        else:
            self.recorder.start()
            self.record_btn.config(text="■ Stop", fg="red")
            self.status.config(text="Recording…")

    def save_and_next(self) -> None:
        if self.recorder.is_recording:
            self.toggle_record()

        english = self.en.get().strip()
        sa = self.sa.get().strip()
        if not english or not sa:
            self.status.config(text="English and transliteration are both required.")
            return

        category = self._label_to_id.get(self.category_var.get(), self.categories[0][0])
        has_audio = self.recorder.audio is not None and len(self.recorder.audio)

        # A queued phrase that already exists updates in place, so finishing its
        # audio does not create a second copy of the same phrase.
        queued = self._current() if self.mode == "queue" else None
        if queued is not None and queued.phrase_id:
            entry = next(p for p in self.phrases if p["id"] == queued.phrase_id)
            entry.update(
                en=english, sa=sa, category=category,
                lit=self.lit.get().strip(), note=self.note.get().strip(),
            )
            if has_audio:
                self.recorder.write_mp3(AUDIO_DIR / f"{entry['id']}.mp3")
                entry["audio"] = f"{entry['id']}.mp3"
            save_phrases(self.phrases)
            self.position += 1
            self._show_current()
            self.status.config(text=f"Updated {entry['id']}.")
            return

        if self.mode == "edit":
            entry = next(p for p in self.phrases if p["id"] == self.edit_id)
            entry.update(
                en=english, sa=sa, category=category,
                lit=self.lit.get().strip(), note=self.note.get().strip(),
            )
            if has_audio:
                self.recorder.write_mp3(AUDIO_DIR / f"{entry['id']}.mp3")
                entry["audio"] = f"{entry['id']}.mp3"
            save_phrases(self.phrases)
            self.status.config(text=f"Updated {entry['id']}.")
            return

        if self.mode == "queue" and self._current() is None:
            self.status.config(text='Queue is done — use "+ Own phrase" to add more.')
            return

        if not has_audio and not messagebox.askyesno(
            "No audio", "Save this phrase without a recording?"
        ):
            return

        phrase_id = next_id(self.phrases)
        audio_name = None
        if has_audio:
            self.recorder.write_mp3(AUDIO_DIR / f"{phrase_id}.mp3")
            audio_name = f"{phrase_id}.mp3"

        self.phrases.append({
            "id": phrase_id,
            "sa": sa,
            "en": english,
            "lit": self.lit.get().strip(),
            "audio": audio_name,
            "category": category,
            "note": self.note.get().strip(),
        })
        save_phrases(self.phrases)

        if self.mode == "queue":
            self.position += 1
        else:
            self.mode = "queue"  # after one custom phrase, drop back into the queue
        self._show_current()
        self.status.config(text=f"Saved {phrase_id}.")

    def skip(self) -> None:
        """Reject a prompt permanently — recorded in data/skipped.json."""
        if self.mode != "queue":
            return
        if self.recorder.is_recording:
            self.recorder.stop()
            self.record_btn.config(text="● Record", fg="black")
        item = self._current()
        if item is None:
            return
        self.position += 1
        if item.phrase_id:
            # Already in the dataset — rejecting the prompt would not remove it,
            # so this only defers it. Delete the phrase if you want it gone.
            self._show_current()
            self.status.config(
                text=f"Left {item.phrase_id} without audio — back next session."
            )
            return
        self.skipped.add(normalize(item.prompt))
        save_skipped(self.skipped)
        self._show_current()
        self.status.config(text=f'Skipped "{item.prompt}" — it will not come back.')

    def start_custom(self) -> None:
        self.mode = "custom"
        self.edit_id = None
        self._show_current()

    def load_existing(self) -> None:
        wanted = self.redo_entry.get().strip().zfill(4)
        if not any(p["id"] == wanted for p in self.phrases):
            self.status.config(text=f"No phrase with id {wanted}.")
            return
        self.mode = "edit"
        self.edit_id = wanted
        self._show_current()

    def exit_edit(self) -> None:
        self.mode = "queue"
        self.edit_id = None
        self._show_current()


def main() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found — install it with: brew install ffmpeg")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    App().mainloop()


if __name__ == "__main__":
    main()
