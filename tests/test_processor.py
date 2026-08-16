import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
import fitz
import pytest
from backend.app.processor import _render_page
from backend.app.config import settings


def test_render_page_rejects_oversized_mediabox(tmp_path):
    doc = fitz.open()
    doc.new_page(width=20000, height=20000)  # far beyond a realistic scan/print page
    page = doc[0]
    with pytest.raises(ValueError):
        _render_page(page, tmp_path / "out.png")
    doc.close()
    assert not (tmp_path / "out.png").exists()


def test_render_page_accepts_normal_page(tmp_path):
    doc = fitz.open()
    doc.new_page(width=595, height=842)  # A4
    page = doc[0]
    out = tmp_path / "out.png"
    _render_page(page, out)
    assert out.exists()
    doc.close()


def test_max_render_pixels_default_is_sane():
    assert settings.max_render_pixels > 0
