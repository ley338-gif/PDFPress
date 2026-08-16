from __future__ import annotations
import csv
import io
import subprocess
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter
from .config import settings


def _detect_rotation(image_path: Path) -> int:
    cmd = ["tesseract", str(image_path), "stdout", "--psm", "0"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.ocr_timeout_seconds, check=False)
    if proc.returncode != 0:
        return 0
    for line in proc.stdout.splitlines():
        if line.startswith("Rotate:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return 0
    return 0


def correct_orientation(image_path: Path) -> None:
    """Erkennt und korrigiert eine falsch herum gescannte Seite vor der eigentlichen OCR.

    Tesseracts Orientierungserkennung (--psm 0) meldet den nötigen Korrekturwinkel im
    Uhrzeigersinn; PIL.Image.rotate() dreht dagegen gegen den Uhrzeigersinn, daher das
    Minuszeichen. Schlägt die Erkennung fehl (z. B. zu wenig Text auf der Seite), bleibt
    das Bild unverändert — der reguläre OCR-Lauf versucht es danach trotzdem, nur ohne
    Korrektur, statt die Seite abzubrechen.
    """
    rotation = _detect_rotation(image_path)
    if rotation:
        img = Image.open(image_path)
        img.rotate(-rotation, expand=True).save(image_path)


def preprocess_image(path: Path) -> Path:
    img = Image.open(path).convert("L")
    img = ImageOps.autocontrast(img)
    # Light sharpening helps common office scans without aggressive thresholding.
    img = img.filter(ImageFilter.SHARPEN)
    out = path.with_name(path.stem + "-prep.png")
    img.save(out, optimize=True)
    return out


def run_tesseract_tsv(image_path: Path, language: str) -> tuple[list[tuple[str, list[float], float]], float | None]:
    cmd = [
        "tesseract", str(image_path), "stdout", "-l", language,
        "--psm", "3", "tsv"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.ocr_timeout_seconds, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Tesseract OCR failed")
    reader = csv.DictReader(io.StringIO(proc.stdout), delimiter="\t")
    grouped: dict[tuple[str, str, str, str], dict] = {}
    all_conf = []
    for row in reader:
        text = (row.get("text") or "").strip()
        try:
            conf_raw = float(row.get("conf") or -1)
        except ValueError:
            conf_raw = -1
        if not text or conf_raw < 0:
            continue
        conf = max(0.0, min(1.0, conf_raw / 100.0))
        all_conf.append(conf)
        key = (row.get("block_num", "0"), row.get("par_num", "0"), row.get("line_num", "0"), row.get("page_num", "1"))
        x, y = int(row.get("left") or 0), int(row.get("top") or 0)
        w, h = int(row.get("width") or 0), int(row.get("height") or 0)
        item = grouped.setdefault(key, {"words": [], "x0": x, "y0": y, "x1": x+w, "y1": y+h, "conf": []})
        item["words"].append(text)
        item["x0"] = min(item["x0"], x)
        item["y0"] = min(item["y0"], y)
        item["x1"] = max(item["x1"], x+w)
        item["y1"] = max(item["y1"], y+h)
        item["conf"].append(conf)
    lines = []
    for item in grouped.values():
        text = " ".join(item["words"])
        confidence = sum(item["conf"]) / len(item["conf"]) if item["conf"] else 0.0
        lines.append((text, [item["x0"], item["y0"], item["x1"], item["y1"]], confidence))
    overall = sum(all_conf) / len(all_conf) if all_conf else None
    return lines, overall
