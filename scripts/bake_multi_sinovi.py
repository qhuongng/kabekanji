"""
Bake hand-corrected Sino-Vietnamese readings from data/multi_sinovi.json
back into data/kanji.json

Reads the shape produced (and then hand-edited) by extract_multi_sinovi.py:

    {
      "character": {
        "sinovi": "...",
        "vocabulary": [
          { "word": "...", "sinovi": "corrected reading", "reviewed": true },
          ...
        ]
      },
      ...
    }

Only entries with `reviewed: true` are applied. Everything else is skipped
so you can bake incrementally as you review batches. Warns on any word that
can't be found.

Usage:
    python scripts/bake_multi_sinovi.py
"""

import json
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KANJI_JSON_PATH = DATA_DIR / "kanji.json"
CORRECTIONS_PATH = DATA_DIR / "multi_sinovi.json"


# Y -> I mapping preserving tone marks and case
_Y_TO_I: dict[int, str] = {
    ord(y): i
    for y, i in zip(
        "yýỳỷỹỵYÝỲỶỸỴ",
        "iíìỉĩịIÍÌỈĨỊ",
    )
}


_VIET_VOWEL_BASES = set("aeiouy")


def _is_vowel(ch: str) -> bool:
    """True if `ch` is any Vietnamese vowel letter, regardless of tone/diacritic
    (a, ă, â, e, ê, i, o, ô, ơ, u, ư, y and their tone forms)"""
    if not ch:
        return False
    decomp = unicodedata.normalize("NFD", ch)
    return decomp[0].lower() in _VIET_VOWEL_BASES


def normalize_yi(s: str) -> str:
    """Enforce the Vietnamese y/i spelling rule (just my pet peeve lmao):
    y stays when it's the first char of a syllable (space-separated tokens)
    or when preceded by any vowel. y after a consonant becomes i, preserving
    tone marks and case
    """
    s = unicodedata.normalize("NFC", s)
    tokens = []
    for token in s.split(" "):
        chars = list(token)
        for i, ch in enumerate(chars):
            if ord(ch) not in _Y_TO_I:
                continue
            if i == 0 or _is_vowel(chars[i - 1]):
                continue
            chars[i] = _Y_TO_I[ord(ch)]
        tokens.append("".join(chars))
    return " ".join(tokens)


def main():
    with KANJI_JSON_PATH.open(encoding="utf-8") as f:
        kanji = json.load(f)
    with CORRECTIONS_PATH.open(encoding="utf-8") as f:
        corrections = json.load(f)

    updated = 0
    unchanged = 0
    pending = 0
    missing_kanji: list[str] = []
    missing_words: list[tuple[str, str]] = []

    # A word may appear under multiple multi-reading kanji
    # Apply each correction to every kanji.json vocab list that contains it
    corrections_by_word: dict[str, str] = {}
    for char, entry in corrections.items():
        if char not in kanji:
            missing_kanji.append(char)
            continue
        for corr in entry.get("vocabulary", []):
            if not corr.get("reviewed"):
                pending += 1
                continue
            corrections_by_word[corr["word"]] = corr["sinovi"]

    for word, new_sinovi in corrections_by_word.items():
        applied = False
        for entry in kanji.values():
            for v in entry.get("vocabulary", []):
                if v.get("word") != word:
                    continue
                applied = True
                if v.get("sinovi") == new_sinovi:
                    unchanged += 1
                else:
                    v["sinovi"] = new_sinovi
                    updated += 1
        if not applied:
            # Word appears in corrections but not in any kanji's vocab list
            missing_words.append(("?", word))

    # Enforce the Vietnamese y/i rule across every sinovi in kanji.json
    yi_kanji_level = 0
    yi_vocab_level = 0
    for entry in kanji.values():
        original = entry.get("sinovi", "")
        if original:
            normalized = normalize_yi(original)
            if normalized != original:
                entry["sinovi"] = normalized
                yi_kanji_level += 1
        for v in entry.get("vocabulary", []):
            original_v = v.get("sinovi", "")
            if not original_v:
                continue
            normalized_v = normalize_yi(original_v)
            if normalized_v != original_v:
                v["sinovi"] = normalized_v
                yi_vocab_level += 1

    with KANJI_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(kanji, f, ensure_ascii=False, indent=2)

    print(f"Wrote {KANJI_JSON_PATH.relative_to(BASE_DIR)}")
    print(f"  {updated} vocab sinovi values updated from corrections")
    print(f"  {unchanged} unchanged (already matched)")
    print(f"  {pending} skipped (reviewed=false)")
    print(f"  y/i normalization: {yi_kanji_level} kanji-level, {yi_vocab_level} vocab-level")
    if missing_kanji:
        print(f"  ! {len(missing_kanji)} unknown kanji in corrections: {missing_kanji}")
    if missing_words:
        print(f"  ! {len(missing_words)} unknown words in corrections:")
        for _, word in missing_words:
            print(f"      {word}")


if __name__ == "__main__":
    main()
