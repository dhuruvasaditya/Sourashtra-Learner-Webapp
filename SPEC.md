# Saurashtra Learning App — Spec

A phone-friendly web app for learning conversational Saurashtra from English,
plus a desktop tool for collecting the data. Two users. No backend.

## Assumptions (fixed, do not add fields for these)

- **The learner is female.** All first-person phrases are recorded in the female
  speaker form. No gender field.
- **All speech is respectful register.** No register field.
- **No number or direction vocabulary.** English is fine for those.
- **No sentence patterns with slot substitution.** Record concrete full
  sentences instead: `"I want tea"` and `"I want water"` are two separate items,
  each with its own audio. Simpler to collect, simpler to learn, simpler to build.

## Repo layout

```
data/
  phrases.json      # the dataset (single source of truth)
  prompts.json      # recording queue: English prompts by category
record.py           # Tkinter collection tool (Mac)
docs/
  index.html        # the entire app — one file, vanilla JS, no build step
  phrases.json      # copy of data/phrases.json, written by record.py
  audio/0001.mp3 ...
```

Hosting: GitHub Pages, serving `docs/`. Add to Home Screen on iPhone.

## Data schema

`phrases.json` is a flat array. Six fields, nothing else.

```json
{
  "id": "0042",
  "sa": "thumi kaithiryaya?",
  "en": "Have you eaten?",
  "lit": "you eaten-Q",
  "audio": "0042.mp3",
  "category": "food",
  "note": "Used constantly as a general greeting, like 'how are you'."
}
```

| Field | Meaning |
|---|---|
| `id` | Zero-padded 4-digit string. Also the audio filename stem. |
| `sa` | Saurashtra in Latin transliteration. The primary display text. |
| `en` | Natural English meaning — not a literal translation. |
| `lit` | Word-by-word gloss. Costs seconds to write, and it is what lets the learner start decomposing phrases instead of memorizing opaque blobs. Empty string if unclear. |
| `audio` | Filename in `docs/audio/`. `null` until recorded. |
| `category` | One of the ids in `prompts.json`. |
| `note` | Usage hint from the speaker. Optional, often the most valuable field. |

## Romanization key

Decide once, apply everywhere — inconsistent spelling across 250 entries makes
search useless and confuses the ear.

- Long vowels doubled: `aa`, `ee`, `oo`
- Gemination doubled: `hallu`, `angum`
- `th` = dental t (as in `thumi`), `t` = retroflex
- Question suffix written attached: `kalaai` → `kalaaiya?`
- Always end questions with `?`

Patterns visible in the seed data (confirm with the speaker before relying on them):

- `-ya` is a question suffix: `kalaai` (know) → `kalaaiya?` (do you know?)
- `thumi` = you (subject), `thunga` = to you (dative) — `thunga bhook keraras ya?`
- `kai` = what, `konu` = who, `illa` = this, `enu` = that
- `me` = I

## Learning design

The dataset is small on purpose. ~250 items is enough for comfortable everyday
domestic conversation. Everything below is about making those 250 stick.

### Home screen

One primary button: **Practice today**. Two secondary links: **Browse** and
**Listen**. Nothing else. Never show a grid of options.

### Practice session

Ten minutes, ~20 cards: 5 new + 15 due for review. The learner picks the mode
from the home screen; it applies to the whole session:

| Mode | Shown | Learner does | Then reveals |
|---|---|---|---|
| **Listen** | audio auto-plays | guess the meaning | English + `sa` + `lit` |
| **Recall** | English text | **says it out loud**, taps Reveal | audio + `sa` + `lit` |

Recognition feels like learning and isn't. The learner must produce the phrase
before seeing the answer — that retrieval effort is the entire mechanism.

A typing mode was built and removed: spelling a transliteration is not a skill
worth drilling, and marking a phrase wrong over a doubled vowel is noise.

After each reveal: two buttons, **Again** and **Got it**. That is the whole
grading UI.

### Scheduling — Leitner boxes

| Box | Next review |
|---|---|
| 1 | today |
| 2 | +2 days |
| 3 | +5 days |
| 4 | +12 days |
| 5 | +30 days |

**Got it** promotes one box, **Again** drops straight to box 1. The mode is the
learner's choice, so boxes only control scheduling.

State lives in `localStorage`. No accounts. Provide a one-tap export/import of
the progress blob so a phone reset doesn't erase six months of work.

### Browse mode

Flat searchable list, grouped by category. Search must match **both** English
and transliteration. This is what gets opened thirty seconds before a phone call
with family — make it fast and make it the second thing on the home screen.

### Listen mode

Hands-free playlist for one category: audio → pause for the learner to repeat →
next item, with the card on screen to read. For dishes, driving, walking. Roughly
twenty lines of JS and it is where passive hours turn into real exposure.
No text-to-speech — a synthetic English voice reading the answer is unpleasant
and adds nothing over the text already on screen.

## Recorder requirements (`record.py`, Tkinter)

**Prompt-driven, not blank-form-driven.** The tool loads `data/prompts.json`,
skips prompts already present in `phrases.json`, and walks the remainder one at
a time: English prompt on screen → speaker says it → record → fill in `sa`,
`lit`, `note` → save → next. Staring at an empty box asking "what should we add
next?" is what kills a recording session at item 15. With a queue, 30 items in
20 minutes is realistic.

- Audio: capture WAV via `sounddevice`, convert to **mp3** with `ffmpeg`
  (iOS Safari is picky). Save as `docs/audio/<id>.mp3`.
- Buttons: Record / Stop / Play / Save & Next / Skip.
- Save appends to `data/phrases.json` and copies it to `docs/phrases.json`.
- Show a progress counter: `food — 7 / 18`.
- Allow re-recording an existing id (fix a bad take without re-typing text).
