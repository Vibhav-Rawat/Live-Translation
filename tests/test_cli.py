import signal

import pytest

from livetranslate.cli import main
from tests.helpers import read_until_end_of_audio, send, start_server, tok


@pytest.fixture(autouse=True)
def restore_sigint():
    old = signal.getsignal(signal.SIGINT)
    yield
    signal.signal(signal.SIGINT, old)


def test_cli_with_audio_file_end_to_end(tmp_path, monkeypatch, capsys):
    def handler(ws):
        ws.recv()
        for _ in read_until_end_of_audio(ws):
            send(ws, [tok("\ub124", True, "original", language="ko"),
                      tok("Yes", True, "translation"), tok(".", True, "translation"),
                      tok("<end>", True, "none")], total_ms=500)
        send(ws, [], finished=True)

    audio = tmp_path / "fake.wav"
    audio.write_bytes(b"\x00" * 3840 * 3)
    server, url = start_server(handler)
    monkeypatch.setenv("SONIOX_API_KEY", "k")
    monkeypatch.setenv("SONIOX_WS_URL", url)
    monkeypatch.chdir(tmp_path)  # so a stray .env in the repo isn't read
    try:
        code = main(["--target", "en", "--file", str(audio), "--tts", "none", "--save-dir", str(tmp_path / "out")])
    finally:
        server.shutdown()
    out = capsys.readouterr().out
    assert code == 0
    assert "-> Yes." in out
    assert "Transcript saved" in out
    saved = list((tmp_path / "out").glob("*.md"))
    assert len(saved) == 1
    assert "\ub124" in saved[0].read_text(encoding="utf-8")


def test_cli_needs_key_and_target(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SONIOX_API_KEY", raising=False)
    assert main(["--target", "en"]) == 2
    monkeypatch.setenv("SONIOX_API_KEY", "k")
    monkeypatch.delenv("LT_TARGET", raising=False)
    assert main([]) == 2
