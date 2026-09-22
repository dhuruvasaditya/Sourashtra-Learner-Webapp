#!/usr/bin/env python3
"""Flat review sheet for the whole phrase list.

    python3 review.py            # (re)generate data/review.txt
    python3 review.py apply      # delete anything missing from the sheet

Editing is delete-only: remove a line to drop that word or phrase. Recorded
entries are keyed by id, so you can retype the English freely; queued prompts
are keyed by their exact text, so changing one is reported rather than guessed
at. Audio for deleted entries moves to data/trash/ — nothing is unlinked.
"""
import json, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).parent
DATA, DOCS = ROOT / "data", ROOT / "docs"
SHEET = DATA / "review.txt"
HEAD = """\
# Delete any line you don't want, then run:  python3 review.py apply
#   ● recorded (has audio)   ○ to record   ✕ skipped, not being recorded
# Change ✕ to ○ to put a word back in the queue, or ○ to ✕ to park it.
# Delete the line entirely to drop it for good. Lines starting with # are ignored.
"""

def load():
    return (json.loads((DATA / "phrases.json").read_text()),
            json.loads((DATA / "prompts.json").read_text()))

def save(ph, pr):
    for name, obj in (("phrases.json", ph), ("prompts.json", pr)):
        text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
        (DATA / name).write_text(text)
        (DOCS / name).write_text(text)

def export():
    ph, pr = load()
    by = {}
    for x in ph: by.setdefault(x["category"], []).append(x)
    done = {x["en"].lower() for x in ph}
    sk = {x.lower() for x in json.loads((DATA / "skipped.json").read_text())}

    out = [HEAD]
    for c in pr["categories"]:
        rec = by.get(c["id"], [])
        todo = [p for p in c["prompts"] if p.lower() not in done and p.lower() not in sk]
        park = [p for p in c["prompts"] if p.lower() in sk]
        out.append(f"\n## {c['id']}  —  {c['label']}  "
                   f"({len(rec)} recorded, {len(todo)} to record)\n")
        for x in rec:
            out.append(f"{x['id']}  ● {x['en']:<40} {x['sa']}")
        for p in todo:
            out.append(f"      ○ {p}")
        for p in park:
            out.append(f"      ✕ {p}")
    SHEET.write_text("\n".join(out) + "\n")
    print(f"wrote {SHEET}  —  {len(ph)} recorded, "
          f"{sum(1 for c in pr['categories'] for p in c['prompts'])} prompts")

def apply():
    ph, pr = load()
    keep_ids, keep_txt, skip_txt = set(), set(), set()
    for line in SHEET.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if m := re.match(r"^(\d{4})\s+●\s+(.*)$", line):
            keep_ids.add(m.group(1))
        elif m := re.match(r"^○\s+(.*)$", line):
            keep_txt.add(m.group(1).strip().lower())
        elif m := re.match(r"^✕\s+(.*)$", line):
            skip_txt.add(m.group(1).strip().lower())

    trash = DATA / "trash"; trash.mkdir(exist_ok=True)
    dropped = [x for x in ph if x["id"] not in keep_ids]
    for x in dropped:
        if x.get("audio") and (a := DOCS / "audio" / x["audio"]).exists():
            shutil.move(str(a), trash / x["audio"])
    ph = [x for x in ph if x["id"] in keep_ids]

    unmatched, n_pr = [], 0
    for c in pr["categories"]:
        kept = []
        for p in c["prompts"]:
            low = p.lower()
            if low in {x["en"].lower() for x in ph} or low in keep_txt or low in skip_txt:
                kept.append(p)
            else:
                unmatched.append(f"{c['id']}: {p}"); n_pr += 1
        c["prompts"] = kept

    # Skipped entries that match no prompt line (wording drift, e.g. "okay fine"
    # vs the prompt "Okay / Fine") have no row to survive on. Carry them over
    # rather than silently dropping them.
    prior = {x.lower() for x in json.loads((DATA / "skipped.json").read_text())}
    sheet = {p.lower() for c in pr["categories"] for p in c["prompts"]}
    (DATA / "skipped.json").write_text(
        json.dumps(sorted(skip_txt | (prior - sheet)), indent=2, ensure_ascii=False) + "\n")
    save(ph, pr)
    print(f"removed {len(dropped)} recorded ({len(dropped)} audio files -> data/trash/) "
          f"and {n_pr} queued prompts")
    for x in dropped: print(f"  ● {x['id']} {x['en']}")
    for u in unmatched: print(f"  ○ {u}")
    export()

apply() if len(sys.argv) > 1 and sys.argv[1] == "apply" else export()
