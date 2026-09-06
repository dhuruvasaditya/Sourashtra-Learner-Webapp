# Sourashtra Learner Webapp

Learn conversational Sourashtra from English — every phrase with a recording of a
native speaker, a transliteration, and a word-by-word gloss.

**→ [dhuruvasaditya.github.io/Sourashtra-Learner-Webapp](https://dhuruvasaditya.github.io/Sourashtra-Learner-Webapp/)**

Open it in Safari on an iPhone, then **Share → Add to Home Screen**. It gets an
icon and opens fullscreen, like an app. No install, no account, no App Store.

---

## Using the app

### Practice

Pick a mode, then pick what to practise — a single category, or everything
mixed. A session is about 20 cards, and the app tracks which ones are due.

| Mode | You see | You do |
|---|---|---|
| **See English → say it** | the English | say it aloud in Sourashtra, tap Reveal |
| **Hear it → guess the meaning** | audio plays | work out what it means, tap Reveal |

The category step matters: drilling *Food* before a family dinner beats a random
mix of everything. Each category shows how many phrases it holds and how many
are due. At the end of a session you can go another round, switch category, or
go home.

Reveal shows the transliteration, the English, the gloss, any usage note, and
plays the recording. Then grade yourself: **Again** or **Got it**. Saying the
phrase *before* revealing is the part that makes it stick — recognising an answer
feels like learning and isn't.

### Scheduling

Cards move through Leitner boxes. **Got it** pushes the next review further out;
**Again** drops it back to today and shows it again before the session ends.

| Box | Next review |
|---|---|
| 1 | today |
| 2 | in 2 days |
| 3 | in 5 days |
| 4 | in 12 days |
| 5 | in 30 days |

### Browse

Searchable list grouped by category, matching English *and* transliteration. Tap
a row to hear it. The coloured dot shows how well you know it. This is the one to
open thirty seconds before a phone call with family.

### Listen hands-free

Pick a category and it plays through it — phrase, pause to repeat, next — while
you read along. For dishes, driving, walking.

### Progress

Kept in the browser under `saurashtra.progress.v1`. It survives reloads and app
restarts, but it is **per device** — clearing Safari data or moving to a new phone
loses it. **Export progress** on the home screen copies a blob that **Import**
restores on the other device.

---

## Adding phrases

`record.py` is a small Tkinter tool for collecting new phrases with a speaker
sitting next to you. Mac only.

### Setup

```sh
ffmpeg -version || brew install ffmpeg    # skip if you already have it
uv venv
uv pip install -r requirements.txt
```

### Recording

```sh
uv run record.py
```

macOS asks for microphone permission the first time; say yes.

The window shows one English prompt at a time from the queue in
`data/prompts.json`. For each:

1. **● Record** — speaker says it, then **■ Stop** (or `Ctrl-R` for both)
2. **▶ Play** — check the take. Not happy? Record again, it overwrites.
3. Type the **Sourashtra** transliteration. Gloss and note are optional but
   worth the five seconds.
4. **Save & Next** (or `Ctrl-Return`)

Thirty phrases in twenty minutes is a realistic pace. The queue picks up where
you left off — anything already recorded is skipped, and phrases that have text
but no audio yet come first, prefilled, so you only need to hit Record.

Recordings are loudness-normalised at encode time, so takes from different days
and different mic distances all play back at the same volume.

### The other buttons

| Button | What it does |
|---|---|
| **Skip prompt** | Reject a prompt for good. Logged in `data/skipped.json`, never offered again. |
| **+ Own phrase** | Add something not in the queue — type your own English, pick a category, record. |
| **Re-record an existing id** | Type an id (e.g. `0007`) and hit **Load** to fix a bad take or a typo. **Back to queue** when done. |

The English field is always editable, so you can reword a prompt before saving.

### Publishing what you recorded

```sh
git add -A && git commit -m "more phrases" && git push
```

Live within a minute. The recorder writes straight into `docs/`, so there is no
build or export step.

---

## Layout

```
data/phrases.json     the dataset — single source of truth
data/prompts.json     recording queue, English prompts by category
data/skipped.json     prompts rejected during recording
record.py             the collection tool
docs/index.html       the entire app — one file, vanilla JS, no build step
docs/phrases.json     copy of the dataset, served to the app
docs/audio/0042.mp3   one recording per phrase
```

Every save from the recorder writes both copies of `phrases.json`.

`docs/` is the folder GitHub Pages serves — Pages only accepts the repo root or
`/docs`, which is the only reason for the name.

See `SPEC.md` for the design reasoning.
