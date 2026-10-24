import json
import threading

import pytest

from livetranslate.config import Settings
from livetranslate.display import Display
from livetranslate.pipeline import Pipeline
from livetranslate.soniox_client import SonioxError, build_start_request, run_forever
from livetranslate.transcript import TranscriptRecorder
from livetranslate.tts import ListSpeaker
from tests.helpers import ListSource, read_until_end_of_audio, send, start_server, tok


class QuietDisplay(Display):
    def __init__(self):
        super().__init__(live_caption=False)
        self.shown = []

    def show(self, utt):
        self.shown.append(utt)

    def info(self, m):
        pass


def run(url, source, tmp_path, stop=None, **kw):
    s = Settings(api_key="test-key", target="en", url=url, hints=["ko", "en"], **kw)
    speaker, display = ListSpeaker(), QuietDisplay()
    rec = TranscriptRecorder(str(tmp_path), "en", enabled=False)
    pl = Pipeline(s, speaker, rec, display)
    stop = stop or threading.Event()
    run_forever(s, source, pl.on_batch, stop, on_status=lambda m: None, backoff_start=0.05)
    pl._speak(pl.planner.flush())
    pl.close()
    return speaker, display, rec


def test_happy_path_korean_to_english(tmp_path):
    seen = {}

    def handler(ws):
        seen["auth"] = ws.request.headers.get("Authorization")
        seen["start"] = json.loads(ws.recv())
        for _ in read_until_end_of_audio(ws):
            # first audio chunk arrived -> answer like Soniox would
            send(ws, [tok("\uc548\ub155", True, "original", language="ko"),
                      tok(" Hello", False, "translation")], total_ms=300)
            send(ws, [tok("\ud558\uc138\uc694", True, "original", language="ko"),
                      tok(" Hello", True, "translation"), tok(" there", True, "translation"),
                      tok(",", True, "translation"), tok(" how", True, "translation"),
                      tok(" are", True, "translation"), tok(" you", True, "translation"),
                      tok("?", True, "translation"), tok("<end>", True, "none")], total_ms=800)
        send(ws, [], total_ms=900, finished=True)

    server, url = start_server(handler)
    try:
        speaker, display, rec = run(url, ListSource(), tmp_path)
    finally:
        server.shutdown()

    assert seen["auth"] == "Bearer test-key"
    start = seen["start"]
    assert start["model"] == "stt-rt-v5"
    assert start["translation"] == {"type": "one_way", "target_language": "en"}
    assert start["enable_endpoint_detection"] is True
    assert start["audio_format"] == "pcm_s16le" and start["sample_rate"] == 16000
    assert start["language_hints"] == ["ko", "en"]
    assert speaker.phrases == ["Hello there, how are you?"]
    assert len(display.shown) == 1
    assert display.shown[0].original == "\uc548\ub155\ud558\uc138\uc694"
    assert display.shown[0].translation == "Hello there, how are you?"


def test_bad_key_is_fatal(tmp_path):
    def handler(ws):
        ws.recv()
        ws.send(json.dumps({"tokens": [], "error_code": 401, "error_type": "unauthenticated",
                            "error_message": "Incorrect API key"}))

    server, url = start_server(handler)
    try:
        with pytest.raises(SonioxError) as e:
            run(url, ListSource(reconnectable=True), tmp_path)
    finally:
        server.shutdown()
    assert e.value.code == 401 and not e.value.retryable


def test_reconnects_after_503(tmp_path):
    calls = {"n": 0}
    stop = threading.Event()

    def handler(ws):
        calls["n"] += 1
        ws.recv()
        if calls["n"] == 1:
            ws.send(json.dumps({"tokens": [], "error_code": 503, "error_type": "service_unavailable",
                                "error_message": "try again"}))
            return
        for _ in read_until_end_of_audio(ws):
            send(ws, [tok("Back", True, "translation"), tok(" again", True, "translation"),
                      tok(".", True, "translation")], total_ms=200)
        stop.set()  # the user "pressed Ctrl+C": don't reconnect again
        send(ws, [], finished=True)

    server, url = start_server(handler)
    try:
        speaker, _, _ = run(url, ListSource(reconnectable=True), tmp_path, stop=stop)
    finally:
        server.shutdown()
    assert calls["n"] == 2
    assert speaker.phrases == ["Back again."]


def test_start_request_options():
    s = Settings(api_key="k", target="ko", diarize=True, endpoint_delay_ms=800, latency_level=2, max_non_final_ms=1500)
    req = build_start_request(s, ListSource())
    assert req["enable_speaker_diarization"] is True
    assert req["max_endpoint_delay_ms"] == 800
    assert req["endpoint_latency_adjustment_level"] == 2
    assert req["max_non_final_tokens_duration_ms"] == 1500
    assert req["translation"]["target_language"] == "ko"
