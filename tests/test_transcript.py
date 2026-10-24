import datetime

from livetranslate.soniox_client import Token
from livetranslate.transcript import UtteranceBuilder, TranscriptRecorder, render_markdown


def test_builder_groups_by_end_token():
    b = UtteranceBuilder(clock=lambda: 10.0)
    out = []
    for t in [
        Token("\uc548\ub155", True, "original", language="ko", speaker="1"),
        Token("\ud558\uc138\uc694", True, "original", language="ko", speaker="1"),
        Token("Hello", True, "translation"),
        Token(" there", True, "translation"),
        Token("<end>", True, "none"),
        Token("Next", True, "translation"),
    ]:
        u = b.add(t)
        if u:
            out.append(u)
    assert len(out) == 1
    assert out[0].original == "\uc548\ub155\ud558\uc138\uc694"
    assert out[0].translation == "Hello there"
    assert out[0].source_language == "ko"
    assert out[0].speaker == "1"
    last = b.flush()
    assert last.translation == "Next" and last.original == ""


def test_empty_flush_returns_none():
    assert UtteranceBuilder().flush() is None


def test_markdown_and_files(tmp_path):
    b = UtteranceBuilder(clock=lambda: 65.0)
    for t in [Token("\uc548\ub155", True, "original", language="ko"), Token("Hi", True, "translation")]:
        b.add(t)
    utt = b.flush()
    md = render_markdown([utt], "en", datetime.datetime(2026, 10, 24, 14, 30))
    assert "# Conversation transcript" in md
    assert "\u201c\uc548\ub155\u201d" in md
    assert "*Translation:* \u201cHi\u201d" in md

    rec = TranscriptRecorder(str(tmp_path), "en")
    rec.add(utt)
    path = rec.finish()
    assert path.endswith(".md")
    assert "\uc548\ub155" in open(path, encoding="utf-8").read()
    assert open(rec.jsonl_path, encoding="utf-8").read().count("\n") == 1
