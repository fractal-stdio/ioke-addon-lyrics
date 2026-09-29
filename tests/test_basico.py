"""Sem internet: o manifesto e a conversao do formato palavra a palavra do NetEase."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import letras  # noqa: E402


def test_manifest():
    m = json.loads((RAIZ / "karaoke-complemento.json").read_text(encoding="utf-8"))
    assert m["id"] == "letras-extras" and m["oferece"] == ["fonte_letras"] and not m["celular"]


def test_yrc_to_enhanced_lrc():
    yrc = "\n".join(f"[{i * 2000},1500](%d,500,0)Word (%d,500,0)two " % (i * 2000, i * 2000 + 600) for i in range(6))
    lrc = letras.yrc_to_lrc(yrc)
    assert letras.is_synced(lrc) and letras.has_words(lrc)
    assert lrc.splitlines()[1].startswith("[00:02.00]<00:02.00>Word")
