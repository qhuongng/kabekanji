import io
import json

from PIL import Image, ImageDraw, ImageFont

from server.config import FONTS, DATA_DIR

# Radical char to Sino-Vietnamese name, loaded once
_RADICAL_SINOVI: dict[str, str] = {}
_radical_path = DATA_DIR / "radicals.json"
if _radical_path.exists():
    _raw = json.loads(_radical_path.read_text(encoding="utf-8"))
    _RADICAL_SINOVI = {v["char"]: v["sinovi"] for v in _raw.values()}


# Color helpers
def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _blend(fg: tuple[int, int, int], bg: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """Composite fg over bg at the given alpha (0.0 = bg, 1.0 = fg)."""
    return tuple(int(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))


def _make_palette(bg_hex: str, text_hex: str) -> dict:
    bg = _hex_to_rgb(bg_hex)
    text = _hex_to_rgb(text_hex)
    return {
        "bg": bg,
        "text": text,
        "muted": _blend(text, bg, 0.55),   # secondary text, e.g. meanings, furigana
        "subtle": _blend(text, bg, 0.18),  # dividers, style-sample labels
    }


def _load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS.get(key)
    if path and path.exists():
        return ImageFont.truetype(str(path), size)
    # Fallback to default; will look wrong for CJK but won't crash
    return ImageFont.load_default()


class _DryDraw:
    """Proxy for ImageDraw that measures via textbbox but skips actual drawing
    Used to pre-measure a section's height so it can be laid out before drawing"""

    __slots__ = ("_real",)

    def __init__(self, real: ImageDraw.ImageDraw):
        self._real = real

    def textbbox(self, *args, **kwargs):
        return self._real.textbbox(*args, **kwargs)

    def text(self, *args, **kwargs):  # no-op
        pass

    def line(self, *args, **kwargs):  # no-op
        pass


def render_wallpaper(kanji: dict, config: dict) -> bytes:
    """
    Render a lock screen wallpaper PNG for the given kanji and config

    Returns PNG bytes
    """
    w = config["screen_width"]
    h = config["screen_height"]
    top = config["top_margin"]
    bottom = config["bottom_margin"]
    colors = _make_palette(config["bg_color"], config["text_color"])

    img = Image.new("RGB", (w, h), colors["bg"])
    real_draw = ImageDraw.Draw(img)

    # Usable content area
    content_top = top
    content_bottom = h - bottom
    content_height = content_bottom - content_top
    margin_x = int(w * 0.15)

    # Section spacing
    SECTION_GAP = 56
    LABEL_GAP = 32
    HERO_BOTTOM_GAP = 48
    DIVIDER_GAP = 48

    # Fonts
    # main_size is the character size of the hero, which is dynamic
    # Measure the middle + vocab sections first, then give the hero whatever remains
    MAIN_SIZE_MAX = min(int(content_height * 0.32), int(w * 0.5))
    MAIN_SIZE_MIN = 220
    main_size = MAIN_SIZE_MAX
    main_font = _load_font("stroke_order", main_size)
    readings_font_jp = _load_font("mincho", 54)
    readings_font_serif = _load_font("serif", 54)
    label_font = _load_font("serif_bold", 34)
    meaning_font = _load_font("serif", 46)
    word_font = _load_font("mincho", 56)
    furi_font = _load_font("mincho", 28)
    word_sinovi_font = _load_font("serif", 34)
    vocab_meaning_font = _load_font("serif", 42)

    char = kanji["character"]
    on_yomi = json.loads(kanji["on_yomi"]) if isinstance(kanji["on_yomi"], str) else kanji["on_yomi"]
    kun_yomi = json.loads(kanji["kun_yomi"]) if isinstance(kanji["kun_yomi"], str) else kanji["kun_yomi"]
    meanings = json.loads(kanji["meanings"]) if isinstance(kanji["meanings"], str) else kanji["meanings"]
    vocab = json.loads(kanji["vocabulary"]) if isinstance(kanji["vocabulary"], str) else kanji["vocabulary"]

    on_yomi_text = "、".join(on_yomi)
    kun_yomi_text = "、".join(kun_yomi)
    sinovi_text = kanji.get("sinovi", "") if config.get("show_sinovi", True) else ""
    radical_char = kanji.get("radical", "")
    radical_sv = _RADICAL_SINOVI.get(radical_char, "") if radical_char else ""

    # Layout metrics
    ja_line_h = real_draw.textbbox((0, 0), "あ", font=readings_font_jp, anchor="lt")[3] + 12
    meaning_line_h = 60
    vocab_meaning_line_h = 54
    right_col_x = margin_x + (w - 2 * margin_x) // 2
    on_yomi_col_w = right_col_x - margin_x - 24
    full_col_w = w - 2 * margin_x
    max_meaning_w = full_col_w
    max_vocab_meaning_w = full_col_w - 24
    max_vocab_meaning_lines = 3

    # Section closures
    # Each takes a draw-like object (real or _DryDraw) and a starting y,
    # and returns the y just past the last drawn pixel
    def _label(d, x, y_pos, text):
        d.text((x, y_pos), text, font=label_font, fill=colors["muted"], anchor="lt")
        return d.textbbox((x, y_pos), text, font=label_font, anchor="lt")[3] + LABEL_GAP

    def _measure_width(text, font):
        return real_draw.textbbox((0, 0), text, font=font, anchor="lt")[2] if text else 0

    def _wrapped_lines(d, text, font, max_w):
        return _wrap_ja_text(d if isinstance(d, ImageDraw.ImageDraw) else real_draw, text, font, max_w)

    def draw_hero(d, y_start):
        main_bbox = d.textbbox((0, 0), char, font=main_font, anchor="lt")
        main_char_w = main_bbox[2]
        main_char_h = main_bbox[3]

        hero_right_x = w - margin_x - main_char_w
        d.text((hero_right_x, y_start), char, font=main_font, fill=colors["text"], anchor="lt")

        styles = []
        if config.get("show_mincho", True):
            styles.append("mincho")
        if config.get("show_gothic", True):
            styles.append("gothic")
        if config.get("show_handwritten", True):
            styles.append("handwritten")

        if styles:
            n = len(styles)
            # Smaller style chars for more breathing room; gap is approx. 40% of a style char
            style_size = int(main_char_h / (n + 0.8)) if n else 0
            for i, font_key in enumerate(styles):
                style_font = _load_font(font_key, style_size)
                # Space-between distribution: top of char 0 aligns with hero top,
                # bottom of char n-1 aligns with hero bottom (main char's bottom)
                if n == 1:
                    slot_center_y = y_start + main_char_h / 2
                else:
                    slot_center_y = (
                        y_start + style_size / 2
                        + i * (main_char_h - style_size) / (n - 1)
                    )
                d.text(
                    (margin_x, int(slot_center_y)), char, font=style_font,
                    fill=colors["text"], anchor="lm",
                )
        return y_start + main_char_h

    def draw_middle(d, y_start):
        """Divider + readings row + kun'yomi + meaning. Returns bottom-of-content y (no trailing gap)."""
        y = y_start
        # Divider
        d.line([(margin_x, y), (w - margin_x, y)], fill=colors["subtle"], width=2)
        y += DIVIDER_GAP

        # Row 1: on'yomi and inline sinovi on left, radical on right
        row_top = y
        y_left = row_top
        y_right = row_top

        if on_yomi_text or sinovi_text:
            value_y = _label(d, margin_x, row_top, "ON'YOMI")
            inline_ok = False
            if on_yomi_text and sinovi_text:
                joined = f" · {sinovi_text}"
                if _measure_width(on_yomi_text, readings_font_jp) + _measure_width(joined, readings_font_serif) <= on_yomi_col_w:
                    d.text((margin_x, value_y), on_yomi_text, font=readings_font_jp, fill=colors["text"], anchor="lt")
                    onb = d.textbbox((margin_x, value_y), on_yomi_text, font=readings_font_jp, anchor="lt")
                    d.text((onb[2], value_y), joined, font=readings_font_serif, fill=colors["text"], anchor="lt")
                    svb = d.textbbox((onb[2], value_y), joined, font=readings_font_serif, anchor="lt")
                    y_left = max(onb[3], svb[3])
                    inline_ok = True
            if not inline_ok:
                cur_y = value_y
                if on_yomi_text:
                    for line in _wrapped_lines(d, on_yomi_text, readings_font_jp, on_yomi_col_w):
                        d.text((margin_x, cur_y), line, font=readings_font_jp, fill=colors["text"], anchor="lt")
                        cur_y += ja_line_h
                if sinovi_text:
                    d.text((margin_x, cur_y), sinovi_text, font=readings_font_serif, fill=colors["text"], anchor="lt")
                    svb = d.textbbox((margin_x, cur_y), sinovi_text, font=readings_font_serif, anchor="lt")
                    cur_y = svb[3]
                y_left = cur_y

        if radical_char:
            # If the left column has nothing (kokuji with no on'yomi and no sinovi),
            # slide RADICAL over to the left column so it doesn't sit alone on the right
            rad_x = right_col_x if (on_yomi_text or sinovi_text) else margin_x
            rad_value_y = _label(d, rad_x, row_top, "RADICAL")
            d.text((rad_x, rad_value_y), radical_char, font=readings_font_jp, fill=colors["text"], anchor="lt")
            rb = d.textbbox((rad_x, rad_value_y), radical_char, font=readings_font_jp, anchor="lt")
            if radical_sv:
                d.text((rb[2] + 24, rad_value_y), radical_sv, font=readings_font_serif, fill=colors["text"], anchor="lt")
                rb2 = d.textbbox((rb[2] + 24, rad_value_y), radical_sv, font=readings_font_serif, anchor="lt")
                y_right = max(rb[3], rb2[3])
            else:
                y_right = rb[3]

        y = max(y_left, y_right)

        # Row 2: kun'yomi
        if kun_yomi_text:
            y += SECTION_GAP
            value_y = _label(d, margin_x, y, "KUN'YOMI")
            cur_y = value_y
            for line in _wrapped_lines(d, kun_yomi_text, readings_font_jp, full_col_w):
                d.text((margin_x, cur_y), line, font=readings_font_jp, fill=colors["text"], anchor="lt")
                cur_y += ja_line_h
            y = cur_y - (ja_line_h - real_draw.textbbox((0, 0), "あ", font=readings_font_jp, anchor="lt")[3])

        # Meaning
        if meanings:
            y += SECTION_GAP
            text = "; ".join(meanings)
            lines = _wrap_text(real_draw, text, meaning_font, max_meaning_w)[:2]
            for line in lines:
                d.text((margin_x, y), line, font=meaning_font, fill=colors["text"], anchor="lt")
                y += meaning_line_h
            y -= (meaning_line_h - real_draw.textbbox((0, 0), "A", font=meaning_font, anchor="lt")[3])

        return y

    def draw_vocab(d, y_start):
        """Vocab section. Always draws all 3 entries at fixed font sizes
        """
        if not config.get("show_vocabulary", True) or not vocab:
            return y_start

        y = _label(d, margin_x, y_start, "VOCABULARY")

        entry_gap = 30
        furi_gap = 4
        word_meaning_gap = 8
        meaning_indent = 24
        furi_h = 34
        word_h = 66

        entries = vocab[:3]
        last_entry_end = y
        for i, entry in enumerate(entries):
            word = entry.get("word", "")
            reading = entry.get("reading", "")
            meaning = entry.get("meaning", "")

            meaning_lines = _wrap_text(real_draw, meaning, vocab_meaning_font, max_vocab_meaning_w)[:max_vocab_meaning_lines]

            wb = real_draw.textbbox((0, 0), word, font=word_font, anchor="lt")
            fb = real_draw.textbbox((0, 0), reading, font=furi_font, anchor="lt")
            word_w = wb[2]
            furi_w = fb[2]
            d.text(
                (margin_x + (word_w - furi_w) // 2, y),
                reading, font=furi_font, fill=colors["muted"], anchor="lt",
            )
            y += furi_h + furi_gap

            d.text((margin_x, y), word, font=word_font, fill=colors["text"], anchor="lt")
            word_bb = real_draw.textbbox((margin_x, y), word, font=word_font, anchor="lt")
            entry_sinovi = entry.get("sinovi", "")
            if entry_sinovi:
                mid_y = (word_bb[1] + word_bb[3]) // 2
                d.text(
                    (word_bb[2] + 20, mid_y), entry_sinovi,
                    font=word_sinovi_font, fill=colors["muted"], anchor="lm",
                )
            y += word_h + word_meaning_gap

            for line in meaning_lines:
                d.text(
                    (margin_x + meaning_indent, y), line,
                    font=vocab_meaning_font, fill=colors["text"], anchor="lt",
                )
                y += vocab_meaning_line_h
            last_entry_end = y

            if i < len(entries) - 1:
                y += entry_gap

        return last_entry_end

    # Pipeline: measure middle + vocab first (at their fixed font sizes)
    # Shrink the hero character to fit whatever vertical space is left.
    dry = _DryDraw(real_draw)
    middle_h = draw_middle(dry, 0)
    vocab_h = draw_vocab(dry, 0)

    # Room reserved for the hero: content_height minus everything else, minus
    # the HERO_BOTTOM_GAP and a SECTION_GAP between middle and vocab
    hero_budget = content_height - HERO_BOTTOM_GAP - middle_h - SECTION_GAP - vocab_h
    main_size = max(MAIN_SIZE_MIN, min(MAIN_SIZE_MAX, hero_budget))
    main_font = _load_font("stroke_order", main_size)

    hero_end_y = draw_hero(real_draw, content_top)
    hero_boundary = hero_end_y + HERO_BOTTOM_GAP

    slack = content_bottom - hero_boundary - middle_h - vocab_h
    if slack >= 2 * SECTION_GAP:
        # Plenty of room: center middle, bottom-anchor vocab
        # Both gaps (above middle and between middle and vocab) >= SECTION_GAP
        middle_top = hero_boundary + slack // 2
        vocab_top = content_bottom - vocab_h
    else:
        # Not enough slack for a symmetric split
        # Enforce SECTION_GAP between middle and vocab and put any remaining slack above middle
        gap_above = max(0, slack - SECTION_GAP)
        middle_top = hero_boundary + gap_above
        vocab_top = middle_top + middle_h + SECTION_GAP

    draw_middle(real_draw, middle_top)
    draw_vocab(real_draw, vocab_top)

    # Output
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


def render_preview(kanji: dict, config: dict, max_height: int = 800) -> bytes:
    """Render a smaller preview image for the web UI."""
    full_bytes = render_wallpaper(kanji, config)
    full_img = Image.open(io.BytesIO(full_bytes))

    ratio = max_height / full_img.height
    preview_w = int(full_img.width * ratio)
    preview = full_img.resize((preview_w, max_height), Image.LANCZOS)

    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def _wrap_ja_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Wrap Japanese text. Prefers breaking after 、; falls back to per-char breaks
    for a single overlong segment"""
    if not text:
        return []

    def width_of(s: str) -> int:
        return draw.textbbox((0, 0), s, font=font, anchor="lt")[2]

    if width_of(text) <= max_width:
        return [text]

    # Split by 、 keeping the separator glued to the segment on its left
    if "、" in text:
        parts = text.split("、")
        segments = [p + "、" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    else:
        segments = [text]

    lines: list[str] = []
    current = ""
    for seg in segments:
        candidate = current + seg
        if not current or width_of(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            # If this segment alone is still too wide, char-split it
            if width_of(seg) > max_width:
                buf = ""
                for ch in seg:
                    if buf and width_of(buf + ch) > max_width:
                        lines.append(buf)
                        buf = ch
                    else:
                        buf += ch
                current = buf
            else:
                current = seg
    if current:
        lines.append(current)
    return lines


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Wrap Latin text at word boundaries

    A single word longer than max_width is left on its own line (may extend
    past the margin)
    """
    def width_of(s: str) -> int:
        bbox = draw.textbbox((0, 0), s, font=font)
        return bbox[2] - bbox[0]

    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if not current or width_of(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines
