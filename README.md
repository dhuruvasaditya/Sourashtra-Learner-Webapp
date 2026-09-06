# Saurashtra learning app

Two pieces: a Mac recorder for collecting phrases, and a phone web app for learning them.
See `SPEC.md` for the full design.

## Recording phrases

Once:

```sh
ffmpeg -version || brew install ffmpeg    # skip if you already have it
uv venv
uv pip install -r requirements.txt
```

Then, every session:

```sh
uv run record.py
```

macOS will ask for microphone permission on the first recording; say yes.

### How a session works

The window shows one English prompt at a time, pulled from the queue in
`data/prompts.json`. For each one:

1. **● Record** — speaker says the phrase, then **■ Stop** (button, or `Ctrl-R` for both)
2. **▶ Play** — check the take. Not happy? Just record again, it overwrites.
3. Type the **Saurashtra** transliteration. `Word-by-word gloss` and `Note` are
   optional but worth the five seconds.
4. **Save & Next** (or `Ctrl-Return`)

Aim for 30 phrases in 20 minutes. The queue remembers where you are — anything
already recorded is skipped when you reopen the app.

### The other buttons

| Button | What it does |
|---|---|
| **Skip prompt** | Reject a prompt you don't want. Written to `data/skipped.json`, never offered again. |
| **+ Own phrase** | Add something not in the queue — type your own English, pick a category, record. Returns to the queue after saving. |
| **Re-record an existing id** | Type an id (e.g. `0007`), hit **Load**. Fixes a bad take or a typo without retyping everything. **Back to queue** when done. |

The English field is always editable, so you can reword a prompt before saving it.

## What gets written

```
data/phrases.json    the dataset — single source of truth
data/skipped.json    prompts you rejected
docs/phrases.json    copy of the dataset, served to the app
docs/audio/0042.mp3  one file per phrase
```

Every save writes all of these, so there is no export step. Committing and pushing
`docs/` is what publishes new phrases to the learners.

## The learning app

`docs/` is the whole app — one HTML file, no build step, no backend.

Preview it locally:

```sh
cd docs && python3 -m http.server
```

then open <http://localhost:8000>.

### What it does

**Practice** — a session of 20 cards: everything due for review, topped up with
new phrases. Each card asks you to produce the phrase *before* showing the
answer, then you grade yourself **Again** or **Got it**.

Cards climb three stages as they stick: hear the audio and guess the meaning →
see the English and say it aloud → see the English and type the transliteration.
A phrase with no audio yet starts at the "say it" stage instead.

Scheduling is Leitner boxes — **Got it** pushes the next review out to 2, 5, 12
then 30 days; **Again** drops it back to today and re-queues it before the
session ends.

**Browse** — searchable list grouped by category, matching English *and*
transliteration. Tap a row to hear it. The coloured dot shows how well you know it.

**Listen** — hands-free playlist for one category: phrase plays, pause to repeat,
next. Read along on screen.

### Progress

Stored in the browser under `saurashtra.progress.v1`. It survives reloads and app
restarts, but it is per-device — clearing Safari data or switching phones loses it.
**Export progress** on the home screen copies a blob that **Import** restores.

## Publishing

Push the repo to GitHub, then in Settings → Pages set the source to the `main`
branch, folder `/docs`. Anything you commit under `docs/` goes live.

On the iPhone: open the URL in Safari → Share → **Add to Home Screen**. It gets
the app icon and opens fullscreen with no browser chrome.
