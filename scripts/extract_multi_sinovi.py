"""
Extract kanji-only vocab that involves any kanji with multiple Sino-Vietnamese
readings for manual review

For each kanji whose `sinovi` field contains more than one reading (comma-
separated, e.g. "THÌ, THỜI"), collect every kanji-only compound *anywhere in
the corpus* that contains that kanji, not just the compounds listed under
that kanji's own `vocabulary` array, since the top-N-per-kanji limit means a
multi-reading kanji can appear in another kanji's vocab list without appearing
in its own

Output shape (data/multi_sinovi.json):

    {
      "character": {
        "sinovi": "READING 1, READING 2",
        "vocabulary": [
          { "word": "...", "sinovi": "...", "reviewed": true|false },
          ...
        ]
      },
      ...
    }

Each entry carries a `reviewed` boolean. On regeneration:
  - Entries preserved from an existing multi_sinovi.json keep their existing
    `reviewed` value, defaulting to `true` if missing (i.e. all previously
    hand-corrected entries are treated as reviewed on first run)
  - Newly-discovered entries are added with `reviewed: false`

Flip `reviewed` to `true` as you finish each entry. `bake_multi_sinovi.py`
only writes corrections back for entries with `reviewed: true`

Usage:
    python scripts/extract_multi_sinovi.py
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KANJI_JSON_PATH = DATA_DIR / "kanji.json"
OUT_PATH = DATA_DIR / "multi_sinovi.json"


def main():
    with KANJI_JSON_PATH.open(encoding="utf-8") as f:
        kanji = json.load(f)

    # Existing entries: {char: {word: {"sinovi": ..., "reviewed": bool}}}
    existing: dict[str, dict[str, dict]] = {}
    if OUT_PATH.exists():
        with OUT_PATH.open(encoding="utf-8") as f:
            for char, entry in json.load(f).items():
                existing[char] = {
                    v["word"]: {
                        "sinovi": v["sinovi"],
                        # If a legacy file has no `reviewed` field, treat as already reviewed
                        "reviewed": v.get("reviewed", True),
                    }
                    for v in entry.get("vocabulary", [])
                }

    # Global de-duplicated word -> first-seen sinovi (kanji-only compounds only)
    word_to_sinovi: dict[str, str] = {}
    for entry in kanji.values():
        for v in entry.get("vocabulary", []):
            if not v.get("sinovi"):
                continue
            word_to_sinovi.setdefault(v["word"], v["sinovi"])

    # Kanji with multi-reading sinovi
    multi_kanji = {c: e["sinovi"] for c, e in kanji.items() if "," in e.get("sinovi", "")}

    out: dict[str, dict] = {}
    preserved = 0
    new_entries = 0
    orphan_preserved = 0

    for char, sinovi in multi_kanji.items():
        seen_words: set[str] = set()
        vocab_out = []
        for word, current_sinovi in word_to_sinovi.items():
            if char not in word:
                continue
            existing_entry = existing.get(char, {}).get(word)
            if existing_entry is not None:
                vocab_out.append({
                    "word": word,
                    "sinovi": existing_entry["sinovi"],
                    "reviewed": existing_entry["reviewed"],
                })
                preserved += 1
            else:
                vocab_out.append({
                    "word": word,
                    "sinovi": current_sinovi,
                    "reviewed": False,
                })
                new_entries += 1
            seen_words.add(word)

        # Carry over any hand-correction the new corpus scan didn't pick up
        for word, existing_entry in existing.get(char, {}).items():
            if word in seen_words:
                continue
            vocab_out.append({
                "word": word,
                "sinovi": existing_entry["sinovi"],
                "reviewed": existing_entry["reviewed"],
            })
            orphan_preserved += 1

        if not vocab_out:
            continue
        vocab_out.sort(key=lambda v: v["word"])
        out[char] = {"sinovi": sinovi, "vocabulary": vocab_out}

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    total = sum(len(v["vocabulary"]) for v in out.values())
    reviewed = sum(
        1 for entry in out.values() for v in entry["vocabulary"] if v["reviewed"]
    )
    print(f"Wrote {OUT_PATH.relative_to(BASE_DIR)}")
    print(f"  {len(out)} kanji with multiple sinovi readings")
    print(f"  {total} total vocab entries ({reviewed} reviewed, {total - reviewed} pending)")
    print(f"    {preserved} preserved from existing file")
    print(f"    {new_entries} new entries added (reviewed=false)")
    if orphan_preserved:
        print(f"    {orphan_preserved} carried over from existing file (no longer matched by corpus scan)")


if __name__ == "__main__":
    main()
