import re
import signal

import pytest

from livetranslate import demo
from livetranslate.cli import main


def test_script_plays_through_the_pipeline_and_speaks_every_translation():
    from livetranslate.config import Settings
    from livetranslate.pipeline import Pipeline
    from livetranslate.transcript import TranscriptRecorder
    from livetranslate.tts import ListSpeaker
    import threading

    class D:
        def __init__(self):
            self.shown = []

        def update_partial(self, o, t):
            pass

        def show(self, u):
            self.shown.append(u)

    spk, d = ListSpeaker(), D()
    pl = Pipeline(Settings(api_key="x", target="en"), spk, TranscriptRecorder("/tmp/lt_demo", "en", enabled=False), d)
    demo.play(pl.on_batch, threading.Event(), speed=200)
    pl.close()
    spoken = re.sub(r"\s+", " ", " ".join(spk.phrases))
    expected = re.sub(r"\s+", " ", " ".join(t for _, t in demo.SCRIPT))
    assert spoken == expected
    assert len(d.shown) == len(demo.SCRIPT)
    assert d.shown[0].original.startswith("안녕하세요")


@pytest.fixture(autouse=True)
def restore_sigint():
    old = signal.getsignal(signal.SIGINT)
    yield
    signal.signal(signal.SIGINT, old)


def test_cli_demo_needs_no_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SONIOX_API_KEY", raising=False)
    code = main(["--demo", "--demo-speed", "200", "--tts", "none", "--save-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 0
    assert "DEMO" in out and "Hello, how are you doing today?" in out
    assert len(list((tmp_path / "out").glob("*.md"))) == 1
