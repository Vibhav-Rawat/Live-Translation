"""--demo: replays a scripted Korean conversation through the whole pipeline.

No microphone, no API key, no Soniox. Use it to check that captions, the phrase planner,
the voice and your earbuds all work on your machine. The timing mimics a real stream
(translation trails the speaker by about a second).
"""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Tuple

from .soniox_client import Batch, Token

# (Korean original, English translation)
SCRIPT = [
    ("안녕하세요, 오늘 어떻게 지내세요?", "Hello, how are you doing today?"),
    ("저는 한국에서 온 학생이에요.", "I am a student from Korea."),
    ("오늘 저녁에 같이 밥 먹을래요?", "Do you want to have dinner together this evening?"),
    ("시간이 괜찮으면 일곱 시에 만나요.", "If you have time, let us meet at seven."),
]

SECONDS_PER_WORD = 0.35   # how fast the "speaker" talks
TRANSLATION_LAG = 1.1     # translation starts this long after the speaker starts
PAUSE_AFTER_LINE = 1.2


def _pieces(text: str) -> List[str]:
    words = text.split()
    return [w if i == 0 else " " + w for i, w in enumerate(words)]


def build_events(script=SCRIPT) -> List[Tuple[float, List[Token]]]:
    events: List[Tuple[float, List[Token]]] = []
    t0 = 0.5
    for original, translation in script:
        o = _pieces(original)
        tr = _pieces(translation)
        speak_time = len(o) * SECONDS_PER_WORD
        for i, piece in enumerate(o):
            events.append((t0 + i * SECONDS_PER_WORD,
                           [Token(piece, True, "original", language="ko", start_ms=int((t0 + i * SECONDS_PER_WORD) * 1000))]))
        step = speak_time / max(1, len(tr))
        for j, piece in enumerate(tr):
            events.append((t0 + TRANSLATION_LAG + j * step, [Token(piece, True, "translation", language="en", source_language="ko")]))
        end = t0 + max(speak_time, TRANSLATION_LAG + len(tr) * step) + 0.6
        events.append((end, [Token("<end>", True, "none")]))
        t0 = end + PAUSE_AFTER_LINE
    events.sort(key=lambda e: e[0])
    return events


def play(on_batch: Callable[[Batch], None], stop: threading.Event, speed: float = 1.0) -> None:
    """Feed the scripted stream to the pipeline in (scaled) real time."""
    start = time.monotonic()
    for t, tokens in build_events():
        delay = t / speed - (time.monotonic() - start)
        if delay > 0 and stop.wait(delay):
            return
        if stop.is_set():
            return
        on_batch(Batch(tokens=tokens, total_audio_proc_ms=int(t * 1000)))
