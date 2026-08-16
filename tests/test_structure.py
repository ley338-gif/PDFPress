from backend.app.structure import clean_text, infer_type, blocks_to_markdown
from backend.app.models import TextBlock

def test_hyphenation_and_linewrap():
    assert clean_text("Daten-\nbankserver") == "Datenbankserver"

def test_number_preserved():
    text = "Kosten 12.345,67 EUR"
    assert clean_text(text) == text

def test_heading_and_list():
    blocks=[TextBlock("1. Ausgangssituation","heading"),TextBlock("• Server A","list_item")]
    md=blocks_to_markdown(blocks)
    assert "## 1. Ausgangssituation" in md
    assert "- Server A" in md
