"""
Extract runtime data from Anki decks in data/ into JSONs.

Usage:
    python scripts/extract_data.py

Reads from data/:
    - Hn_T_Thng_Dng_Ting_Nht_Kanji_JLPT_N5_ti_N1.apkg
    - B_Th_Ch_Hn_Ting_Nht.apkg
    - Japanese_Jouyou_Kanji_Word_Readings.apkg

Writes to data/:
    - kanji.json:       per-kanji data (meanings, readings, sino-vietnamese pronunciation, radical, vocabulary,...)
    - radicals.json:    per-radical data (indexed by Kangxi number)

After running once, the .apkg files can be moved out of data/. The app only
needs the two generated JSONs for seed_db.py to run.
"""

import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KANJI_APKG = DATA_DIR / "Hn_T_Thng_Dng_Ting_Nht_Kanji_JLPT_N5_ti_N1.apkg"
RADICALS_APKG = DATA_DIR / "B_Th_Ch_Hn_Ting_Nht.apkg"
VOCAB_APKG = DATA_DIR / "Japanese_Jouyou_Kanji_Word_Readings.apkg"

# Grade values in the kanji deck's "Jouyou Grade" field
JOUYOU_GRADES = {"1", "2", "3", "4", "5", "6", "S"}

HTML_TAG_RE = re.compile(r"<[^>]+>")

# Field indices in the main deck's 28-field note type
F_KANJI = 0
F_ONYOMI = 1
F_KUNYOMI = 2
F_ENGLISH = 4          # comma-separated meanings
F_SINOVI = 6           # Âm Hán Việt (Sino-Vietnamese reading)
F_JLPT = 10            # "1"–"5" or empty
F_GRADE = 11           # "1"–"6", "S", "S+", or empty
F_STROKES = 14
F_RADICAL_CHAR = 15
F_RADICAL_NUM = 16


def strip_html(text: str) -> str:
    return HTML_TAG_RE.sub("", text).strip()


def is_all_kanji(text: str) -> bool:
    """True if the string contains only CJK ideographs (no hiragana/katakana/other)"""
    if not text:
        return False
    for c in text:
        cp = ord(c)
        if not (
            0x3400 <= cp <= 0x9FFF     # CJK Unified + Extension A
            or 0xF900 <= cp <= 0xFAFF  # CJK Compatibility Ideographs
            or 0x20000 <= cp <= 0x2FFFF  # CJK Extensions B–F
        ):
            return False
    return True


def word_sinovi(word: str, sinovi_map: dict[str, str]) -> str:
    """Return space-separated lowercase Sino-Vietnamese reading for a kanji-only word

    For kanji with multiple readings (comma-separated in the source), takes the
    first (primary) reading. Returns "" if any character has no reading
    """
    parts = []
    for c in word:
        reading = sinovi_map.get(c, "")
        if not reading:
            return ""
        primary = reading.split(",")[0].strip()
        parts.append(primary.lower())
    return " ".join(parts)


def open_anki_db(apkg_path: Path, tmp_dir: Path) -> sqlite3.Connection:
    """Extract .apkg (zip) and open its collection database"""
    if not apkg_path.exists():
        raise FileNotFoundError(f"{apkg_path} not found")
    extract_dir = tmp_dir / apkg_path.stem
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(apkg_path) as z:
        z.extractall(extract_dir)
    db_file = extract_dir / "collection.anki21"
    if not db_file.exists():
        db_file = extract_dir / "collection.anki2"
    return sqlite3.connect(db_file)


def _split_readings(raw: str) -> list[str]:
    """Split '、'-separated Japanese readings, trimming whitespace and empties"""
    return [s.strip() for s in raw.split("、") if s.strip()]


def _split_meanings(raw: str) -> list[str]:
    """Split ','-separated English meanings, trimming whitespace and empties"""
    return [s.strip() for s in raw.split(",") if s.strip()]


def extract_kanji_core(tmp_dir: Path) -> tuple[dict[str, dict], dict[str, str]]:
    """Parse the main kanji deck

    Returns (kanji_data, sinovi_map):
      - kanji_data: only jouyou kanji, full data per entry (what goes into kanji.json)
      - sinovi_map: kanji to Sino-Vietnamese reading for EVERY kanji in the deck,
        including jinmeiyou/extended ones. Used for word-level lookup so that
        vocabulary words containing non-jouyou kanji (e.g. 蕎麦) still get
        proper Sino-Vietnamese readings
    """
    con = open_anki_db(KANJI_APKG, tmp_dir)
    rows = con.execute("SELECT flds FROM notes").fetchall()
    con.close()

    kanji_data: dict[str, dict] = {}
    sinovi_map: dict[str, str] = {}

    for (flds,) in rows:
        fs = flds.split("\x1f")
        if len(fs) <= F_RADICAL_NUM:
            continue
        kanji = fs[F_KANJI].strip()
        if not kanji:
            continue

        # Populate the deck-wide Sino-Vietnamese lookup unconditionally
        sinovi_reading = fs[F_SINOVI].strip()
        if sinovi_reading:
            sinovi_map[kanji] = sinovi_reading

        # Only jouyou kanji get a full entry in the output
        grade_raw = fs[F_GRADE].strip()
        if grade_raw not in JOUYOU_GRADES:
            continue

        # Normalize grade: "S" (secondary school) to 8
        grade = 8 if grade_raw == "S" else int(grade_raw)

        try:
            jlpt = int(fs[F_JLPT].strip()) if fs[F_JLPT].strip() else 0
        except ValueError:
            jlpt = 0

        try:
            strokes = int(fs[F_STROKES].strip())
        except ValueError:
            strokes = 0

        entry = {
            "meanings": _split_meanings(fs[F_ENGLISH]),
            "on_yomi": _split_readings(fs[F_ONYOMI]),
            "kun_yomi": _split_readings(fs[F_KUNYOMI]),
            "radical": fs[F_RADICAL_CHAR].strip(),
            "stroke_count": strokes,
            "grade": grade,
            "jlpt": jlpt,
        }
        if sinovi_reading:
            entry["sinovi"] = sinovi_reading

        kanji_data[kanji] = entry

    return kanji_data, sinovi_map


def extract_radicals(tmp_dir: Path):
    """Radical number to {char, sinovi, english, ja_reading}; save to data/radicals.json"""
    con = open_anki_db(RADICALS_APKG, tmp_dir)
    rows = con.execute("SELECT flds FROM notes").fetchall()
    con.close()

    radicals: dict[str, dict] = {}
    for (flds,) in rows:
        fields = flds.split("\x1f")
        if len(fields) < 7:
            continue
        char = fields[0].strip()
        try:
            number = int(fields[1].strip())
        except ValueError:
            continue
        english = strip_html(fields[4])
        ja_reading = fields[5].strip()
        sinovi = fields[6].strip()
        if char and sinovi:
            radicals[str(number)] = {
                "char": char,
                "sinovi": sinovi,
                "english": english,
                "ja_reading": ja_reading,
            }

    out = DATA_DIR / "radicals.json"
    out.write_text(json.dumps(radicals, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"radicals.json: {len(radicals)} radicals → {out.name}")


def add_vocabulary(kanji_data: dict[str, dict], sinovi_map: dict[str, str], tmp_dir: Path):
    """Add vocabulary entries to each kanji in kanji_data (in place)

    `sinovi_map` covers the whole deck (including non-Jouyou kanji) so that
    vocabulary words containing e.g. jinmeiyou characters still get proper
    word-level Sino-Vietnamese reading
    """
    con = open_anki_db(VOCAB_APKG, tmp_dir)
    rows = con.execute("SELECT flds FROM notes").fetchall()
    con.close()

    # Field layout (Kanji Card model):
    # 0: Kanji, 1: Keyword, 2: Story,
    # for i in 0..4: [3+4i]=Word, [4+4i]=Reading, [5+4i]=Definition, [6+4i]=Frequency
    total_words = 0
    kanji_with_vocab = 0
    for (flds,) in rows:
        fields = flds.split("\x1f")
        if not fields:
            continue
        kanji = fields[0].strip()
        if not kanji or kanji not in kanji_data:
            continue

        entries = []
        for i in range(5):
            base = 3 + i * 4
            if base + 3 >= len(fields):
                break
            word = strip_html(fields[base])
            reading = strip_html(fields[base + 1])
            meaning = strip_html(fields[base + 2])
            freq_raw = strip_html(fields[base + 3])
            if not word or not reading:
                continue
            try:
                frequency = int(freq_raw)
            except ValueError:
                frequency = 999999
            entry = {
                "word": word,
                "reading": reading,
                "meaning": meaning,
                "frequency": frequency,
            }
            if is_all_kanji(word):
                sv = word_sinovi(word, sinovi_map)
                if sv:
                    entry["sinovi"] = sv
            entries.append(entry)

        if entries:
            entries.sort(key=lambda e: e["frequency"])
            kanji_data[kanji]["vocabulary"] = entries
            total_words += len(entries)
            kanji_with_vocab += 1

    # Report word-level Sino-Vietnamese coverage
    total_sv = 0
    total_kanji_only = 0
    for entry in kanji_data.values():
        for e in entry.get("vocabulary", []):
            if is_all_kanji(e["word"]):
                total_kanji_only += 1
                if "sinovi" in e:
                    total_sv += 1
    print(f"  vocabulary: {kanji_with_vocab} kanji, {total_words} words total")
    print(f"  word-level Sino-Vietnamese: {total_sv}/{total_kanji_only} kanji-only words")


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)

        print("Extracting kanji core data…")
        kanji_data, sinovi_map = extract_kanji_core(tmp_dir)
        sinovi_count = sum(1 for v in kanji_data.values() if "sinovi" in v)
        missing = sorted(k for k, v in kanji_data.items() if "sinovi" not in v)
        print(f"  {len(kanji_data)} jouyou kanji")
        print(f"  Sino-Vietnamese (jouyou): {sinovi_count}/{len(kanji_data)}")
        print(f"  Sino-Vietnamese (full deck lookup): {len(sinovi_map)} kanji")
        if missing:
            print(f"  {len(missing)} without Sino-Vietnamese (likely kokuji): {' '.join(missing)}")

        print("\nExtracting radicals…")
        extract_radicals(tmp_dir)

        print("\nExtracting vocabulary…")
        add_vocabulary(kanji_data, sinovi_map, tmp_dir)

        out = DATA_DIR / "kanji.json"
        out.write_text(
            json.dumps(kanji_data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"\nkanji.json: {len(kanji_data)} kanji → {out.name}")


if __name__ == "__main__":
    main()
