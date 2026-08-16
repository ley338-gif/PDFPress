from __future__ import annotations
import re
from statistics import median
from .models import TextBlock

BULLET = re.compile(r"^\s*[-•▪◦*]\s+")
NUMBERED = re.compile(r"^\s*(?:\d+[.)]|[a-zA-Z][.)])\s+")
SECTION = re.compile(r"^\s*\d+(?:\.\d+){0,4}\s+\S+")
PAGE_NUMBER = re.compile(r"^\s*\d{1,4}\s*$")


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"([A-Za-zÄÖÜäöüß])-\n([a-zäöüß])", r"\1\2", text)
    text = re.sub(r"(?<![.!?:;\n])\n(?=[a-zäöüß])", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def infer_type(text: str, font_size: float | None = None, body_size: float | None = None, bold: bool = False) -> str:
    stripped = text.strip()
    if not stripped:
        return "empty"
    if PAGE_NUMBER.fullmatch(stripped):
        return "page_number"
    if BULLET.match(stripped):
        return "list_item"
    if NUMBERED.match(stripped) and len(stripped) < 140:
        return "numbered_list_item"
    if SECTION.match(stripped) and len(stripped) < 140:
        return "heading"
    if font_size and body_size:
        if font_size >= body_size * 1.45:
            return "title"
        if font_size >= body_size * 1.18 or (bold and font_size >= body_size * 0.98):
            return "heading"
    if len(stripped) <= 80 and stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return "heading"
    return "paragraph"


def blocks_to_markdown(blocks: list[TextBlock]) -> str:
    out: list[str] = []
    for block in blocks:
        text = clean_text(block.text)
        if not text or block.type in {"page_number", "header", "footer"}:
            continue
        if block.type == "title":
            out.append(f"# {text}")
        elif block.type == "heading":
            # Numbered subsection depth approximates markdown heading depth.
            m = re.match(r"^(\d+(?:\.\d+)*)\s+", text)
            depth = min(5, 1 + (m.group(1).count(".") + 1 if m else 1))
            out.append(f"{'#' * depth} {text}")
        elif block.type == "list_item":
            out.append("- " + BULLET.sub("", text))
        elif block.type == "numbered_list_item":
            m = NUMBERED.match(text)
            marker = text[: m.end()].strip() if m else "1."
            content = text[m.end():].strip() if m else text
            out.append(f"{marker} {content}")
        else:
            out.append(text)
    return "\n\n".join(out).strip()


def extract_embedded_blocks(page_dict: dict) -> list[TextBlock]:
    candidates = []
    sizes = []
    raw_blocks = [b for b in page_dict.get("blocks", []) if "lines" in b]
    raw_blocks.sort(key=lambda b: (round(b.get("bbox", [0, 0, 0, 0])[1] / 8), b.get("bbox", [0, 0, 0, 0])[0]))
    for block in raw_blocks:
        if "lines" not in block:
            continue
        line_parts = []
        block_sizes = []
        bold = False
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            line_text = "".join(span.get("text", "") for span in spans).strip()
            if line_text:
                line_parts.append(line_text)
            for span in spans:
                size = float(span.get("size", 0) or 0)
                if size:
                    block_sizes.append(size)
                    sizes.append(size)
                font = str(span.get("font", "")).lower()
                flags = int(span.get("flags", 0) or 0)
                if "bold" in font or "semibold" in font or "black" in font or "heavy" in font or flags & 16:
                    bold = True
        text = "\n".join(line_parts).strip()
        if text:
            candidates.append((text, list(block.get("bbox", [])) or None, max(block_sizes) if block_sizes else None, bold))
    body_size = median(sizes) if sizes else None
    return [TextBlock(text=t, type=infer_type(t, s, body_size, b), bbox=bbox, confidence=1.0, source="embedded_text") for t, bbox, s, b in candidates]


def structure_ocr_lines(lines: list[tuple[str, list[float], float]]) -> list[TextBlock]:
    blocks = []
    for text, bbox, conf in lines:
        clean = clean_text(text)
        if not clean:
            continue
        blocks.append(TextBlock(text=clean, type=infer_type(clean), bbox=bbox, confidence=conf, source="ocr"))
    return blocks


def suppress_repeated_headers_footers(pages: dict[int, object]) -> None:
    """Mark likely recurring first/last blocks without moving content across pages."""
    if len(pages) < 2:
        return
    from collections import Counter
    def key(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())
    first = Counter()
    last = Counter()
    for page in pages.values():
        visible = [b for b in page.blocks if b.text.strip()]
        if visible:
            first[key(visible[0].text)] += 1
            last[key(visible[-1].text)] += 1
    threshold = max(2, (len(pages) + 1) // 2)
    headers = {k for k,v in first.items() if v >= threshold and 0 < len(k) <= 160}
    footers = {k for k,v in last.items() if v >= threshold and 0 < len(k) <= 160}
    for page in pages.values():
        visible = [b for b in page.blocks if b.text.strip()]
        if visible and key(visible[0].text) in headers:
            visible[0].type = "header"
        if visible and key(visible[-1].text) in footers:
            visible[-1].type = "footer"
        page.markdown = blocks_to_markdown(page.blocks)
        page.text = clean_text("\n\n".join(b.text for b in page.blocks if b.type not in {"header", "footer", "page_number"}))
