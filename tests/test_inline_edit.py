import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import anchor, strip_anchors


def test_anchor_produces_editable_span():
    html = anchor("Texto", "edit_field")
    assert html.startswith("<span")
    assert 'contenteditable="true"' in html
    assert 'data-key="edit_field"' in html


def test_strip_anchors_removes_wrapper():
    html = anchor("Texto", "edit_field")
    stripped = strip_anchors(html)
    assert stripped == "Texto"
